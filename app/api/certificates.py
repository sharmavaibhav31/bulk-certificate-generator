"""
Certificates API: Direct endpoints for downloading single certificates.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Certificate, CertificateStatus
from app.services.storage import LocalStorage

router = APIRouter(prefix="/certificates", tags=["Certificates"])
storage = LocalStorage()

MIME_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


@router.get("/{certificate_id}/download")
def download_single_certificate(certificate_id: UUID, db: Session = Depends(get_db)):
    """
    Download a single generated certificate file (PDF, PNG, or JPG).
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

    cert_bytes = storage.read(cert.file_path)
    file_name = cert.file_name or f"certificate_{str(cert.id)[:8]}.pdf"
    ext = file_name.split(".")[-1].lower() if "." in file_name else "pdf"
    media_type = MIME_TYPES.get(ext, "application/octet-stream")

    return Response(
        content=cert_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
