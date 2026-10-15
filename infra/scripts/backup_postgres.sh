#!/usr/bin/env bash
# Backup the Road Risk production Postgres database.
#
# Tracked by https://github.com/KOKUTBON/xROAD/issues/96
#
# Usage:
#   BACKUP_DIR=/var/backups/road-risk \
#   PGHOST=... PGPORT=5432 PGUSER=road_risk PGPASSWORD=... \
#   PGDATABASE=road_risk \
#   infra/scripts/backup_postgres.sh
#
# Produces a timestamped, compressed `pg_dump` artifact and prunes
# artifacts older than $BACKUP_RETENTION_DAYS (default: 14).

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PGDATABASE="${PGDATABASE:-road_risk}"

mkdir -p "$BACKUP_DIR"

OUTPUT_PATH="${BACKUP_DIR}/road_risk_${PGDATABASE}_${TIMESTAMP}.sql.gz"

echo "[backup_postgres] writing ${OUTPUT_PATH}"
pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    --serializable-deferrable \
    --quote-all-identifiers \
    "${PGDATABASE}" \
    | gzip --rsyncable > "${OUTPUT_PATH}"

# Verify the artifact was produced and is non-empty.
if [[ ! -s "${OUTPUT_PATH}" ]]; then
    echo "[backup_postgres] ERROR: backup file is empty or missing" >&2
    exit 1
fi

echo "[backup_postgres] pruning artifacts older than ${BACKUP_RETENTION_DAYS} days"
find "${BACKUP_DIR}" -type f -name "road_risk_*.sql.gz" -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete

echo "[backup_postgres] done"
