# Contributing to DocManFu

Thanks for your interest in contributing! This guide covers how to set up a development environment, our coding conventions, and how to submit changes.

## Development Setup

### Docker (recommended)

```bash
git clone https://github.com/docmanfu/docmanfu.git && cd docmanfu
./dev              # Start all services with hot-reload
./dev migrate      # Run database migrations
./dev seed         # Load sample data
```

Services start at: frontend (`:5180`), API (`:8100`), PostgreSQL (`:5450`), Redis (`:6390`).

### Local (without Docker)

You need Python 3.11+, Node.js 18+, PostgreSQL, Redis, Tesseract, and Ghostscript.

```bash
# Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env  # Edit with your DB/Redis URLs
alembic upgrade head
uvicorn app.main:app --reload

# Worker (separate terminal)
celery -A app.core.celery_app:celery_app worker --loglevel=info

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

This runs black, ruff, and prettier automatically on commit.

## Project Structure

```
app/                    # Python backend
  api/                  # FastAPI route handlers
  core/                 # Config, Celery, AI provider
  db/                   # Database session, base classes
  models/               # SQLAlchemy models
  tasks/                # Celery background tasks (OCR, AI)
alembic/                # Database migrations
frontend/               # Svelte SPA
  src/
    lib/components/     # Reusable Svelte components
    routes/             # SvelteKit page routes
scripts/                # Utility scripts (seed, backup, restore)
docs/                   # Documentation
```

## Coding Conventions

### Python (Backend)

- **Formatter:** [black](https://github.com/psf/black) (line length 88)
- **Linter:** [ruff](https://github.com/astral-sh/ruff) (rules: E, F, W, I)
- All primary keys are UUIDs
- Models inherit from `UUIDMixin` and `TimestampMixin` (in `app/db/base.py`)
- Documents use soft deletes (`deleted_at`) — never hard delete
- New models must be exported from `app/models/__init__.py` and imported in `alembic/env.py`

```bash
black app/               # Format
ruff check app/           # Lint
ruff check app/ --fix     # Auto-fix lint issues
```

### Frontend (Svelte)

- **Formatter:** [prettier](https://prettier.io/) with Svelte plugin
- **No JSX** — Svelte components only (`.svelte` files)
- UnoCSS for styling (utility classes)
- TypeScript for type safety

```bash
cd frontend
npx prettier --check src/    # Check formatting
npx prettier --write src/    # Fix formatting
npm run check                # Type checking (svelte-check)
```

### General

- Keep changes minimal and focused — don't refactor unrelated code
- Use existing patterns — look at how similar features are implemented
- No unnecessary abstractions

## Database Migrations

When changing models:

```bash
# Create migration
alembic revision -m "add column to documents"

# Edit the generated file in alembic/versions/
# Fill in upgrade() and downgrade()

# Apply
alembic upgrade head
```

## Submitting Changes

### Branch Naming

- `feature/short-description` — New features
- `fix/short-description` — Bug fixes
- `docs/short-description` — Documentation changes

### Commit Messages

Write concise commit messages that explain *why*, not just *what*:

```
Add bill tracking with due date alerts

Track bill amounts, due dates, and payment status.
Auto-extract from AI metadata when document_type is "bill".
```

### Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Make your changes with clear, focused commits
3. Ensure linting passes: `black --check app/ && ruff check app/`
4. Ensure the frontend builds: `cd frontend && npm run build`
5. Open a PR against `main` using the [PR template](.github/PULL_REQUEST_TEMPLATE.md)
6. Describe what changed and why in the PR description
7. Link related issues (e.g., "Closes #42")

### What Makes a Good PR

- Small and focused — one feature or fix per PR
- Includes migration if database changes are needed
- Doesn't break existing functionality
- Follows the existing code style

## Reporting Bugs

Use the [bug report template](https://github.com/docmanfu/docmanfu/issues/new?template=bug_report.md) on GitHub. Include:

- Steps to reproduce
- Expected vs. actual behavior
- Environment info (OS, Docker version, browser)
- Relevant logs (`./dev logs api` or `./dev logs worker`)

## Requesting Features

Use the [feature request template](https://github.com/docmanfu/docmanfu/issues/new?template=feature_request.md) on GitHub.

## Code of Conduct

Be respectful and constructive. We're building this together.

## Questions?

Open a [discussion](https://github.com/docmanfu/docmanfu/discussions) or file an issue.
