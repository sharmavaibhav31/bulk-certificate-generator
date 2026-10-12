"""
Templates API: Endpoints for listing, previewing, and uploading certificate templates.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import TemplateOut
from app.services import template_service
from app.services.certificate_renderer import render_preview
from app.services.storage import LocalStorage

router = APIRouter(prefix="/templates", tags=["Templates"])
storage = LocalStorage()


@router.get("", response_model=List[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    """List all available certificate templates (built-in and custom)."""
    return template_service.list_active_templates(db)


@router.get("/{template_id}/preview")
def get_template_preview(
    template_id: UUID,
    name: str = Query("Sample Name", description="Sample recipient name to render on preview"),
    db: Session = Depends(get_db),
):
    """
    Render and return a live preview PNG for a template.
    Uses the exact same Pillow rendering pipeline as the background worker.
    """
    template = template_service.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID '{template_id}' was not found.",
        )

    snapshot = {
        "kind": template.kind,
        "key": template.key,
        "background_path": template.background_path,
        "layout": template.layout,
        "required_fields": template.required_fields,
    }

    try:
        png_bytes = render_preview(snapshot, sample_name=name, storage=storage)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render template preview: {str(exc)}",
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="preview_{template_id}.png"'},
    )


@router.post("/custom", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def upload_custom_template(
    name: str = Form(..., description="Template display name"),
    image: UploadFile = File(..., description="Certificate background image (PNG or JPEG, up to 10MB)"),
    name_x: float = Form(50.0, ge=0.0, le=100.0, description="Recipient name X percentage (0-100, default 50)"),
    name_y: float = Form(57.0, ge=0.0, le=100.0, description="Recipient name Y percentage (0-100, default 57)"),
    font: str = Form("dejavu_sans", description="Font key from bundled fonts (dejavu_sans, dejavu_serif, liberation_sans, liberation_serif)"),
    font_size_pct: float = Form(5.0, gt=0.0, le=50.0, description="Font size as percent of image height"),
    color: str = Form("#1A202C", description="Hex color code for recipient name"),
    max_width_pct: float = Form(70.0, gt=0.0, le=100.0, description="Max width percentage before text auto-shrinks"),
    db: Session = Depends(get_db),
):
    """
    Upload a custom certificate background image and configure name overlay coordinates.
    - Validates size under 10 MB, pixels under 25M, format PNG or JPEG.
    - Saves image as lossless PNG at backgrounds/{template_id}.png at ORIGINAL resolution.
    - Does not enforce aspect ratio or resize the image.
    """
    file_bytes = await image.read()
    layout_data = {
        "name_x": name_x,
        "name_y": name_y,
        "font": font,
        "font_size_pct": font_size_pct,
        "color": color,
        "max_width_pct": max_width_pct,
    }

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


@router.post("/preview/draft")
async def preview_custom_draft(
    image: UploadFile = File(..., description="Certificate background image"),
    name_x: float = Form(50.0, ge=0.0, le=100.0),
    name_y: float = Form(57.0, ge=0.0, le=100.0),
    font: str = Form("dejavu_sans"),
    font_size_pct: float = Form(5.0, gt=0.0, le=50.0),
    color: str = Form("#1A202C"),
    max_width_pct: float = Form(70.0, gt=0.0, le=100.0),
    sample_name: str = Form("Jane Doe"),
):
    """
    Render a live preview PNG on the fly from an uploaded draft image and layout specs,
    without saving anything to persistent storage.
    """
    import io
    from PIL import Image
    from app.services.certificate_renderer import render_certificate

    file_bytes = await image.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file is empty.")

    try:
        loaded_img = Image.open(io.BytesIO(file_bytes))
        if loaded_img.mode not in ("RGB", "RGBA"):
            loaded_img = loaded_img.convert("RGBA" if "A" in loaded_img.mode else "RGB")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid image file: {str(exc)}")

    snapshot = {
        "kind": "custom",
        "key": "custom",
        "background_path": None,
        "layout": {
            "name_x": name_x,
            "name_y": name_y,
            "font": font,
            "font_size_pct": font_size_pct,
            "color": color,
            "max_width_pct": max_width_pct,
        },
        "required_fields": ["name"],
    }

    try:
        png_bytes = render_certificate(
            name=sample_name,
            template_snapshot=snapshot,
            job_fields={},
            output_format="png",
            preloaded_base_image=loaded_img,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render preview: {str(exc)}",
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": 'inline; filename="draft_preview.png"'},
    )

