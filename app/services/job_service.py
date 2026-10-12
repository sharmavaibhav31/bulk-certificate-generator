"""
Job Service: Orchestrates job creation, validation, progress calculation, and export.
"""

from datetime import datetime, timezone
import re
import tempfile
from typing import Optional, Tuple, List, Generator, Dict
from uuid import UUID
import zipfile

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Job, Certificate, Template, CertificateStatus
from app.schemas import JobCreate, JobProgress, DerivedJobStatus, FailedRecipientOut
from app.services.storage import StorageInterface, LocalStorage

# Standard RFC-compliant lenient email regex
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Windows reserved device names to prevent problematic filenames in cross-platform archives
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_file_name(name: str, ext: str, seen_counts: Dict[str, int]) -> str:
    """
    Generate a safe, friendly, deduplicated file name for certificate export.
    E.g. 'Jane Doe' -> 'Jane_Doe.pdf', 'Jane_Doe (2).pdf'.
    Guards against reserved names and limits base length to 100 characters.
    """
    clean = re.sub(r"[^\w\s\-]", "", name).strip()
    clean = re.sub(r"\s+", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("._-")

    if not clean or clean.upper() in WINDOWS_RESERVED_NAMES:
        clean = "certificate"

    base_name = clean[:100].rstrip("._-")
    if not base_name:
        base_name = "certificate"

    extension = (ext or "pdf").lower().lstrip(".")

    seen_counts[base_name] = seen_counts.get(base_name, 0) + 1
    count = seen_counts[base_name]
    if count == 1:
        return f"{base_name}.{extension}"
    return f"{base_name} ({count}).{extension}"


def validate_recipient_data(
    name: Optional[str],
    email: Optional[str],
) -> Tuple[bool, Optional[str], str, Optional[str]]:
    """
    Level 2 Per-Recipient Business Rules Validation.
    - name: Mandatory, non-empty, max 200 chars.
    - email: Optional. If present, must be syntactically valid.

    Returns:
        (is_valid: bool, error_message: Optional[str], clean_name: str, clean_email: Optional[str])
    """
    clean_name = (name or "").strip()
    clean_email = (email or "").strip() if email else None

    if not clean_name:
        return False, "Recipient name cannot be empty.", clean_name, clean_email

    if len(clean_name) > 200:
        return False, "Recipient name exceeds 200 characters limit.", clean_name, clean_email

    if clean_email:
        if not EMAIL_REGEX.match(clean_email):
            return False, f"Invalid email format: '{clean_email}'.", clean_name, clean_email
    else:
        clean_email = None

    return True, None, clean_name, clean_email


def create_job(db: Session, payload: JobCreate) -> Tuple[Job, bool]:
    """
    Create a bulk certificate generation job and initialize recipient rows.

    Features:
    - Idempotency: Returns existing job if payload.idempotency_key already exists.
    - Template snapshot: Freezes template layout and required_fields so template changes
      never modify in-flight jobs.
    - Required fields check: Validates payload against template.required_fields.
    - Level 2 Recipient validation: Bad recipients are stored as status='failed'
      with descriptive error messages; valid recipients are stored as status='pending'.
    - Sanitized, deduplicated filenames generated per recipient.

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

    # 3. Validate template required fields
    required_fields = template.required_fields or ["name"]
    missing = []
    if "title" in required_fields and (not payload.title or not payload.title.strip()):
        missing.append("title")
    if "issued_date" in required_fields and payload.issued_date is None:
        missing.append("issued_date")
    if missing:
        raise ValueError(f"Template '{template.name}' requires the following fields: {', '.join(missing)}")

    # 4. Create frozen snapshot of template layout and styling
    layout_snapshot = {
        "kind": template.kind,
        "key": template.key,
        "background_path": template.background_path,
        "layout": template.layout,
        "required_fields": template.required_fields,
    }

    out_format = (payload.output_format or "pdf").lower()

    # 5. In ONE database transaction: Create Job and all recipient Certificate rows
    job = Job(
        title=payload.title.strip() if payload.title else None,
        organization_name=payload.organization_name.strip() if payload.organization_name else None,
        issued_date=payload.issued_date,
        template_id=template.id,
        output_format=out_format,
        layout_snapshot=layout_snapshot,
        idempotency_key=payload.idempotency_key,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()  # Generate job.id for certificates foreign key

    # 6. Populate Certificate rows with Level 2 validation and deduplicated filenames
    seen_filenames: Dict[str, int] = {}
    certificate_objects = []
    for rec in payload.recipients:
        is_valid, error_msg, clean_name, clean_email = validate_recipient_data(rec.name, rec.email)
        status = CertificateStatus.PENDING if is_valid else CertificateStatus.FAILED
        file_name = sanitize_file_name(clean_name or rec.name, out_format, seen_filenames)

        cert = Certificate(
            job_id=job.id,
            recipient_name=clean_name if clean_name else (rec.name or "").strip(),
            recipient_email=clean_email,
            file_name=file_name,
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
    Includes list of failed recipients with error details.
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
    processing = counts.get(CertificateStatus.PROCESSING, 0)
    pending_only = counts.get(CertificateStatus.PENDING, 0)
    pending = pending_only + processing
    total = sum(counts.values())

    percent = round(((succeeded + failed) / total * 100.0), 2) if total > 0 else 100.0

    # Derive high-level job status from counts
    if total == 0:
        derived_status = DerivedJobStatus.COMPLETED
    elif pending > 0 and processing == 0 and succeeded == 0:
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

    # Fetch failed recipients
    failed_certs = (
        db.query(Certificate.recipient_name, Certificate.recipient_email, Certificate.error_message)
        .filter(Certificate.job_id == job_id, Certificate.status == CertificateStatus.FAILED)
        .order_by(Certificate.created_at.asc())
        .all()
    )
    failed_recipients = [
        FailedRecipientOut(name=fc[0], email=fc[1], error_message=fc[2])
        for fc in failed_certs
    ]

    return JobProgress(
        total=total,
        succeeded=succeeded,
        failed=failed,
        pending=pending,
        percent=percent,
        status=derived_status,
        failed_recipients=failed_recipients,
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
    Stream a ZIP archive of all succeeded certificates for a job.
    Uses ZIP_STORED (no compression overhead) and streams via a temporary spool file.
    Entries inside the ZIP are named using the sanitized, deduplicated cert.file_name.
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
        with zipfile.ZipFile(tmp_file, mode="w", compression=zipfile.ZIP_STORED) as zf:
            for cert in succeeded_certs:
                if cert.file_path and storage.exists(cert.file_path):
                    entry_name = cert.file_name or f"certificate_{str(cert.id)[:8]}.pdf"
                    file_data = storage.read(cert.file_path)
                    zf.writestr(entry_name, file_data)

        # Rewind to start and stream chunks
        tmp_file.seek(0)
        while True:
            chunk = tmp_file.read(chunk_size)
            if not chunk:
                break
            yield chunk
