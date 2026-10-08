import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///./app.db"
)

# Connect args specific to SQLite (used for local dev / pytest fallback)
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.0 models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a transactional SQLAlchemy session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables using Base.metadata.create_all and seed initial data."""
    # Import models here to ensure they are registered on Base.metadata before create_all
    import app.models  # noqa: F401
    from app.seed import seed_builtin_templates

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_builtin_templates(db)
