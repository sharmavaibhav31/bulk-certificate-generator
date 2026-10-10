"""
Background Worker for Asynchronous Certificate Generation.

================================================================================
CONCURRENCY & WORKER ARCHITECTURE:
================================================================================
1. Atomic Row Claim (Race Condition Prevention):
   When worker threads pick up pending certificates, they atomically execute:
     UPDATE certificates SET status = 'processing'
     WHERE id = :id AND status = 'pending';
   Because the database enforces row locks on UPDATE, only one worker can match
   status = 'pending' and receive rowcount == 1. All concurrent workers receive
   rowcount == 0 and skip that certificate, preventing double-processing.

2. Failure Isolation:
   Each certificate is rendered inside its own try/except block. A rendering error
   or invalid font on one recipient records status = 'failed' with error_message,
   committing immediately without interrupting remaining recipients in the batch.

3. Celery / Distributed Task Queue Ready:
   The core function `process_job(job_id)` is completely self-contained with its
   own DB session and storage lifecycle. In a larger production setup, Celery
   could invoke `process_job.delay(str(job_id))` with zero changes to business logic.

4. Configurable Execution Mode:
   - WORKER_MODE='thread': Asynchronous processing via ThreadPoolExecutor.
   - WORKER_MODE='inline': Synchronous execution in current thread (ideal for pytest).
================================================================================
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
import os
from typing import Union
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Job, Certificate, CertificateStatus
from app.services.pdf_generator import render_certificate
from app.services.storage import StorageInterface, LocalStorage

logger = logging.getLogger("app.worker")

# Worker configuration
WORKER_MAX_WORKERS = int(os.getenv("WORKER_MAX_WORKERS", "4"))
WORKER_MODE = os.getenv("WORKER_MODE", "thread")  # "thread" or "inline"
BATCH_SIZE = 50

# App-level ThreadPoolExecutor
_executor = ThreadPoolExecutor(
    max_workers=WORKER_MAX_WORKERS,
    thread_name_prefix="cert_worker_",
)


def process_job(
    job_id: Union[str, UUID],
    storage: StorageInterface = None,
) -> None:
    """
    Main certificate processing engine for a given job_id.

    This function is completely agnostic of how it is scheduled (ThreadPoolExecutor,
    FastAPI BackgroundTasks, or Celery task worker). It manages its own DB sessions,
    atomically claims rows, and commits progress per-certificate so UI pollers see
    immediate live progress updates.
    """
    if storage is None:
        storage = LocalStorage()

    target_job_uuid = UUID(str(job_id))

    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == target_job_uuid).first()
        if not job:
            logger.error("Job %s not found for processing.", target_job_uuid)
            return

        # Continuous batch processing until no pending certificates remain
        while True:
            # Fetch a batch of pending certificate IDs for this job
            pending_ids = (
                db.query(Certificate.id)
                .filter(
                    Certificate.job_id == target_job_uuid,
                    Certificate.status == CertificateStatus.PENDING,
                )
                .limit(BATCH_SIZE)
                .all()
            )

            if not pending_ids:
                break

            for (cert_id,) in pending_ids:
                # 1. ATOMIC CLAIM: Update status to 'processing' only if currently 'pending'
                stmt = (
                    update(Certificate)
                    .where(
                        Certificate.id == cert_id,
                        Certificate.status == CertificateStatus.PENDING,
                    )
                    .values(
                        status=CertificateStatus.PROCESSING,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                res = db.execute(stmt)
                db.commit()

                # If another worker claimed this row, skip it
                if res.rowcount != 1:
                    continue

                # 2. Re-fetch certificate for rendering
                cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
                if not cert:
                    continue

                # 3. Render PDF inside isolated try/except block
                try:
                    pdf_bytes = render_certificate(
                        recipient_name=cert.recipient_name,
                        course_title=job.title,
                        issued_date=job.issued_date,
                        organization_name=job.organization_name,
                        template=job.layout_snapshot,
                        storage=storage,
                    )

                    file_path = f"certificates/{job.id}/{cert.id}.pdf"
                    storage.save(file_path, pdf_bytes)

                    cert.status = CertificateStatus.SUCCEEDED
                    cert.file_path = file_path
                    cert.error_message = None

                except Exception as exc:
                    logger.warning("Error generating certificate %s: %s", cert.id, str(exc))
                    cert.status = CertificateStatus.FAILED
                    cert.error_message = str(exc)

                finally:
                    cert.updated_at = datetime.now(timezone.utc)
                    db.commit()

        # 4. Mark job.finished_at when no pending or processing rows remain
        remaining_count = (
            db.query(Certificate.id)
            .filter(
                Certificate.job_id == target_job_uuid,
                Certificate.status.in_([CertificateStatus.PENDING, CertificateStatus.PROCESSING]),
            )
            .count()
        )

        if remaining_count == 0:
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("Job %s completed all certificate processing.", target_job_uuid)


def submit_job(job_id: Union[str, UUID]) -> None:
    """Submit a job for execution according to configured WORKER_MODE."""
    mode = os.getenv("WORKER_MODE", WORKER_MODE)
    if mode == "inline":
        # Synchronous execution (ideal for unit and integration testing)
        process_job(job_id)
    else:
        # Asynchronous background thread execution
        _executor.submit(process_job, job_id)


def recover_stuck_certificates(db: Session) -> int:
    """
    On app startup: Reset any certificates stranded in 'processing' back to 'pending'
    (caused by unexpected server reboots or crashes) and re-queue their jobs.
    """
    stuck_certs = (
        db.query(Certificate.id, Certificate.job_id)
        .filter(Certificate.status == CertificateStatus.PROCESSING)
        .all()
    )

    if not stuck_certs:
        return 0

    stuck_ids = [c[0] for c in stuck_certs]
    unique_job_ids = list({c[1] for c in stuck_certs})

    stmt = (
        update(Certificate)
        .where(Certificate.id.in_(stuck_ids))
        .values(
            status=CertificateStatus.PENDING,
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.execute(stmt)
    db.commit()

    logger.info("Recovered %d stuck certificates. Re-submitting %d jobs.", len(stuck_ids), len(unique_job_ids))

    for jid in unique_job_ids:
        submit_job(jid)

    return len(stuck_ids)
