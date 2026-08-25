from dataclasses import dataclass
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CodeFile
from app.services.retriever import RepositoryRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

INSUFFICIENT_CONTEXT_RESPONSE = "I could not find enough information in this repository."


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    sources: list[str]


def invoke_llm_with_fallback(prompt: str) -> str:
    """
    Invokes Groq or Gemini with automatic provider failover and resilient model cascading.
    """
    current_settings = get_settings()
    providers = []

    # Priority 1: Groq (if key provided)
    if current_settings.groq_api_key and current_settings.groq_api_key.strip():
        groq_key = current_settings.groq_api_key.strip()
        groq_models = [
            current_settings.groq_model or "llama-3.3-70b-versatile",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ]
        # Deduplicate while preserving priority order
        seen_groq = set()
        unique_groq_models = [m for m in groq_models if not (m in seen_groq or seen_groq.add(m))]

        for model_name in unique_groq_models:
            providers.append(
                (
                    f"Groq ({model_name})",
                    lambda m=model_name, k=groq_key: ChatGroq(
                        model_name=m,
                        groq_api_key=k,
                        temperature=0.1,
                    ),
                )
            )

    # Priority 2: Google Gemini (if key provided)
    if current_settings.google_api_key and current_settings.google_api_key.strip():
        gemini_key = current_settings.google_api_key.strip()
        raw_model = (current_settings.gemini_chat_model or "gemini-2.0-flash").strip()
        clean_model = raw_model.replace("models/", "").strip()
        # Protect against non-existent 2.5 flash string
        if clean_model == "gemini-2.5-flash":
            clean_model = "gemini-2.0-flash"

        gemini_models = [
            clean_model,
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]
        seen_gemini = set()
        unique_gemini_models = [m for m in gemini_models if not (m in seen_gemini or seen_gemini.add(m))]

        for model_name in unique_gemini_models:
            providers.append(
                (
                    f"Google Gemini ({model_name})",
                    lambda m=model_name, k=gemini_key: ChatGoogleGenerativeAI(
                        model=m,
                        google_api_key=k,
                        temperature=0.1,
                    ),
                )
            )

    if not providers:
        raise RuntimeError(
            "No LLM API keys configured. Please set GROQ_API_KEY or GOOGLE_API_KEY in your Render environment variables."
        )

    last_error = None
    for name, get_client in providers:
        try:
            client = get_client()
            response = client.invoke(prompt)
            text = str(response.content).strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("LLM provider %s returned error: %s. Attempting fallback provider...", name, exc)
            last_error = exc

    raise RuntimeError(f"All configured LLM providers failed: {last_error}")


class RepositoryRagService:
    def __init__(self) -> None:
        self.retriever = RepositoryRetriever()

    def answer_question(self, db: Session, repository_id: int, question: str) -> RagAnswer:
        chunks = self.retriever.retrieve(db, repository_id, question, limit=6)

        # Query for README context to provide high-level project orientation
        readme_content = None
        readme_path = None
        readme_file = (
            db.query(CodeFile)
            .filter(
                CodeFile.repository_id == repository_id,
                CodeFile.file_path.ilike("%readme%"),
            )
            .first()
        )
        if readme_file:
            readme_content = readme_file.content[:3500]
            readme_path = readme_file.file_path

        if not chunks and not readme_content:
            return RagAnswer(answer=INSUFFICIENT_CONTEXT_RESPONSE, sources=[])

        prompt = self._build_prompt(chunks, question, readme_content, readme_path)
        answer = invoke_llm_with_fallback(prompt)

        if not answer:
            answer = INSUFFICIENT_CONTEXT_RESPONSE

        sources = []
        if readme_path:
            sources.append(readme_path)
        sources.extend(chunk.file_path for chunk in chunks)
        sources = list(dict.fromkeys(sources))

        return RagAnswer(answer=answer, sources=sources)

    def _build_prompt(
        self,
        chunks: list[RetrievedChunk],
        question: str,
        readme_content: str | None = None,
        readme_path: str | None = None,
    ) -> str:
        context_blocks = []

        if readme_content:
            context_blocks.append(
                f"Source README ({readme_path}):\n```\n{readme_content}\n```"
            )

        for index, chunk in enumerate(chunks, start=1):
            if readme_path and chunk.file_path == readme_path:
                continue
            context_blocks.append(
                f"Source {index} ({chunk.file_path}):\n```\n{chunk.content}\n```"
            )

        context = "\n\n".join(context_blocks)

        return f"""You are RepoMind AI, an expert code analysis assistant.
Answer the user's question clearly, thoroughly, and accurately based on the indexed repository code and files below.

If the user asks about system architecture, models, routes, or setup, reference the relevant code snippets provided in the context.

Repository Context:
{context}

User Question:
{question}
"""
