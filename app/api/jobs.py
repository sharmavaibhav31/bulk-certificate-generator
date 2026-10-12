"""
Jobs API: Endpoints for submitting, monitoring, listing, and exporting certificate jobs.
"""

import re
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job
from app.schemas import JobCreate, JobProgress, CertificateOut
from app.services import job_service, template_service
from app.services.storage import LocalStorage
from app.worker import submit_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])
storage = LocalStorage()


class JobCreatedResponse(BaseModel):
    id: UUID
    status: str
    status_url: str


class CertificateListResponse(BaseModel):
    items: List[CertificateOut]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.post("", response_model=JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
def create_bulk_job(
    payload: JobCreate,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """
    Create a bulk certificate generation job.
    Returns HTTP 202 Accepted with job ID and polling status URL.
    Dispatches generation task to the background worker after database commit.
    """
    # Header takes precedence if provided
    if idempotency_key_header:
        payload.idempotency_key = idempotency_key_header.strip()

    # Verify template exists
    template = template_service.get_template_by_id(db, payload.template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID '{payload.template_id}' not found.",
        )

    try:
        job, is_new = job_service.create_job(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # Dispatch to background worker
    if is_new or job.finished_at is None:
        submit_job(job.id)

    return JobCreatedResponse(
        id=job.id,
        status="queued",
        status_url=f"/api/v1/jobs/{job.id}",
    )


@router.get("/{job_id}", response_model=JobProgress)
def get_job_progress(job_id: UUID, db: Session = Depends(get_db)):
    """
    Fetch live progress of a generation job.
    Counts and progress percentage are dynamically calculated from certificate rows.
    Returns failed recipients list with name, email, and error_message.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    return job_service.get_progress(db, job_id)


@router.get("/{job_id}/certificates", response_model=CertificateListResponse)
def get_job_certificates(
    job_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status (pending, processing, succeeded, failed)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated recipient certificates for a job, including error messages for failed rows.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    items, total_count = job_service.list_certificates(
        db, job_id=job_id, status=status, page=page, page_size=page_size
    )
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    return CertificateListResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{job_id}/download")
def download_all_certificates_zip(job_id: UUID, db: Session = Depends(get_db)):
    """
    Stream a ZIP file containing all successfully generated certificates in this job.
    Uses ZIP_STORED, entries named by cert.file_name, download named after job title.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    safe_title = re.sub(r"[^\w\s\-]", "", job.title or "").strip().replace(" ", "_")
    zip_filename = f"{safe_title}.zip" if safe_title else f"certificates_{job_id}.zip"

    return StreamingResponse(
        job_service.stream_job_zip(db, job_id, storage=storage),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
