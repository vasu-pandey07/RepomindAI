from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CodeFile
from app.services.retriever import RepositoryRetriever, RetrievedChunk

INSUFFICIENT_CONTEXT_RESPONSE = "I could not find enough information in this repository."


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    sources: list[str]


class RepositoryRagService:
    def __init__(self) -> None:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY must be configured before using repository chat.")

        self.retriever = RepositoryRetriever()
        self.chat_model = ChatGoogleGenerativeAI(
            model=settings.gemini_chat_model,
            google_api_key=settings.google_api_key,
            temperature=0,
        )

    def answer_question(self, db: Session, repository_id: int, question: str) -> RagAnswer:
        chunks = self.retriever.retrieve(db, repository_id, question, limit=5)
        
        # Query for README context to handle general queries
        readme_content = None
        readme_path = None
        readme_file = (
            db.query(CodeFile)
            .filter(
                CodeFile.repository_id == repository_id,
                CodeFile.file_path.ilike("%readme%")
            )
            .first()
        )
        if readme_file:
            readme_content = readme_file.content[:3500]
            readme_path = readme_file.file_path

        if not chunks and not readme_content:
            return RagAnswer(answer=INSUFFICIENT_CONTEXT_RESPONSE, sources=[])

        prompt = self._build_prompt(chunks, question, readme_content, readme_path)
        response = self.chat_model.invoke(prompt)
        answer = str(response.content).strip()
        if not answer:
            answer = INSUFFICIENT_CONTEXT_RESPONSE

        sources = []
        if readme_path:
            sources.append(readme_path)
        sources.extend(chunk.file_path for chunk in chunks)
        sources = list(dict.fromkeys(sources))

        return RagAnswer(answer=answer, sources=sources)

    def _build_prompt(self, chunks: list[RetrievedChunk], question: str, readme_content: str | None = None, readme_path: str | None = None) -> str:
        context_blocks = []
        
        if readme_content:
            context_blocks.append(
                f"Source README: {readme_path}\n```\n{readme_content}\n```"
            )

        for index, chunk in enumerate(chunks, start=1):
            if readme_path and chunk.file_path == readme_path:
                continue
            context_blocks.append(
                "\n".join(
                    [
                        f"Source {index}: {chunk.file_path}",
                        "```",
                        chunk.content,
                        "```",
                    ]
                )
            )

        context = "\n\n".join(context_blocks)

        return f"""You are RepoMind AI, a repository-aware code assistant.

Answer the user's question using the repository context below. Try to be as helpful as possible.
If the user greets you (e.g., "hello", "hi"), greet them back warmly and offer to help them explore this repository.

If the context does not contain enough information to answer a specific question directly, use what details are present in the context (such as directories, code comments, or framework setup) to explain what you can deduce about the codebase, rather than refusing.
Only reply exactly with "{INSUFFICIENT_CONTEXT_RESPONSE}" if the context is completely empty or has no relevance whatsoever to the repository or code.

Do not make up facts or use outside knowledge unrelated to the code files provided.

Repository context:
{context}

User question:
{question}
"""


