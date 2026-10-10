import io
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.seed import seed_builtin_templates
from app import worker
from app.services.storage import LocalStorage
from app.api import templates, jobs, certificates


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "api_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    # Seed templates
    with TestingSessionLocal() as session:
        seed_builtin_templates(session)

    # Isolated test storage
    test_storage = LocalStorage(base_dir=str(tmp_path / "storage"))
    monkeypatch.setattr(templates, "storage", test_storage)
    monkeypatch.setattr(jobs, "storage", test_storage)
    monkeypatch.setattr(certificates, "storage", test_storage)
    monkeypatch.setattr(worker, "SessionLocal", TestingSessionLocal)
    monkeypatch.setenv("WORKER_MODE", "inline")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client, TestingSessionLocal

    app.dependency_overrides.clear()


def test_health_endpoint(client_and_db):
    client, _ = client_and_db
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_templates(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/v1/templates")
    assert res.status_code == 200
    templates_list = res.json()
    assert len(templates_list) >= 5
    keys = [t["key"] for t in templates_list if t["key"]]
    assert "classic" in keys


def test_template_preview(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/v1/templates")
    template_id = res.json()[0]["id"]

    preview_res = client.get(f"/api/v1/templates/{template_id}/preview")
    assert preview_res.status_code == 200
    assert preview_res.headers["content-type"] == "application/pdf"
    assert preview_res.content.startswith(b"%PDF-")


def test_custom_template_upload(client_and_db):
    client, _ = client_and_db

    # Create A4 landscape test image (1414 x 1000)
    img = Image.new("RGB", (1414, 1000), color="darkblue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": ("bg.png", buf, "image/png")}
    data = {
        "name": "Custom Tech Certificate",
        "name_y": "45.0",
        "course_y": "60.0",
        "date_y": "75.0",
    }

    res = client.post("/api/v1/templates/custom", data=data, files=files)
    assert res.status_code == 201
    tpl = res.json()
    assert tpl["kind"] == "custom"
    assert tpl["name"] == "Custom Tech Certificate"


def test_custom_template_upload_bad_aspect(client_and_db):
    client, _ = client_and_db
    # Square image (ratio 1.0)
    img = Image.new("RGB", (500, 500), color="darkblue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"image": ("bg.png", buf, "image/png")}
    data = {"name": "Bad Aspect", "name_y": "45.0", "course_y": "60.0", "date_y": "75.0"}

    res = client.post("/api/v1/templates/custom", data=data, files=files)
    assert res.status_code == 400
    err = res.json()["error"]
    assert err["code"] == "BAD_REQUEST"
    assert "aspect ratio" in err["message"]


def test_create_and_poll_job_flow(client_and_db):
    client, _ = client_and_db
    res = client.get("/api/v1/templates")
    template_id = res.json()[0]["id"]

    job_payload = {
        "title": "Machine Learning Specialization",
        "organization_name": "AI Institute",
        "issued_date": "2026-10-10",
        "template_id": template_id,
        "recipients": [
            {"name": "Grace Hopper", "email": "grace@example.com"},
            {"name": "Bad Recipient", "email": "invalid-email"},
            {"name": "Alan Turing", "email": "alan@example.com"},
        ],
    }

    create_res = client.post(
        "/api/v1/jobs",
        json=job_payload,
        headers={"Idempotency-Key": "test-idem-key-999"},
    )
    assert create_res.status_code == 202
    job_info = create_res.json()
    job_id = job_info["id"]

    # Poll progress
    prog_res = client.get(f"/api/v1/jobs/{job_id}")
    assert prog_res.status_code == 200
    prog = prog_res.json()
    assert prog["total"] == 3
    assert prog["succeeded"] == 2
    assert prog["failed"] == 1
    assert prog["status"] == "completed_with_errors"

    # List certificates
    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates")
    assert certs_res.status_code == 200
    certs_data = certs_res.json()
    assert certs_data["total"] == 3
    items = certs_data["items"]

    succeeded_cert = next(c for c in items if c["status"] == "succeeded")
    failed_cert = next(c for c in items if c["status"] == "failed")
    assert failed_cert["error_message"] is not None

    # Download single certificate
    dl_res = client.get(f"/api/v1/certificates/{succeeded_cert['id']}/download")
    assert dl_res.status_code == 200
    assert dl_res.content.startswith(b"%PDF-")

    # Download failed cert returns 404
    bad_dl = client.get(f"/api/v1/certificates/{failed_cert['id']}/download")
    assert bad_dl.status_code == 404

    # Download all as ZIP
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    assert len(zip_res.content) > 0
