from datetime import date
import io
import uuid
import zipfile
from PIL import Image
import pytest

from app.models import Job, Certificate, CertificateStatus, Template
from app.services.job_service import sanitize_file_name, get_progress
from app.services.certificate_renderer import render_certificate
from app.services.template_registry import BUILTIN_STYLE_CONFIGS
from app import worker


def test_1_custom_template_keeps_upload(client, temp_storage):
    """
    1. Custom template keeps the upload:
    Create a test background image with a distinctive colored rectangle in a known position,
    upload it as a custom template, generate a certificate as PNG, and assert the output has
    the same dimensions and that the pixel color at the known position still matches
    (proves it did not become a blank template).
    """
    W, H = 1000, 600
    # Background in soft blue
    bg_img = Image.new("RGB", (W, H), color=(200, 220, 240))
    # Stamp a distinctive purple rectangle at known coords: [60, 60, 200, 200]
    for x in range(60, 200):
        for y in range(60, 200):
            bg_img.putpixel((x, y), (255, 0, 255))

    buf = io.BytesIO()
    bg_img.save(buf, format="PNG")
    buf.seek(0)

    # Upload custom template
    res = client.post(
        "/api/v1/templates/custom",
        data={
            "name": "Distinctive Background Template",
            "name_x": "50.0",
            "name_y": "57.0",
            "font": "dejavu_sans",
            "font_size_pct": "5.0",
            "color": "#1A202C",
            "max_width_pct": "70.0",
        },
        files={"image": ("bg.png", buf, "image/png")},
    )
    assert res.status_code == 201
    tpl_data = res.json()
    template_id = tpl_data["id"]

    # Submit job generating as PNG
    job_payload = {
        "template_id": template_id,
        "output_format": "png",
        "recipients": [{"name": "Arthur Dent"}],
    }
    job_res = client.post("/api/v1/jobs", json=job_payload)
    assert job_res.status_code == 202
    job_id = job_res.json()["id"]

    # Fetch generated certificate
    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates")
    cert = certs_res.json()["items"][0]
    assert cert["status"] == "succeeded"

    dl_res = client.get(f"/api/v1/certificates/{cert['id']}/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "image/png"

    # Open rendered output image
    rendered_img = Image.open(io.BytesIO(dl_res.content))
    # Dimensions match original uploaded image
    assert rendered_img.size == (W, H)
    # Distinctive colored rectangle pixel at (100, 100) is preserved exactly
    assert rendered_img.getpixel((100, 100))[:3] == (255, 0, 255)


def test_2_name_is_drawn(client, temp_storage):
    """
    2. The name is drawn:
    Compare the region around (name_x, name_y) between the background and the output
    and assert it changed.
    """
    W, H = 1000, 600
    bg_color = (255, 255, 255)
    bg_img = Image.new("RGB", (W, H), color=bg_color)
    buf = io.BytesIO()
    bg_img.save(buf, format="PNG")
    buf.seek(0)

    # Upload template with name at center (50%, 57%)
    res = client.post(
        "/api/v1/templates/custom",
        data={
            "name": "Text Difference Test",
            "name_x": "50.0",
            "name_y": "57.0",
            "font": "dejavu_sans",
            "font_size_pct": "6.0",
            "color": "#000000",
            "max_width_pct": "70.0",
        },
        files={"image": ("bg.png", buf, "image/png")},
    )
    tpl_id = res.json()["id"]

    recipient_name = "Major Tom"
    job_res = client.post(
        "/api/v1/jobs",
        json={
            "template_id": tpl_id,
            "output_format": "png",
            "recipients": [{"name": recipient_name}],
        },
    )
    job_id = job_res.json()["id"]

    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates")
    cert_id = certs_res.json()["items"][0]["id"]
    dl_res = client.get(f"/api/v1/certificates/{cert_id}/download")

    rendered_img = Image.open(io.BytesIO(dl_res.content)).convert("RGB")

    # Name center is at (500, 342). Crop a bounding region around the name.
    target_box = (400, 320, 600, 365)
    bg_crop = bg_img.crop(target_box)
    rendered_crop = rendered_img.crop(target_box)

    # Assert pixels in the name region changed
    assert list(bg_crop.getdata()) != list(rendered_crop.getdata())

    # Assert that non-white (black text) pixels exist in the rendered name crop
    rendered_pixels = list(rendered_crop.getdata())
    black_pixels = [p for p in rendered_pixels if p != (255, 255, 255)]
    assert len(black_pixels) > 50


def test_3_required_fields_validation(client):
    """
    3. Required fields:
    - Custom template job without title or date is accepted (202).
    - Builtin template job without title is rejected with 422.
    - Recipient without email is accepted and succeeds.
    - Recipient with malformed email is stored as failed.
    """
    # 1. Custom template accepts job without title or date
    custom_img = Image.new("RGB", (800, 600), color="white")
    buf = io.BytesIO()
    custom_img.save(buf, format="PNG")
    buf.seek(0)
    tpl_res = client.post(
        "/api/v1/templates/custom",
        data={"name": "Optional Fields Custom Template"},
        files={"image": ("bg.png", buf, "image/png")},
    )
    custom_tpl_id = tpl_res.json()["id"]

    # Job without title and without date -> Accepted (202)
    job_custom_res = client.post(
        "/api/v1/jobs",
        json={
            "template_id": custom_tpl_id,
            "recipients": [{"name": "User Without Email"}],
        },
    )
    assert job_custom_res.status_code == 202
    job_custom_id = job_custom_res.json()["id"]

    prog = client.get(f"/api/v1/jobs/{job_custom_id}").json()
    assert prog["total"] == 1
    assert prog["succeeded"] == 1
    assert prog["failed"] == 0

    # 2. Builtin template without title -> Rejected with 422
    builtin_tpl = client.get("/api/v1/templates").json()[0]
    job_builtin_no_title = client.post(
        "/api/v1/jobs",
        json={
            "template_id": builtin_tpl["id"],
            "issued_date": "2026-10-12",
            "recipients": [{"name": "User One"}],
        },
    )
    assert job_builtin_no_title.status_code == 422

    # 3. Recipient with malformed email -> Stored as failed with error reason
    job_bad_email_res = client.post(
        "/api/v1/jobs",
        json={
            "template_id": custom_tpl_id,
            "recipients": [
                {"name": "Valid Recipient", "email": "valid@example.com"},
                {"name": "Bad Email Recipient", "email": "not-an-email"},
            ],
        },
    )
    assert job_bad_email_res.status_code == 202
    job_bad_email_id = job_bad_email_res.json()["id"]

    prog_bad = client.get(f"/api/v1/jobs/{job_bad_email_id}").json()
    assert prog_bad["total"] == 2
    assert prog_bad["succeeded"] == 1
    assert prog_bad["failed"] == 1
    assert len(prog_bad["failed_recipients"]) == 1
    assert "Invalid email format" in prog_bad["failed_recipients"][0]["error_message"]


def test_4_output_formats_signatures(temp_storage):
    """
    4. Output formats:
    - pdf starts with %PDF
    - png starts with PNG signature (\x89PNG\r\n\x1a\n)
    - jpg starts with FFD8 (\xff\xd8)
    For both builtin and custom templates.
    """
    # 1. Custom template setup
    custom_bg = Image.new("RGB", (1000, 700), color="darkgreen")
    c_buf = io.BytesIO()
    custom_bg.save(c_buf, format="PNG")
    tpl_id = uuid.uuid4()
    bg_path = temp_storage.save(f"backgrounds/{tpl_id}.png", c_buf.getvalue())
    custom_snapshot = {
        "kind": "custom",
        "background_path": bg_path,
        "layout": {"name_x": 50.0, "name_y": 50.0, "font": "dejavu_sans", "font_size_pct": 5.0, "color": "#FFFFFF", "max_width_pct": 70.0},
    }

    # 2. Builtin template setup
    builtin_snapshot = {
        "kind": "builtin",
        "key": "classic",
        "layout": BUILTIN_STYLE_CONFIGS["classic"]["layout"],
    }
    job_fields = {"title": "Certificate", "issued_date": "2026-10-12", "organization_name": "Org"}

    for snapshot in (builtin_snapshot, custom_snapshot):
        # PDF
        pdf_bytes = render_certificate(
            name="Format Tester",
            template_snapshot=snapshot,
            job_fields=job_fields,
            output_format="pdf",
            storage=temp_storage,
        )
        assert pdf_bytes.startswith(b"%PDF")

        # PNG
        png_bytes = render_certificate(
            name="Format Tester",
            template_snapshot=snapshot,
            job_fields=job_fields,
            output_format="png",
            storage=temp_storage,
        )
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

        # JPG
        jpg_bytes = render_certificate(
            name="Format Tester",
            template_snapshot=snapshot,
            job_fields=job_fields,
            output_format="jpg",
            storage=temp_storage,
        )
        assert jpg_bytes.startswith(b"\xff\xd8")


def test_5_filename_sanitization_and_deduplication():
    """
    5. File names:
    - sanitization (slashes, quotes, reserved names, empty name, very long name, unicode)
    - duplicate names become "Name.pdf", "Name (2).pdf", "Name (3).pdf"
    """
    seen_counts = {}

    # Slashes and quotes
    fn1 = sanitize_file_name('John/Doe\\Smith "Quote"?', "pdf", seen_counts)
    assert "/" not in fn1 and "\\" not in fn1 and '"' not in fn1 and "?" not in fn1
    assert fn1 == "JohnDoeSmith_Quote.pdf"

    # Reserved Windows device names
    fn_con = sanitize_file_name("CON", "pdf", seen_counts)
    assert fn_con == "certificate.pdf"
    fn_prn = sanitize_file_name("PRN", "pdf", seen_counts)
    assert fn_prn == "certificate (2).pdf"

    # Empty name
    fn_empty = sanitize_file_name("   ", "pdf", seen_counts)
    assert fn_empty == "certificate (3).pdf"

    # Very long name (> 100 chars)
    long_name = "A" * 150
    fn_long = sanitize_file_name(long_name, "pdf", seen_counts)
    base_part = fn_long.split(".")[0]
    assert len(base_part) <= 100

    # Unicode names
    fn_unicode = sanitize_file_name("Renée Müller", "pdf", seen_counts)
    assert "Renée_Müller" in fn_unicode

    # Duplicate in-job names
    dup_counts = {}
    d1 = sanitize_file_name("Jane Doe", "pdf", dup_counts)
    d2 = sanitize_file_name("Jane Doe", "pdf", dup_counts)
    d3 = sanitize_file_name("Jane Doe", "pdf", dup_counts)
    assert d1 == "Jane_Doe.pdf"
    assert d2 == "Jane_Doe (2).pdf"
    assert d3 == "Jane_Doe (3).pdf"


def test_6_zip_download_contents(client):
    """
    6. ZIP:
    - contains only succeeded certificates
    - entries use the friendly names
    - count matches
    - header attachment named after job title
    """
    tpl = client.get("/api/v1/templates").json()[0]

    payload = {
        "title": "Quantum Computing Essentials",
        "issued_date": "2026-10-12",
        "template_id": tpl["id"],
        "recipients": [
            {"name": "Alice Wonderland", "email": "alice@example.com"},
            {"name": "Alice Wonderland", "email": "alice2@example.com"},  # Duplicate name
            {"name": "Bad Email Recipient", "email": "malformed_email"},   # Failed
        ],
    }

    res = client.post("/api/v1/jobs", json=payload)
    assert res.status_code == 202
    job_id = res.json()["id"]

    # Poll status: 2 succeeded, 1 failed
    prog = client.get(f"/api/v1/jobs/{job_id}").json()
    assert prog["succeeded"] == 2
    assert prog["failed"] == 1

    # Download ZIP
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    assert 'filename="Quantum_Computing_Essentials.zip"' in zip_res.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        namelist = zf.namelist()
        assert len(namelist) == 2
        assert "Alice_Wonderland.pdf" in namelist
        assert "Alice_Wonderland (2).pdf" in namelist
        assert not any("Bad" in name for name in namelist)


def test_7_missing_background_fails_cleanly(client, temp_storage):
    """
    7. Missing background:
    Delete the background file after upload, run a job, and assert certificates
    are marked failed with an error (no blank output).
    """
    # 1. Upload custom template
    img = Image.new("RGB", (800, 600), color="navy")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    upload_res = client.post(
        "/api/v1/templates/custom",
        data={"name": "Template With Disappearing Background"},
        files={"image": ("bg.png", buf, "image/png")},
    )
    tpl_data = upload_res.json()
    tpl_id = tpl_data["id"]
    bg_path = tpl_data["background_path"]

    # 2. Delete the background file from storage backend
    assert temp_storage.exists(bg_path)
    temp_storage.delete(bg_path)
    assert not temp_storage.exists(bg_path)

    # 3. Submit and process job
    job_res = client.post(
        "/api/v1/jobs",
        json={
            "template_id": tpl_id,
            "recipients": [{"name": "Ghost Certificate Recipient"}],
        },
    )
    assert job_res.status_code == 202
    job_id = job_res.json()["id"]

    prog = client.get(f"/api/v1/jobs/{job_id}").json()
    assert prog["total"] == 1
    assert prog["succeeded"] == 0
    assert prog["failed"] == 1
    assert prog["status"] == "failed"

    # Verify failure reason is recorded explicitly
    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates")
    cert = certs_res.json()["items"][0]
    assert cert["status"] == "failed"
    assert "not found" in cert["error_message"].lower()
    # Confirm no certificate file was saved
    assert cert["file_path"] is None


def test_8_individual_failure_isolates(client, monkeypatch):
    """
    8. Individual failure still isolates:
    Patch the renderer to fail for one name, job ends completed_with_errors, others succeed.
    """
    orig_render = worker.render_certificate

    def faulty_render(name, *args, **kwargs):
        if name == "Crashing Recipient":
            raise RuntimeError("Renderer crash on specific glyph!")
        return orig_render(name, *args, **kwargs)

    monkeypatch.setattr(worker, "render_certificate", faulty_render)

    tpl = client.get("/api/v1/templates").json()[0]
    res = client.post(
        "/api/v1/jobs",
        json={
            "template_id": tpl["id"],
            "title": "Robustness Testing",
            "issued_date": "2026-10-12",
            "recipients": [
                {"name": "Solid User One"},
                {"name": "Crashing Recipient"},
                {"name": "Solid User Two"},
            ],
        },
    )
    job_id = res.json()["id"]

    prog = client.get(f"/api/v1/jobs/{job_id}").json()
    assert prog["total"] == 3
    assert prog["succeeded"] == 2
    assert prog["failed"] == 1
    assert prog["status"] == "completed_with_errors"

    certs = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]
    crashed = next(c for c in certs if c["recipient_name"] == "Crashing Recipient")
    assert crashed["status"] == "failed"
    assert "Renderer crash on specific glyph!" in crashed["error_message"]


def test_9_template_snapshot_immutability(test_db_session_factory, temp_storage, monkeypatch):
    """
    9. Snapshot:
    Change the template layout after creating a job and assert the running job
    still uses the old layout.
    """
    monkeypatch.setenv("WORKER_MODE", "inline")
    monkeypatch.setattr(worker, "SessionLocal", test_db_session_factory)
    monkeypatch.setattr(worker, "default_storage", temp_storage)

    with test_db_session_factory() as db:
        # Create a custom template
        img = Image.new("RGB", (800, 600), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        bg_path = temp_storage.save("backgrounds/snapshot_test.png", buf.getvalue())

        original_layout = {
            "name_x": 50.0,
            "name_y": 57.0,
            "font": "dejavu_sans",
            "font_size_pct": 5.0,
            "color": "#1A202C",
            "max_width_pct": 70.0,
        }
        tpl = Template(
            id=uuid.uuid4(),
            name="Snapshot Template",
            kind="custom",
            background_path=bg_path,
            layout=original_layout,
            required_fields=["name"],
        )
        db.add(tpl)
        db.commit()

        # Create job
        from app.services.job_service import create_job
        from app.schemas import JobCreate, RecipientIn

        payload = JobCreate(
            template_id=tpl.id,
            output_format="png",
            recipients=[RecipientIn(name="Immutable Student")],
        )
        job, _ = create_job(db, payload)
        job_id = job.id

        # Mutate the template in the database
        tpl.layout = {
            "name_x": 10.0,
            "name_y": 99.0,
            "font": "liberation_serif",
            "font_size_pct": 14.0,
            "color": "#FF0000",
            "max_width_pct": 30.0,
        }
        db.commit()

        # Run worker on the job
        worker.process_job(job_id, storage=temp_storage)

        # Assert job's frozen snapshot still preserves the original values
        db.expire_all()
        reloaded_job = db.query(Job).filter(Job.id == job_id).first()
        assert reloaded_job.layout_snapshot["layout"]["name_y"] == 57.0
        assert reloaded_job.layout_snapshot["layout"]["font"] == "dejavu_sans"
        assert reloaded_job.layout_snapshot["layout"]["color"] == "#1A202C"

        # Assert certificate succeeded
        cert = db.query(Certificate).filter(Certificate.job_id == job_id).first()
        assert cert.status == CertificateStatus.SUCCEEDED
        assert temp_storage.exists(cert.file_path)
