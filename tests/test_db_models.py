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
    TemplateLayout,
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
        status=CertificateStatus.SUCCEEDED,
    )
    cert2 = Certificate(
        job_id=job.id,
        recipient_name="Bob Jones",
        recipient_email="invalid-email-format",
        status=CertificateStatus.FAILED,
        error_message="Invalid email address format",
    )
    db_session.add_all([cert1, cert2])
    db_session.commit()

    assert job.id is not None
    assert len(job.certificates) == 2
    assert cert1.status == CertificateStatus.SUCCEEDED
    assert cert2.status == CertificateStatus.FAILED


def test_schemas_lenient_recipient_validation():
    # Structural valid request with non-standard email should pass Level 1 validation
    rec = RecipientIn(name="John Doe", email="not-an-email")
    assert rec.email == "not-an-email"

    job_data = JobCreate(
        title="Web Dev Bootcamp",
        issued_date=date(2026, 10, 7),
        template_id=uuid.uuid4(),
        recipients=[rec],
    )
    assert len(job_data.recipients) == 1


def test_template_layout_bounds():
    valid_layout = TemplateLayout(name_y=45.0, course_y=60.0, date_y=75.0)
    assert valid_layout.name_y == 45.0

    with pytest.raises(Exception):
        TemplateLayout(name_y=150.0, course_y=60.0, date_y=75.0)  # > 100
