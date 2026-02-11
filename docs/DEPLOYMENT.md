# DocManFu Production Deployment

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- 2 GB RAM minimum (4 GB recommended with Ollama)
- 10 GB disk space for images + data

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> docmanfu && cd docmanfu

# 2. Create .env from the production template
cp .env.production.example .env

# 3. Generate and set required secrets
#    Edit .env and fill in:
#    POSTGRES_PASSWORD (generate: openssl rand -hex 16)
#    JWT_SECRET_KEY    (generate: openssl rand -hex 32)
nano .env

# 4. Start all services
./prod up -d

# 5. Verify everything is running
./prod ps
```

The app is available at `http://localhost:8080` (or your configured `FRONTEND_PORT`).

## Reverse Proxy Setup

The frontend container serves the SPA and proxies `/api/` requests to the backend. Point your reverse proxy at port 8080.

### Caddy (recommended)

```
docs.example.com {
    reverse_proxy localhost:8080
}
```

Caddy handles HTTPS automatically via Let's Encrypt.

For SSE (Server-Sent Events) support, Caddy works out of the box — no extra configuration needed.

### nginx

```nginx
server {
    listen 443 ssl http2;
    server_name docs.example.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    client_max_body_size 50m;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

After setting up the reverse proxy, update `CORS_ORIGINS` in `.env`:

```
CORS_ORIGINS=["https://docs.example.com"]
```

## AI Provider Configuration

### Ollama in Docker — with NVIDIA GPU (Linux)

Best option for Linux servers with an NVIDIA GPU. Requires the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

```bash
# Start with the ollama profile
./prod up -d --profile ollama

# Pull models into the container
./prod pull-models
```

In `.env`:

```
AI_PROVIDER=ollama
AI_BASE_URL=http://ollama:11434
AI_MODEL=llama3.2
AI_VISION_MODEL=granite3.2-vision
```

### Ollama in Docker — CPU only

Works on any machine but significantly slower. Suitable for light usage or testing.

```bash
./prod up -d --profile ollama-cpu
./prod pull-models
```

Same `.env` settings as above (`AI_BASE_URL=http://ollama-cpu:11434`).

### Ollama on macOS host (native GPU via Metal)

Docker Desktop on macOS cannot pass through Apple Silicon GPU, so Ollama must run natively on the host.

```bash
brew install ollama
ollama serve
ollama pull llama3.2
```

In `.env`:

```
AI_PROVIDER=ollama
AI_BASE_URL=http://host.docker.internal:11434
AI_MODEL=llama3.2
AI_VISION_MODEL=granite3.2-vision
```

### OpenAI

```
AI_PROVIDER=openai
AI_API_KEY=sk-...
AI_MODEL=gpt-4o-mini
```

### Anthropic

```
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...
AI_MODEL=claude-sonnet-4-5-20250929
```

## Backup & Restore

### Manual Backup

```bash
# Database only
./prod backup

# Database + uploaded files
./prod backup --uploads
```

Backups are saved to `backups/` with timestamps (e.g., `docmanfu_db_20250201_020000.sql.gz`).

### Scheduled Backups (cron)

```bash
# Daily at 2 AM, keep 30 days
0 2 * * * /path/to/docmanfu/scripts/backup.sh >> /var/log/docmanfu-backup.log 2>&1

# Weekly with uploads, keep 90 days
0 3 * * 0 BACKUP_RETENTION_DAYS=90 /path/to/docmanfu/scripts/backup.sh --uploads >> /var/log/docmanfu-backup.log 2>&1
```

### Restore

```bash
# List available backups
./prod restore

# Restore a specific backup (will prompt for confirmation)
./prod restore backups/docmanfu_db_20250201_020000.sql.gz
```

The restore script stops the API and worker, drops and recreates the database, restores from the backup, then restarts services.

## Scaling

### API Workers

Increase `API_WORKERS` in `.env` to handle more concurrent HTTP requests. Each worker is a separate uvicorn process.

```
API_WORKERS=4
```

### Celery Worker Concurrency

Increase `WORKER_CONCURRENCY` for more parallel background task processing. Note that OCR holds a per-process lock, so only one OCR task runs per worker process.

```
WORKER_CONCURRENCY=4
```

### Multiple Worker Containers

For heavier workloads, scale the worker service:

```bash
docker compose up -d --scale worker=3
```

## Logging

All services use Docker's JSON log driver with 10 MB rotation (5 files max).

```bash
# Follow all logs
./prod logs

# Follow a specific service
./prod logs api
./prod logs worker

# View recent logs
docker compose logs --tail 100 api
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild images and restart (migrations run automatically)
./prod rebuild -d
```

The `migrate` init service runs `alembic upgrade head` before the API and worker start, so schema changes are applied automatically.

## Troubleshooting

### Services won't start

Check the logs:

```bash
./prod logs
```

Verify `.env` has all required values (`POSTGRES_PASSWORD`, `JWT_SECRET_KEY`).

### Database issues / disk space

Docker can run out of disk space silently, causing PostgreSQL crash loops.

```bash
# Check disk usage
docker system df

# Clean up unused resources
docker volume prune -f
docker builder prune -f
docker image prune -a -f
```

### Ollama connection issues

Verify Ollama is running on the host:

```bash
curl http://localhost:11434/api/tags
```

Containers reach it via `host.docker.internal:11434`. Make sure `.env` has:

```
AI_BASE_URL=http://host.docker.internal:11434
```

### OCR not working

The production image includes `tesseract-ocr`, `ghostscript`, and `unpaper`. For additional languages:

1. Add the package to the `Dockerfile` runtime stage (e.g., `tesseract-ocr-fra` for French)
2. Rebuild: `./prod rebuild -d`
3. Set `OCR_LANGUAGE=eng+fra` in `.env`

### Upload size limits

If uploads fail for large files, check:

1. `MAX_FILE_SIZE_MB` in `.env` (default: 50)
2. Your reverse proxy's client body size limit (nginx: `client_max_body_size`)
3. Caddy has no default limit, so it works out of the box

### Health checks failing

```bash
# Check individual service health
docker inspect --format='{{.State.Health.Status}}' docmanfu-api-1

# View health check logs
docker inspect --format='{{json .State.Health}}' docmanfu-api-1 | python -m json.tool
```
