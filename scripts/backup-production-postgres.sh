#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
  pwd
)"

ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env.production}"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.production.yml"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups/production}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing production environment file: $ENV_FILE"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="$BACKUP_DIR/bc_workspace_${TIMESTAMP}.dump"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

echo "Creating PostgreSQL backup: $BACKUP_FILE"

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  exec -T postgres \
  sh -c \
  'pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    --username="$POSTGRES_USER" \
    "$POSTGRES_DB"' \
  > "$BACKUP_FILE"

sha256sum "$BACKUP_FILE" > "$CHECKSUM_FILE"

echo "Backup completed:"
ls -lh "$BACKUP_FILE" "$CHECKSUM_FILE"
