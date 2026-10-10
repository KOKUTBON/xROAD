#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${STAGING_ENV_FILE:-$ROOT_DIR/infra/staging/.env.example}"
COMPOSE_FILE="${STAGING_COMPOSE_FILE:-$ROOT_DIR/infra/staging/docker-compose.staging.yml}"
SEED_SQL="$ROOT_DIR/infra/staging/seed_staging.sql"

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

if [[ "${STAGING_RESET:-1}" == "1" ]]; then
  "${COMPOSE[@]}" down --volumes --remove-orphans
fi

"${COMPOSE[@]}" build api worker web
"${COMPOSE[@]}" up -d postgres redis minio
"${COMPOSE[@]}" run --rm api alembic -c alembic.ini upgrade head
"${COMPOSE[@]}" exec -T postgres psql \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-road_risk_staging}" \
  -v ON_ERROR_STOP=1 < "$SEED_SQL"
"${COMPOSE[@]}" up -d api worker scheduler web

python3 "$ROOT_DIR/infra/staging/smoke_staging.py" \
  --api-base-url "http://localhost:${API_HOST_PORT:-18000}" \
  --web-base-url "http://localhost:${WEB_HOST_PORT:-13000}" \
  --organization-id "${STAGING_ORGANIZATION_ID:-00000000-0000-0000-0000-000000000118}" \
  --municipality-id "${STAGING_MUNICIPALITY_ID:-00000000-0000-0000-0000-000000000119}" \
  --city-key "${STAGING_CITY_KEY:-bari}" \
  --minio-public-base-url "http://localhost:${MINIO_API_HOST_PORT:-19000}" \
  --dispatch-mode "${STAGING_DISPATCH_MODE:-inline}" \
  --json-output "$ROOT_DIR/docs/staging-smoke-results.latest.json"
