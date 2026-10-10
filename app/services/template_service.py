"""
Template Service: Business logic for retrieving and uploading certificate templates.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Template
from app.services.storage import StorageInterface, LocalStorage
from app.services.template_upload import validate_and_store_background, MAX_FILE_SIZE_BYTES


class TemplateServiceError(Exception):
    """Base exception for template service operations."""
    pass


class FileSizeExceededError(TemplateServiceError):
    """Raised when uploaded file exceeds 5MB limit (maps to HTTP 413)."""
    pass


class UnsupportedFormatError(TemplateServiceError):
    """Raised when file format is not PNG or JPEG (maps to HTTP 415)."""
    pass


class InvalidTemplateError(TemplateServiceError):
    """Raised when template coordinates or aspect ratio are invalid (maps to HTTP 400)."""
    pass


def list_active_templates(db: Session) -> List[Template]:
    """Retrieve all non-deleted certificate templates."""
    return (
        db.query(Template)
        .filter(Template.is_deleted == False)  # noqa: E712
        .order_by(Template.created_at.asc())
        .all()
    )


def get_template_by_id(db: Session, template_id: UUID) -> Optional[Template]:
    """Fetch a non-deleted template by UUID."""
    return (
        db.query(Template)
        .filter(Template.id == template_id, Template.is_deleted == False)  # noqa: E712
        .first()
    )


def create_custom_template(
    db: Session,
    name: str,
    file_bytes: bytes,
    layout_data: Dict[str, Any],
    storage: Optional[StorageInterface] = None,
) -> Template:
    """
    Validate uploaded background, persist it, and insert custom template record into the database.
    """
    if storage is None:
        storage = LocalStorage()

    clean_name = (name or "").strip()
    if not clean_name:
        raise InvalidTemplateError("Template name cannot be empty.")

    # Validate layout coordinate ranges (0 to 100)
    for field in ("name_y", "course_y", "date_y"):
        val = layout_data.get(field)
        if val is None or not (0.0 <= float(val) <= 100.0):
            raise InvalidTemplateError(f"Field '{field}' must be a percentage between 0 and 100.")

    # Validate file size
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise FileSizeExceededError(
            f"File size ({len(file_bytes) / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of 5 MB."
        )

    # Validate image format and aspect ratio
    try:
        stored_path = validate_and_store_background(file_bytes, storage)
    except ValueError as e:
        msg = str(e)
        if "Unsupported image format" in msg:
            raise UnsupportedFormatError(msg)
        elif "aspect ratio" in msg or "corrupted" in msg:
            raise InvalidTemplateError(msg)
        elif "exceeds maximum" in msg:
            raise FileSizeExceededError(msg)
        raise InvalidTemplateError(msg)

    template = Template(
        name=clean_name,
        kind="custom",
        key=None,
        background_path=stored_path,
        layout={
            "name_y": float(layout_data["name_y"]),
            "course_y": float(layout_data["course_y"]),
            "date_y": float(layout_data["date_y"]),
        },
        is_deleted=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return template
