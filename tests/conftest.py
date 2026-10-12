import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.seed import seed_builtin_templates
from app.services.storage import LocalStorage
from app import worker
from app.api import templates, jobs, certificates


@pytest.fixture
def temp_storage(tmp_path):
    """Provides a fresh, isolated LocalStorage directory for each test."""
    storage_dir = tmp_path / "storage"
    return LocalStorage(base_dir=str(storage_dir))


@pytest.fixture
def test_db_session_factory(tmp_path):
    """Creates a temporary SQLite database with all tables created and built-in templates seeded."""
    db_file = tmp_path / "test_app.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    # Seed templates
    with TestingSession() as session:
        seed_builtin_templates(session)

    return TestingSession


@pytest.fixture
def client(test_db_session_factory, temp_storage, monkeypatch):
    """
    Configures FastAPI TestClient with:
    - Inline synchronous worker execution (WORKER_MODE=inline)
    - Test database session override
    - Isolated temporary storage backend
    """
    monkeypatch.setenv("WORKER_MODE", "inline")
    monkeypatch.setattr(worker, "SessionLocal", test_db_session_factory)
    monkeypatch.setattr(templates, "storage", temp_storage)
    monkeypatch.setattr(jobs, "storage", temp_storage)
    monkeypatch.setattr(certificates, "storage", temp_storage)
    monkeypatch.setattr(worker, "default_storage", temp_storage)

    def override_get_db():
        db = test_db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
