from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import TemplateOut
from app.services import template_service
from app.services.pdf_generator import render_preview
from app.services.storage import LocalStorage

router = APIRouter(prefix="/templates", tags=["Templates"])
storage = LocalStorage()


@router.get("", response_model=List[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    """List all available certificate templates (built-in and custom)."""
    return template_service.list_active_templates(db)


@router.get("/{template_id}/preview")
def get_template_preview(template_id: UUID, db: Session = Depends(get_db)):
    """Render and return a sample preview PDF for a template."""
    template = template_service.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID '{template_id}' was not found.",
        )

    pdf_bytes = render_preview(template, storage=storage)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="preview_{template_id}.pdf"'},
    )


@router.post("/custom", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def upload_custom_template(
    name: str = Form(..., description="Template display name"),
    image: UploadFile = File(..., description="Certificate background image (PNG/JPEG)"),
    name_y: float = Form(..., ge=0.0, le=100.0, description="Recipient name Y percentage (0-100)"),
    course_y: float = Form(..., ge=0.0, le=100.0, description="Course title Y percentage (0-100)"),
    date_y: float = Form(..., ge=0.0, le=100.0, description="Issue date Y percentage (0-100)"),
    db: Session = Depends(get_db),
):
    """
    Upload a custom certificate background image with layout percentage coordinates.
    Rejects with 413 if > 5MB, 415 if unsupported format, or 400 if bad aspect ratio/coordinates.
    """
    file_bytes = await image.read()
    layout_data = {"name_y": name_y, "course_y": course_y, "date_y": date_y}

    try:
        template = template_service.create_custom_template(
            db=db,
            name=name,
            file_bytes=file_bytes,
            layout_data=layout_data,
            storage=storage,
        )
        return template

    except template_service.FileSizeExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except template_service.UnsupportedFormatError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e),
        )
    except template_service.InvalidTemplateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
