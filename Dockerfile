# =============================================================================
# DocManFu Production Backend Image (multi-stage)
# Used by: api, worker, migrate services
# =============================================================================

# --- Stage 1: Build dependencies ---
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# --- Stage 2: Production runtime ---
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install only runtime dependencies (no compilers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ghostscript \
    unpaper \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user and the uploads directory it writes to
RUN groupadd -g 1000 docmanfu && \
    useradd -u 1000 -g docmanfu -m docmanfu && \
    mkdir -p /app/uploads && chown docmanfu:docmanfu /app/uploads

WORKDIR /app

# Copy application code last, with no RUN after it, so a code-only change
# rebuilds just these layers
COPY --chown=docmanfu:docmanfu alembic.ini .
COPY --chown=docmanfu:docmanfu alembic/ alembic/
COPY --chown=docmanfu:docmanfu scripts/ scripts/
COPY --chown=docmanfu:docmanfu app/ app/

USER docmanfu

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
