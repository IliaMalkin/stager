#!/usr/bin/env bash
# Daily backup. Запускать через cron:
#   0 4 * * * /opt/stager/deploy/backup.sh >> /var/log/stager-backup.log 2>&1
#
# Хранит 7 последних дампов postgres + еженедельный mc-mirror MinIO.

set -euo pipefail

STAGER_DIR=${STAGER_DIR:-/opt/stager}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/stager}
DATE=$(date +%Y-%m-%d)

mkdir -p "$BACKUP_DIR/pg" "$BACKUP_DIR/minio"

# Postgres dump
docker compose -f "$STAGER_DIR/docker-compose.yml" -f "$STAGER_DIR/docker-compose.prod.yml" \
    exec -T postgres pg_dump -U stager stager | gzip > "$BACKUP_DIR/pg/stager-$DATE.sql.gz"

# Retention: keep last 7 days
find "$BACKUP_DIR/pg" -name "stager-*.sql.gz" -mtime +7 -delete

# Weekly MinIO mirror (Mondays)
if [ "$(date +%u)" = "1" ]; then
    docker run --rm --network stager_default \
        -v "$BACKUP_DIR/minio:/backup" \
        -e MC_HOST_local="http://${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}@minio:9000" \
        minio/mc mirror --overwrite local/stager-receipts "/backup/$DATE"
fi

echo "[$(date -Iseconds)] backup ok: $DATE"
