import logging
import time
from typing import List
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

# Global singleton for FastEmbed model so it loads once in memory
_fastembed_model = None


def get_fastembed_model():
    global _fastembed_model
    if _fastembed_model is None:
        from fastembed import TextEmbedding
        logger.info("Initializing Local FastEmbed model (BAAI/bge-small-en-v1.5)...")
        _fastembed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _fastembed_model


class LocalFastEmbeddings(Embeddings):
    """
    High-performance, local embedding model that runs directly on CPU with 0 API calls,
    0 quotas, and 100% offline reliability.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", dimensionality: int = 384):
        self.model_name = model_name
        self.dimensionality = dimensionality
        self._model = get_fastembed_model()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            embeddings_generator = self._model.embed(texts)
            return [vector.tolist() for vector in embeddings_generator]
        except Exception as e:
            logger.error("FastEmbed embed_documents error: %s", e)
            raise RuntimeError(f"Error embedding documents with FastEmbed: {e}") from e

    def embed_query(self, text: str) -> List[float]:
        try:
            embeddings_generator = self._model.embed([text])
            return next(iter(embeddings_generator)).tolist()
        except Exception as e:
            logger.error("FastEmbed embed_query error: %s", e)
            raise RuntimeError(f"Error embedding query with FastEmbed: {e}") from e


class GeminiEmbeddings(Embeddings):
    def __init__(self, model: str, google_api_key: str, dimensionality: int = 768):
        import google.generativeai as genai
        self.model = model
        self.google_api_key = google_api_key
        self.dimensionality = dimensionality
        genai.configure(api_key=google_api_key)

    def _embed_with_retry(self, content, max_retries: int = 5, initial_delay: float = 2.0) -> list:
        import google.generativeai as genai
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                response = genai.embed_content(
                    model=self.model,
                    content=content,
                    output_dimensionality=self.dimensionality
                )
                return response['embedding']
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "429" in err_msg or "exhausted" in err_msg or "quota" in err_msg or "rate limit" in err_msg
                
                if is_rate_limit and attempt < max_retries - 1:
                    logger.warning(
                        "Gemini embedding API rate limit hit (429). Retrying in %.2f seconds (attempt %d/%d)...",
                        delay, attempt + 1, max_retries
                    )
                    time.sleep(delay)
                    delay *= 2.0
                else:
                    raise e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._embed_with_retry(texts)
        except Exception as e:
            raise RuntimeError(f"Error embedding content: {e}")

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._embed_with_retry(text)
        except Exception as e:
            raise RuntimeError(f"Error embedding content: {e}")
