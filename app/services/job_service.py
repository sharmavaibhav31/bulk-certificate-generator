"""
Job Service: Orchestrates job creation, validation, progress calculation, and export.
"""

from datetime import datetime, timezone
import re
import tempfile
from typing import Optional, Tuple, List, Generator
from uuid import UUID
import zipfile

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.models import Job, Certificate, Template, CertificateStatus
from app.schemas import JobCreate, JobProgress, DerivedJobStatus
from app.services.storage import StorageInterface, LocalStorage

# Standard RFC-compliant lenient email regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_recipient_data(name: str, email: str) -> Tuple[bool, Optional[str]]:
    """
    Level 2 Per-Recipient Business Rules Validation.

    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    clean_name = (name or "").strip()
    clean_email = (email or "").strip()

    if not clean_name:
        return False, "Recipient name cannot be empty."

    if len(clean_name) > 200:
        return False, "Recipient name exceeds 200 characters limit."

    if not clean_email:
        return False, "Recipient email cannot be empty."

    if not EMAIL_REGEX.match(clean_email):
        return False, f"Invalid email format: '{clean_email}'."

    return True, None


def create_job(db: Session, payload: JobCreate) -> Tuple[Job, bool]:
    """
    Create a bulk certificate generation job and initialize recipient rows.

    Features:
    - Idempotency: Returns existing job if payload.idempotency_key already exists.
    - Template snapshot: Freezes template layout so changes to templates don't alter in-flight jobs.
    - Level 2 Recipient validation: Bad recipients are accepted and stored as status='failed'
      with descriptive error messages; valid recipients are stored as status='pending'.

    Returns:
        (job: Job, created: bool)
    """
    # 1. Check idempotency key if provided
    if payload.idempotency_key:
        existing_job = (
            db.query(Job)
            .filter(Job.idempotency_key == payload.idempotency_key)
            .first()
        )
        if existing_job:
            return existing_job, False

    # 2. Verify Template exists and is active
    template = (
        db.query(Template)
        .filter(Template.id == payload.template_id, Template.is_deleted == False)  # noqa: E712
        .first()
    )
    if not template:
        raise ValueError(f"Template '{payload.template_id}' not found or has been deleted.")

    # 3. Create frozen snapshot of template layout and styling
    layout_snapshot = {
        "kind": template.kind,
        "key": template.key,
        "background_path": template.background_path,
        "layout": template.layout,
    }

    # 4. In ONE database transaction: Create Job and all recipient Certificate rows
    job = Job(
        title=payload.title.strip(),
        organization_name=payload.organization_name.strip() if payload.organization_name else None,
        issued_date=payload.issued_date,
        template_id=template.id,
        layout_snapshot=layout_snapshot,
        idempotency_key=payload.idempotency_key,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()  # Generate job.id for certificates foreign key

    # 5. Populate Certificate rows with Level 2 validation
    certificate_objects = []
    for rec in payload.recipients:
        is_valid, error_msg = validate_recipient_data(rec.name, rec.email)
        status = CertificateStatus.PENDING if is_valid else CertificateStatus.FAILED

        cert = Certificate(
            job_id=job.id,
            recipient_name=rec.name.strip(),
            recipient_email=rec.email.strip(),
            status=status,
            error_message=error_msg,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        certificate_objects.append(cert)

    db.add_all(certificate_objects)
    db.commit()
    db.refresh(job)

    return job, True


def get_progress(db: Session, job_id: UUID) -> JobProgress:
    """
    Dynamically computes job progress from certificate status counts.
    Never relies on stored counters to avoid desynchronization.
    """
    rows = (
        db.query(Certificate.status, func.count(Certificate.id))
        .filter(Certificate.job_id == job_id)
        .group_by(Certificate.status)
        .all()
    )

    counts = {status: count for status, count in rows}
    succeeded = counts.get(CertificateStatus.SUCCEEDED, 0)
    failed = counts.get(CertificateStatus.FAILED, 0)
    pending = (
        counts.get(CertificateStatus.PENDING, 0)
        + counts.get(CertificateStatus.PROCESSING, 0)
    )
    total = sum(counts.values())

    percent = round(((succeeded + failed) / total * 100.0), 2) if total > 0 else 100.0

    # Derive high-level job status from counts
    if total == 0:
        derived_status = DerivedJobStatus.COMPLETED
    elif pending > 0 and (succeeded + failed) == 0:
        derived_status = DerivedJobStatus.QUEUED
    elif pending > 0:
        derived_status = DerivedJobStatus.PROCESSING
    else:
        if failed == 0:
            derived_status = DerivedJobStatus.COMPLETED
        elif succeeded > 0:
            derived_status = DerivedJobStatus.COMPLETED_WITH_ERRORS
        else:
            derived_status = DerivedJobStatus.FAILED

    return JobProgress(
        total=total,
        succeeded=succeeded,
        failed=failed,
        pending=pending,
        percent=percent,
        status=derived_status,
    )


def list_certificates(
    db: Session,
    job_id: UUID,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[Certificate], int]:
    """Return paginated list of certificates for a job with optional status filter."""
    query = db.query(Certificate).filter(Certificate.job_id == job_id)

    if status:
        query = query.filter(Certificate.status == status)

    total_count = query.count()
    offset = max(0, (page - 1) * page_size)
    items = query.order_by(Certificate.created_at.asc()).offset(offset).limit(page_size).all()

    return items, total_count


def stream_job_zip(
    db: Session,
    job_id: UUID,
    storage: Optional[StorageInterface] = None,
    chunk_size: int = 65536,
) -> Generator[bytes, None, None]:
    """
    Stream a ZIP archive of all succeeded certificate PDFs for a job.
    Uses a temporary spool file to stream in chunks without holding all PDFs in RAM.
    """
    if storage is None:
        storage = LocalStorage()

    succeeded_certs = (
        db.query(Certificate)
        .filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.SUCCEEDED,
            Certificate.file_path.isnot(None),
        )
        .all()
    )

    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp_file:
        with zipfile.ZipFile(tmp_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for cert in succeeded_certs:
                if cert.file_path and storage.exists(cert.file_path):
                    safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", cert.recipient_name).replace(" ", "_")
                    filename_in_zip = f"{safe_name}_{str(cert.id)[:8]}.pdf"
                    pdf_data = storage.read(cert.file_path)
                    zf.writestr(filename_in_zip, pdf_data)

        # Rewind to start and stream chunks
        tmp_file.seek(0)
        while True:
            chunk = tmp_file.read(chunk_size)
            if not chunk:
                break
            yield chunk
