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
        try:
            _fastembed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", threads=1)
        except TypeError:
            _fastembed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _fastembed_model


class LocalFastEmbeddings(Embeddings):
    """
    High-performance, local embedding model that runs directly on CPU with 0 API calls.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", dimensionality: int = 384):
        self.model_name = model_name
        self.dimensionality = dimensionality
        self._model = get_fastembed_model()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            try:
                embeddings_generator = self._model.embed(texts, batch_size=16)
            except TypeError:
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
    """
    Zero-RAM, high-speed remote embeddings powered by Google Gemini API.
    """
    def __init__(self, model: str = "models/text-embedding-004", google_api_key: str = "", dimensionality: int = 384):
        import google.generativeai as genai
        self.model = model if model.startswith("models/") else f"models/{model}"
        self.google_api_key = google_api_key
        self.dimensionality = dimensionality
        genai.configure(api_key=google_api_key)

    def _embed_with_retry(self, content, max_retries: int = 3, initial_delay: float = 1.0) -> list:
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
        if not texts:
            return []
        try:
            result = self._embed_with_retry(texts)
            if isinstance(result, list) and result and isinstance(result[0], list):
                return result
        except Exception as batch_exc:
            logger.info("Batch embedding fallback to single item embedding: %s", batch_exc)

        vectors: list[list[float]] = []
        for idx, text in enumerate(texts):
            try:
                vectors.append(self._embed_with_retry(text))
            except Exception as e:
                raise RuntimeError(f"Error embedding content: {e}") from e
        return vectors

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._embed_with_retry(text)
        except Exception as e:
            raise RuntimeError(f"Error embedding query: {e}") from e
