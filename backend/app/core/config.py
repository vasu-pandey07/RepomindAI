from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(..., alias="DATABASE_URL")
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    github_client_id: str = Field(..., alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(..., alias="GITHUB_CLIENT_SECRET")
    frontend_url: str = Field("http://localhost:3000", alias="FRONTEND_URL")
    backend_url: str = Field("http://localhost:8000", alias="BACKEND_URL")
    access_token_expire_minutes: int = Field(60 * 24 * 7, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    google_api_key: str | None = Field(None, alias="GOOGLE_API_KEY")
    gemini_embedding_model: str = Field("models/gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL")
    gemini_chat_model: str = Field("gemini-flash-latest", alias="GEMINI_CHAT_MODEL")
    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")
    groq_model: str = Field("openai/gpt-oss-120b", alias="GROQ_MODEL")
    embedding_provider: str = Field("fastembed", alias="EMBEDDING_PROVIDER")
    embedding_dimension: int = Field(384, alias="EMBEDDING_DIMENSION")
    jwt_algorithm: str = "HS256"

    @field_validator("frontend_url", "backend_url", "database_url", mode="before")
    @classmethod
    def strip_url_whitespace(cls, v: str) -> str:
        """Strip whitespace/newlines from URL env vars to prevent %0A issues."""
        return v.strip().rstrip("/") if isinstance(v, str) else v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
