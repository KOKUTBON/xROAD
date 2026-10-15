#!/usr/bin/env bash
# Mirror the Road Risk MinIO buckets to a backup target.
#
# Tracked by https://github.com/KOKUTBON/xROAD/issues/96
#
# Usage:
#   MC_HOST_road=https://AKID:SECRET@minio.example.com \
#   MC_HOST_backup=https://AKID:SECRET@backup-minio.example.com \
#   BACKUP_BUCKET=road-risk-backup \
#   infra/scripts/backup_minio.sh
#
# Requires the MinIO `mc` client to be on PATH. Use the `mc alias`
# environment variables (`MC_HOST_<name>`) so the script does not
# persist credentials to disk.

set -euo pipefail

SOURCE_ALIAS="${SOURCE_ALIAS:-road}"
BACKUP_ALIAS="${BACKUP_ALIAS:-backup}"
SOURCE_BUCKET="${SOURCE_BUCKET:-road-risk}"
BACKUP_BUCKET="${BACKUP_BUCKET:-road-risk-backup}"

if ! command -v mc >/dev/null 2>&1; then
    echo "[backup_minio] ERROR: 'mc' (MinIO client) is required on PATH" >&2
    exit 1
fi

echo "[backup_minio] mirroring ${SOURCE_ALIAS}/${SOURCE_BUCKET} -> ${BACKUP_ALIAS}/${BACKUP_BUCKET}"

# `mc mirror --remove --overwrite` keeps the backup target identical
# to the source. Use `--newer-than` or `--older-than` if you need
# incremental snapshots; the default here is a full mirror.
mc mirror \
    --overwrite \
    --preserve \
    --quiet \
    "${SOURCE_ALIAS}/${SOURCE_BUCKET}" \
    "${BACKUP_ALIAS}/${BACKUP_BUCKET}"

echo "[backup_minio] done"
