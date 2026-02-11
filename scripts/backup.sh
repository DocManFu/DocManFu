#!/usr/bin/env bash
# =============================================================================
# DocManFu Database Backup Script
# Usage: ./scripts/backup.sh [--uploads]
# Cron:  0 2 * * * /path/to/docmanfu/scripts/backup.sh >> /var/log/docmanfu-backup.log 2>&1
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_UPLOADS=false

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --uploads) BACKUP_UPLOADS=true ;;
        --help|-h)
            echo "Usage: $0 [--uploads]"
            echo "  --uploads    Also backup the uploads volume"
            echo ""
            echo "Environment:"
            echo "  BACKUP_RETENTION_DAYS  Days to keep backups (default: 30)"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

mkdir -p "$BACKUP_DIR"

# Database backup
DB_BACKUP="${BACKUP_DIR}/docmanfu_db_${TIMESTAMP}.sql.gz"
echo "[$(date -Iseconds)] Starting database backup..."

docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    pg_dump -U docmanfu docmanfu | gzip > "$DB_BACKUP"

DB_SIZE="$(du -h "$DB_BACKUP" | cut -f1)"
echo "[$(date -Iseconds)] Database backup complete: ${DB_BACKUP} (${DB_SIZE})"

# Optional uploads backup
if [[ "$BACKUP_UPLOADS" == "true" ]]; then
    UPLOADS_BACKUP="${BACKUP_DIR}/docmanfu_uploads_${TIMESTAMP}.tar.gz"
    echo "[$(date -Iseconds)] Starting uploads backup..."

    docker compose -f "${PROJECT_DIR}/docker-compose.yml" run --rm -T \
        --entrypoint "" api \
        tar czf - -C /app uploads | cat > "$UPLOADS_BACKUP"

    UPLOADS_SIZE="$(du -h "$UPLOADS_BACKUP" | cut -f1)"
    echo "[$(date -Iseconds)] Uploads backup complete: ${UPLOADS_BACKUP} (${UPLOADS_SIZE})"
fi

# Cleanup old backups
if [[ "$RETENTION_DAYS" -gt 0 ]]; then
    DELETED=$(find "$BACKUP_DIR" -name "docmanfu_*" -type f -mtime +"$RETENTION_DAYS" -print -delete | wc -l)
    if [[ "$DELETED" -gt 0 ]]; then
        echo "[$(date -Iseconds)] Cleaned up ${DELETED} backup(s) older than ${RETENTION_DAYS} days"
    fi
fi

echo "[$(date -Iseconds)] Backup complete"
