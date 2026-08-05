import logging
import time
import google.generativeai as genai
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class GeminiEmbeddings(Embeddings):
    def __init__(self, model: str, google_api_key: str, dimensionality: int = 768):
        self.model = model
        self.google_api_key = google_api_key
        self.dimensionality = dimensionality
        genai.configure(api_key=google_api_key)

    def _embed_with_retry(self, content, max_retries: int = 5, initial_delay: float = 2.0) -> list:
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
                    delay *= 2.0  # Exponential backoff
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
