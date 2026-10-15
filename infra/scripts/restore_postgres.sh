#!/usr/bin/env bash
# Restore a Road Risk Postgres backup into a rehearsal or target database.
#
# Usage:
#   RESTORE_BACKUP_PATH=/var/backups/road-risk/road_risk_prod_20260604T010000Z.sql.gz \
#   PGDATABASE=road_risk_restore \
#   RESTORE_CONFIRM=road-risk-restore \
#   infra/scripts/restore_postgres.sh

set -euo pipefail

RESTORE_BACKUP_PATH="${RESTORE_BACKUP_PATH:-}"
RESTORE_CONFIRM="${RESTORE_CONFIRM:-}"
PGDATABASE="${PGDATABASE:-road_risk_restore}"
PG_RESTORE_EXTRA_ARGS="${PG_RESTORE_EXTRA_ARGS:-}"

if [[ -z "${RESTORE_BACKUP_PATH}" ]]; then
    echo "[restore_postgres] ERROR: RESTORE_BACKUP_PATH is required" >&2
    exit 1
fi

if [[ ! -s "${RESTORE_BACKUP_PATH}" ]]; then
    echo "[restore_postgres] ERROR: backup file is missing or empty: ${RESTORE_BACKUP_PATH}" >&2
    exit 1
fi

if [[ "${RESTORE_CONFIRM}" != "road-risk-restore" ]]; then
    echo "[restore_postgres] ERROR: set RESTORE_CONFIRM=road-risk-restore to acknowledge destructive restore semantics" >&2
    exit 1
fi

if ! command -v pg_restore >/dev/null 2>&1; then
    echo "[restore_postgres] ERROR: pg_restore is required on PATH" >&2
    exit 1
fi

echo "[restore_postgres] validating archive ${RESTORE_BACKUP_PATH}"
if [[ "${RESTORE_BACKUP_PATH}" == *.gz ]]; then
    gzip -t "${RESTORE_BACKUP_PATH}"
    LIST_COMMAND=(bash -c "gunzip -c \"${RESTORE_BACKUP_PATH}\" | pg_restore --list")
    RESTORE_COMMAND=(bash -c "gunzip -c \"${RESTORE_BACKUP_PATH}\" | pg_restore --dbname=\"${PGDATABASE}\" --clean --if-exists --no-owner --no-privileges ${PG_RESTORE_EXTRA_ARGS}")
else
    LIST_COMMAND=(pg_restore --list "${RESTORE_BACKUP_PATH}")
    RESTORE_COMMAND=(pg_restore --dbname="${PGDATABASE}" --clean --if-exists --no-owner --no-privileges ${PG_RESTORE_EXTRA_ARGS} "${RESTORE_BACKUP_PATH}")
fi

"${LIST_COMMAND[@]}" >/dev/null

echo "[restore_postgres] restoring into database ${PGDATABASE}"
"${RESTORE_COMMAND[@]}"

echo "[restore_postgres] running post-restore smoke query"
psql --dbname="${PGDATABASE}" --set=ON_ERROR_STOP=1 --tuples-only --command="SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" >/dev/null

echo "[restore_postgres] done"
