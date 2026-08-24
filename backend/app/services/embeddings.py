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
    Local embedding model for environments with sufficient RAM (>= 1GB).
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
    Uses text-embedding-004 which supports true batching (1 API request per batch).
    """
    def __init__(self, model: str = "models/text-embedding-004", google_api_key: str = "", dimensionality: int = 384):
        import google.generativeai as genai
        
        # Ensure we always use the modern batch-capable text-embedding-004 model
        # (even if older deprecated gemini-embedding-001 is set in env vars)
        clean_model = model.replace("models/", "").strip()
        if "gemini-embedding" in clean_model or not clean_model:
            clean_model = "text-embedding-004"
            
        self.model = f"models/{clean_model}"
        self.google_api_key = google_api_key
        self.dimensionality = dimensionality
        genai.configure(api_key=google_api_key)

    def _call_gemini_embed(self, content, max_retries: int = 4, initial_delay: float = 2.0):
        import google.generativeai as genai
        import re
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
                    # Check if retry delay was specified in error message
                    match = re.search(r"retry(?:_delay|\s+in)\s*[:=]?\s*(\d+(?:\.\d+)?)", err_msg)
                    wait_sec = float(match.group(1)) + 1.0 if match else delay
                    logger.warning(
                        "Gemini rate limit hit (429). Backing off for %.1f seconds (attempt %d/%d)...",
                        wait_sec, attempt + 1, max_retries
                    )
                    time.sleep(wait_sec)
                    delay *= 2.0
                else:
                    raise e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Send in true sub-batches of 25 to stay well under API payload limits
        # and consume only 1 request per 25 chunks!
        all_embeddings: list[list[float]] = []
        batch_size = 25

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                res = self._call_gemini_embed(batch)
                # When batch is a list, res is list of list of floats
                if isinstance(res, list) and res and isinstance(res[0], list):
                    all_embeddings.extend(res)
                elif isinstance(res, list) and res and isinstance(res[0], (int, float)):
                    all_embeddings.append(res)
                else:
                    raise ValueError(f"Unexpected response shape from Gemini embedding: {type(res)}")
            except Exception as batch_exc:
                logger.warning("Batch embedding attempt failed (%s), processing item by item with delay...", batch_exc)
                for item in batch:
                    item_res = self._call_gemini_embed(item)
                    all_embeddings.append(item_res)
                    time.sleep(0.3)  # Gentle spacing to stay under 100 req/min

            if i + batch_size < len(texts):
                time.sleep(0.5)  # Spacing between batches

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        try:
            res = self._call_gemini_embed(text)
            if isinstance(res, list) and res and isinstance(res[0], list):
                return res[0]
            return res
        except Exception as e:
            raise RuntimeError(f"Error embedding query with Gemini: {e}") from e
