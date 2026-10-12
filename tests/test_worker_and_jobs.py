from datetime import date
import io
import os
import uuid
import zipfile
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Template, Job, Certificate, CertificateStatus
from app.schemas import JobCreate, RecipientIn, DerivedJobStatus
from app.services.job_service import (
    create_job,
    get_progress,
    list_certificates,
    stream_job_zip,
)
from app.services.storage import LocalStorage
from app.seed import seed_builtin_templates
from app import worker


@pytest.fixture
def test_db_and_storage(tmp_path, monkeypatch):
    storage_dir = tmp_path / "storage"
    storage = LocalStorage(base_dir=str(storage_dir))

    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed templates
    seed_builtin_templates(session)

    # Configure worker to use this SessionLocal and LocalStorage
    monkeypatch.setattr(worker, "SessionLocal", Session)
    monkeypatch.setattr(worker, "default_storage", storage)
    monkeypatch.setenv("WORKER_MODE", "inline")

    try:
        yield session, storage
    finally:
        session.close()


def test_create_job_with_mixed_recipients(test_db_and_storage):
    db, storage = test_db_and_storage
    template = db.query(Template).filter(Template.key == "classic").first()

    recipients = [
        RecipientIn(name="Alice Good", email="alice@example.com"),
        RecipientIn(name="", email="noname@example.com"),  # Invalid: empty name
        RecipientIn(name="Bob BadEmail", email="bad-email-format"),  # Invalid: bad email
        RecipientIn(name="Charlie NoEmail"),  # Valid: optional email omitted
    ]

    payload = JobCreate(
        title="Python Mastery Workshop",
        organization_name="Code Academy",
        issued_date=date(2026, 10, 10),
        template_id=template.id,
        recipients=recipients,
    )

    job, created = create_job(db, payload)
    assert created is True
    assert job.id is not None

    # Check progress immediately after creation
    progress = get_progress(db, job.id)
    assert progress.total == 4
    assert progress.pending == 2
    assert progress.failed == 2
    assert progress.succeeded == 0
    assert progress.status == DerivedJobStatus.QUEUED

    # Verify invalid rows have error messages
    certs = db.query(Certificate).filter(Certificate.job_id == job.id).all()
    failed_certs = [c for c in certs if c.status == CertificateStatus.FAILED]
    assert len(failed_certs) == 2
    assert any("name cannot be empty" in c.error_message.lower() for c in failed_certs)
    assert any("invalid email format" in c.error_message.lower() for c in failed_certs)


def test_job_idempotency_key(test_db_and_storage):
    db, storage = test_db_and_storage
    template = db.query(Template).first()
    key = "unique-client-idempotency-key-123"

    payload = JobCreate(
        title="Web Dev",
        issued_date=date(2026, 10, 10),
        template_id=template.id,
        recipients=[RecipientIn(name="Alice", email="alice@test.com")],
        idempotency_key=key,
    )

    job1, created1 = create_job(db, payload)
    assert created1 is True

    # Submitting identical idempotency key returns existing job
    job2, created2 = create_job(db, payload)
    assert created2 is False
    assert job1.id == job2.id


def test_worker_processing_mixed_batch(test_db_and_storage):
    db, storage = test_db_and_storage
    template = db.query(Template).filter(Template.key == "modern").first()

    recipients = [
        RecipientIn(name="Elena Rostova", email="elena@example.com"),
        RecipientIn(name="Bad Email Guy", email="not_an_email"),
        RecipientIn(name="Daisuke Sato", email="daisuke@example.com"),
    ]

    payload = JobCreate(
        title="Cloud Architecture Certification",
        issued_date=date(2026, 10, 10),
        template_id=template.id,
        recipients=recipients,
    )

    job, _ = create_job(db, payload)

    # Process job synchronously with worker
    worker.process_job(job.id, storage=storage)

    # Refresh DB state
    db.expire_all()
    progress = get_progress(db, job.id)

    assert progress.total == 3
    assert progress.succeeded == 2
    assert progress.failed == 1
    assert progress.pending == 0
    assert progress.percent == 100.0
    assert progress.status == DerivedJobStatus.COMPLETED_WITH_ERRORS

    # Verify PDF files exist in storage for succeeded certs
    succeeded_certs = (
        db.query(Certificate)
        .filter(Certificate.job_id == job.id, Certificate.status == CertificateStatus.SUCCEEDED)
        .all()
    )
    assert len(succeeded_certs) == 2
    for sc in succeeded_certs:
        assert sc.file_path is not None
        assert storage.exists(sc.file_path)
        pdf_bytes = storage.read(sc.file_path)
        assert pdf_bytes.startswith(b"%PDF")


def test_pagination_and_zip_streaming(test_db_and_storage):
    db, storage = test_db_and_storage
    template = db.query(Template).first()

    payload = JobCreate(
        title="Cybersecurity Intensive",
        issued_date=date(2026, 10, 10),
        template_id=template.id,
        recipients=[
            RecipientIn(name="User One", email="one@test.com"),
            RecipientIn(name="User Two", email="two@test.com"),
        ],
    )
    job, _ = create_job(db, payload)
    worker.process_job(job.id, storage=storage)

    # Test list_certificates pagination
    items, total = list_certificates(db, job.id, page=1, page_size=1)
    assert total == 2
    assert len(items) == 1

    # Test stream_job_zip
    zip_bytes_buffer = io.BytesIO()
    for chunk in stream_job_zip(db, job.id, storage=storage):
        zip_bytes_buffer.write(chunk)

    zip_bytes_buffer.seek(0)
    with zipfile.ZipFile(zip_bytes_buffer, "r") as zf:
        namelist = zf.namelist()
        assert len(namelist) == 2
        for fn in namelist:
            assert fn.endswith(".pdf")
