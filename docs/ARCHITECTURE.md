# DocManFu Architecture

## Overview

DocManFu is a self-hosted document management system built as a set of cooperating services. Documents are uploaded, OCR-processed, and optionally analyzed by AI — all running on your own hardware.

## Services

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Frontend (Svelte + UnoCSS)                                 │
│  - SvelteKit SPA served by nginx                            │
│  - Proxies /api/ requests to backend                        │
│  - PDF viewer with search highlights                        │
│  Dev: port 5180 │ Prod: port 8080                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  API Server (FastAPI + Uvicorn)                             │
│  - REST API with JWT authentication                         │
│  - Document CRUD, search, upload, download                  │
│  - Job status tracking (SSE-compatible)                     │
│  - Pydantic request/response validation                     │
│  - Swagger UI at /docs                                      │
│  Dev: port 8100 │ Prod: behind nginx proxy                  │
└──────────┬──────────────────────────────┬───────────────────┘
           │                              │
┌──────────▼──────────┐    ┌──────────────▼───────────────────┐
│  PostgreSQL          │    │  Redis                           │
│  - Document metadata │    │  - Celery task broker             │
│  - User accounts     │    │  - Task result backend            │
│  - Processing jobs   │    │                                   │
│  - Tags & relations  │    │  Dev: port 6390                   │
│  Dev: port 5450      │    │  Prod: internal only              │
│  Prod: internal only │    └──────────────┬───────────────────┘
└─────────────────────┘                    │
                                ┌──────────▼───────────────────┐
                                │  Celery Worker                │
                                │  - OCR processing (ocrmypdf)  │
                                │  - AI analysis task            │
                                │  - Job progress tracking       │
                                │  - Auto-retry on failure       │
                                └──────────┬───────┬───────────┘
                                           │       │
                                    ┌──────▼┐   ┌──▼──────────┐
                                    │ OCR   │   │ AI Provider  │
                                    │ocrmypdf│   │ OpenAI /     │
                                    │Tesseract│   │ Anthropic /  │
                                    │Ghostscript│ │ Ollama       │
                                    └───────┘   └──────────────┘
```

## Data Flow

### Document Upload

```
Client                API                  Database             Worker
  │                    │                      │                    │
  │── POST /upload ───▶│                      │                    │
  │                    │── Create Document ──▶│                    │
  │                    │── Create OCR Job ───▶│                    │
  │                    │── Store PDF file     │                    │
  │                    │── Dispatch task ─────┼───────────────────▶│
  │◀── 200 + job_id ──│                      │                    │
  │                    │                      │                    │
  │                    │                      │◀── Mark started ───│
  │                    │                      │                    │── Run ocrmypdf
  │                    │                      │◀── Update progress─│
  │                    │                      │                    │── Extract text
  │                    │                      │◀── Save text ──────│
  │                    │                      │◀── Mark complete ──│
  │                    │                      │                    │
  │                    │                      │   (if AI enabled)  │
  │                    │                      │◀── Create AI job ──│
  │                    │                      │                    │── Call AI API
  │                    │                      │◀── Save metadata ──│
  │                    │                      │◀── Create tags ────│
  │                    │                      │◀── Mark complete ──│
```

### Search

```
Client                API                  Database
  │                    │                      │
  │── GET /search?q= ▶│                      │
  │                    │── ILIKE query ──────▶│
  │                    │   (content_text,     │
  │                    │    original_name,     │
  │                    │    ai_generated_name) │
  │                    │◀── Results ──────────│
  │◀── Paginated ─────│                      │
```

## Processing Pipeline

### 1. Upload

The API validates the file (PDF only, size limit), stores it in `uploads/YYYY/MM/DD/{uuid}.pdf`, creates a `Document` record, and dispatches an OCR job via Celery.

### 2. OCR (ocrmypdf)

The worker runs `ocrmypdf` on the uploaded PDF to add a searchable text layer. It then extracts the text using `pdfminer.six` and saves it to `Document.content_text`. The original PDF is replaced with the searchable version.

Key behaviors:
- Pages with existing text layers are skipped (`skip_text=True`)
- Already-OCR'd PDFs are detected and handled gracefully
- Encrypted PDFs fail with a descriptive error
- `ocrmypdf` holds a global lock — one OCR per worker process. Scale with multiple worker processes.

### 3. AI Analysis

If `AI_PROVIDER` is configured and OCR extracted text, an AI analysis job is auto-dispatched. The AI receives the document text (truncated to `AI_MAX_TEXT_LENGTH`) and returns:

- `document_type` — Classification (bill, bank_statement, medical, etc.)
- `suggested_name` — Human-readable name with date
- `suggested_tags` — Relevant tags for organization
- `extracted_metadata` — Company, date, amount, account number, summary
- `confidence_score` — How confident the AI is in its analysis

The worker updates the document record and auto-creates tag records.

### 4. Vision Analysis

For image-heavy documents, the AI can also perform vision analysis using a multimodal model (e.g., `granite3.2-vision` for Ollama). This extracts information from charts, tables, and images that text extraction might miss.

## Database Schema

Core tables:

- **documents** — PDF metadata, extracted text, AI results, soft-delete support
- **tags** — Name + color, many-to-many with documents via `document_tags`
- **processing_jobs** — Job type, status, progress (0-100), error messages, results
- **users** — Authentication (email, hashed password, role, API key)
- **admin_settings** — Key-value configuration store

All primary keys are UUIDs. Documents and users use `TimestampMixin` for `created_at`/`updated_at`.

## Authentication

JWT-based authentication with two roles:

- **admin** — Full access, user management, system settings
- **user** — Own documents only

API keys are supported for programmatic access (upload scripts, integrations).

The first user to register becomes the admin. Subsequent registrations can be disabled via admin settings.

## AI Provider Abstraction

The `ai_provider.py` module provides a unified interface across providers:

```
analyze_document(text, provider, model, ...) → dict
```

Provider SDKs are imported lazily — only the configured provider's SDK needs to be installed. Ollama reuses the OpenAI SDK with a custom base URL.

## File Storage

Uploaded PDFs are stored on disk at `{UPLOAD_DIR}/YYYY/MM/DD/{uuid}.pdf`. The date-based directory structure prevents any single directory from accumulating too many files. Files are never moved after upload — the path is recorded in the database.

## Deployment Topology

### Development

All services run in Docker via `docker-compose.dev.yml` with hot-reload enabled. Source code is bind-mounted into containers.

### Production

Multi-stage Docker images keep the final images small. Services communicate over a Docker network — only the frontend (nginx) port is exposed. The `migrate` init container runs Alembic migrations before the API starts.

See [Deployment Guide](DEPLOYMENT.md) for full production setup instructions.
