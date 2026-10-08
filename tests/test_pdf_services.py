import io
from PIL import Image
import pytest

from app.services.storage import LocalStorage
from app.services.template_registry import BUILTIN_STYLE_CONFIGS, get_template_config
from app.services.template_upload import validate_and_store_background
from app.services.pdf_generator import render_certificate, render_preview


@pytest.fixture
def temp_storage(tmp_path):
    return LocalStorage(base_dir=str(tmp_path / "storage"))


def test_storage_save_and_read(temp_storage):
    key = temp_storage.save("test/hello.txt", b"Hello World")
    assert temp_storage.exists("test/hello.txt")
    assert temp_storage.read("test/hello.txt") == b"Hello World"


def test_render_builtin_templates():
    for key in ("classic", "modern", "minimal", "elegant", "bold"):
        tpl_config = {
            "kind": "builtin",
            "key": key,
            "layout": BUILTIN_STYLE_CONFIGS[key]["layout"],
        }
        pdf_bytes = render_certificate(
            recipient_name="Alice Wonderland",
            course_title="Quantum Computing 101",
            issued_date="2026-10-09",
            organization_name="Tech University",
            template=tpl_config,
        )
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000


def test_render_long_recipient_name_auto_shrink():
    tpl_config = {
        "kind": "builtin",
        "key": "modern",
        "layout": {"name_y": 42.0, "course_y": 60.0, "date_y": 76.0},
    }
    very_long_name = "Dr. " + "Supercalifragilisticexpialidocious " * 5 + "The Third"
    pdf_bytes = render_certificate(
        recipient_name=very_long_name,
        course_title="Long Course Title " * 4,
        issued_date="2026-10-09",
        organization_name="Academy",
        template=tpl_config,
    )
    assert pdf_bytes.startswith(b"%PDF-")


def test_validate_and_store_background_success(temp_storage):
    # Create an image matching A4 landscape aspect ratio (1414 x 1000 px -> ratio ~1.414)
    img = Image.new("RGB", (1414, 1000), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()

    stored_path = validate_and_store_background(img_bytes, temp_storage)
    assert stored_path.startswith("backgrounds/")
    assert temp_storage.exists(stored_path)


def test_validate_and_store_background_bad_aspect(temp_storage):
    # Square image (ratio 1.0) fails aspect ratio check
    img = Image.new("RGB", (500, 500), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()

    with pytest.raises(ValueError, match="aspect ratio"):
        validate_and_store_background(img_bytes, temp_storage)


def test_validate_and_store_background_oversized(temp_storage):
    # 6 MB fake byte stream
    huge_bytes = b"\x00" * (6 * 1024 * 1024)
    with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
        validate_and_store_background(huge_bytes, temp_storage)
