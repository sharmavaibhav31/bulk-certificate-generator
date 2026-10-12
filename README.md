# Bulk Certificate Generator

A batch certificate generation service designed for high throughput and fault tolerance. The system accepts recipient lists via CSV, TXT, XLSX, or JSON API requests, validates inputs against template-specific constraints, renders certificates asynchronously using a unified Pillow rendering engine, and outputs individual files (PDF, PNG, JPG) or streamed ZIP archives.

---

## Architecture Overview

```
Client (Web UI / API Client)
       │
       ▼
FastAPI Application (HTTP Layer)
  ├── 1. Schema Validation (Pydantic v2)
  ├── 2. Template Required Fields Check (`required_fields`)
  ├── 3. Template Layout Snapshotting (`job.layout_snapshot`)
  └── 4. Per-Recipient Validation & Sanitization (Level 2)
       │
       ├── Writes Job & Certificate rows in a single DB transaction
       └── Returns HTTP 202 Accepted with Job ID
       │
       ▼
Background Worker Pool (ThreadPoolExecutor)
  ├── Atomic row claiming (`UPDATE ... WHERE status = 'pending'`)
  ├── Base canvas caching (`img.copy()` per recipient)
  ├── Pillow Rendering Engine (Auto-shrinking text, anchor "mm")
  ├── Multi-format encoding (PDF, PNG, JPG)
  └── Isolated try/catch per certificate (individual failure logging)
       │
       ▼
Storage Layer (LocalStorage / S3 Interface)
       │
       ▼
Export & Delivery
  ├── Single Certificate Download (`GET /certificates/{id}/download`)
  └── Streaming ZIP Archive (`GET /jobs/{id}/download`, ZIP_STORED)
```

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL (SQLite for local/test environments), Pydantic v2.
- **Rendering Engine**: Pillow 10.x with bundled Open Font License (OFL) TrueType fonts (`dejavu_sans`, `dejavu_serif`, `liberation_sans`, `liberation_serif`). Zero ReportLab or headless browser runtime dependencies.
- **Frontend**: Vite, React 18, `read-excel-file` (XLSX parsing), `papaparse` (CSV parsing), Vanilla CSS.
- **Testing**: pytest, HTTPX / FastAPI TestClient.

---

## Setup & Running

### Option 1: Docker Compose (Recommended)

Starts the FastAPI backend, PostgreSQL, and the Vite frontend:

```bash
docker compose up --build
```

- **Backend API**: `http://localhost:8000` (Interactive Swagger docs: `http://localhost:8000/docs`)
- **Frontend UI**: `http://localhost:5173`
- **PostgreSQL**: `localhost:5432`

### Option 2: Local Development

#### Backend
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Running Tests

Execute the test suite with pytest:

```bash
pytest tests/ -v
```

Tests run against an in-memory SQLite database and isolated temporary storage directories using synchronous inline execution (`WORKER_MODE=inline`).

---

## Recipient Import Formats & Parsing

The frontend and API support three file formats for recipient lists: **CSV**, **TXT**, and **XLSX**.

### Parser Behavior & Column Detection

1. **Header Autodetection**:
   - The parser inspects the first row for name-related column headers: `name`, `student`, `student name`, `full name`, `recipient`, `recipient name` (case-insensitive).
   - Email columns are detected matching: `email`, `mail`, `e-mail`, `recipient email`.
   - If no recognized header is found, the parser defaults the first column to the recipient name.
2. **Column Override Dropdowns**: Users can manually select which column maps to recipient name and which (if any) maps to email.
3. **Optional Email**: Recipient email is strictly optional across all import formats. If omitted or empty, the row is accepted without error. If provided, it must satisfy standard RFC email syntax.
4. **Validation Feedback**: Empty recipient names are highlighted immediately in the preview table. Leading and trailing whitespace is automatically stripped.

### Format Specifications & Examples

#### 1. CSV (`.csv`)
Comma-delimited text. Headers can be included or omitted:

```csv
name,email
Alice Johnson,alice@example.com
Bob Dylan,bob@example.com
Charlie Brown,
```

A single-column CSV containing only names is equally valid:

```csv
Full Name
Diana Prince
Bruce Wayne
Clark Kent
```

#### 2. Plain Text (`.txt`)
Text files are parsed line-by-line. The parser accepts comma-separated values, angle bracket email syntax, or bare names:

```text
Alice Johnson, alice@example.com
Bob Dylan <bob@example.com>
Charlie Brown
Diana Prince
```

A file with simply one name per line is completely valid:

```text
Jane Doe
John Smith
Alexander Hamilton
```

#### 3. Excel Spreadsheet (`.xlsx`)
Parsed client-side using `read-excel-file` (pure JavaScript, avoiding vulnerable or bloated sheet packages). The parser reads the first worksheet, skips blank rows, and extracts column headers:

| Full Name | Email Address | Department |
|---|---|---|
| Alice Johnson | alice@example.com | Engineering |
| Bob Dylan | bob@example.com | Design |
| Charlie Brown | | Operations |

---

## Custom Templates

Custom templates allow users to supply pre-designed certificate artwork (created in Figma, Canva, Adobe Illustrator, or PowerPoint) and overlay only the dynamic recipient name.

### How Custom Templates Work

1. **Upload Finished Artwork**: The uploaded image must already contain all static visual elements: borders, background graphics, certificate title, course description, date of issue, organization branding, and instructor signatures.
2. **Only the Name is Required**: For custom templates, the only variable element rendered by the server is the recipient's name. Fields such as `title`, `issued_date`, and `organization_name` are not required, are hidden in the submission UI, and are completely ignored during rendering.
3. **Precise Name Placement**: The user defines the bounding region and typographic style for the recipient name:
   - `name_x`: Horizontal anchor coordinate as a percentage of image width (`0.0` to `100.0`, default `50.0` for center alignment).
   - `name_y`: Vertical anchor coordinate as a percentage of image height (`0.0` to `100.0`, default `57.0`).
   - `font`: Font family selected from bundled OFL fonts (`dejavu_sans`, `dejavu_serif`, `liberation_sans`, `liberation_serif`).
   - `font_size_pct`: Target font size as a percentage of image height (default `5.0`).
   - `color`: Hex color code for the text (e.g. `#1A202C`).
   - `max_width_pct`: Maximum width threshold as a percentage of image width (default `70.0`).
4. **Auto-Shrink Logic**: The rendering engine measures text width at the target font size using `draw.textbbox()`. If the recipient's name exceeds `max_width_pct`, the font size is iteratively decreased by 1 pixel until the text fits within the boundary.
5. **Centering Anchor**: The name is drawn using Pillow anchor `"mm"` (middle-middle), ensuring the text remains centered on `(name_x%, name_y%)` regardless of string length.
6. **No Extraneous Drawing**: When rendering against a custom template background, the engine draws only the recipient name text. No frames, lines, or background fills are added.

### Upload Limits & Security Checks

To protect against denial-of-service, remote execution, and storage exhaustion attacks, uploaded template backgrounds pass through strict validation in `app/services/template_upload.py`:

1. **File Size Limit**: Uploads must not exceed 10 MB (`MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024`).
2. **Decompression Bomb Protection**: Total pixel count ($width \times height$) must not exceed 25 million pixels (`MAX_TOTAL_PIXELS = 25_000_000`). Images exceeding this limit are rejected before decoding to prevent memory exhaustion.
3. **Format Verification**: The file content is verified using `Image.open().verify()`. Only genuine `PNG` and `JPEG` files are accepted. File extensions sent by the client are ignored.
4. **Metadata & EXIF Stripping**: The image is re-decoded into raw pixel data (`RGB` or `RGBA`) and re-encoded as an optimized, lossless PNG. Camera metadata, GPS coordinates, embedded profiles, and comments are discarded.
5. **Isolated Path Storage**: Client-provided filenames are discarded. Backgrounds are stored under a server-generated UUID path: `backgrounds/{template_id}.png`.

---

## Required Fields per Template (`required_fields`)

Templates declare their field dependencies via the `required_fields` list (persisted as JSON on the `templates` table and returned by the API):

- **Built-in Templates**: `["name", "title", "issued_date"]`.
  - Built-in templates render procedural layouts requiring the course title and issue date.
  - If a job submission targeting a built-in template omits `title` or `issued_date`, the API rejects the request with HTTP 422.
- **Custom Templates**: `["name"]`.
  - Custom templates require only the recipient name.
  - Job submissions targeting custom templates accept null or missing values for `title`, `issued_date`, and `organization_name`.

---

## Output Formats, File Naming & Duplicate Handling

### Supported Output Formats

The `output_format` field on the job creation request accepts three values (case-insensitive, default `pdf`):

| Format | MIME Type | Implementation Details |
|---|---|---|
| `pdf` | `application/pdf` | Saved directly via Pillow PDF encoder with DPI preservation (300 DPI standard). |
| `png` | `image/png` | Lossless PNG encoding with `compress_level=3` for high-throughput generation. |
| `jpg` / `jpeg` | `image/jpeg` | Converted to RGB mode and encoded at quality `92`. |

### File Naming Rules

Individual certificates are named after the recipient:

```
<Sanitized_Recipient_Name>.<ext>
```

The sanitization pipeline (`app/services/job_service.py:sanitize_file_name`):
1. **Character Stripping**: Removes characters outside `[a-zA-Z0-9_\-\s]`. Slashes (`/`, `\`), null bytes, quotes, and path traversal sequences (`..`) are discarded.
2. **Whitespace Normalization**: Replaces whitespace runs with single underscores (`_`) and trims leading/trailing punctuation (`._-`).
3. **Length Truncation**: Limits the base filename to 100 characters.
4. **Reserved Word Protection**: Checks against Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`). Reserved names fall back to `certificate`.
5. **Empty Name Fallback**: If sanitization leaves an empty string, the base name defaults to `certificate`.

### Duplicate Name Handling

When multiple recipients in the same job share the exact same sanitized name (e.g. duplicate submissions or common names), the system appends a sequential counter suffix:

- 1st recipient ("Jane Doe"): `Jane_Doe.pdf`
- 2nd recipient ("Jane Doe"): `Jane_Doe (2).pdf`
- 3rd recipient ("Jane Doe"): `Jane_Doe (3).pdf`

This deduplication applies to both the database record (`cert.file_name`) and the archive member path inside downloaded ZIP files, preventing file overwrites upon extraction.

---

## ZIP Download

Completed jobs can be downloaded as a single ZIP archive via:

```
GET /api/v1/jobs/{job_id}/download
```

- **Streaming Architecture**: The endpoint uses HTTP chunked transfer encoding (64 KB chunks) via `StreamingResponse`, spooling through an uncompressed `zipfile.ZipFile` with `compression=zipfile.ZIP_STORED`.
- **Zero Compression Overhead**: Using `ZIP_STORED` avoids CPU-intensive re-compression of already-compressed files (PDFs, PNGs, and JPEGs), maximizing network streaming throughput.
- **Archive Filename**: Named after the sanitized job title: `<Sanitized_Title>.zip`. If the job title was omitted (common for custom templates), it defaults to `certificates_{job_id}.zip`.
- **Archive Contents**: Includes all certificates with `status == 'succeeded'`. Certificates that failed validation or rendering are excluded. Member filenames inside the ZIP match each certificate's deduplicated `file_name`.

---

## Technical Design Decisions

### 1. Unified Pillow Rendering Engine vs. ReportLab & Headless Browsers

The service uses Pillow 10.x exclusively for all template types (built-in procedural canvases and custom uploaded backgrounds) and all export formats (PDF, PNG, JPG).

#### Rationale
- **Container Build & Startup Speed**: ReportLab requires compiling C extensions (`_rl_accel`), which can substantially increase container build times or fail on slim Alpine/Debian base images. Headless browser engines (Puppeteer, Playwright, Chrome) require hundreds of megabytes of binary dependencies and consume 150–300 MB of RAM per concurrent worker. Pillow installs in seconds via pre-compiled manylinux wheels and operates with minimal memory overhead.
- **Cross-Format Parity**: Drawing the canvas once in Pillow ensures visual parity between PDF, PNG, and JPG exports.
- **Canvas Caching**: During a batch job, the background image (or built-in canvas background) is decoded from storage into memory once. Workers invoke `image.copy()` per recipient, eliminating redundant disk I/O and image decoding overhead.

#### The Tradeoff: Non-Selectable PDF Text
Because Pillow converts images to PDF by embedding the rasterized bitmap canvas into a PDF page wrapper, text glyphs are baked into the pixel grid. **Text in output PDFs is not selectable, searchable, or copyable in PDF viewers.**

#### ReportLab Upgrade Path
For enterprise environments requiring selectable vector text, font embedding, or PDF/A compliance, ReportLab can be introduced as a dedicated PDF renderer:
1. The existing layout parameters (`name_x`, `name_y`, `font`, `font_size_pct`, `color`) map to ReportLab coordinate points ($pt$).
2. The background image can be drawn onto the ReportLab canvas via `canvas.drawImage(bg_path, 0, 0, width=W_pts, height=H_pts)`.
3. TrueType fonts can be registered via `reportlab.pdfbase.ttfonts.TTFont` and drawn with `canvas.drawCentredString(X_pts, Y_pts, name)`.
4. Because the codebase decouples job orchestration, database state, and rendering via `app/services/certificate_renderer.py`, adding ReportLab requires modifying only the rendering module without altering API schemas or background workers.

---

### 2. Template Snapshotting on Jobs (`job.layout_snapshot`)

When a job is accepted (`POST /api/v1/jobs`), the system copies the template's current layout configuration, background path, kind, and `required_fields` into `job.layout_snapshot` (stored as JSON in the database row).

#### Immutability Guarantee
The background worker renders certificates using `job.layout_snapshot`, never reading live rows from the `templates` table. If an administrator later updates a template's font, moves coordinates, uploads a new background image, or soft-deletes the template, in-flight jobs and historical certificates remain unaffected and reproducible.

---

### 3. Two-Level Validation Strategy

Bulk batch operations frequently fail if a single bad record causes the entire transaction to abort. The system addresses this with two tiers of validation:

- **Level 1 (Structural HTTP Validation)**: Managed by Pydantic schemas. Requests with missing required parameters, invalid JSON types, non-existent template IDs, or recipient lists exceeding 10,000 records are rejected immediately with HTTP 422.
- **Level 2 (Business Rule Recipient Validation)**: Evaluated per recipient during job ingestion (`app/services/job_service.py:validate_recipient_data`).
  - Recipient name must be non-empty and $\le 200$ characters.
  - Recipient email is optional; if supplied, it is validated against standard RFC syntax.
  - If a recipient record fails Level 2 validation, that individual certificate is saved as `status="failed"` with a specific error message (e.g. `"Invalid email format: 'not-an-email'"`).
  - Valid recipients in the same batch are marked `status="pending"`. The job proceeds without failing the entire batch.

---

### 4. Progress Tracking via Aggregates

Job progress is computed on the fly using grouped database counts:

```sql
SELECT status, COUNT(id) FROM certificates WHERE job_id = :job_id GROUP BY status;
```

Stored counters on job records frequently desynchronize due to concurrent worker writes, crashes, or retries. Aggregating directly over the certificate rows guarantees a single source of truth. The derived job status (`queued`, `processing`, `completed`, `completed_with_errors`, `failed`) is calculated deterministically from these counts.

---

### 5. Worker Concurrency & Crash Recovery

- **Atomic Row Claiming**: Worker threads claim pending certificates in batches using an atomic SQL update:
  ```sql
  UPDATE certificates
  SET status = 'processing', updated_at = :now
  WHERE id IN (
      SELECT id FROM certificates
      WHERE job_id = :job_id AND status = 'pending'
      LIMIT :batch_size
      FOR UPDATE SKIP LOCKED
  );
  ```
  This prevents duplicate processing across concurrent worker threads.
- **Crash Recovery**: If the application crashes during execution, certificates may remain stuck in `processing`. On startup, `recover_stuck_certificates()` resets all `processing` certificates back to `pending` and re-queues their jobs in the worker pool.

---

## API Reference

### Templates

#### List Templates
```http
GET /api/v1/templates
```
Returns all active templates with their `kind`, `layout`, and `required_fields`.

#### Template Preview
```http
GET /api/v1/templates/{id}/preview?name=Jane+Doe
```
Returns a sample rendered PNG certificate for the given template.

#### Upload Custom Template
```http
POST /api/v1/templates/custom
Content-Type: multipart/form-data
```

| Field | Type | Description |
|---|---|---|
| `name` | string | Friendly name for the template |
| `image` | file | PNG or JPEG background image ($\le 10$ MB, $\le 25$M pixels) |
| `name_x` | float | Horizontal center percentage (`0.0`–`100.0`, default `50.0`) |
| `name_y` | float | Vertical center percentage (`0.0`–`100.0`, default `57.0`) |
| `font` | string | Bundled font key (`dejavu_sans`, `dejavu_serif`, `liberation_sans`, `liberation_serif`) |
| `font_size_pct` | float | Font size as percentage of image height (default `5.0`) |
| `color` | string | Hex color code (default `#1A202C`) |
| `max_width_pct` | float | Max width threshold percentage before auto-shrinking (default `70.0`) |

---

### Jobs

#### Submit Generation Job
```http
POST /api/v1/jobs
Content-Type: application/json
Idempotency-Key: optional-uuid-or-token
```

```json
{
  "template_id": "8c599ca2-7f21-4d1e-8fe5-1f92e59e414c",
  "title": "Machine Learning Certification",
  "organization_name": "Tech Institute",
  "issued_date": "2026-10-12",
  "output_format": "pdf",
  "recipients": [
    { "name": "Jane Doe", "email": "jane@example.com" },
    { "name": "John Smith" },
    { "name": "Carlos Gomez", "email": "invalid-email" }
  ]
}
```

*Note: For custom templates, `title`, `organization_name`, and `issued_date` may be omitted.*

**Response (HTTP 202 Accepted)**:
```json
{
  "id": "c7a83d34-f8b1-4bb2-b5e0-1c0eb7d65681",
  "status": "queued",
  "status_url": "/api/v1/jobs/c7a83d34-f8b1-4bb2-b5e0-1c0eb7d65681"
}
```

#### Get Job Progress & Status
```http
GET /api/v1/jobs/{id}
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
      "email": "invalid-email",
      "error_message": "Invalid email format: 'invalid-email'."
    }
  ]
}
```

#### Download All Certificates (ZIP)
```http
GET /api/v1/jobs/{id}/download
```
Streams an uncompressed ZIP archive containing all succeeded certificates named after the sanitized job title.

#### Download Single Certificate
```http
GET /api/v1/certificates/{id}/download
```
Returns individual certificate file with `Content-Disposition: attachment; filename="{file_name}"`.

---

## Known Limitations

1. **Single Dynamic Placeholder**: Custom templates currently support placing a single dynamic text field: the recipient name. Static certificate text (course title, issue date, instructor signature labels, accreditation notices) must be flattened directly into the background image before uploading.
2. **One Font Family per Template**: The recipient name on a template is rendered using a single font family selected from the bundled OFL font registry. Multi-font styling or inline Markdown within the recipient name is not supported.
3. **Non-Selectable PDF Text**: As detailed in the rendering design section, output PDFs contain rasterized bitmap image data. Text cannot be highlighted, searched, or copied in PDF viewers. Environments requiring selectable vector text should follow the ReportLab upgrade path.
