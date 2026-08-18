from dataclasses import dataclass
import logging
import os
import time
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import quote

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CodeChunk, CodeFile, Repository, User
from app.services.embeddings import GeminiEmbeddings

logger = logging.getLogger(__name__)

IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "venv",
}

SUPPORTED_EXTENSIONS = {
    ".c",
    ".cpp",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".md",
    ".py",
    ".rs",
    ".ts",
    ".tsx",
}

EMBEDDING_BATCH_SIZE = 5


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
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY must be configured before indexing repositories.")

        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.embeddings = GeminiEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.google_api_key,
            dimensionality=settings.embedding_dimension,
        )

    def index_repository(self, db: Session, repository: Repository, user: User) -> IndexingResult:
        with TemporaryDirectory(prefix="repomind-index-") as temp_dir:
            clone_path = Path(temp_dir) / "repository"
            self._clone_repository(repository.full_name, user.access_token, clone_path)
            files = self._read_supported_files(clone_path)

        return self._store_files_chunks_and_embeddings(db, repository.id, files)

    def _clone_repository(self, full_name: str, access_token: str, clone_path: Path) -> None:
        token = quote(access_token, safe="")
        clone_url = f"https://x-access-token:{token}@github.com/{full_name}.git"
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(clone_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Git is not installed or not available on PATH.") from exc
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or "").replace(access_token, "[redacted]").replace(token, "[redacted]")
            message = message.strip()
            message = message or "Unknown git clone error."
            raise RuntimeError(f"Failed to clone GitHub repository: {message}") from exc

    def _read_supported_files(self, repository_path: Path) -> list[RepositoryFile]:
        files: list[RepositoryFile] = []

        for root, dirnames, filenames in os.walk(repository_path):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in IGNORED_DIRECTORIES
            ]

            for filename in filenames:
                path = Path(root) / filename
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS or path.is_symlink():
                    continue

                try:
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
        db.query(CodeFile).filter(CodeFile.repository_id == repository_id).delete(
            synchronize_session=False,
        )
        db.flush()

        chunks_to_embed: list[CodeChunk] = []
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
                code_chunk = CodeChunk(
                    file_id=code_file.id,
                    chunk_index=chunk_index,
                    content=chunk_content,
                )
                db.add(code_chunk)
                chunks_to_embed.append(code_chunk)

        db.flush()
        embedding_failures = self._embed_chunks(chunks_to_embed)
        db.commit()

        return IndexingResult(
            files_processed=len(files),
            chunks_created=len(chunks_to_embed),
            embedding_failures=embedding_failures,
        )

    def _embed_chunks(self, chunks: list[CodeChunk]) -> int:
        failures = 0
        total_batches = (len(chunks) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE

        for batch_num, start in enumerate(range(0, len(chunks), EMBEDDING_BATCH_SIZE), 1):
            batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
            texts = [chunk.content for chunk in batch]

            try:
                vectors = self.embeddings.embed_documents(texts)
            except Exception as exc:
                logger.warning("Batch embedding failed; retrying chunks individually: %s", exc)
                failures += self._embed_chunks_individually(batch)
                continue

            for chunk, vector in zip(batch, vectors, strict=False):
                if len(vector) != settings.embedding_dimension:
                    logger.warning(
                        "Skipping embedding for chunk %s because dimension %s != %s.",
                        chunk.id,
                        len(vector),
                        settings.embedding_dimension,
                    )
                    failures += 1
                    continue

                chunk.embedding = vector

            logger.info("Embedded batch %d/%d (%d chunks)", batch_num, total_batches, len(batch))
            # Rate-limit between batches to stay under the Gemini free tier RPM
            time.sleep(5)

        return failures

    def _embed_chunks_individually(self, chunks: list[CodeChunk]) -> int:
        failures = 0

        for chunk in chunks:
            try:
                # Generous rate-limiting sleep between individual retries to stay under the free tier RPM (~15 RPM)
                time.sleep(4.5)
                vector = self.embeddings.embed_query(chunk.content)
            except Exception as exc:
                logger.warning("Embedding failed for chunk %s: %s", chunk.id, exc)
                failures += 1
                continue

            if len(vector) != settings.embedding_dimension:
                logger.warning(
                    "Skipping embedding for chunk %s because dimension %s != %s.",
                    chunk.id,
                    len(vector),
                    settings.embedding_dimension,
                )
                failures += 1
                continue

            chunk.embedding = vector

        return failures
