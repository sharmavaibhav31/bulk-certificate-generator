import io
import uuid
from PIL import Image
import pytest

from app.services.certificate_renderer import render_certificate, render_preview
from app.services.template_registry import BUILTIN_STYLE_CONFIGS


def test_render_all_builtin_and_custom_templates(temp_storage):
    """
    Assert valid PDF bytes generated for all 5 builtin templates
    and a custom template with a generated background image.
    """
    # 1. Test each builtin template
    for key in ("classic", "modern", "minimal", "elegant", "bold"):
        tpl_config = {
            "kind": "builtin",
            "key": key,
            "layout": BUILTIN_STYLE_CONFIGS[key]["layout"],
        }
        job_fields = {
            "title": "Radiation Physics & Chemistry",
            "issued_date": "2026-10-10",
            "organization_name": "Sorbonne University",
        }
        pdf_bytes = render_certificate(
            name="Marie Curie",
            template_snapshot=tpl_config,
            job_fields=job_fields,
            output_format="pdf",
            storage=temp_storage,
        )
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1000

    # 2. Test custom template with generated background image
    img = Image.new("RGB", (1200, 800), color="darkgreen")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    tpl_id = uuid.uuid4()
    stored_bg_path = temp_storage.save(f"backgrounds/{tpl_id}.png", img_buf.getvalue())

    custom_tpl = {
        "kind": "custom",
        "background_path": stored_bg_path,
        "layout": {
            "name_x": 50.0,
            "name_y": 57.0,
            "font": "dejavu_sans",
            "font_size_pct": 5.0,
            "color": "#1A202C",
            "max_width_pct": 70.0,
        },
    }
    custom_pdf_bytes = render_certificate(
        name="Ada Lovelace",
        template_snapshot=custom_tpl,
        job_fields={},
        output_format="pdf",
        storage=temp_storage,
    )
    assert custom_pdf_bytes.startswith(b"%PDF")
    assert len(custom_pdf_bytes) > 1000


def test_custom_template_upload_and_preview_flow(client):
    """
    Test custom template upload validation and live PNG preview:
    - Rejects non-image format (415 or 400)
    - Rejects oversized file > 10MB (413)
    - Accepts valid image regardless of aspect ratio (201)
    - Returns live PNG preview for template
    """
    base_data = {
        "name": "Custom Corporate Frame",
        "name_x": "50.0",
        "name_y": "57.0",
        "font": "dejavu_sans",
        "font_size_pct": "5.0",
        "color": "#1A202C",
        "max_width_pct": "70.0",
    }

    # 1. Non-image file -> 415 or 400
    fake_txt = io.BytesIO(b"Hello this is not an image file")
    res_non_img = client.post(
        "/api/v1/templates/custom",
        data=base_data,
        files={"image": ("fake.txt", fake_txt, "text/plain")},
    )
    assert res_non_img.status_code in (400, 415)

    # 2. Oversized file > 10 MB -> 413 Request Entity Too Large
    huge_bytes = io.BytesIO(b"\x00" * (11 * 1024 * 1024))
    res_oversized = client.post(
        "/api/v1/templates/custom",
        data=base_data,
        files={"image": ("huge.png", huge_bytes, "image/png")},
    )
    assert res_oversized.status_code == 413
    assert "exceeds maximum allowed limit" in res_oversized.json()["error"]["message"]

    # 3. Square image (500x500) -> 201 Created (no aspect ratio restriction)
    valid_img = Image.new("RGB", (800, 600), color="navy")
    valid_buf = io.BytesIO()
    valid_img.save(valid_buf, format="PNG")
    valid_buf.seek(0)

    res_valid = client.post(
        "/api/v1/templates/custom",
        data=base_data,
        files={"image": ("custom_frame.png", valid_buf, "image/png")},
    )
    assert res_valid.status_code == 201
    tpl_out = res_valid.json()
    assert tpl_out["kind"] == "custom"
    assert tpl_out["name"] == "Custom Corporate Frame"
    assert tpl_out["required_fields"] == ["name"]
    assert tpl_out["background_path"].startswith("backgrounds/")
    assert tpl_out["background_path"].endswith(".png")

    template_id = tpl_out["id"]

    # 4. Live PNG preview
    preview_res = client.get(f"/api/v1/templates/{template_id}/preview?name=Jane+Doe")
    assert preview_res.status_code == 200
    assert preview_res.headers["content-type"] == "image/png"
    assert preview_res.content.startswith(b"\x89PNG\r\n\x1a\n")
