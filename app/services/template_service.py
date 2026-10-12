"""
Template Service: Business logic for retrieving and uploading certificate templates.
"""

from typing import List, Optional, Dict, Any
import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Template
from app.services.storage import StorageInterface, LocalStorage
from app.services.template_upload import validate_and_store_background, MAX_FILE_SIZE_BYTES
from app.services.font_registry import ALLOWED_FONT_KEYS, DEFAULT_FONT_KEY


class TemplateServiceError(Exception):
    """Base exception for template service operations."""
    pass


class FileSizeExceededError(TemplateServiceError):
    """Raised when uploaded file exceeds 10MB limit (maps to HTTP 413)."""
    pass


class UnsupportedFormatError(TemplateServiceError):
    """Raised when file format is not PNG or JPEG (maps to HTTP 415)."""
    pass


class InvalidTemplateError(TemplateServiceError):
    """Raised when template coordinates, font, or image dimensions are invalid (maps to HTTP 400)."""
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
    Validate uploaded background, persist it at original resolution as lossless PNG named by template_id,
    and insert custom template record into the database with required_fields=['name'].
    """
    if storage is None:
        storage = LocalStorage()

    clean_name = (name or "").strip()
    if not clean_name:
        raise InvalidTemplateError("Template name cannot be empty.")

    # 1. Parse and validate layout values
    try:
        name_x = float(layout_data.get("name_x", 50.0))
        name_y = float(layout_data.get("name_y", 57.0))
        font_size_pct = float(layout_data.get("font_size_pct", 5.0))
        max_width_pct = float(layout_data.get("max_width_pct", 70.0))
    except (ValueError, TypeError) as e:
        raise InvalidTemplateError(f"Layout percentage fields must be numbers: {str(e)}")

    if not (0.0 <= name_x <= 100.0) or not (0.0 <= name_y <= 100.0):
        raise InvalidTemplateError("name_x and name_y must be percentages between 0 and 100.")

    if not (0.5 <= font_size_pct <= 50.0):
        raise InvalidTemplateError("font_size_pct must be between 0.5 and 50 percent of image height.")

    if not (10.0 <= max_width_pct <= 100.0):
        raise InvalidTemplateError("max_width_pct must be between 10 and 100 percent of image width.")

    font_key = str(layout_data.get("font", DEFAULT_FONT_KEY)).strip().lower()
    if font_key not in ALLOWED_FONT_KEYS:
        font_key = DEFAULT_FONT_KEY

    color = str(layout_data.get("color", "#1A202C")).strip()
    if not color.startswith("#"):
        color = f"#{color}"

    # 2. Validate file size (10 MB)
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise FileSizeExceededError(
            f"File size ({len(file_bytes) / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of 10 MB."
        )

    # 3. Generate template ID and validate/store image at original resolution
    template_id = uuid.uuid4()
    try:
        stored_path = validate_and_store_background(file_bytes, template_id, storage)
    except ValueError as e:
        msg = str(e)
        if "Unsupported image format" in msg:
            raise UnsupportedFormatError(msg)
        elif "exceeds maximum allowed limit of 10 MB" in msg:
            raise FileSizeExceededError(msg)
        raise InvalidTemplateError(msg)

    # 4. Insert into database
    layout_config = {
        "name_x": name_x,
        "name_y": name_y,
        "font": font_key,
        "font_size_pct": font_size_pct,
        "color": color,
        "max_width_pct": max_width_pct,
    }

    template = Template(
        id=template_id,
        name=clean_name,
        kind="custom",
        key=None,
        background_path=stored_path,
        layout=layout_config,
        required_fields=["name"],
        is_deleted=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return template
