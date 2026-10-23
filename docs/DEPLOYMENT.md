# DocManFu Production Deployment

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- 2 GB RAM minimum (4 GB recommended with Ollama)
- 10 GB disk space for images + data

## Quick Start (prebuilt images)

DocManFu publishes ready-to-run images to the GitHub Container Registry for `linux/amd64` and `linux/arm64` (Intel/AMD servers, Raspberry Pi 4/5, Apple Silicon):

| Image | Used by |
|-------|---------|
| `ghcr.io/docmanfu/docmanfu/api` | `api`, `worker` and `migrate` services |
| `ghcr.io/docmanfu/docmanfu/frontend` | `frontend` (nginx serving the web app and proxying `/api/`) |

You don't need to clone the repository, just two files:

```bash
mkdir docmanfu && cd docmanfu

# 1. Download the compose file and the settings template
curl -fsSLO https://raw.githubusercontent.com/DocManFu/DocManFu/main/docker-compose.yml
curl -fsSL -o .env https://raw.githubusercontent.com/DocManFu/DocManFu/main/.env.production.example

# 2. Set the required secrets in .env
sed -i.bak "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
sed -i.bak "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$(openssl rand -hex 32)/" .env
rm .env.bak

# 3. Set your domain: CORS_ORIGINS and WEBAUTHN_ORIGIN (see Passkeys below)
nano .env

# 4. Pull the images and start everything
docker compose pull
docker compose up -d

# 5. Verify everything is running
docker compose ps
```

The app is available at `http://localhost:8080` (or your configured `FRONTEND_PORT`). The first account you create becomes the admin.

Uploaded files are stored in `./uploads` next to the compose file (change with `UPLOAD_PATH`); the database lives in the `pgdata` Docker volume.

### Image tags

| Tag | Contents |
|-----|----------|
| `latest`, `main` | The newest build of the `main` branch, published within minutes of every merge |
| `1.2.0`, `1.2` | A release (`1.2` follows the newest `1.2.x`) |
| `sha-<commit>` | One exact commit, useful to roll back |

The default is `latest`. To stay on releases, set the tag in `.env`:

```bash
DOCMANFU_VERSION=1.2
```

### Building from source instead

Clone the repository and use the `./prod` wrapper, which builds the images locally from your checkout:

```bash
git clone https://github.com/DocManFu/DocManFu.git docmanfu && cd docmanfu
cp .env.production.example .env   # then set the secrets as above
./prod up -d
./prod ps
```

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

### Passkeys

To let users sign in with passkeys (e.g. stored in Bitwarden, 1Password, or the OS), set `WEBAUTHN_ORIGIN` in `.env` to the exact URL users open DocManFu at:

```
WEBAUTHN_ORIGIN=https://docs.example.com
```

Passkeys only work over HTTPS (or `http://localhost`) and are bound to that hostname — changing the domain later invalidates registered passkeys. Users add passkeys from their Profile page.

### Login rate limiting behind a proxy

The frontend nginx rate-limits `/api/auth/login` and `/api/auth/setup` per client IP. Behind a reverse proxy every request appears to come from the proxy, so all users share one limit. To rate-limit per real client, tell nginx which address your proxy connects from (only that address — trusting a wider range lets clients spoof `X-Forwarded-For`):

```nginx
# trusted-proxies.conf
set_real_ip_from 172.18.0.1;   # e.g. the Docker gateway when the proxy runs on the host
```

Mount it over the default in `docker-compose.yml`:

```yaml
  frontend:
    volumes:
      - ./trusted-proxies.conf:/etc/nginx/trusted-proxies.conf:ro
```

Check `docker compose logs frontend` to see which address requests arrive from.

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

Running from the prebuilt images without a checkout? Back up with plain Compose commands from the directory holding `docker-compose.yml`:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U docmanfu docmanfu | gzip > backups/docmanfu_db_$(date +%Y%m%d_%H%M%S).sql.gz
tar czf backups/docmanfu_uploads_$(date +%Y%m%d_%H%M%S).tar.gz uploads   # uploaded files
```

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

With the prebuilt images:

```bash
docker compose pull
docker compose up -d
docker image prune -f   # optional: remove the old images
```

When building from source:

```bash
git pull
./prod rebuild -d
```

Either way, the `migrate` init service runs `alembic upgrade head` before the API and worker start, so schema changes are applied automatically. Back up first (see [Backup & Restore](#backup--restore)) if you're jumping several releases.

To roll back, set `DOCMANFU_VERSION` to the previous release or `sha-<commit>` tag and run the two commands above. Migrations aren't reversed automatically, so restore the database backup if the newer version changed the schema.

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
