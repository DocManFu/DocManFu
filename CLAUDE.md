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
    documents.py        # POST /api/documents/upload — PDF file upload
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

### FastAPI & API
- App entry point is `app/main.py` — run with `uvicorn app.main:app --reload`
- CORS middleware is configured from `settings.CORS_ORIGINS`
- Unhandled exceptions return `{"detail": "Internal server error"}` (500) and are logged
- DB sessions in routes use `Depends(get_db)` from `app/db/deps.py`
- New routers go in `app/api/` and are included via `app.include_router()` in `main.py`
- Swagger UI auto-generated at `/docs`, ReDoc at `/redoc`
- **POST /api/documents/upload** — accepts PDF `UploadFile`, validates extension + MIME type, stores in `{UPLOAD_DIR}/YYYY/MM/DD/{uuid}.pdf`, creates `Document` DB record. Returns 400 for non-PDF, 413 for oversized files.

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
alembic upgrade head                  # Run migrations
alembic revision -m "description"     # Create new migration
python scripts/seed_data.py           # Load sample data
```

## Rules
- Don't commit to git unless explicitly told to
- Don't add unnecessary abstractions — keep it simple
- When adding new models, export them from `app/models/__init__.py` and import in `alembic/env.py`
