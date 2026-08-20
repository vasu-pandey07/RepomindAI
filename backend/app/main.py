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
    from sqlalchemy import text, inspect

    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    except Exception as exc:
        print(f"pgvector extension notice: {exc}")

    Base.metadata.create_all(bind=engine)

    # Log current embedding dimension for debugging
    try:
        inspector = inspect(engine)
        cols = inspector.get_columns("code_chunks")
        for col in cols:
            if col["name"] == "embedding":
                print(f"✅ Embedding column exists: {col['type']}")
                break
    except Exception:
        pass


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
