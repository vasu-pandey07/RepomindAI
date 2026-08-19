from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings, settings
from app.db.models import CodeChunk, CodeFile
from app.services.embeddings import GeminiEmbeddings, LocalFastEmbeddings


@dataclass(frozen=True)
class RetrievedChunk:
    file_path: str
    content: str
    score: float


class RepositoryRetriever:
    def __init__(self) -> None:
        current_settings = get_settings()
        if current_settings.embedding_provider == "gemini" and current_settings.google_api_key:
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

    def retrieve(self, db: Session, repository_id: int, user_question: str, limit: int = 5) -> list[RetrievedChunk]:
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

        return [
            RetrievedChunk(
                file_path=file_path,
                content=chunk.content,
                score=float(score),
            )
            for chunk, file_path, score in rows
        ]
