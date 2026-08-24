from dataclasses import dataclass
import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CodeChunk, CodeFile
from app.services.embeddings import GeminiEmbeddings, LocalFastEmbeddings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    file_path: str
    content: str
    score: float


class RepositoryRetriever:
    def __init__(self) -> None:
        current_settings = get_settings()
        if current_settings.google_api_key:
            self.embeddings = GeminiEmbeddings(
                model=current_settings.gemini_embedding_model,
                google_api_key=current_settings.google_api_key,
                dimensionality=current_settings.embedding_dimension,
            )
        else:
            self.embeddings = LocalFastEmbeddings(
                model_name="BAAI/bge-small-en-v1.5",
                dimensionality=current_settings.embedding_dimension,
            )

    def retrieve(self, db: Session, repository_id: int, user_question: str, limit: int = 6) -> list[RetrievedChunk]:
        # Method 1: Semantic vector retrieval with pgvector
        try:
            question_embedding = self.embeddings.embed_query(user_question)
            distance = CodeChunk.embedding.cosine_distance(question_embedding).label("score")

            rows = (
                db.query(CodeChunk, CodeFile.file_path, distance)
                .join(CodeFile, CodeChunk.file_id == CodeFile.id)
                .filter(CodeFile.repository_id == repository_id, CodeChunk.embedding.is_not(None))
                .order_by(distance.asc())
                .limit(limit)
                .all()
            )

            if rows:
                return [
                    RetrievedChunk(
                        file_path=file_path,
                        content=chunk.content,
                        score=float(score),
                    )
                    for chunk, file_path, score in rows
                ]
        except Exception as exc:
            logger.warning("Vector retrieval notice: %s. Falling back to keyword search.", exc)

        # Method 2: Keyword / lexical search fallback
        try:
            words = [w.lower().strip(",.?!:;\"'") for w in user_question.split() if len(w) > 2][:6]
            query = db.query(CodeFile).filter(CodeFile.repository_id == repository_id)
            if words:
                conditions = [CodeFile.content.ilike(f"%{w}%") for w in words]
                query = query.filter(or_(*conditions))

            fallback_files = query.limit(limit).all()
            return [
                RetrievedChunk(
                    file_path=f.file_path,
                    content=f.content[:1500],
                    score=0.5,
                )
                for f in fallback_files
            ]
        except Exception as exc:
            logger.error("Keyword retrieval fallback failed: %s", exc)
            return []
