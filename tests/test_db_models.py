from datetime import date
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Template, Job, Certificate, CertificateStatus
from app.schemas import (
    RecipientIn,
    JobCreate,
    JobProgress,
    DerivedJobStatus,
)
from app.seed import seed_builtin_templates


@pytest.fixture
def db_session():
    """Fixture providing an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_seed_builtin_templates(db_session):
    seed_builtin_templates(db_session)
    templates = db_session.query(Template).filter(Template.kind == "builtin").all()
    assert len(templates) == 5
    keys = {t.key for t in templates}
    assert keys == {"classic", "modern", "minimal", "elegant", "bold"}
    for t in templates:
        assert t.required_fields == ["name", "title", "issued_date"]


def test_create_job_and_certificate(db_session):
    seed_builtin_templates(db_session)
    template = db_session.query(Template).first()
    assert template is not None

    job = Job(
        title="Python Developer Workshop",
        organization_name="Tech Academy",
        issued_date=date(2026, 10, 7),
        template_id=template.id,
        layout_snapshot=template.layout,
    )
    db_session.add(job)
    db_session.commit()

    cert1 = Certificate(
        job_id=job.id,
        recipient_name="Alice Smith",
        recipient_email="alice@example.com",
        file_name="Alice_Smith.pdf",
        status=CertificateStatus.SUCCEEDED,
    )
    cert2 = Certificate(
        job_id=job.id,
        recipient_name="Bob Jones",
        recipient_email="invalid-email-format",
        file_name="Bob_Jones.pdf",
        status=CertificateStatus.FAILED,
        error_message="Invalid email address format",
    )
    db_session.add_all([cert1, cert2])
    db_session.commit()

    assert job.id is not None
    assert len(job.certificates) == 2
    assert cert1.status == CertificateStatus.SUCCEEDED
    assert cert2.status == CertificateStatus.FAILED
    assert cert1.file_name == "Alice_Smith.pdf"


def test_schemas_lenient_recipient_validation():
    # Email is optional in RecipientIn
    rec1 = RecipientIn(name="John Doe", email="john@example.com")
    assert rec1.email == "john@example.com"

    rec2 = RecipientIn(name="Jane Doe")  # email omitted
    assert rec2.email is None

    job_data = JobCreate(
        title="Web Dev Bootcamp",
        issued_date=date(2026, 10, 7),
        template_id=uuid.uuid4(),
        recipients=[rec1, rec2],
    )
    assert len(job_data.recipients) == 2
    assert job_data.output_format == "pdf"
