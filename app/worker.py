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
   or missing background on one recipient records status = 'failed' with error_message,
   committing immediately without interrupting remaining recipients in the batch.

3. Base Template Preloading:
   Loads the background image or base canvas once per job. Individual certificates
   use fast in-memory copies (`image.copy()`), avoiding repeated disk I/O and decodes.
   If a custom template background is missing or unreadable, the job fails immediately
   with a clear error rather than falling back to an incorrect blank design.

4. Celery / Distributed Task Queue Ready:
   The core function `process_job(job_id)` is completely self-contained with its
   own DB session and storage lifecycle. In a larger production setup, Celery
   could invoke `process_job.delay(str(job_id))` with zero changes to business logic.

5. Configurable Execution Mode:
   - WORKER_MODE='thread': Asynchronous processing via ThreadPoolExecutor.
   - WORKER_MODE='inline': Synchronous execution in current thread (ideal for pytest).
================================================================================
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import io
import logging
import os
from typing import Union
from uuid import UUID

from PIL import Image
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Job, Certificate, CertificateStatus
from app.services.certificate_renderer import (
    render_certificate,
    BUILTIN_CANVAS_WIDTH,
    BUILTIN_CANVAS_HEIGHT,
)
from app.services.template_registry import get_template_config
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


default_storage = LocalStorage()


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
        storage = default_storage

    target_job_uuid = UUID(str(job_id))

    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == target_job_uuid).first()
        if not job:
            logger.error("Job %s not found for processing.", target_job_uuid)
            return

        # Preload base template image once per job for high-performance batch rendering
        preloaded_base_image = None
        preload_error = None
        kind = job.layout_snapshot.get("kind", "builtin")

        if kind == "custom":
            bg_path = job.layout_snapshot.get("background_path")
            if not bg_path:
                preload_error = "Custom template is missing background_path."
            elif not storage.exists(bg_path):
                preload_error = f"Custom template background image '{bg_path}' not found."
            else:
                try:
                    bg_bytes = storage.read(bg_path)
                    loaded_img = Image.open(io.BytesIO(bg_bytes))
                    if loaded_img.mode not in ("RGB", "RGBA"):
                        loaded_img = loaded_img.convert("RGBA" if "A" in loaded_img.mode else "RGB")
                    preloaded_base_image = loaded_img
                except Exception as exc:
                    preload_error = f"Failed to open custom background image '{bg_path}': {str(exc)}"
        else:
            try:
                key = job.layout_snapshot.get("key", "classic")
                config = get_template_config(key)
                bg_color = config.get("colors", {}).get("background", "#FFFDF7")
                preloaded_base_image = Image.new("RGB", (BUILTIN_CANVAS_WIDTH, BUILTIN_CANVAS_HEIGHT), color=bg_color)
            except Exception as exc:
                preload_error = f"Failed to initialize builtin canvas: {str(exc)}"

        # If base image failed to load, fail all pending certificates immediately
        if preload_error:
            logger.error("Job %s base template error: %s", target_job_uuid, preload_error)
            stmt = (
                update(Certificate)
                .where(
                    Certificate.job_id == target_job_uuid,
                    Certificate.status.in_([CertificateStatus.PENDING, CertificateStatus.PROCESSING]),
                )
                .values(
                    status=CertificateStatus.FAILED,
                    error_message=preload_error,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            db.execute(stmt)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        out_format = (job.output_format or "pdf").lower()
        job_fields = {
            "title": job.title,
            "organization_name": job.organization_name,
            "issued_date": str(job.issued_date) if job.issued_date else None,
        }

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

                # 3. Render certificate inside isolated try/except block
                try:
                    cert_bytes = render_certificate(
                        name=cert.recipient_name,
                        template_snapshot=job.layout_snapshot,
                        job_fields=job_fields,
                        output_format=out_format,
                        storage=storage,
                        preloaded_base_image=preloaded_base_image,
                    )

                    file_path = f"{job.id}/{cert.id}.{out_format}"
                    storage.save(file_path, cert_bytes)

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
