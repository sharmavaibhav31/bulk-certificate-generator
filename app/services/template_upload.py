import io
import uuid
from PIL import Image
from app.services.storage import StorageInterface

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
A4_LANDSCAPE_ASPECT_RATIO = 841.89 / 595.27  # ~1.4142
ALLOWED_ASPECT_TOLERANCE = 0.10  # 10% tolerance


def validate_and_store_background(
    file_bytes: bytes, storage: StorageInterface
) -> str:
    """
    Validate an uploaded certificate background image and store it securely.

    Security & Validation Rules:
    1. Size Check: Must be <= 5 MB.
    2. Format Check: Must be PNG or JPEG.
    3. Aspect Ratio Check: Must be within 10% of A4 landscape (841.89 x 595.27 pt -> ~1.4142).
    4. Metadata Stripping: Re-saved without EXIF or embedded client metadata.
    5. Path Generation: Stored under a generated UUID filename, ignoring untrusted client filenames.

    Returns:
        str: Relative storage path (e.g. 'backgrounds/<uuid>.png')
    """
    if not file_bytes:
        raise ValueError("Uploaded image file is empty.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Image file size ({len(file_bytes) / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of 5 MB."
        )

    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # Verify image integrity
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

    # Re-open after verify() because verify() mutates image stream state
    img = Image.open(io.BytesIO(file_bytes))

    if img.format not in ("PNG", "JPEG"):
        raise ValueError(
            f"Unsupported image format '{img.format}'. Only PNG and JPEG formats are allowed."
        )

    width, height = img.size
    if height == 0:
        raise ValueError("Invalid image dimensions: height cannot be 0.")

    aspect_ratio = width / float(height)
    min_ratio = A4_LANDSCAPE_ASPECT_RATIO * (1.0 - ALLOWED_ASPECT_TOLERANCE)
    max_ratio = A4_LANDSCAPE_ASPECT_RATIO * (1.0 + ALLOWED_ASPECT_TOLERANCE)

    if not (min_ratio <= aspect_ratio <= max_ratio):
        raise ValueError(
            f"Image aspect ratio ({aspect_ratio:.3f}) must be within 10% of A4 landscape ({A4_LANDSCAPE_ASPECT_RATIO:.3f}). Allowed range: [{min_ratio:.3f}, {max_ratio:.3f}]."
        )

    # Convert image to RGB/RGBA and strip metadata by saving clean pixel buffer
    output_buffer = io.BytesIO()

    if img.format == "JPEG":
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(output_buffer, format="JPEG", quality=95)
        ext = "jpg"
    else:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.save(output_buffer, format="PNG", optimize=True)
        ext = "png"

    clean_bytes = output_buffer.getvalue()
    filename = f"backgrounds/{uuid.uuid4()}.{ext}"

    stored_path = storage.save(filename, clean_bytes)
    return stored_path
