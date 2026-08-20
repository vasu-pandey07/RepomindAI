import ssl
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _build_engine():
    """Build SQLAlchemy engine with proper SSL config for Neon/cloud PostgreSQL."""
    url = str(settings.database_url).strip()

    # Detect cloud/Neon databases that require SSL
    is_cloud_db = any(
        host in url for host in ("neon.tech", "supabase.co", "render.com", "amazonaws.com")
    )

    if is_cloud_db or "sslmode" in url:
        # Ensure sslmode=require is in the URL for psycopg2
        if "sslmode" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
