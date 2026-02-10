# DocManFu - Claude Code Instructions

## Project Overview
Self-hosted AI-powered document management system (Evernote replacement). Python/FastAPI backend, Svelte frontend, PostgreSQL, Celery/Redis workers. See `DEVELOPMENT_PLAN.md` for the full 12-session roadmap.

## Tech Stack
- **Backend**: Python 3 / FastAPI
- **Database**: PostgreSQL (UUID primary keys everywhere)
- **ORM**: SQLAlchemy 2.x with Alembic migrations
- **Frontend**: Svelte — **NO JSX, ever**
- **Queue**: Celery + Redis
- **OCR**: ocrmypdf
- **AI**: Configurable providers (OpenAI, Anthropic, local)
- **Config**: pydantic-settings reading from `.env`

## Project Structure
```
app/
  main.py               # FastAPI app entry point (CORS, error handling, logging)
  core/config.py        # Pydantic Settings (DATABASE_URL, CORS_ORIGINS, LOG_LEVEL, etc.)
  db/base.py            # DeclarativeBase, UUIDMixin, TimestampMixin
  db/session.py         # engine + SessionLocal factory
  db/deps.py            # get_db() dependency for FastAPI route injection
  models/               # SQLAlchemy models (document, tag, processing_job)
  api/                  # FastAPI routers
    health.py           # GET /health — app + DB status check
    documents.py        # Document CRUD, search, upload, download, reprocess
    jobs.py             # GET /api/jobs/{job_id}/status — job progress tracking
  tasks/                # Celery background tasks
    base.py             # DocManFuTask base class with DB job tracking
    ocr.py              # OCR processing task (ocrmypdf + pdfminer text extraction)
    ai_analysis.py      # AI analysis task (classifies docs, suggests names/tags)
  core/ai_provider.py   # AI provider abstraction (OpenAI, Anthropic)
    file_organization.py # File org task (stub — future session)
  core/celery_app.py    # Celery app instance and configuration
alembic/                # Migrations
  versions/             # Migration scripts
uploads/                # Uploaded files stored as {YYYY}/{MM}/{DD}/{uuid}.pdf
scripts/
  seed_data.py          # Sample data fixtures
```

## Key Conventions

### Database & Models
- All primary keys are **UUIDs** (`uuid4`)
- All models inherit from `UUIDMixin` (in `app/db/base.py`) for the `id` column
- Models with timestamps use `TimestampMixin` for `created_at`/`updated_at`
- Documents use **soft deletes** (`deleted_at` column) — never hard delete documents
- Enums for `JobType` (ocr, ai_analysis, file_organization) and `JobStatus` (pending, processing, completed, failed) in `app/models/processing_job.py`
- Association table `document_tags` for many-to-many Document <-> Tag

### Configuration
- App config lives in `app/core/config.py` using `pydantic_settings.BaseSettings`
- Environment variables loaded from `.env` file (see `.env.example` for template)
- Alembic reads DATABASE_URL from app config (set dynamically in `alembic/env.py`), not from `alembic.ini`
- `CORS_ORIGINS` is a JSON list of allowed origins (default: `["http://localhost:5173"]`)
- `LOG_LEVEL` controls Python logging verbosity (default: `INFO`)
- `UPLOAD_DIR` is the base directory for uploaded files (default: `uploads/`)
- `MAX_FILE_SIZE_MB` is the maximum upload file size in megabytes (default: `50`)
- `REDIS_URL` is the Redis connection string for Celery broker/backend (default: `redis://localhost:6379/0`)
- `CELERY_TASK_MAX_RETRIES` is the max retry count for failed tasks (default: `3`)
- `CELERY_TASK_RETRY_DELAY` is the delay in seconds between retries (default: `60`)
- `OCR_LANGUAGE` is the Tesseract language code(s), use `+` to combine (default: `eng`, e.g. `eng+fra`)
- `OCR_DPI` is the resolution for rasterizing image-only pages during OCR (default: `300`)
- `OCR_SKIP_TEXT` skips OCR on pages that already contain text (default: `true`)
- `OCR_CLEAN` removes intermediate files after OCR processing (default: `true`)
- `AI_PROVIDER` selects the AI backend: `"openai"`, `"anthropic"`, or `"none"` to disable (default: `none`)
- `AI_API_KEY` is the API key for the selected AI provider (required when AI_PROVIDER is not "none")
- `AI_MODEL` overrides the default model name (defaults: `gpt-4o-mini` for OpenAI, `claude-sonnet-4-5-20250929` for Anthropic)
- `AI_MAX_TEXT_LENGTH` caps document text sent to the AI to control costs (default: `4000` chars)
- `AI_TIMEOUT` is the max seconds to wait for an AI API response (default: `60`)

### FastAPI & API
- App entry point is `app/main.py` — run with `uvicorn app.main:app --reload`
- CORS middleware is configured from `settings.CORS_ORIGINS`
- Unhandled exceptions return `{"detail": "Internal server error"}` (500) and are logged
- DB sessions in routes use `Depends(get_db)` from `app/db/deps.py`
- New routers go in `app/api/` and are included via `app.include_router()` in `main.py`
- Swagger UI auto-generated at `/docs`, ReDoc at `/redoc`
- **GET /api/documents** — list documents with pagination (offset/limit, max 100), filtering (document_type, tag name, date_from, date_to), and sorting (upload_date|name|size|type, asc|desc). Returns `PaginatedResponse` with `documents`, `total`, `offset`, `limit`. Excludes soft-deleted documents.
- **GET /api/documents/search** — full-text search via ILIKE across `content_text`, `original_name`, and `ai_generated_name`. Required `q` param. Supports same `document_type` and `tag` filters. Returns `PaginatedResponse`.
- **GET /api/documents/{id}** — single document with full metadata including `content_text`, `ai_metadata`, `created_at`, `updated_at`, and tags. Returns `DocumentDetail`. 404 if not found or soft-deleted.
- **PUT /api/documents/{id}** — update `original_name` and/or `tags` (list of tag name strings). Tags are found-or-created (default color `#6B7280`). Setting `tags` replaces all existing tags. Returns updated `DocumentDetail`.
- **DELETE /api/documents/{id}** — soft-delete (sets `deleted_at`). Returns `{"detail": "Document deleted"}`.
- **GET /api/documents/{id}/download** — streams the PDF file via `FileResponse`. Uses `ai_generated_name.pdf` as download filename when available, otherwise `original_name`. 404 if file missing from disk.
- **POST /api/documents/{id}/reprocess** — creates new OCR job and dispatches Celery task. AI analysis auto-follows OCR when `AI_PROVIDER` is configured. 404 if file missing from disk. Returns list of created jobs.
- **POST /api/documents/upload** — accepts PDF `UploadFile`, validates extension + MIME type, stores in `{UPLOAD_DIR}/YYYY/MM/DD/{uuid}.pdf`, creates `Document` DB record, creates OCR `ProcessingJob`, and dispatches Celery task. Returns 400 for non-PDF, 413 for oversized files. Response includes `job_id` for tracking.
- **GET /api/jobs/{job_id}/status** — returns job status, progress (0-100), error_message, and result_data
- Route ordering in `documents.py`: `/search` and `/upload` are defined **before** `/{document_id}` to prevent FastAPI from parsing path literals as UUIDs
- List/search queries use `selectinload(Document.tags)` to eagerly load tags without affecting pagination counts
- Pydantic response models use `model_config = {"from_attributes": True}` for ORM-to-schema conversion

### Background Tasks (Celery)
- Celery app defined in `app/core/celery_app.py` with Redis as broker and backend
- All tasks inherit from `DocManFuTask` (in `app/tasks/base.py`) which provides DB job tracking
- Tasks auto-discover from `app/tasks/` package
- Each task receives `job_id` and `document_id` as string UUIDs
- `DocManFuTask` provides: `mark_job_started()`, `update_job_progress()`, `mark_job_completed()`, `mark_job_failed()`
- Failed tasks auto-retry up to `CELERY_TASK_MAX_RETRIES` times with `CELERY_TASK_RETRY_DELAY` seconds between attempts
- On final failure, `on_failure` callback marks the ProcessingJob as failed with the error message
- ProcessingJob has `celery_task_id` (links to Celery) and `result_data` (JSON for task output)
- Document upload auto-dispatches OCR task; OCR auto-dispatches AI analysis when `AI_PROVIDER` is configured and text was extracted

### OCR Pipeline (`app/tasks/ocr.py`)
- Uses `ocrmypdf` (Python library) for OCR processing and `pdfminer.six` for text extraction
- **System deps required**: `tesseract` and `ghostscript` must be on PATH
- Pipeline: validate file → run ocrmypdf → extract text with pdfminer → replace original PDF with searchable version → update `Document.content_text` and `processed_date`
- OCR output goes to a temp file in the same directory, then atomically replaces the original on success
- Handles `PriorOcrFoundError` (already OCR'd), `EncryptedPdfError`, and `InputFileError` gracefully — marks job as failed with descriptive message instead of retrying
- `ocrmypdf.ocr()` `language` param takes a list of strings; the `OCR_LANGUAGE` config is split on `+` before passing
- `skip_text=True` means pages with existing text layers are passed through without re-OCR
- Text extraction uses `pdfminer.high_level.extract_text()` — falls back to empty string on failure
- Page count uses `pdfminer.pdfpage.PDFPage.get_pages()`
- Result data includes: `document_id`, `pages_processed`, `text_length`, `text_extracted` (bool)
- **Note**: `ocrmypdf.ocr()` holds a global threading lock — only one OCR task runs per Python process. Scale with multiple Celery worker processes, not threads

### AI Analysis Pipeline (`app/tasks/ai_analysis.py` + `app/core/ai_provider.py`)
- Automatically dispatched after OCR completes (when `AI_PROVIDER != "none"` and text was extracted)
- **Provider module** (`app/core/ai_provider.py`): abstraction over OpenAI and Anthropic with a common `analyze_document()` function
- Provider SDKs imported lazily inside the call functions so they aren't required at import time
- Prompt asks AI to return a JSON object with: `document_type`, `suggested_name`, `suggested_tags`, `extracted_metadata`, `confidence_score`
- Supported document types: bill, bank_statement, medical, insurance, tax, invoice, receipt, legal, correspondence, report, other
- `suggested_name` format: `YYYY-MM-DD_Company_DocumentType` (no extension)
- `extracted_metadata` includes: company, date, amount, account_number, summary
- Task updates `Document.ai_generated_name`, `Document.document_type`, and `Document.ai_metadata` (JSON)
- Auto-creates `Tag` records for suggested tags (default color `#6B7280`) and associates them with the document
- `ValueError` from provider (missing config/key) marks job as failed without retrying; other exceptions trigger normal retry logic
- Result data in ProcessingJob includes: `document_id`, `suggested_name`, `document_type`, `suggested_tags`, `extracted_metadata`, `confidence_score`
- OpenAI uses `response_format={"type": "json_object"}` for structured output; Anthropic relies on prompt instructions
- Document text is truncated to `AI_MAX_TEXT_LENGTH` characters before sending to the AI

### Migrations
- Use Alembic for all schema changes: `alembic revision -m "description"` then fill in upgrade/downgrade
- All models must be imported in `alembic/env.py` for autogenerate to detect them
- Run migrations: `alembic upgrade head`

### Python Environment
- Virtual env in `venv/` (activate with `source venv/bin/activate`)
- Dependencies in `requirements.txt` — install with `pip install -r requirements.txt`

## Development Commands
```bash
source venv/bin/activate              # Activate venv
pip install -r requirements.txt       # Install deps
uvicorn app.main:app --reload         # Run dev server (http://localhost:8000)
celery -A app.core.celery_app:celery_app worker --loglevel=info  # Run Celery worker
alembic upgrade head                  # Run migrations
alembic revision -m "description"     # Create new migration
python scripts/seed_data.py           # Load sample data
```

## Rules
- Don't commit to git unless explicitly told to
- Don't add unnecessary abstractions — keep it simple
- When adding new models, export them from `app/models/__init__.py` and import in `alembic/env.py`
