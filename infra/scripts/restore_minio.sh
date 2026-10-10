#!/usr/bin/env bash
# Restore Road Risk object-storage contents from a backup mirror.
#
# Usage:
#   MC_HOST_backup=https://AKID:SECRET@backup-minio.example.com \
#   MC_HOST_road=https://AKID:SECRET@minio-restore.example.com \
#   BACKUP_BUCKET=road-risk-backup \
#   RESTORE_BUCKET=road-risk-restore \
#   RESTORE_CONFIRM=road-risk-restore \
#   infra/scripts/restore_minio.sh

set -euo pipefail

BACKUP_ALIAS="${BACKUP_ALIAS:-backup}"
RESTORE_ALIAS="${RESTORE_ALIAS:-road}"
BACKUP_BUCKET="${BACKUP_BUCKET:-road-risk-backup}"
RESTORE_BUCKET="${RESTORE_BUCKET:-road-risk-restore}"
RESTORE_CONFIRM="${RESTORE_CONFIRM:-}"
RESTORE_REMOVE_EXTRA="${RESTORE_REMOVE_EXTRA:-false}"

if [[ "${RESTORE_CONFIRM}" != "road-risk-restore" ]]; then
    echo "[restore_minio] ERROR: set RESTORE_CONFIRM=road-risk-restore to acknowledge restore semantics" >&2
    exit 1
fi

if ! command -v mc >/dev/null 2>&1; then
    echo "[restore_minio] ERROR: 'mc' (MinIO client) is required on PATH" >&2
    exit 1
fi

echo "[restore_minio] checking source ${BACKUP_ALIAS}/${BACKUP_BUCKET}"
mc ls "${BACKUP_ALIAS}/${BACKUP_BUCKET}" >/dev/null

MIRROR_ARGS=(--overwrite --preserve --quiet)
if [[ "${RESTORE_REMOVE_EXTRA}" == "true" ]]; then
    MIRROR_ARGS+=(--remove)
fi

echo "[restore_minio] restoring ${BACKUP_ALIAS}/${BACKUP_BUCKET} -> ${RESTORE_ALIAS}/${RESTORE_BUCKET}"
mc mirror "${MIRROR_ARGS[@]}" "${BACKUP_ALIAS}/${BACKUP_BUCKET}" "${RESTORE_ALIAS}/${RESTORE_BUCKET}"

echo "[restore_minio] post-restore object count"
mc ls --recursive "${RESTORE_ALIAS}/${RESTORE_BUCKET}" | wc -l

echo "[restore_minio] done"
