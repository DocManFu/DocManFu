# DocManFu - Development Plan 📄🦞🥋

## Project Overview

**DocManFu** - Master Your Documents!
Self-hosted document management system to replace Evernote:

- Python/FastAPI backend with background workers
- Svelte frontend (NO JSX!)
- AI-powered document analysis and naming
- OCR integration with existing workflow
- Open source for community use

---

## Session 1: Database Design & Models

**Goal:** Define data models and database schema

**Claude Code Instructions:**

```
I'm building DocManFu - a self-hosted document management system to replace Evernote.

Tech stack: Python/FastAPI, PostgreSQL, background workers (Celery/Redis)

Create the database models for:
- Documents (id, filename, original_name, content_text, ai_generated_name, file_path, mime_type, file_size, upload_date, processed_date)
- Tags (id, name, color)
- Document-Tag relationships (many-to-many)
- Processing Jobs (id, document_id, status, progress, error_message, created_at, completed_at)

Use SQLAlchemy ORM with Alembic migrations. Include sample data fixtures.
```

**Deliverable:** Database schema, models.py, initial migration

---

## Session 2: Basic FastAPI Setup

**Goal:** Core API structure with health checks

**Claude Code Instructions:**

```
Set up FastAPI project structure with:
- main.py with FastAPI app
- /health endpoint
- Database connection setup (PostgreSQL)
- Environment configuration (.env support)
- CORS for frontend
- Basic error handling middleware
- Logging configuration

Project structure:
/app
  /api
  /models
  /core
  /db
  main.py
requirements.txt
.env.example
```

**Deliverable:** Working FastAPI app with database connection

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 3: File Upload & Storage

**Goal:** Handle file uploads with validation

**Claude Code Instructions:**

```
Create file upload system:
- POST /api/documents/upload endpoint
- Accept PDF files only (validate MIME type and extension)
- Store files in organized directory structure: /uploads/YYYY/MM/DD/
- Generate unique filenames to avoid conflicts
- Save document metadata to database
- File size limits and validation
- Return document ID and upload confirmation

Include proper error handling for:
- Invalid file types
- File size limits
- Storage errors
- Database save failures
```

**Deliverable:** File upload endpoint with validation and storage

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 4: Background Job System

**Goal:** Set up Celery for async processing

**Claude Code Instructions:**

```
Set up background job processing with Celery + Redis:
- Celery configuration and worker setup
- Redis connection and task queue
- Job status tracking in database
- Progress updates during processing
- GET /api/jobs/{job_id}/status endpoint
- Error handling and retry logic
- Task result storage

Create base task structure for document processing pipeline:
1. OCR processing task
2. AI analysis task
3. File organization task
```

**Deliverable:** Working Celery setup with job tracking

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 5: OCR Integration

**Goal:** Add OCR processing to background jobs

**Claude Code Instructions:**

```
Integrate OCR processing using ocrmypdf:
- Install and configure ocrmypdf
- Create Celery task for OCR processing
- Handle OCR errors gracefully
- Extract text content from PDFs
- Save OCR results to database
- Update job progress during OCR
- Handle non-text PDFs (image-only scans)

OCR task should:
- Take document ID as input
- Run ocrmypdf on uploaded file
- Extract text content
- Save searchable PDF
- Update document record with extracted text
- Mark OCR job as complete
```

**Deliverable:** Working OCR pipeline with progress tracking

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 6: AI Analysis & Smart Naming

**Goal:** AI-powered document analysis

**Claude Code Instructions:**

```
Add AI analysis for smart document naming:
- Support multiple AI providers (OpenAI, Anthropic, local models)
- Configurable AI provider in settings
- Document classification (bill, bank statement, medical, etc.)
- Extract key metadata (company, date, amount, account numbers)
- Generate intelligent filenames based on content
- Suggest relevant tags
- Handle AI API errors and fallbacks

AI prompt engineering for document types:
- Electric/gas bills
- Bank statements
- Medical documents
- Insurance documents
- Tax documents
- General correspondence

Return structured data: suggested_name, document_type, extracted_metadata, confidence_score
```

**Deliverable:** AI analysis pipeline with smart naming

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 7: Document Management API

**Goal:** CRUD operations for documents

**Claude Code Instructions:**

```
Create full document management API:
- GET /api/documents - list documents with filtering/pagination
- GET /api/documents/{id} - get single document with metadata
- PUT /api/documents/{id} - update document (name, tags)
- DELETE /api/documents/{id} - soft delete document
- GET /api/documents/{id}/download - download original file
- GET /api/documents/search - full-text search
- POST /api/documents/{id}/reprocess - trigger reprocessing

Include:
- Pagination with cursor-based or offset/limit
- Filtering by date, document type, tags
- Search across document text content
- Sorting options (date, name, relevance)
```

**Deliverable:** Complete document management API

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 8: Svelte Frontend - Basic UI

**Goal:** Document viewing interface

**Claude Code Instructions:**

```
Create Svelte frontend for document management:
- Document list view with pagination
- Document detail view with metadata
- Search functionality with filters
- File upload interface with drag/drop
- Processing status indicators
- Basic responsive design

NO JSX - use Svelte syntax only!

Pages needed:
- /documents - main list view
- /documents/{id} - document detail
- /upload - upload interface
- /search - search results

Use modern CSS or a CSS framework like Tailwind.
Include real-time updates for processing status.
```

**Deliverable:** Basic Svelte frontend with document management

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 9: Upload Script & CLI

**Goal:** Batch upload automation

**Claude Code Instructions:**

```
Create Python script to replace current manual workflow:
- Monitor specified directory for PDF files
- Upload files in batches to API
- Show upload progress and processing status
- Handle upload errors and retries
- Option to watch directory or process once
- Configuration file for API endpoint, directories
- Logging for troubleshooting

Script should replace current OCRmyPDF workflow:
- Read from /Users/dustin/Documents/PreEvernote
- Upload to web service instead of local processing
- Clean up uploaded files after confirmation
- Show processing status until completion

Include systemd service file for continuous monitoring.
```

**Deliverable:** Automated upload script with monitoring

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 10: Search & Advanced Features

**Goal:** Full-text search and tagging

**Claude Code Instructions:**

```
Add advanced search capabilities:
- Full-text search with PostgreSQL or Elasticsearch
- Advanced filtering (date ranges, document types, tags)
- Search result highlighting
- Saved searches/bookmarks
- Tag management (create, edit, delete, merge)
- Bulk operations (tag multiple documents, delete, reprocess)
- Document versioning (track changes)
- Export functionality (PDF, CSV metadata)

Frontend improvements:
- Advanced search interface
- Tag management UI
- Bulk selection and operations
- Keyboard shortcuts
- Dark mode toggle
```

**Deliverable:** Advanced search and document management features

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 11: Authentication & Multi-User

**Goal:** User management and security

**Claude Code Instructions:**

```
Add authentication and multi-user support:
- JWT-based authentication
- User registration and login
- Password hashing (bcrypt)
- User roles (admin, user, read-only)
- Document ownership and permissions
- API key authentication for upload scripts
- Rate limiting on endpoints
- HTTPS configuration

Multi-tenancy:
- Users can only see their own documents
- Admin can manage all users and documents
- Shared documents/collections (optional)
- Storage quotas per user

Include middleware for auth protection and rate limiting.
```

**Deliverable:** Secure multi-user system

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Session 12: Docker & Deployment

**Goal:** Production deployment setup

**Claude Code Instructions:**

```
Create production deployment configuration:
- Multi-stage Dockerfiles (backend, frontend, workers)
- docker-compose.yml with all services
- nginx reverse proxy configuration
- Environment-based configuration
- Health checks for all services
- Log aggregation setup
- Database backup scripts
- SSL certificate setup (Let's Encrypt)

Services needed:
- FastAPI backend
- Celery workers
- Redis broker
- PostgreSQL database
- Svelte frontend (nginx)
- nginx reverse proxy

Include documentation for:
- Initial setup
- Environment configuration
- Backup/restore procedures
- Scaling workers
```

**Deliverable:** Complete deployment setup with documentation

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Final Session: Documentation & Open Source Prep

**Goal:** Project documentation and GitHub setup

**Claude Code Instructions:**

```
Prepare DocManFu for open source release:
- Comprehensive README.md with setup instructions
- API documentation (OpenAPI/Swagger)
- Contribution guidelines
- License file (MIT/Apache)
- Docker quick-start guide
- Configuration documentation
- Troubleshooting guide
- Screenshots and demo
- Architecture documentation
- Performance tuning guide

GitHub setup (github.com/docmanfu/docmanfu):
- Issue templates
- Pull request templates
- GitHub Actions for CI/CD
- Automated testing setup
- Code formatting (black, prettier)
- Security scanning
```

**Deliverable:** Complete open source project ready for release

When you're done, update CLAUDE.md with information that will be useful for you in the future to fix and/or enhance this application.

---

## Notes for Each Session:

1. **Keep context:** Save important code/decisions between sessions
2. **Test thoroughly:** Each session should have working functionality
3. **Document decisions:** Why certain approaches were chosen
4. **Progressive enhancement:** Each session builds on previous work
5. **Stay focused:** Don't try to do everything in one session

**Estimated timeline:** 12-15 sessions over 2-3 weeks

Ready to start with Session 1? 🚀
