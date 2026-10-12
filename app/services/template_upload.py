"""
Template Upload Validation: Enforces security constraints on uploaded certificate backgrounds.
"""

import io
from uuid import UUID
from PIL import Image
from app.services.storage import StorageInterface

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
MAX_TOTAL_PIXELS = 25_000_000           # 25 Megapixels limit


def validate_and_store_background(
    file_bytes: bytes,
    template_id: UUID,
    storage: StorageInterface,
) -> str:
    """
    Validate uploaded certificate background image and store it at its original resolution as a lossless PNG.

    Security & Validation Rules:
    1. Size Check: Must be <= 10 MB.
    2. Format Check: Must be PNG or JPEG.
    3. Dimension Check: Total pixels (width * height) must be < 25 million to prevent memory exhaustion (decompression bombs).
    4. No Aspect Ratio Enforcement: Any aspect ratio is accepted at original resolution (no resizing).
    5. Clean Lossless Re-save: Re-encoded as a clean PNG without client EXIF or metadata.
    6. Filename: Named by template_id (backgrounds/{template_id}.png) - client filename is completely ignored.

    Returns:
        str: Relative storage path (e.g. 'backgrounds/<template_id>.png')
    """
    if not file_bytes:
        raise ValueError("Uploaded image file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Image file size ({len(file_bytes) / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of 10 MB."
        )

    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

    # Re-open after verify() because verify() exhausts image stream
    img = Image.open(io.BytesIO(file_bytes))

    if img.format not in ("PNG", "JPEG"):
        raise ValueError(
            f"Unsupported image format '{img.format}'. Only PNG and JPEG formats are allowed."
        )

    width, height = img.size
    total_pixels = width * height
    if total_pixels > MAX_TOTAL_PIXELS:
        raise ValueError(
            f"Image resolution ({width}x{height} = {total_pixels:,} pixels) exceeds maximum allowed limit of 25 million pixels."
        )

    # Convert to RGB or RGBA for lossless PNG storage
    output_buffer = io.BytesIO()
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    # Save as lossless PNG at original resolution, stripping EXIF/client metadata
    img.save(output_buffer, format="PNG", optimize=True)
    clean_bytes = output_buffer.getvalue()

    filename = f"backgrounds/{str(template_id)}.png"
    stored_path = storage.save(filename, clean_bytes)
    return stored_path
