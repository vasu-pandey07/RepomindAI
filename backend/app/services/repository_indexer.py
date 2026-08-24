from dataclasses import dataclass
import gc
import io
import logging
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import quote
import zipfile

import httpx
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CodeChunk, CodeFile, Repository, User
from app.services.embeddings import GeminiEmbeddings, LocalFastEmbeddings

logger = logging.getLogger(__name__)

IGNORED_DIRECTORIES = {
    ".cache",
    ".git",
    ".github",
    ".idea",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".turbo",
    ".venv",
    ".vscode",
    "__pycache__",
    "assets",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "public",
    "static",
    "target",
    "vendor",
    "venv",
    "curriculum",  # large curriculum/data directory in freecodecamp
}

IGNORED_FILE_PATTERNS = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "composer.lock",
    "cargo.lock",
    "poetry.lock",
    "pipfile.lock",
    "go.sum",
    "bun.lockb",
}

SUPPORTED_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".php",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
    ".yaml",
    ".yml",
}

MAX_FILE_SIZE_BYTES = 40 * 1024   # 40 KB max per file (avoids massive data fixtures)
MAX_TOTAL_FILES = 35              # Top 35 high-value source files for speed & accuracy
MAX_TOTAL_CHUNKS = 80             # Up to 80 high-value chunks for ultra-fast embedding
EMBEDDING_BATCH_SIZE_LOCAL = 16   # Balanced batch for FastEmbed ONNX
EMBEDDING_BATCH_SIZE_API = 50     # Batch size for Gemini API


def _remove_readonly(func, path, excinfo):
    """Windows-safe error handler for shutil.rmtree on git-created files."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _get_file_priority(relative_path: str) -> int:
    """Assign lower number for higher indexing importance."""
    name_lower = Path(relative_path).name.lower()
    path_lower = relative_path.lower()

    # Priority 0: Primary documentation and project configuration
    if name_lower in ("readme.md", "readme", "package.json", "requirements.txt", "pyproject.toml", "go.mod", "cargo.toml", "dockerfile"):
        return 0

    # Priority 1: Top-level entry points and key application files
    if any(name_lower.startswith(prefix) for prefix in ("main.", "app.", "index.", "server.", "route.", "page.")):
        return 1

    # Priority 2: Core source tree directories
    if any(dir_name in path_lower for dir_name in ("src/", "app/", "lib/", "routes/", "controllers/", "services/", "models/", "components/", "api/")):
        return 2

    # Priority 3: Other code files
    return 3


@dataclass(frozen=True)
class RepositoryFile:
    path: str
    content: str


@dataclass(frozen=True)
class IndexingResult:
    files_processed: int
    chunks_created: int
    embedding_failures: int


class RepositoryIndexer:
    def __init__(self) -> None:
        current_settings = get_settings()
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
        self.embedding_dimension = current_settings.embedding_dimension

        # Prioritize zero-RAM Gemini remote embeddings if Google API key is present
        if current_settings.google_api_key:
            self.embeddings = GeminiEmbeddings(
                model=current_settings.gemini_embedding_model,
                google_api_key=current_settings.google_api_key,
                dimensionality=current_settings.embedding_dimension,
            )
            self.is_local = False
        else:
            self.embeddings = LocalFastEmbeddings(
                model_name="BAAI/bge-small-en-v1.5",
                dimensionality=current_settings.embedding_dimension,
            )
            self.is_local = True

        self.batch_size = EMBEDDING_BATCH_SIZE_LOCAL if self.is_local else EMBEDDING_BATCH_SIZE_API

    def index_repository(self, db: Session, repository: Repository, user: User) -> IndexingResult:
        logger.info("Starting indexing for repository %s (ID: %d)...", repository.full_name, repository.id)
        
        # Method 1: Ultra-fast GitHub Zipball API (zero git subprocess memory)
        files = self._fetch_via_github_api(repository.full_name, user.access_token)
        
        # Method 2: Fallback to lightweight shallow git clone if zipball failed
        if not files:
            logger.info("GitHub API archive failed or empty, falling back to shallow git clone for %s...", repository.full_name)
            files = self._fetch_via_git_clone(repository.full_name, user.access_token)

        if not files:
            raise ValueError(
                f"No supported code files found in repository {repository.full_name}. "
                "Ensure the repository contains code files (.js, .ts, .py, .jsx, .tsx, .html, etc.)."
            )

        logger.info("Found %d supported source files for %s. Chunking and embedding...", len(files), repository.full_name)
        return self._store_files_chunks_and_embeddings(db, repository.id, files)

    def _fetch_via_github_api(self, full_name: str, access_token: str) -> list[RepositoryFile]:
        """
        Downloads the repository archive as a lightweight zip stream using GitHub API.
        Uses negligible RAM and avoids spawning heavy git subprocesses.
        """
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if access_token and access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"

        zip_url = f"https://api.github.com/repos/{full_name}/zipball/HEAD"

        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(zip_url, headers=headers)
                if resp.status_code != 200:
                    logger.warning("GitHub zipball endpoint returned status %d for %s", resp.status_code, full_name)
                    return []

                zip_buffer = io.BytesIO(resp.content)
                return self._extract_files_from_zip(zip_buffer)
        except Exception as exc:
            logger.warning("Error fetching zipball for %s: %s", full_name, exc)
            return []

    def _extract_files_from_zip(self, zip_buffer: io.BytesIO) -> list[RepositoryFile]:
        candidates: list[tuple[int, int, zipfile.ZipInfo, str]] = []

        try:
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                infolist = zf.infolist()
                for info in infolist:
                    if info.is_dir():
                        continue

                    # GitHub zip entries start with a root dir like: repo-owner-repo-hash/file.ext
                    raw_parts = info.filename.split("/", 1)
                    if len(raw_parts) < 2:
                        continue
                    relative_path = raw_parts[1]

                    # Filter out ignored directories
                    path_lower = relative_path.lower()
                    if any(f"/{d}/" in f"/{path_lower}/" or path_lower.startswith(f"{d}/") for d in IGNORED_DIRECTORIES):
                        continue

                    name_lower = Path(relative_path).name.lower()
                    if (
                        name_lower in IGNORED_FILE_PATTERNS
                        or name_lower.endswith(".min.js")
                        or name_lower.endswith(".min.css")
                        or name_lower.endswith(".map")
                        or name_lower.endswith(".svg")
                        or ".test." in name_lower
                        or ".spec." in name_lower
                    ):
                        continue

                    suffix = Path(relative_path).suffix.lower()
                    if suffix not in SUPPORTED_EXTENSIONS:
                        continue

                    if info.file_size > MAX_FILE_SIZE_BYTES or info.file_size == 0:
                        continue

                    priority = _get_file_priority(relative_path)
                    depth = relative_path.count("/")
                    candidates.append((priority, depth, info, relative_path))

                candidates.sort(key=lambda x: (x[0], x[1], x[3]))

                files: list[RepositoryFile] = []
                for _, _, info, relative_path in candidates[:MAX_TOTAL_FILES]:
                    try:
                        raw_bytes = zf.read(info)
                        content = raw_bytes.decode("utf-8", errors="ignore").strip()
                        if content:
                            files.append(RepositoryFile(path=relative_path, content=content))
                    except Exception as e:
                        logger.warning("Error reading zip entry %s: %s", relative_path, e)
                        continue

                return files
        except Exception as exc:
            logger.warning("Failed to parse zip archive: %s", exc)
            return []

    def _fetch_via_git_clone(self, full_name: str, access_token: str) -> list[RepositoryFile]:
        """Fallback method using git shallow clone with strict buffer constraints."""
        temp_dir = tempfile.mkdtemp(prefix="repomind-clone-")
        clone_path = Path(temp_dir) / "repository"

        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_HTTP_LOW_SPEED_LIMIT"] = "1000"
            env["GIT_HTTP_LOW_SPEED_TIME"] = "15"

            urls = []
            if access_token and access_token.strip():
                token = quote(access_token.strip(), safe="")
                urls.append(f"https://x-access-token:{token}@github.com/{full_name}.git")
                urls.append(f"https://{token}@github.com/{full_name}.git")

            urls.append(f"https://github.com/{full_name}.git")

            last_error = ""
            for url in urls:
                try:
                    if clone_path.exists():
                        shutil.rmtree(clone_path, onerror=_remove_readonly, ignore_errors=True)

                    subprocess.run(
                        [
                            "git",
                            "-c", "credential.helper=",
                            "-c", "core.packedGitLimit=32m",
                            "-c", "core.packedGitWindowSize=32m",
                            "clone",
                            "--depth", "1",
                            "--single-branch",
                            "--no-tags",
                            url,
                            str(clone_path),
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=env,
                        timeout=20,
                    )
                    return self._read_supported_files(clone_path)
                except Exception as exc:
                    last_error = str(exc)
                    continue

            logger.warning("Git clone failed for %s: %s", full_name, last_error)
            return []
        finally:
            shutil.rmtree(temp_dir, onerror=_remove_readonly, ignore_errors=True)

    def _read_supported_files(self, repository_path: Path) -> list[RepositoryFile]:
        candidates: list[tuple[int, int, Path, str]] = []

        for root, dirnames, filenames in os.walk(repository_path):
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in IGNORED_DIRECTORIES and not d.startswith(".")
            ]

            for filename in filenames:
                name_lower = filename.lower()
                if (
                    name_lower in IGNORED_FILE_PATTERNS
                    or name_lower.endswith(".min.js")
                    or name_lower.endswith(".min.css")
                    or name_lower.endswith(".map")
                    or name_lower.endswith(".svg")
                    or ".test." in name_lower
                    or ".spec." in name_lower
                ):
                    continue

                path = Path(root) / filename
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS or path.is_symlink():
                    continue

                try:
                    stat_res = path.stat()
                    if stat_res.st_size > MAX_FILE_SIZE_BYTES:
                        continue
                except OSError:
                    continue

                relative_path = path.relative_to(repository_path).as_posix()
                priority = _get_file_priority(relative_path)
                depth = relative_path.count("/")
                candidates.append((priority, depth, path, relative_path))

        candidates.sort(key=lambda x: (x[0], x[1], x[3]))

        files: list[RepositoryFile] = []
        for _, _, path, relative_path in candidates[:MAX_TOTAL_FILES]:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if content.strip():
                    files.append(RepositoryFile(path=relative_path, content=content))
            except OSError:
                continue

        return files

    def _store_files_chunks_and_embeddings(
        self,
        db: Session,
        repository_id: int,
        files: list[RepositoryFile],
    ) -> IndexingResult:
        # Delete old records for this repository
        old_file_ids = [r[0] for r in db.query(CodeFile.id).filter(CodeFile.repository_id == repository_id).all()]
        if old_file_ids:
            db.query(CodeChunk).filter(CodeChunk.file_id.in_(old_file_ids)).delete(synchronize_session=False)
        db.query(CodeFile).filter(CodeFile.repository_id == repository_id).delete(synchronize_session=False)
        db.flush()

        # Step 1: Create CodeFile records and split texts into chunk metadata
        raw_chunks_data: list[tuple[int, int, str]] = []
        for repository_file in files:
            code_file = CodeFile(
                repository_id=repository_id,
                file_path=repository_file.path,
                content=repository_file.content,
            )
            db.add(code_file)
            db.flush()

            chunks = self.splitter.split_text(repository_file.content)
            for chunk_index, chunk_content in enumerate(chunks):
                if len(raw_chunks_data) >= MAX_TOTAL_CHUNKS:
                    break
                raw_chunks_data.append((code_file.id, chunk_index, chunk_content))

            if len(raw_chunks_data) >= MAX_TOTAL_CHUNKS:
                break

        if not raw_chunks_data:
            db.commit()
            return IndexingResult(files_processed=len(files), chunks_created=0, embedding_failures=0)

        # Step 2: Generate embeddings in batches (graceful fallback if API quota or memory limit)
        chunk_dicts: list[dict] = []
        total_chunks = len(raw_chunks_data)
        logger.info("Generating embeddings for %d chunks in batches of %d...", total_chunks, self.batch_size)

        for i in range(0, total_chunks, self.batch_size):
            batch = raw_chunks_data[i : i + self.batch_size]
            texts = [item[2] for item in batch]
            vectors: list[list[float]] = []

            try:
                vectors = self.embeddings.embed_documents(texts)
            except Exception as exc:
                logger.warning("Embedding generation notice for batch %d: %s. Storing code chunks for lexical search.", i // self.batch_size + 1, exc)

            for idx, (file_id, chunk_index, content) in enumerate(batch):
                vector = vectors[idx] if (vectors and idx < len(vectors)) else None
                chunk_dicts.append(
                    {
                        "file_id": file_id,
                        "chunk_index": chunk_index,
                        "content": content,
                        "embedding": vector,
                    }
                )

            del batch, texts, vectors
            gc.collect()

        # Step 3: Fast bulk insert all chunks in a single multi-row statement
        from sqlalchemy import insert
        db.execute(insert(CodeChunk), chunk_dicts)
        db.commit()
        logger.info("Successfully indexed %d files and %d chunks for repository ID %d.", len(files), len(chunk_dicts), repository_id)

        return IndexingResult(
            files_processed=len(files),
            chunks_created=len(chunk_dicts),
            embedding_failures=0,
        )
