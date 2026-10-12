import io
import uuid
from PIL import Image
import pytest

from app.services.storage import LocalStorage
from app.services.template_registry import BUILTIN_STYLE_CONFIGS
from app.services.template_upload import validate_and_store_background
from app.services.certificate_renderer import render_certificate, render_preview


@pytest.fixture
def temp_storage(tmp_path):
    return LocalStorage(base_dir=str(tmp_path / "storage"))


def test_storage_save_and_read(temp_storage):
    key = temp_storage.save("test/hello.txt", b"Hello World")
    assert temp_storage.exists("test/hello.txt")
    assert temp_storage.read("test/hello.txt") == b"Hello World"


def test_render_builtin_templates(temp_storage):
    """Verify built-in template rendering for PDF, PNG, and JPG formats."""
    for key in ("classic", "modern", "minimal", "elegant", "bold"):
        tpl_config = {
            "kind": "builtin",
            "key": key,
            "layout": BUILTIN_STYLE_CONFIGS[key]["layout"],
        }
        job_fields = {
            "title": "Quantum Computing 101",
            "issued_date": "2026-10-09",
            "organization_name": "Tech University",
        }

        # PDF format
        pdf_bytes = render_certificate(
            name="Alice Wonderland",
            template_snapshot=tpl_config,
            job_fields=job_fields,
            output_format="pdf",
            storage=temp_storage,
        )
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1000

        # PNG format
        png_bytes = render_certificate(
            name="Alice Wonderland",
            template_snapshot=tpl_config,
            job_fields=job_fields,
            output_format="png",
            storage=temp_storage,
        )
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

        # JPG format
        jpg_bytes = render_certificate(
            name="Alice Wonderland",
            template_snapshot=tpl_config,
            job_fields=job_fields,
            output_format="jpg",
            storage=temp_storage,
        )
        assert jpg_bytes.startswith(b"\xff\xd8")


def test_render_long_recipient_name_auto_shrink(temp_storage):
    tpl_config = {
        "kind": "builtin",
        "key": "modern",
        "layout": BUILTIN_STYLE_CONFIGS["modern"]["layout"],
    }
    very_long_name = "Dr. " + "Supercalifragilisticexpialidocious " * 5 + "The Third"
    job_fields = {
        "title": "Long Course Title " * 4,
        "issued_date": "2026-10-09",
        "organization_name": "Academy",
    }
    pdf_bytes = render_certificate(
        name=very_long_name,
        template_snapshot=tpl_config,
        job_fields=job_fields,
        output_format="pdf",
        storage=temp_storage,
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_validate_and_store_background_success(temp_storage):
    # Any aspect ratio should now succeed (A4 check removed)
    img = Image.new("RGB", (1000, 1000), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()

    tpl_id = uuid.uuid4()
    stored_path = validate_and_store_background(img_bytes, tpl_id, temp_storage)
    assert stored_path == f"backgrounds/{tpl_id}.png"
    assert temp_storage.exists(stored_path)


def test_validate_and_store_background_oversized(temp_storage):
    # 11 MB fake byte stream exceeds 10 MB limit
    huge_bytes = b"\x00" * (11 * 1024 * 1024)
    tpl_id = uuid.uuid4()
    with pytest.raises(ValueError, match="exceeds maximum allowed limit of 10 MB"):
        validate_and_store_background(huge_bytes, tpl_id, temp_storage)


def test_validate_and_store_background_unsupported_format(temp_storage):
    # Plain text file fails image decoding
    tpl_id = uuid.uuid4()
    with pytest.raises(ValueError, match="Invalid or corrupted image file"):
        validate_and_store_background(b"not an image file at all", tpl_id, temp_storage)
