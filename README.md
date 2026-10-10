# Bulk Certificate Generator

A high-performance, fault-tolerant service for generating PDF completion certificates in bulk. It accepts batches of recipients via CSV, text files, or direct API payloads, renders landscape A4 PDFs using ReportLab, tracks progress asynchronously, and provides single-file and ZIP archive downloads.

---

## Features

- **Asynchronous Batch Processing**: `POST /jobs` validates request structure and returns HTTP 202 with a job identifier immediately. Processing occurs in the background without tying up HTTP request threads.
- **Per-Certificate Fault Isolation**: Each recipient certificate is rendered inside its own isolated `try/except` block. An individual failure (e.g. malformed email or font glyph issue) marks that certificate as failed with an error message, while the rest of the batch continues uninterrupted.
- **Two-Level Validation**:
  - *Level 1 (HTTP Layer)*: Pydantic rejects malformed request bodies, missing required parameters, or out-of-bounds lists with HTTP 422.
  - *Level 2 (Business Layer)*: Invalid recipient data within a batch is accepted at the API level, allowing the job to proceed while marking flawed records as failed with specific reasons.
- **Dynamic Progress Calculation**: Job status and progress percentages are computed on the fly using grouped counts over the database rows. No stored counter is used, preventing race conditions and counter drift.
- **Atomic Concurrency Protection**: Worker threads claim pending certificates using an atomic SQL `UPDATE ... WHERE status = 'pending'`, preventing duplicate processing across concurrent workers.
- **Built-in & Custom Templates**: Comes with 5 built-in styles (`classic`, `modern`, `minimal`, `elegant`, `bold`) and supports custom uploaded background images with percentage-based text coordinate placement.
- **Single-Page React Frontend**: A lightweight, responsive interface built with Vite and plain CSS. Features CSV/TXT file parsing, live text-positioning sliders on custom template uploads, real-time progress polling, and failed row inspection.

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL (with SQLite support for tests), Pydantic v2.
- **PDF Engine**: ReportLab 4.x (canvas drawing on landscape A4), Pillow (image validation and metadata stripping).
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

### Option 2: Manual Local Setup

#### Prerequisites
- Python 3.12+
- Node.js 18+ and npm
- PostgreSQL (or use default local SQLite)

#### 1. Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations / seeding & start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

By default, without a `DATABASE_URL` environment variable set, the backend falls back to a local SQLite database (`sqlite:///./app.db`). To connect to PostgreSQL:
```bash
export DATABASE_URL="postgresql+psycopg://postgres:password@localhost:5432/cert_generator_db"
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Running Tests

The test suite runs against SQLite using isolated temporary directories for file storage and `WORKER_MODE=inline` (synchronous execution for deterministic tests):

```bash
python3 -m pytest tests/ -v
```

To run individual test files:
```bash
python3 -m pytest tests/test_jobs.py -v
python3 -m pytest tests/test_templates.py -v
```

---

## Submitting a Generation Request

You can dispatch a generation job via `curl`:

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: job-req-batch-001" \
  -d '{
    "title": "Full-Stack Web Development Masterclass",
    "organization_name": "Dev Academy",
    "issued_date": "2026-10-10",
    "template_id": "00000000-0000-0000-0000-000000000001",
    "recipients": [
      {"name": "Alice Johnson", "email": "alice@example.com"},
      {"name": "Bob Smith", "email": "bob@example.com"},
      {"name": "Malformed Record", "email": "invalid-email-address"}
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

The UI and client accept recipients in standard spreadsheet and plain-text formats:

### CSV File Format
Headers are case-insensitive (`name`, `email`). If headers are absent, the parser automatically treats column 1 as the recipient name and column 2 as the email address.

```csv
name,email
Alice Johnson,alice@example.com
Bob Dylan,bob@example.com
Charlie Brown,charlie@example.com
```

### TXT File Format
Text files can be structured with commas or email angle brackets, line-by-line:

```text
Alice Johnson, alice@example.com
Bob Dylan <bob@example.com>
Charlie Brown, charlie@example.com
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

### Custom Template Requirements
- **File Format**: PNG or JPEG only.
- **Dimensions / Aspect Ratio**: Must match the A4 landscape ratio ($841.89 \times 595.27\text{ pt} \approx 1.414$) within a 10% tolerance range ($[1.272, 1.555]$).
- **Size Limit**: Maximum 5 MB.
- **Layout Definition**: Three percentage coordinates ($0.0$ to $100.0$) representing vertical placement from the top of the page:
  - `name_y`: Vertical position for recipient name.
  - `course_y`: Vertical position for course title.
  - `date_y`: Vertical position for issue date.

Upload via `curl`:
```bash
curl -X POST http://localhost:8000/api/v1/templates/custom \
  -F "name=Corporate Annual Certificate" \
  -F "image=@/path/to/background.png" \
  -F "name_y=42.0" \
  -F "course_y=58.0" \
  -F "date_y=76.0"
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
  "status": "completed_with_errors"
}
```

### Derived Job Statuses:
- `queued`: Certificates created; generation has not yet started.
- `processing`: At least one certificate has been completed or failed, and pending certificates remain.
- `completed`: All certificates succeeded without any failures.
- `completed_with_errors`: Finished with a mix of succeeded and failed certificates.
- `failed`: All certificates in the job failed.

---

## Retrieving Certificates

### Single Certificate Download
```bash
curl -X GET http://localhost:8000/api/v1/certificates/{certificate_id}/download -o certificate.pdf
```
*Returns HTTP 404 if the certificate is not found or did not succeed.*

### Bulk ZIP Archive Download
```bash
curl -X GET http://localhost:8000/api/v1/jobs/{job_id}/download -o certificates.zip
```
*Streams a ZIP archive containing all successfully generated certificates in 64 KB chunks.*

---

## API Reference

| Method | Endpoint | Description | Status Code |
|---|---|---|---|
| `GET` | `/health` | Health and liveness probe | `200 OK` |
| `GET` | `/api/v1/templates` | List all active templates | `200 OK` |
| `GET` | `/api/v1/templates/{id}/preview` | Download sample preview PDF for template | `200 OK` |
| `POST` | `/api/v1/templates/custom` | Upload custom background and percentage layout | `201 Created` |
| `POST` | `/api/v1/jobs` | Submit bulk certificate generation job | `202 Accepted` |
| `GET` | `/api/v1/jobs/{id}` | Get real-time job progress and derived status | `200 OK` |
| `GET` | `/api/v1/jobs/{id}/certificates` | List paginated certificates (filters: `status`, `page`, `page_size`) | `200 OK` |
| `GET` | `/api/v1/jobs/{id}/download` | Stream ZIP archive of all succeeded certificates | `200 OK` |
| `GET` | `/api/v1/certificates/{id}/download` | Download single generated PDF certificate | `200 OK` |

---

## Design Decisions

### 1. Asynchronous Processing with Job ID and Polling
Rendering PDFs is CPU- and I/O-intensive. When a user uploads a batch of 500 or 5,000 recipients, doing the work inside the request-response cycle would quickly exceed standard HTTP gateway timeouts (typically 30–60 seconds), tie up web workers, and make client connections brittle on unreliable networks.

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
- **Level 2 (Per-Recipient Data Quality)**: Handled in the service layer. Individual recipient emails and names are validated when inserting certificate rows. Flawed rows (such as missing names or invalid email syntax) are saved as `status="failed"` with a specific error message. Valid recipients are saved as `status="pending"`.

This prevents an all-or-nothing failure where a typo on row 4,892 discards the entire batch.

### 4. Progress Computed from Rows
Job progress is computed dynamically via an aggregate query (`SELECT status, COUNT(id) FROM certificates WHERE job_id = :id GROUP BY status`) rather than maintaining incremented counters on the `jobs` row.

Stored counters in high-concurrency systems frequently suffer from lost updates, race conditions, or drift after crashes and retries. Querying the certificate rows directly provides a single source of truth. If a certificate state changes or a failed job is retried, the progress percentage and derived status remain mathematically consistent without requiring reconciliation routines.

### 5. Crash Recovery
If the server terminates unexpectedly during a batch (such as an out-of-memory kill, deployment restart, or power outage), some certificates could be left stranded in the `processing` state indefinitely.

On startup, the application lifecycle hook runs `recover_stuck_certificates(db)`. This executes a query resetting any certificates currently marked as `processing` back to `pending`, identifies the affected job IDs, and re-submits those jobs to the worker pool. This guarantees that jobs resume automatically after crashes without manual database intervention.

### 6. Background Images + Percentage Overlay vs. DOCX / HTML
Custom templates use an uploaded background image (PNG/JPEG) combined with percentage-based coordinate positioning (`name_y`, `course_y`, `date_y`), rather than rendering from HTML/CSS (e.g. via WeasyPrint or headless Chrome) or Microsoft Word (DOCX) files.

**Rationale**:
- **Cross-Platform Visual Determinism**: HTML-to-PDF tools and headless browsers frequently render fonts, line heights, and margins differently across Linux, macOS, and container environments. ReportLab renders vector graphics and text onto a fixed canvas with mathematical precision.
- **Resource Footprint**: Running headless Chromium or complex DOCX conversion engines in production consumes hundreds of megabytes of RAM per worker and introduces significant attack surfaces. ReportLab and Pillow are lightweight, fast, and require minimal system dependencies.
- **Designer Workflow**: Organizations already design certificates in tools like Canva, Figma, or Illustrator. Exporting a blank background and setting text coordinates is a natural workflow that does not require writing HTML templates.

### 7. Upload Security Checks
User-uploaded images represent a common security vector. In `app/services/template_upload.py`, every upload passes through strict validation:
1. **Size Enforcement**: Bounded strictly to $\le 5$ MB to prevent disk exhaustion.
2. **Integrity & Format Whitelisting**: Pillow calls `img.verify()`, rejecting non-images or malformed byte streams. Only `PNG` and `JPEG` formats are accepted.
3. **Aspect Ratio Constraints**: The image dimensions are checked against the A4 landscape ratio ($1.414$) within 10% tolerance, preventing distorted certificates.
4. **Metadata Stripping & Re-encoding**: The image is decoded into raw pixel data and re-saved, stripping EXIF tags, GPS metadata, and embedded comments.
5. **UUID Pathing**: The original filename provided by the client is discarded. Files are stored using randomly generated UUIDs (`backgrounds/<uuid>.png`) to prevent path traversal attacks.

### 8. Layout Snapshotting on Jobs
When a job is created, the template's current layout configuration and background path are deep-copied into `job.layout_snapshot`.

If a template is modified or deleted later, already-generated or currently-running jobs are unaffected. Their certificates will always render against the exact design that was active at the moment the job was submitted.

### 9. Storage Interface for S3
File operations are abstracted behind the `StorageInterface` protocol in `app/services/storage.py`, exposing `save`, `read`, `exists`, and `delete`.

The application currently uses `LocalStorage`, storing files relative to a local path. To support Amazon S3 or Google Cloud Storage in a multi-server setup, one can implement `S3Storage(StorageInterface)` using `boto3`. The PDF generator, worker, ZIP streamer, and template upload modules interact exclusively with the interface, requiring zero changes when swapping storage providers.

### 10. Known Limitations & Future Work
With additional time, the following enhancements would be prioritised:
- **Distributed Worker Scaling**: Moving from the in-memory `ThreadPoolExecutor` to Celery with Redis to scale rendering workers horizontally across multiple nodes.
- **Dynamic Font Uploads**: Bundling additional TTF font families (e.g. Google Fonts) and allowing users to select typography per template.
- **Direct Email Dispatching**: Adding an optional toggle to email generated certificates directly to recipients via AWS SES or SendGrid as each certificate succeeds.
- **Interactive Visual Layout Editor**: Expanding the frontend custom template tool to allow drag-and-drop text box placement with live bounding box resizing and font size controls.
