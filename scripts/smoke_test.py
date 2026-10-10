"""
End-to-End Live Stack Smoke Test Script.

Tests the live running application (local or docker compose) by:
1. Checking /health
2. Listing templates
3. Submitting a bulk job with valid & invalid recipients
4. Polling progress until terminal status
5. Downloading an individual certificate PDF
6. Downloading the ZIP archive and verifying its contents
"""

import sys
import time
import io
import zipfile
import urllib.request
import json

BASE_URL = "http://localhost:8000"


def request_json(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, method=method)
    for k, v in headers.items():
        req.add_header(k, v)

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, data=body, timeout=10) as resp:
            content = resp.read()
            return resp.status, json.loads(content.decode("utf-8")) if content else (resp.status, None)
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_content)
        except Exception:
            return e.code, err_content


def run_smoke_test():
    print(f"=== Starting E2E Smoke Test against {BASE_URL} ===\n")

    # 1. Health check
    print("[1/6] Checking /health endpoint...")
    status, body = request_json(f"{BASE_URL}/health")
    if status != 200 or body.get("status") != "ok":
        print(f"FAILED: Health check returned status {status}, body: {body}")
        sys.exit(1)
    print("      ✓ API is healthy.")

    # 2. List templates
    print("\n[2/6] Listing templates...")
    status, templates = request_json(f"{BASE_URL}/api/v1/templates")
    if status != 200 or not isinstance(templates, list) or len(templates) < 5:
        print(f"FAILED: Expected at least 5 templates, got {templates}")
        sys.exit(1)
    template_id = templates[0]["id"]
    template_name = templates[0]["name"]
    print(f"      ✓ Retrieved {len(templates)} templates. Selected: '{template_name}' ({template_id})")

    # 3. Submit bulk job
    print("\n[3/6] Dispatching bulk generation job (POST /api/v1/jobs)...")
    payload = {
        "title": "Docker Stack Integration Test",
        "organization_name": "Docker Certification Board",
        "issued_date": "2026-10-10",
        "template_id": template_id,
        "recipients": [
            {"name": "Ada Lovelace", "email": "ada@example.com"},
            {"name": "Bad Recipient Record", "email": "bad_email_address"},
            {"name": "Alan Turing", "email": "alan@example.com"},
        ],
    }
    status, res = request_json(f"{BASE_URL}/api/v1/jobs", method="POST", data=payload)
    if status != 202 or "id" not in res:
        print(f"FAILED: Expected 202 Accepted, got {status}: {res}")
        sys.exit(1)
    job_id = res["id"]
    print(f"      ✓ Job accepted. Job ID: {job_id}")

    # 4. Poll progress
    print("\n[4/6] Polling job progress...")
    final_status = None
    for attempt in range(1, 15):
        time.sleep(1)
        status, prog = request_json(f"{BASE_URL}/api/v1/jobs/{job_id}")
        if status != 200:
            print(f"FAILED polling: {status} {prog}")
            sys.exit(1)

        print(f"      Attempt {attempt}: {prog['succeeded'] + prog['failed']}/{prog['total']} ({prog['percent']}%) - Status: {prog['status']}")
        if prog["status"] in ("completed", "completed_with_errors", "failed"):
            final_status = prog["status"]
            break

    if final_status != "completed_with_errors":
        print(f"FAILED: Expected final status 'completed_with_errors', got '{final_status}'")
        sys.exit(1)
    print("      ✓ Job finished with correct status and error isolation.")

    # 5. Download individual certificate
    print("\n[5/6] Verifying individual certificate download...")
    status, certs_data = request_json(f"{BASE_URL}/api/v1/jobs/{job_id}/certificates")
    succeeded_certs = [c for c in certs_data["items"] if c["status"] == "succeeded"]
    failed_certs = [c for c in certs_data["items"] if c["status"] == "failed"]

    if len(succeeded_certs) != 2 or len(failed_certs) != 1:
        print(f"FAILED: Expected 2 succeeded and 1 failed cert, got {len(succeeded_certs)} / {len(failed_certs)}")
        sys.exit(1)

    succeeded_id = succeeded_certs[0]["id"]
    req = urllib.request.Request(f"{BASE_URL}/api/v1/certificates/{succeeded_id}/download")
    with urllib.request.urlopen(req) as pdf_resp:
        pdf_bytes = pdf_resp.read()
        if not pdf_bytes.startswith(b"%PDF-"):
            print("FAILED: Downloaded file is not a valid PDF")
            sys.exit(1)
    print(f"      ✓ Successfully downloaded valid PDF certificate ({len(pdf_bytes)} bytes).")

    # 6. Download ZIP archive
    print("\n[6/6] Verifying ZIP archive download...")
    req = urllib.request.Request(f"{BASE_URL}/api/v1/jobs/{job_id}/download")
    with urllib.request.urlopen(req) as zip_resp:
        zip_bytes = zip_resp.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            if len(names) != 2:
                print(f"FAILED: Expected 2 files in ZIP, got {len(names)}: {names}")
                sys.exit(1)
            for n in names:
                if not n.endswith(".pdf"):
                    print(f"FAILED: Archive file '{n}' does not end with .pdf")
                    sys.exit(1)
    print(f"      ✓ Successfully downloaded ZIP archive with {len(names)} succeeded certificates.")

    print("\n=======================================================")
    print("🎉 ALL E2E SMOKE TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")


if __name__ == "__main__":
    run_smoke_test()
