from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.routers import agents, auth, chat, repositories


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
    from sqlalchemy import text
    from app.core.config import get_settings

    current_settings = get_settings()
    dim = current_settings.embedding_dimension

    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            # Auto-migrate vector column dimension if changed from 768 to 384
            conn.execute(text(f"ALTER TABLE code_chunks ALTER COLUMN embedding TYPE vector({dim});"))
            conn.commit()
    except Exception as exc:
        print(f"Database startup extension/migration notice: {exc}")

    Base.metadata.create_all(bind=engine)

    # Pre-warm FastEmbed model in memory
    try:
        from app.services.embeddings import get_fastembed_model
        get_fastembed_model()
    except Exception as exc:
        print(f"FastEmbed pre-warm notice: {exc}")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
