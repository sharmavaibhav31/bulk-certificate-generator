# Bulk Certificate Generator

A high-performance, fault-tolerant service for generating completion certificates in bulk. It accepts batches of recipients via CSV, text files, or direct API payloads, renders pixel-precise certificates using a unified Pillow rendering engine (supporting PDF, PNG, and JPG formats), tracks progress asynchronously, and provides single-file and ZIP archive downloads.

---

## Features

- **Asynchronous Batch Processing**: `POST /jobs` validates request structure and returns HTTP 202 with a job identifier immediately. Processing occurs in the background without tying up HTTP request threads.
- **Per-Certificate Fault Isolation**: Each recipient certificate is rendered inside its own isolated `try/except` block. An individual failure (e.g. invalid font or malformed image) marks that certificate as failed with an error message, while the rest of the batch continues uninterrupted.
- **Two-Level Validation**:
  - *Level 1 (HTTP Layer)*: Pydantic rejects malformed request bodies, missing required parameters, or out-of-bounds lists with HTTP 422.
  - *Level 2 (Business Layer)*: Recipient email is optional (if provided, validated for syntax). Recipient name is mandatory (non-empty, max 200 chars). Invalid recipient data within a batch is accepted at the API level, allowing the job to proceed while marking flawed records as failed with specific reasons.
- **Dynamic Progress Calculation & Failure Reporting**: Job status and progress percentages are computed on the fly using grouped counts over the database rows. Status endpoints return detailed lists of failed recipients with reasons.
- **Atomic Concurrency Protection**: Worker threads claim pending certificates using an atomic SQL `UPDATE ... WHERE status = 'pending'`, preventing duplicate processing across concurrent workers.
- **Unified Pillow Engine & Multi-Format Output**: Builtin styles render on a crisp $3508 \times 2480$ canvas; custom templates render on original resolution background images with auto-shrinking text and `"mm"` centering anchor. Generates PDF, PNG, or JPG formats.
- **Single-Page React Frontend**: A lightweight, responsive interface built with Vite and plain CSS. Features CSV/TXT file parsing, live text-positioning sliders on custom template uploads, real-time progress polling, and failed row inspection.

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL (with SQLite support for tests), Pydantic v2.
- **Rendering Engine**: Pillow 10.x (multi-format drawing engine for PDF, PNG, JPG; bundled OFL fonts). Zero ReportLab dependencies.
- **Frontend**: Vite, React 18, PapaParse, Vanilla CSS.
- **Testing**: pytest, HTTPX / FastAPI TestClient.

---

## Setup & Installation

### Option 1: Docker Compose (Recommended)

To spin up PostgreSQL, the FastAPI backend, and the Vite frontend with a single command:

```bash
docker compose up --build
```

- **Backend API**: `http://localhost:8000` (Interactive Swagger docs at `http://localhost:8000/docs`)
- **Frontend UI**: `http://localhost:5173`
- **PostgreSQL**: `localhost:5432`

---

### Option 2: Manual Setup

#### 1. Backend Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## Running Tests

Run the comprehensive pytest suite:

```bash
pytest tests/ -v
```

All 27 integration tests run synchronously with in-memory SQLite and isolated temporary disk storage (`WORKER_MODE=inline`).

---

## Submitting a Generation Request

Submit a batch generation request via `curl`:

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: job-request-unique-abc-123" \
  -d '{
    "template_id": "8c599ca2-7f21-4d1e-8fe5-1f92e59e414c",
    "title": "Full-Stack Web Development Bootcamp",
    "organization_name": "Acme Institute of Technology",
    "issued_date": "2026-10-12",
    "output_format": "pdf",
    "recipients": [
      {
        "name": "Jane Doe",
        "email": "jane@example.com"
      },
      {
        "name": "Alex Smith"
      },
      {
        "name": "Carlos Gomez",
        "email": "not-an-email"
      }
    ]
  }'
```

**Response (HTTP 202 Accepted)**:
```json
{
  "id": "c7a83d34-f8b1-4bb2-b5e0-1c0eb7d65681",
  "status": "queued",
  "status_url": "/api/v1/jobs/c7a83d34-f8b1-4bb2-b5e0-1c0eb7d65681"
}
```

---

## Importing from CSV / TXT Files

### CSV File Format
Headers are case-insensitive (`name`, `email`). Email is optional:

```csv
name,email
Alice Johnson,alice@example.com
Bob Dylan,bob@example.com
Charlie Brown,
```

### TXT File Format
Text files can be structured with commas or email angle brackets:

```text
Alice Johnson, alice@example.com
Bob Dylan <bob@example.com>
Charlie Brown
```

---

## Using Templates & Uploading Custom Templates

### Built-in Styles
Five styles are automatically seeded into the database on startup:
1. `classic`: Traditional gold double-frame with formal serif typography.
2. `modern`: Clean sans-serif layout with royal blue accent bars.
3. `minimal`: Ultra-clean monochromatic framing.
4. `elegant`: Navy borders with gold trim and traditional layout.
5. `bold`: High-contrast dark mode canvas with cyan tech borders.

Built-in templates enforce `required_fields: ["name", "title", "issued_date"]`.

### Custom Templates
Custom templates allow uploading pre-designed certificate artwork (from Canva, Figma, etc.) and positioning the recipient name.
- **File Format**: PNG or JPEG.
- **File Size**: Up to 10 MB.
- **Image Resolution**: Up to 25 million pixels. No aspect ratio restrictions.
- **Output**: Saved losslessly as original resolution PNG at `backgrounds/{template_id}.png`.
- **Layout Definition**:
  - `name_x`: Horizontal center percentage (0 to 100, default 50).
  - `name_y`: Vertical position percentage (0 to 100, default 57).
  - `font`: One of bundled keys (`dejavu_sans`, `dejavu_serif`, `liberation_sans`, `liberation_serif`).
  - `font_size_pct`: Font size as percentage of image height (default 5.0).
  - `color`: Hex color string (default `#1A202C`).
  - `max_width_pct`: Maximum width percentage before auto-shrinking text (default 70.0).

Upload via `curl`:
```bash
curl -X POST http://localhost:8000/api/v1/templates/custom \
  -F "name=Corporate Annual Certificate" \
  -F "image=@/path/to/background.png" \
  -F "name_x=50.0" \
  -F "name_y=57.0" \
  -F "font=dejavu_sans" \
  -F "font_size_pct=5.0" \
  -F "color=#1A202C" \
  -F "max_width_pct=70.0"
```

Live PNG preview:
```bash
curl -X GET "http://localhost:8000/api/v1/templates/{id}/preview?name=Jane+Doe" -o preview.png
```

---

## Checking Progress

Poll `GET /api/v1/jobs/{job_id}`:

```bash
curl -X GET http://localhost:8000/api/v1/jobs/c7a83d34-f8b1-4bb2-b5e0-1c0eb7d65681
```

**Response**:
```json
{
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "pending": 0,
  "percent": 100.0,
  "status": "completed_with_errors",
  "failed_recipients": [
    {
      "name": "Carlos Gomez",
      "email": "not-an-email",
      "error_message": "Invalid email format: 'not-an-email'."
    }
  ]
}
```

### Derived Job Statuses:
- `queued`: Certificates created; generation has not yet started.
- `processing`: Worker is actively claiming and rendering certificates.
- `completed`: All certificates succeeded without any failures.
- `completed_with_errors`: Finished with a mix of succeeded and failed certificates.
- `failed`: All certificates in the job failed.

---

## Retrieving Certificates

### Single Certificate Download
```bash
curl -X GET http://localhost:8000/api/v1/certificates/{certificate_id}/download -o Jane_Doe.pdf
```
*Returns `Content-Disposition: attachment; filename="{cert.file_name}"` with the appropriate MIME type (`application/pdf`, `image/png`, `image/jpeg`).*

### Bulk ZIP Archive Download
```bash
curl -X GET http://localhost:8000/api/v1/jobs/{job_id}/download -o Certificates.zip
```
*Streams an uncompressed `ZIP_STORED` archive named after the sanitized job title, with entries named after the sanitized, deduplicated recipient names (e.g. `Jane_Doe.pdf`, `Jane_Doe (2).pdf`).*

---

## API Reference

| Method | Endpoint | Description | Status Code |
|---|---|---|---|
| `GET` | `/health` | Health and liveness probe | `200 OK` |
| `GET` | `/api/v1/templates` | List all active templates | `200 OK` |
| `GET` | `/api/v1/templates/{id}/preview` | Download live PNG preview for template (`?name=...`) | `200 OK` |
| `POST` | `/api/v1/templates/custom` | Upload custom background and percentage layout | `201 Created` |
| `POST` | `/api/v1/jobs` | Submit bulk certificate generation job | `202 Accepted` |
| `GET` | `/api/v1/jobs/{id}` | Get real-time job progress, status, and failed recipients | `200 OK` |
| `GET` | `/api/v1/jobs/{id}/certificates` | List paginated certificates (filters: `status`, `page`, `page_size`) | `200 OK` |
| `GET` | `/api/v1/jobs/{id}/download` | Stream ZIP archive of all succeeded certificates | `200 OK` |
| `GET` | `/api/v1/certificates/{id}/download` | Download single generated certificate | `200 OK` |

---

## Design Decisions

### 1. Asynchronous Processing with Job ID and Polling
Rendering certificates in bulk is CPU- and I/O-intensive. When a user uploads a batch of 500 or 5,000 recipients, processing inside the request-response cycle would exceed standard HTTP gateway timeouts (typically 30–60 seconds), tie up web workers, and make client connections brittle on unreliable networks.

Instead, the `POST /jobs` endpoint validates structural integrity, writes the job and certificate rows to the database in a single transaction, dispatches background execution, and immediately returns HTTP `202 Accepted` with a job ID. The client polls `GET /jobs/{id}` periodically. This provides a responsive UI with clear progress feedback and allows the client to disconnect and reconnect without interrupting ongoing generation.

### 2. Thread Pool + DB State vs. Celery (and the Upgrade Path)
For this implementation, background execution uses an application-scoped `ThreadPoolExecutor` coordinated directly via database row states, rather than introducing an external distributed task broker like Celery with Redis or RabbitMQ.

**Why this choice?**
- **Operational Simplicity**: It removes external infrastructure dependencies, making local development, CI/CD, and dockerized deployment completely self-contained.
- **Transactional Consistency**: Progress tracking, job snapshots, and failure logs already live in the relational database. By having workers claim rows using atomic SQL statements, we avoid dual-state synchronization issues between a broker queue and the database.

**Celery Upgrade Path**:
The worker logic in `app/worker.py` is fully decoupled from the execution mechanism. The core function `process_job(job_id)` is a pure Python function that creates its own database session and processes rows in batches. To switch to Celery:
```python
# tasks.py
@celery_app.task
def process_job_task(job_id: str):
    process_job(job_id)
```
In `app/api/jobs.py`, replacing `submit_job(job.id)` with `process_job_task.delay(str(job.id))` is all that is required. The core worker logic, progress queries, and error handling remain unchanged.

### 3. Two-Level Validation Approach
Bulk operations frequently fail due to a single bad record in an otherwise valid batch of thousands. 
- **Level 1 (Structural HTTP Validation)**: Handled by Pydantic schemas. If the request body is missing required fields, has an invalid template ID, or exceeds the 10,000 recipient limit, FastAPI immediately rejects the payload with HTTP 422.
- **Level 2 (Per-Recipient Data Quality)**: Handled in the service layer. Recipient email is optional, but if present it is validated for RFC email syntax. Recipient name is mandatory (non-empty, max 200 chars). Flawed rows are saved as `status="failed"` with a specific error message. Valid recipients are saved as `status="pending"`.

This prevents an all-or-nothing failure where a typo on row 4,892 discards the entire batch.

### 4. Progress Computed from Rows
Job progress is computed dynamically via an aggregate query (`SELECT status, COUNT(id) FROM certificates WHERE job_id = :id GROUP BY status`) rather than maintaining incremented counters on the `jobs` row.

Stored counters in high-concurrency systems frequently suffer from lost updates, race conditions, or drift after crashes and retries. Querying the certificate rows directly provides a single source of truth. If a certificate state changes or a failed job is retried, the progress percentage and derived status remain mathematically consistent without requiring reconciliation routines.

### 5. Crash Recovery
If the server terminates unexpectedly during a batch (such as an out-of-memory kill, deployment restart, or power outage), some certificates could be left stranded in the `processing` state indefinitely.

On startup, the application lifecycle hook runs `recover_stuck_certificates(db)`. This executes a query resetting any certificates currently marked as `processing` back to `pending`, identifies the affected job IDs, and re-submits those jobs to the worker pool. This guarantees that jobs resume automatically after crashes without manual database intervention.

### 6. Pillow Rendering Engine vs. ReportLab / Headless Browsers
The system uses a single Pillow rendering engine across all template types and export formats.

**Rationale**:
- **Zero Heavy C-Extension or Browser Overhead**: ReportLab requires complex C compiling during container builds (often taking hundreds of seconds), and headless Chrome consumes hundreds of megabytes of RAM per worker. Pillow installs in seconds via pre-built wheels and has minimal memory footprint.
- **Multi-Format Versatility**: Pillow encodes directly to PDF, PNG, and JPEG from the exact same canvas drawing pass, enabling pixel-perfect consistency across formats.
- **Base Canvas Preloading**: For batch jobs, the worker loads and decodes the custom background image or builtin canvas once, and uses `image.copy()` per recipient. This avoids redundant disk I/O and image decoding.
- **Auto-Shrinking Name with Centering Anchor**: In custom templates, recipient names are placed at `(name_x%, name_y%)` with anchor `"mm"`, and an iterative text-bounding loop reduces font size until the name fits within `max_width_pct`.

### 7. Upload Security Checks
User-uploaded images represent a common security vector. In `app/services/template_upload.py`, every upload passes through strict validation:
1. **Size Enforcement**: Bounded strictly to $\le 10$ MB to prevent disk exhaustion.
2. **Decompression Bomb Protection**: Pillow enforces a maximum limit of 25 million pixels (`MAX_IMAGE_PIXELS = 25_000_000`).
3. **Format Whitelisting**: Pillow calls `img.verify()`, rejecting non-images or malformed byte streams. Only `PNG` and `JPEG` formats are accepted.
4. **Metadata Stripping & Lossless Re-encoding**: The image is decoded into raw pixel data and re-saved as a lossless PNG, stripping EXIF tags, GPS metadata, and embedded comments.
5. **UUID Pathing**: The original filename provided by the client is discarded. Files are stored using randomly generated UUIDs (`backgrounds/<template_id>.png`) to prevent path traversal attacks.

### 8. Layout Snapshotting on Jobs
When a job is created, the template's current layout configuration, background path, and required fields are deep-copied into `job.layout_snapshot`.

If a template is modified or deleted later, already-generated or currently-running jobs are unaffected. Their certificates will always render against the exact design that was active at the moment the job was submitted.

### 9. Storage Interface for S3
File operations are abstracted behind the `StorageInterface` protocol in `app/services/storage.py`, exposing `save`, `read`, `exists`, and `delete`.

The application currently uses `LocalStorage`, storing files relative to a local path. To support Amazon S3 or Google Cloud Storage in a multi-server setup, one can implement `S3Storage(StorageInterface)` using `boto3`. The rendering engine, worker, ZIP streamer, and template upload modules interact exclusively with the interface, requiring zero changes when swapping storage providers.

### 10. Known Limitations & Future Work
With additional time, the following enhancements would be prioritised:
- **Distributed Worker Scaling**: Moving from the in-memory `ThreadPoolExecutor` to Celery with Redis to scale rendering workers horizontally across multiple nodes.
- **Direct Email Dispatching**: Adding an optional toggle to email generated certificates directly to recipients via AWS SES or SendGrid as each certificate succeeds.
- **Interactive Drag-and-Drop Visual Canvas**: Expanding the frontend custom template tool to allow interactive dragging of the name bounding box directly on top of the image canvas.
