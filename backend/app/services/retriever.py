from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings, settings
from app.db.models import CodeChunk, CodeFile
from app.services.embeddings import GeminiEmbeddings


@dataclass(frozen=True)
class RetrievedChunk:
    file_path: str
    content: str
    score: float


class RepositoryRetriever:
    def __init__(self) -> None:
        current_settings = get_settings()
        if not current_settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY must be configured before retrieving code context.")

        self.embeddings = GeminiEmbeddings(
            model=current_settings.gemini_embedding_model,
            google_api_key=current_settings.google_api_key,
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
