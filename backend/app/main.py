import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.routers import agents, auth, chat, repositories

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("repomind")

app = FastAPI(title="RepoMind AI API", version="0.1.0")

app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(repositories.router)
app.include_router(chat.router)
app.include_router(agents.router)


@app.on_event("startup")
def on_startup():
    from app.db.database import Base, engine
    import app.db.models  # noqa: F401
    from sqlalchemy import text, inspect

    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    except Exception as exc:
        logger.warning("pgvector extension notice: %s", exc)

    Base.metadata.create_all(bind=engine)

    # Ensure embedding column dimension matches settings.embedding_dimension
    try:
        with engine.connect() as conn:
            conn.execute(
                text(f"ALTER TABLE code_chunks ALTER COLUMN embedding TYPE vector({settings.embedding_dimension});")
            )
            conn.commit()
            logger.info("✅ Verified code_chunks.embedding column is vector(%d)", settings.embedding_dimension)
    except Exception as exc:
        logger.info("Vector column check notice: %s", exc)

    # Pre-warm FastEmbed model at startup
    try:
        if settings.embedding_provider == "fastembed":
            from app.services.embeddings import get_fastembed_model
            logger.info("Pre-warming FastEmbed model...")
            get_fastembed_model()
            logger.info("✅ FastEmbed model ready in memory.")
    except Exception as exc:
        logger.warning("Embedding model pre-warm notice: %s", exc)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
