#!/bin/bash
# FLOWRA — Tier 1 MongoDB backup
# Runs daily at 02:00 IST via cron, retains last 30 backups.
# Backups written to BACKUP_DIR (default /app/backups) — gzipped mongodump.
#
# Schedule via:
#   echo "0 2 * * * /app/scripts/backup_mongo.sh >> /var/log/flowra-backup.log 2>&1" | sudo crontab -
#
# Triggered on-demand from SuperAdmin → Backups → "Run Now".
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
RETENTION="${RETENTION:-30}"
MONGO_URL="${MONGO_URL:-$(grep -m1 '^MONGO_URL=' /app/backend/.env | cut -d= -f2-)}"
DB_NAME="${DB_NAME:-$(grep -m1 '^DB_NAME=' /app/backend/.env | cut -d= -f2-)}"
TS="$(date -u +%Y%m%d_%H%M%SZ)"
OUT_FILE="${BACKUP_DIR}/flowra_backup_${TS}.archive.gz"

mkdir -p "$BACKUP_DIR"

if ! command -v mongodump >/dev/null 2>&1; then
  echo "[$(date -u)] ERROR: mongodump not installed. Install MongoDB Database Tools." >&2
  exit 2
fi

echo "[$(date -u)] Starting backup → $OUT_FILE"
mongodump --uri="$MONGO_URL" --db="$DB_NAME" --archive="$OUT_FILE" --gzip --quiet

SIZE="$(du -h "$OUT_FILE" | cut -f1)"
echo "[$(date -u)] Backup complete ($SIZE)"

# Rotate — keep newest $RETENTION files only
cd "$BACKUP_DIR"
ls -1t flowra_backup_*.archive.gz 2>/dev/null | tail -n +$((RETENTION + 1)) | xargs -r rm -f
echo "[$(date -u)] Rotation complete (retention=$RETENTION)"
