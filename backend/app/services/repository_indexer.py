from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
from urllib.parse import quote

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
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
    "venv",
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

MAX_FILE_SIZE_BYTES = 250 * 1024  # 250 KB max per file
MAX_TOTAL_FILES = 300
EMBEDDING_BATCH_SIZE = 64


def _remove_readonly(func, path, excinfo):
    """Windows-safe error handler for shutil.rmtree on git-created files."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


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
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.embedding_dimension = current_settings.embedding_dimension

        if current_settings.embedding_provider == "gemini" and current_settings.google_api_key:
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

    def index_repository(self, db: Session, repository: Repository, user: User) -> IndexingResult:
        temp_dir = tempfile.mkdtemp(prefix="repomind-index-")
        clone_path = Path(temp_dir) / "repository"
        try:
            self._clone_repository(repository.full_name, user.access_token, clone_path)
            files = self._read_supported_files(clone_path)
        finally:
            shutil.rmtree(temp_dir, onerror=_remove_readonly, ignore_errors=True)

        if not files:
            raise ValueError(
                f"No supported code files found in repository {repository.full_name}. "
                "Ensure the repository contains code files (.js, .ts, .py, .jsx, .tsx, .html, etc.)."
            )

        return self._store_files_chunks_and_embeddings(db, repository.id, files)

    def _clone_repository(self, full_name: str, access_token: str, clone_path: Path) -> None:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = ""
        env["GCM_INTERACTIVE"] = "never"
        env["GIT_HTTP_LOW_SPEED_LIMIT"] = "1000"
        env["GIT_HTTP_LOW_SPEED_TIME"] = "15"

        # Build candidate URLs in order of preference
        urls = []
        if access_token and access_token.strip():
            token = quote(access_token.strip(), safe="")
            urls.append(f"https://{token}@github.com/{full_name}.git")
            urls.append(f"https://x-access-token:{token}@github.com/{full_name}.git")
            urls.append(f"https://oauth2:{token}@github.com/{full_name}.git")

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
                    timeout=120,
                )
                return  # Clone succeeded
            except FileNotFoundError as exc:
                raise RuntimeError("Git is not installed or not available on PATH.") from exc
            except subprocess.TimeoutExpired:
                last_error = "Git clone operation timed out."
                logger.warning("Git clone timeout for %s on %s", full_name, url.split("@")[-1])
                continue
            except subprocess.CalledProcessError as exc:
                last_error = exc.stderr.strip() if exc.stderr else "Unknown git clone error"
                logger.warning("Git clone failed for %s: %s", full_name, last_error)
                continue

        if "authentication" in last_error.lower() or "403" in last_error or "401" in last_error or "could not read Username" in last_error:
            raise PermissionError(
                f"Authentication failed for {full_name}. "
                "Your GitHub token may have expired. Please log out and sign back in with GitHub."
            )

        raise RuntimeError(f"Failed to clone repository {full_name}: {last_error}")

    def _read_supported_files(self, repository_path: Path) -> list[RepositoryFile]:
        files: list[RepositoryFile] = []

        for root, dirnames, filenames in os.walk(repository_path):
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in IGNORED_DIRECTORIES and not d.startswith(".")
            ]

            for filename in filenames:
                if len(files) >= MAX_TOTAL_FILES:
                    logger.warning("Reached maximum file limit of %d", MAX_TOTAL_FILES)
                    return files

                name_lower = filename.lower()
                if (
                    name_lower in IGNORED_FILE_PATTERNS
                    or name_lower.endswith(".min.js")
                    or name_lower.endswith(".min.css")
                    or name_lower.endswith(".map")
                ):
                    continue

                path = Path(root) / filename
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS or path.is_symlink():
                    continue

                try:
                    stat_res = path.stat()
                    if stat_res.st_size > MAX_FILE_SIZE_BYTES:
                        continue
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except OSError as exc:
                    logger.warning("Skipping unreadable file %s: %s", path, exc)
                    continue

                if not content.strip():
                    continue

                relative_path = path.relative_to(repository_path).as_posix()
                files.append(RepositoryFile(path=relative_path, content=content))

        return files

    def _store_files_chunks_and_embeddings(
        self,
        db: Session,
        repository_id: int,
        files: list[RepositoryFile],
    ) -> IndexingResult:
        # Delete old records
        old_file_ids = [r[0] for r in db.query(CodeFile.id).filter(CodeFile.repository_id == repository_id).all()]
        if old_file_ids:
            db.query(CodeChunk).filter(CodeChunk.file_id.in_(old_file_ids)).delete(synchronize_session=False)
        db.query(CodeFile).filter(CodeFile.repository_id == repository_id).delete(synchronize_session=False)
        db.flush()

        # Step 1: Create all CodeFile records and split texts into chunk metadata
        raw_chunks_data: list[tuple[int, int, str]] = []  # (file_id, chunk_index, text)
        for repository_file in files:
            code_file = CodeFile(
                repository_id=repository_id,
                file_path=repository_file.path,
                content=repository_file.content,
            )
            db.add(code_file)
            db.flush()  # Populates code_file.id

            chunks = self.splitter.split_text(repository_file.content)
            for chunk_index, chunk_content in enumerate(chunks):
                raw_chunks_data.append((code_file.id, chunk_index, chunk_content))

        if not raw_chunks_data:
            db.commit()
            return IndexingResult(files_processed=len(files), chunks_created=0, embedding_failures=0)

        # Step 2: Generate embeddings in batches and prepare insert dictionaries
        chunk_dicts: list[dict] = []
        total_chunks = len(raw_chunks_data)
        logger.info("Generating embeddings for %d chunks in batches of %d...", total_chunks, EMBEDDING_BATCH_SIZE)

        for i in range(0, total_chunks, EMBEDDING_BATCH_SIZE):
            batch = raw_chunks_data[i : i + EMBEDDING_BATCH_SIZE]
            texts = [item[2] for item in batch]

            try:
                vectors = self.embeddings.embed_documents(texts)
            except Exception as exc:
                logger.error("Embedding generation failed on batch %d: %s", i // EMBEDDING_BATCH_SIZE + 1, exc)
                raise RuntimeError(f"Embedding failed: {exc}") from exc

            for (file_id, chunk_index, content), vector in zip(batch, vectors, strict=False):
                chunk_dicts.append(
                    {
                        "file_id": file_id,
                        "chunk_index": chunk_index,
                        "content": content,
                        "embedding": vector,
                    }
                )

            if not self.is_local:
                time.sleep(2)

        # Step 3: Fast bulk insert all chunks in a single multi-row statement
        from sqlalchemy import insert
        db.execute(insert(CodeChunk), chunk_dicts)
        db.commit()
        logger.info("Successfully indexed %d files and %d chunks.", len(files), len(chunk_dicts))

        return IndexingResult(
            files_processed=len(files),
            chunks_created=len(chunk_dicts),
            embedding_failures=0,
        )
