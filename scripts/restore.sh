#!/usr/bin/env bash
# =============================================================================
# DocManFu Database Restore Script
# Usage: ./scripts/restore.sh <backup_file.sql.gz>
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh "${PROJECT_DIR}/backups"/docmanfu_db_*.sql.gz 2>/dev/null || echo "  No backups found in backups/"
    exit 1
fi

BACKUP_FILE="$1"

# Resolve relative paths
if [[ ! "$BACKUP_FILE" = /* ]]; then
    BACKUP_FILE="${PWD}/${BACKUP_FILE}"
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

BACKUP_SIZE="$(du -h "$BACKUP_FILE" | cut -f1)"
echo "Restore from: ${BACKUP_FILE} (${BACKUP_SIZE})"
echo ""
echo "WARNING: This will:"
echo "  1. Stop the api and worker services"
echo "  2. Drop and recreate the docmanfu database"
echo "  3. Restore from the backup file"
echo "  4. Restart the api and worker services"
echo ""
read -r -p "Are you sure? [y/N] " confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "[$(date -Iseconds)] Stopping api and worker..."
docker compose -f "$COMPOSE_FILE" stop api worker

echo "[$(date -Iseconds)] Restoring database..."
gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U docmanfu -d postgres -c "DROP DATABASE IF EXISTS docmanfu;" -c "CREATE DATABASE docmanfu OWNER docmanfu;" 2>/dev/null

gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T db \
    psql -U docmanfu -d docmanfu --quiet

echo "[$(date -Iseconds)] Restarting services..."
docker compose -f "$COMPOSE_FILE" start api worker

echo "[$(date -Iseconds)] Restore complete"
