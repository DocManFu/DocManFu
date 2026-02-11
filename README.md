<div align="center">

![DocManFu Logo](assets/images/logo.png)

# DocManFu 📄🥋

**Master Your Documents**

</div>

Self-hosted AI-powered document management system that replaces expensive cloud services like Evernote.

## 🎯 What is DocManFu?

DocManFu is an open-source document management system that combines:
- **AI-powered smart naming** - Automatically analyzes and renames your scanned documents
- **OCR processing** - Full-text search across all your documents  
- **Self-hosted** - Your documents stay on your hardware
- **Cost-effective** - Replace expensive monthly subscriptions
- **Open source** - Customize and extend as needed

## ✨ Key Features

- 🤖 **AI Document Analysis** - Intelligent naming based on content (bills, statements, medical docs, etc.)
- 📄 **OCR Integration** - Full-text search across scanned PDFs
- 🏠 **Self-hosted** - Run on your NAS, VPS, or local machine
- 🔍 **Smart Search** - Find documents by content, not just filename
- 🏷️ **Auto-tagging** - AI suggests relevant tags for organization
- 📱 **Web Interface** - Access from any device on your network
- 🔄 **Batch Processing** - Handle multiple documents efficiently
- 🔒 **Privacy-focused** - Your documents never leave your control

## 🛠️ Tech Stack

- **Backend**: Python/FastAPI with Celery background workers
- **Frontend**: Svelte + UnoCSS (clean, modern UI without JSX complexity)
- **Database**: PostgreSQL with full-text search
- **OCR**: OCRmyPDF integration
- **AI**: Configurable (OpenAI, Anthropic, or local models)
- **Queue**: Redis for background job processing

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### Running with Docker

```bash
# Start all services (attached)
./dev

# Start in background
./dev up -d

# Run database migrations
./dev migrate

# Load sample data
./dev seed

# View logs
./dev logs

# Stop everything
./dev down
```

This starts PostgreSQL (port 5450), Redis (port 6390), the FastAPI API (port 8100), Celery worker, and Svelte frontend (port 5180) with hot-reload enabled.

Run `./dev --help` for all available commands.

## 📋 Roadmap

See our detailed [Development Plan](DEVELOPMENT_PLAN.md) for the complete 12-session roadmap.

**Current Status**: 🏗️ Planning & Architecture Phase

- ✅ Project planning and architecture
- ✅ Domain secured (DocManFu.com)
- ✅ GitHub organization created
- 🔄 Session 1: Database design (next)

## 🤝 Contributing

We welcome contributions! This project is being built in the open with detailed session-by-session development.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Motivation

Born from frustration with expensive document management services and the desire for true ownership of personal data. DocManFu aims to provide enterprise-level document management capabilities without the enterprise price tag or privacy concerns.

---

**Status**: 🏗️ Under Development | **Version**: Pre-release | **License**: MIT