import io
from PIL import Image
import pytest

from app.services.pdf_generator import render_certificate
from app.services.template_registry import BUILTIN_STYLE_CONFIGS


def test_render_all_builtin_and_custom_templates(temp_storage):
    """
    Assert valid PDF bytes (starting with %PDF-) generated for all 5 builtin templates
    and a custom template with generated background image.
    """
    # 1. Test each builtin template
    for key in ("classic", "modern", "minimal", "elegant", "bold"):
        tpl_config = {
            "kind": "builtin",
            "key": key,
            "layout": BUILTIN_STYLE_CONFIGS[key]["layout"],
        }
        pdf_bytes = render_certificate(
            recipient_name="Marie Curie",
            course_title="Radiation Physics & Chemistry",
            issued_date="2026-10-10",
            organization_name="Sorbonne University",
            template=tpl_config,
            storage=temp_storage,
        )
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000

    # 2. Test custom template with generated background image
    # Generate A4 landscape test image (1414 x 1000)
    img = Image.new("RGB", (1414, 1000), color="darkgreen")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    stored_bg_path = temp_storage.save("backgrounds/test_bg.png", img_buf.getvalue())

    custom_tpl = {
        "kind": "custom",
        "background_path": stored_bg_path,
        "layout": {"name_y": 40.0, "course_y": 55.0, "date_y": 70.0},
    }
    custom_pdf_bytes = render_certificate(
        recipient_name="Ada Lovelace",
        course_title="Analytical Computing",
        issued_date="2026-10-10",
        organization_name="University of Cambridge",
        template=custom_tpl,
        storage=temp_storage,
    )
    assert custom_pdf_bytes.startswith(b"%PDF-")
    assert len(custom_pdf_bytes) > 1000


def test_custom_template_upload_rules(client):
    """
    Test custom template upload validation:
    - Rejects non-image / unsupported format (415)
    - Rejects oversized file > 5MB (413)
    - Rejects non-A4 aspect ratio (400)
    - Accepts valid PNG and re-saves with metadata stripped (201)
    """
    base_data = {
        "name": "Custom Corporate Frame",
        "name_y": "45.0",
        "course_y": "60.0",
        "date_y": "75.0",
    }

    # 1. Non-image file (e.g. text file masquerading as image) -> 415 or 400
    fake_txt = io.BytesIO(b"Hello this is not an image file")
    res_non_img = client.post(
        "/api/v1/templates/custom",
        data=base_data,
        files={"image": ("fake.txt", fake_txt, "text/plain")},
    )
    assert res_non_img.status_code in (400, 415)

    # 2. Oversized file > 5 MB -> 413 Request Entity Too Large
    huge_bytes = io.BytesIO(b"\x00" * (6 * 1024 * 1024))
    res_oversized = client.post(
        "/api/v1/templates/custom",
        data=base_data,
        files={"image": ("huge.png", huge_bytes, "image/png")},
    )
    assert res_oversized.status_code == 413
    assert "exceeds maximum allowed limit" in res_oversized.json()["error"]["message"]

    # 3. Wrong aspect ratio (Square 500x500 instead of A4 ~1.414) -> 400 Bad Request
    square_img = Image.new("RGB", (500, 500), color="blue")
    sq_buf = io.BytesIO()
    square_img.save(sq_buf, format="PNG")
    sq_buf.seek(0)

    res_bad_aspect = client.post(
        "/api/v1/templates/custom",
        data=base_data,
        files={"image": ("square.png", sq_buf, "image/png")},
    )
    assert res_bad_aspect.status_code == 400
    assert "aspect ratio" in res_bad_aspect.json()["error"]["message"]

    # 4. Valid A4 landscape PNG (1414 x 1000) -> 201 Created
    valid_img = Image.new("RGB", (1414, 1000), color="navy")
    valid_buf = io.BytesIO()
    valid_img.save(valid_buf, format="PNG")
    valid_buf.seek(0)

    res_valid = client.post(
        "/api/v1/templates/custom",
        data=base_data,
        files={"image": ("valid_a4.png", valid_buf, "image/png")},
    )
    assert res_valid.status_code == 201
    tpl_out = res_valid.json()
    assert tpl_out["kind"] == "custom"
    assert tpl_out["name"] == "Custom Corporate Frame"
    assert tpl_out["background_path"].startswith("backgrounds/")
    assert tpl_out["background_path"].endswith(".png")
