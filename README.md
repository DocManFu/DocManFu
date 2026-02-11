<div align="center">

![DocManFu Logo](assets/images/logo.png)

# DocManFu

**Master Your Documents**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/docmanfu/docmanfu/actions/workflows/ci.yml/badge.svg)](https://github.com/docmanfu/docmanfu/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)

Self-hosted AI-powered document management system. Replace expensive cloud services with your own private, intelligent document vault.

</div>

---

## Features

- **AI Document Analysis** — Automatically classifies documents (bills, statements, medical, tax, etc.), suggests intelligent names, and extracts metadata
- **OCR Processing** — Converts scanned PDFs into searchable documents with full-text extraction
- **Smart Search** — Find documents by content, name, type, tags, or date range
- **Auto-Tagging** — AI suggests relevant tags for organization
- **Bill Tracking** — Track bills with amounts, due dates, and payment status
- **Authentication** — JWT-based auth with admin and user roles
- **Self-Hosted** — Your documents stay on your hardware, under your control
- **Multiple AI Providers** — OpenAI, Anthropic, or Ollama (local/free)

## Screenshots

<!-- TODO: Add screenshots -->
*Coming soon — contributions welcome!*

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2

### Development

```bash
git clone https://github.com/docmanfu/docmanfu.git && cd docmanfu

# Start all services (API, frontend, database, Redis, worker)
./dev

# In another terminal: run migrations and seed sample data
./dev migrate
./dev seed
```

Open [http://localhost:5180](http://localhost:5180) in your browser.

Services: frontend (`:5180`), API (`:8100`), PostgreSQL (`:5450`), Redis (`:6390`)

### Production

```bash
# Create .env from template
cp .env.production.example .env
# Edit .env — set POSTGRES_PASSWORD and JWT_SECRET_KEY at minimum
nano .env

# Start all services
./prod up -d

# Verify
./prod ps
```

Open [http://localhost:8080](http://localhost:8080). See [Deployment Guide](docs/DEPLOYMENT.md) for reverse proxy, AI configuration, backups, and scaling.

### AI Setup (optional)

DocManFu works without AI — documents are still uploaded and OCR'd. To enable AI analysis:

**Ollama (free, local):**
```bash
brew install ollama && ollama serve   # macOS
ollama pull llama3.2
```

Set in `.env`:
```
AI_PROVIDER=ollama
AI_BASE_URL=http://host.docker.internal:11434
AI_MODEL=llama3.2
```

**OpenAI / Anthropic:** Set `AI_PROVIDER`, `AI_API_KEY`, and optionally `AI_MODEL` in `.env`.

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery |
| `AI_PROVIDER` | `none` | `openai`, `anthropic`, `ollama`, or `none` |
| `AI_API_KEY` | — | API key (not needed for Ollama) |
| `AI_MODEL` | varies | Model name (e.g., `gpt-4o-mini`, `llama3.2`) |
| `OCR_LANGUAGE` | `eng` | Tesseract language codes (e.g., `eng+fra`) |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `JWT_SECRET_KEY` | — | Secret for JWT token signing |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON list) |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Architecture

```
                    ┌─────────────┐
                    │   Browser   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Frontend  │  Svelte + UnoCSS
                    │  (nginx)    │  SPA with /api proxy
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │  REST API + JWT Auth
                    │   Backend   │  Pydantic validation
                    └──┬──────┬───┘
                       │      │
              ┌────────▼┐  ┌──▼────────┐
              │ PostgreSQL│  │   Redis   │  Task broker
              │ Database │  │           │  + result backend
              └──────────┘  └──┬────────┘
                               │
                        ┌──────▼──────┐
                        │   Celery    │  Background workers
                        │   Worker    │
                        └──┬──────┬───┘
                           │      │
                    ┌──────▼┐  ┌──▼──────┐
                    │  OCR  │  │   AI    │  OpenAI / Anthropic
                    │(ocrmypdf)│ │Analysis│  / Ollama
                    └───────┘  └─────────┘
```

**Processing Pipeline:** Upload PDF → OCR (text extraction) → AI Analysis (classification, naming, tagging) → Searchable document with metadata

See [Architecture Documentation](docs/ARCHITECTURE.md) for details.

## Development

```bash
./dev                     # Start all services
./dev logs [service]      # Follow logs
./dev shell               # Shell into API container
./dev migrate             # Run database migrations
./dev seed                # Load sample data
./dev rebuild             # Full rebuild
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding conventions, and how to submit changes.

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md) — Production setup, reverse proxy, AI config, backups
- [Architecture](docs/ARCHITECTURE.md) — System design, services, data flow
- [Contributing](CONTRIBUTING.md) — Development setup, conventions, PR process
- [Security Policy](SECURITY.md) — Vulnerability reporting
- [API Docs](http://localhost:8100/docs) — Interactive Swagger UI (when running)

## License

MIT License — see [LICENSE](LICENSE) for details.
