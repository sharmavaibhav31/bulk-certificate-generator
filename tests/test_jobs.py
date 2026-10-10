from datetime import date, datetime, timezone
import io
import uuid
import zipfile
import pytest

from app.models import Job, Certificate, CertificateStatus, Template
from app.services.job_service import get_progress
from app.schemas import DerivedJobStatus
from app import worker
from app.worker import recover_stuck_certificates


def test_create_job_and_idempotency(client):
    # 1. Fetch template ID
    tpl_res = client.get("/api/v1/templates")
    assert tpl_res.status_code == 200
    template_id = tpl_res.json()[0]["id"]

    idem_key = f"idem-key-{uuid.uuid4()}"
    payload = {
        "title": "Full-Stack Web Development",
        "organization_name": "Tech Institute",
        "issued_date": "2026-10-10",
        "template_id": template_id,
        "recipients": [
            {"name": "Alice Cooper", "email": "alice@example.com"},
            {"name": "Bob Dylan", "email": "bob@example.com"},
        ],
    }

    # First submission: returns 202 Accepted
    res1 = client.post("/api/v1/jobs", json=payload, headers={"Idempotency-Key": idem_key})
    assert res1.status_code == 202
    data1 = res1.json()
    assert "id" in data1
    assert data1["status"] == "queued"
    assert data1["status_url"] == f"/api/v1/jobs/{data1['id']}"

    # Repeated submission with identical Idempotency-Key returns same job
    res2 = client.post("/api/v1/jobs", json=payload, headers={"Idempotency-Key": idem_key})
    assert res2.status_code == 202
    data2 = res2.json()
    assert data1["id"] == data2["id"]


def test_job_request_validation(client):
    tpl_res = client.get("/api/v1/templates")
    template_id = tpl_res.json()[0]["id"]

    base_payload = {
        "title": "Machine Learning",
        "issued_date": "2026-10-10",
        "template_id": template_id,
    }

    # 1. Missing recipients field -> 422
    res_missing = client.post("/api/v1/jobs", json=base_payload)
    assert res_missing.status_code == 422

    # 2. Empty recipients list -> 422 (min_length=1)
    res_empty = client.post("/api/v1/jobs", json={**base_payload, "recipients": []})
    assert res_empty.status_code == 422

    # 3. Unknown template ID -> 404
    non_existent_id = str(uuid.uuid4())
    res_unknown_tpl = client.post(
        "/api/v1/jobs",
        json={**base_payload, "template_id": non_existent_id, "recipients": [{"name": "A", "email": "a@a.com"}]},
    )
    assert res_unknown_tpl.status_code == 404
    assert "not found" in res_unknown_tpl.json()["error"]["message"].lower()

    # 4. Request with invalid email: ACCEPTED (202), row stored as failed
    mixed_payload = {
        **base_payload,
        "recipients": [
            {"name": "Valid User", "email": "valid@example.com"},
            {"name": "Bad Email User", "email": "not-an-email-at-all"},
        ],
    }
    res_mixed = client.post("/api/v1/jobs", json=mixed_payload)
    assert res_mixed.status_code == 202
    job_id = res_mixed.json()["id"]

    # Poll status: valid user succeeded, bad email user failed
    prog = client.get(f"/api/v1/jobs/{job_id}").json()
    assert prog["total"] == 2
    assert prog["succeeded"] == 1
    assert prog["failed"] == 1
    assert prog["status"] == "completed_with_errors"

    # Verify failure reason is recorded on failed row
    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates?status=failed")
    assert certs_res.status_code == 200
    failed_rows = certs_res.json()["items"]
    assert len(failed_rows) == 1
    assert "invalid email format" in failed_rows[0]["error_message"].lower()


def test_job_progress_derived_statuses(test_db_session_factory):
    """Verifies that all 5 derived statuses are calculated correctly from certificate counts."""
    with test_db_session_factory() as db:
        tpl = db.query(Template).first()
        job = Job(
            title="Status Test Job",
            issued_date=date(2026, 10, 10),
            template_id=tpl.id,
            layout_snapshot=tpl.layout,
        )
        db.add(job)
        db.commit()

        # 1. QUEUED: pending > 0, succeeded == 0, failed == 0
        c1 = Certificate(job_id=job.id, recipient_name="C1", recipient_email="c1@a.com", status=CertificateStatus.PENDING)
        c2 = Certificate(job_id=job.id, recipient_name="C2", recipient_email="c2@a.com", status=CertificateStatus.PENDING)
        db.add_all([c1, c2])
        db.commit()
        prog = get_progress(db, job.id)
        assert prog.status == DerivedJobStatus.QUEUED
        assert prog.percent == 0.0

        # 2. PROCESSING: pending > 0, (succeeded + failed) > 0
        c1.status = CertificateStatus.SUCCEEDED
        db.commit()
        prog = get_progress(db, job.id)
        assert prog.status == DerivedJobStatus.PROCESSING
        assert prog.percent == 50.0

        # 3. COMPLETED: pending == 0, failed == 0
        c2.status = CertificateStatus.SUCCEEDED
        db.commit()
        prog = get_progress(db, job.id)
        assert prog.status == DerivedJobStatus.COMPLETED
        assert prog.percent == 100.0

        # 4. COMPLETED_WITH_ERRORS: pending == 0, succeeded > 0, failed > 0
        c2.status = CertificateStatus.FAILED
        c2.error_message = "Some error"
        db.commit()
        prog = get_progress(db, job.id)
        assert prog.status == DerivedJobStatus.COMPLETED_WITH_ERRORS
        assert prog.percent == 100.0

        # 5. FAILED: pending == 0, succeeded == 0, failed > 0
        c1.status = CertificateStatus.FAILED
        db.commit()
        prog = get_progress(db, job.id)
        assert prog.status == DerivedJobStatus.FAILED


def test_individual_failure_isolation(client, monkeypatch):
    """Monkeypatch the generator to raise for one recipient and verify others succeed."""
    original_render = worker.render_certificate

    def faulty_render(recipient_name, *args, **kwargs):
        if recipient_name == "Crashing Person":
            raise RuntimeError("Renderer simulated crash on character set!")
        return original_render(recipient_name, *args, **kwargs)

    monkeypatch.setattr(worker, "render_certificate", faulty_render)

    tpl_res = client.get("/api/v1/templates")
    template_id = tpl_res.json()[0]["id"]

    payload = {
        "title": "Resilience Workshop",
        "issued_date": "2026-10-10",
        "template_id": template_id,
        "recipients": [
            {"name": "Solid Person One", "email": "one@example.com"},
            {"name": "Crashing Person", "email": "crash@example.com"},
            {"name": "Solid Person Two", "email": "two@example.com"},
        ],
    }

    res = client.post("/api/v1/jobs", json=payload)
    assert res.status_code == 202
    job_id = res.json()["id"]

    prog = client.get(f"/api/v1/jobs/{job_id}").json()
    assert prog["total"] == 3
    assert prog["succeeded"] == 2
    assert prog["failed"] == 1
    assert prog["status"] == "completed_with_errors"

    # Assert error message on crashing person
    certs_res = client.get(f"/api/v1/jobs/{job_id}/certificates")
    items = certs_res.json()["items"]
    crashed_cert = next(c for c in items if c["recipient_name"] == "Crashing Person")
    assert crashed_cert["status"] == "failed"
    assert "Renderer simulated crash" in crashed_cert["error_message"]


def test_certificate_and_zip_retrieval(client):
    tpl_res = client.get("/api/v1/templates")
    template_id = tpl_res.json()[0]["id"]

    payload = {
        "title": "Cloud Computing",
        "issued_date": "2026-10-10",
        "template_id": template_id,
        "recipients": [
            {"name": "Good Recipient", "email": "good@example.com"},
            {"name": "Bad Recipient", "email": "bad_email_addr"},
        ],
    }

    res = client.post("/api/v1/jobs", json=payload)
    job_id = res.json()["id"]

    certs = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]
    good_cert = next(c for c in certs if c["status"] == "succeeded")
    bad_cert = next(c for c in certs if c["status"] == "failed")

    # 1. Single PDF download succeeds for valid cert
    single_res = client.get(f"/api/v1/certificates/{good_cert['id']}/download")
    assert single_res.status_code == 200
    assert single_res.content.startswith(b"%PDF-")

    # 2. Single PDF download returns 404 for failed cert
    bad_res = client.get(f"/api/v1/certificates/{bad_cert['id']}/download")
    assert bad_res.status_code == 404

    # 3. Single PDF download returns 404 for non-existent cert
    missing_res = client.get(f"/api/v1/certificates/{uuid.uuid4()}/download")
    assert missing_res.status_code == 404

    # 4. Streamed ZIP download contains ONLY succeeded certificates
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        file_list = zf.namelist()
        assert len(file_list) == 1  # Only good_cert included
        assert file_list[0].endswith(".pdf")


def test_crash_recovery(test_db_session_factory, temp_storage, monkeypatch):
    """Verifies that certificates stuck in 'processing' are reset to 'pending' and re-executed."""
    monkeypatch.setattr(worker, "storage", temp_storage)

    with test_db_session_factory() as db:
        tpl = db.query(Template).first()
        job = Job(
            title="Crash Recovery Test",
            issued_date=date(2026, 10, 10),
            template_id=tpl.id,
            layout_snapshot=tpl.layout,
        )
        db.add(job)
        db.flush()

        # Simulate a crash: certificate stranded in PROCESSING state
        stuck_cert = Certificate(
            job_id=job.id,
            recipient_name="Stranded Recipient",
            recipient_email="stranded@example.com",
            status=CertificateStatus.PROCESSING,
        )
        db.add(stuck_cert)
        db.commit()
        stuck_cert_id = stuck_cert.id

        # Execute recovery
        recovered_count = recover_stuck_certificates(db)
        assert recovered_count == 1

        # Re-fetch certificate: should now be SUCCEEDED because worker re-executed it
        db.refresh(stuck_cert)
        assert stuck_cert.status == CertificateStatus.SUCCEEDED
        assert stuck_cert.file_path is not None
        assert temp_storage.exists(stuck_cert.file_path)
