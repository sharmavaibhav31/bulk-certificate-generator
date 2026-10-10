import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Certificate, CertificateStatus
from app.services.storage import LocalStorage

router = APIRouter(prefix="/certificates", tags=["Certificates"])
storage = LocalStorage()


@router.get("/{certificate_id}/download")
def download_single_certificate(certificate_id: UUID, db: Session = Depends(get_db)):
    """
    Download a single generated certificate PDF file.
    Returns 404 if the certificate is not found, failed, or still processing.
    """
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' not found.",
        )

    if cert.status != CertificateStatus.SUCCEEDED or not cert.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{certificate_id}' has not succeeded (status: {cert.status.value}).",
        )

    if not storage.exists(cert.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate file for '{certificate_id}' is not found on disk.",
        )

    pdf_bytes = storage.read(cert.file_path)
    safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", cert.recipient_name).replace(" ", "_")
    download_filename = f"{safe_name}_{str(cert.id)[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'},
    )
