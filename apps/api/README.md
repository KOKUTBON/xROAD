# Road Risk API (FastAPI)

This is a lightweight FastAPI shell for the production backend track.

## Quick start

```bash
python3 -m pip install -e '.[api]'
uvicorn apps.api.main:app --reload
```

OpenAPI schema: `GET /openapi.json`
Swagger UI: `GET /docs`
ReDoc: `GET /redoc`
Stable v1 API contract package: [`docs/api/README.md`](../../docs/api/README.md)

## Configuration

Environment variables (all optional):

- `ROAD_RISK_API_ROOT_DIR` (default: `.`)
- `ROAD_RISK_API_PUBLISHED_INDEX_PATH` (default: `data/published_index/published_resources.json`)
- `ROAD_RISK_API_DASHBOARD_SUMMARY_PATH` (default: `data/dashboard/dashboard_summary.json`)
- `ROAD_RISK_API_DASHBOARD_DIR` (default: `dashboard`)
- `ROAD_RISK_API_SCENARIO_WORKSPACE_PATH` (default: `data/runtime/scenario_workspace/scenarios.json`)
- `ROAD_RISK_API_ENV` (default: `local`)
- `ROAD_RISK_API_REQUEST_LOGGING_ENABLED` (default: `true`)
- `ROAD_RISK_API_REQUEST_LOG_JSON` (default: `true`)
- `ROAD_RISK_API_REQUEST_ID_HEADER` (default: `X-Request-ID`)
- `ROAD_RISK_API_RATE_LIMIT_ENABLED` (default: `false`)
- `ROAD_RISK_API_RATE_LIMIT_REQUESTS` (default: `120`)
- `ROAD_RISK_API_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `ROAD_RISK_API_RATE_LIMIT_EXEMPT_PATHS` (default: `/healthz,/v1/healthz,/v1/public/health,/v1/observability/info,/v1/observability/readiness`)
- `ROAD_RISK_API_ERROR_TRACKING_ENABLED` (default: `false`)
- `ROAD_RISK_API_SENTRY_DSN` (default: unset)
- `ROAD_RISK_API_SENTRY_ENVIRONMENT` (default: `ROAD_RISK_API_ENV`)
- `ROAD_RISK_API_SENTRY_TRACES_SAMPLE_RATE` (default: `0.0`)
- `ROAD_RISK_API_AUTH_ENABLED` (default: `false`)
- `ROAD_RISK_API_AUTH_PROVIDER` (default: `keycloak`)
- `ROAD_RISK_API_AUTH_JWKS_URL` (default: unset)
- `ROAD_RISK_API_AUTH_AUDIENCE` (default: unset)
- `ROAD_RISK_API_AUTH_ISSUER` (default: unset)
- `ROAD_RISK_API_AUTH_CLIENT_ID` (default: unset)
- `ROAD_RISK_API_AUTH_ROLE_CLAIM` (default: `realm_access.roles`)
- `ROAD_RISK_API_AUTH_ORGANIZATION_CLAIM` (default: `organization_ids`)
- `ROAD_RISK_API_AUTH_MUNICIPALITY_CLAIM` (default: `municipality_ids`)
- `ROAD_RISK_API_AUTH_ALGORITHMS` (default: `RS256`)
- `ROAD_RISK_API_AUTH_JWKS_CACHE_SECONDS` (default: `300`)
- `ROAD_RISK_DATABASE_URL` (default: `postgresql+psycopg://postgres:postgres@localhost:5432/road_risk`)
- `ROAD_RISK_STORAGE_ENDPOINT_URL` (default: unset)
- `ROAD_RISK_STORAGE_REGION` (default: `us-east-1`)
- `ROAD_RISK_STORAGE_ACCESS_KEY_ID` (default: unset)
- `ROAD_RISK_STORAGE_SECRET_ACCESS_KEY` (default: unset)
- `ROAD_RISK_STORAGE_SESSION_TOKEN` (default: unset)
- `ROAD_RISK_STORAGE_BUCKET` (default: `road-risk`)
- `ROAD_RISK_STORAGE_PUBLIC_BUCKET` (default: unset)
- `ROAD_RISK_STORAGE_PREFIX` (default: `artifacts`)
- `ROAD_RISK_STORAGE_UPLOADS_PREFIX` (default: `uploads`)
- `ROAD_RISK_STORAGE_REPORTS_PREFIX` (default: `reports`)
- `ROAD_RISK_STORAGE_MANIFESTS_PREFIX` (default: `manifests`)
- `ROAD_RISK_STORAGE_ADDRESSING_STYLE` (default: `auto`)
- `ROAD_RISK_STORAGE_USE_SSL` (default: `true`)
- `ROAD_RISK_STORAGE_VERIFY_SSL` (default: `true`)
- `ROAD_RISK_STORAGE_PRESIGN_EXPIRES_S` (default: `3600`)
- `ROAD_RISK_STORAGE_AUTO_CREATE_BUCKETS` (default: `false`)

## Auth provider path

Default provider decision: `Keycloak`.

- Recommended for municipal and EU-sensitive deployments where self-hosted OIDC matters.
- Supported alternatives through the same JWKS/OIDC validation path: `Entra ID`, `Cognito`, `Auth0`.
- Validation flow: `Bearer token -> JWKS verification -> role extraction -> organization scope -> municipality scope`.

## Role matrix

The API exposes the live role matrix at `GET /v1/auth/role-matrix`. The current production matrix is:

| Role | Purpose |
| --- | --- |
| `public` | Public dashboard and public reports only |
| `municipality_viewer` | Read-only internal access for scoped municipalities |
| `analyst` | Internal analysis, hotspot inspection, scenario use |
| `data_operator` | Upload, ingestion, and data-quality operations |
| `traffic_engineer` | Signal-phase and traffic-engineering workflows |
| `admin` | Organization-level governance, users, and publication controls |
| `super_admin` | Cross-organization platform administration |

When auth is enabled, requests must supply a `Bearer` token. Internal authorization now includes:

- role hierarchy expansion, so `admin` and `super_admin` inherit lower internal capabilities
- organization-scoped access checks
- municipality-scoped access checks
- reusable audit-event hooks for sensitive actions

## Migrations

```bash
export ROAD_RISK_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/road_risk"
alembic -c alembic.ini upgrade head
```

Reset a local development database:

```bash
dropdb --if-exists road_risk
createdb road_risk
alembic -c alembic.ini upgrade head
```

## PostGIS domain serving

The v1 serving path now has first-class PostGIS product tables for:

- `model_runs`
- `crash_records`
- `road_segments`
- `road_nodes`
- `crossings`
- `movement_objects`
- `risk_scores`
- `public_risk_tiles`
- `scenario_runs`
- `interventions`

Public and analyst risk-map APIs try the PostGIS domain tables first and
fall back to published artifacts only when the database is not populated or
temporarily unavailable. Production deployments should treat artifact fallback
as a migration safety net, not the default serving mode.

Admin sync endpoints:

- `GET /v1/admin/postgis-domain/sync-plan?city_key=bari` previews artifact counts.
- `POST /v1/admin/postgis-domain/sync` loads published artifacts into PostGIS-scoped product tables.

The sync payload is:

```json
{
  "organization_id": "uuid",
  "municipality_id": "uuid",
  "city_key": "bari",
  "source_id": "optional-uuid",
  "ingestion_job_id": "optional-uuid"
}
```

## Object storage

The API uses an S3-compatible client for uploads and generated artifacts (MinIO locally, S3 in production).

The production storage pattern is now:

- uploaded source files reserve a remote object slot first, then persist the `input_storage_uri` on the queued ingestion job
- generated reports reserve a remote object slot first, then persist the `file_storage_uri` on the report record
- generated manifests and published bundles persist as `artifact_references` whose `lineage_json.storage_contract` links the stored object back to jobs, reports, and related manifests
- public artifacts resolve to a direct/public URL pattern
- restricted or internal artifacts resolve through presigned GET URLs

For local MinIO development, a minimal setup is:

```bash
export ROAD_RISK_STORAGE_ENDPOINT_URL="http://127.0.0.1:9000"
export ROAD_RISK_STORAGE_ACCESS_KEY_ID="minioadmin"
export ROAD_RISK_STORAGE_SECRET_ACCESS_KEY="minioadmin"
export ROAD_RISK_STORAGE_USE_SSL="false"
export ROAD_RISK_STORAGE_VERIFY_SSL="false"
export ROAD_RISK_STORAGE_AUTO_CREATE_BUCKETS="true"
```

That keeps uploads, manifests, and generated reports out of the repo worktree while preserving stable metadata links in PostgreSQL.

## Operational hardening

Every API response receives an `X-Request-ID` value, using the incoming
header when supplied or generating one per request. The
`RequestObservabilityMiddleware` records structured JSON request logs to
`road_risk.api.requests` with safe fields only:

- request id
- HTTP method
- route template, not raw URLs with object IDs
- status code and duration
- job/report/scenario id when it is already a route parameter
- hashed user subject
- organization and municipality scope ids
- role count

The admin metrics endpoint returns the same in-process runtime snapshot
under `api_runtime`, plus organization-scoped job, ingestion row-quality,
report, artifact, stale-source, active-user, error-tracking, and
security-control rollups.

Production deployments should enable rate limiting at the API process
or gateway layer. The built-in per-process limiter is controlled by:

```bash
ROAD_RISK_API_RATE_LIMIT_ENABLED=true
ROAD_RISK_API_RATE_LIMIT_REQUESTS=120
ROAD_RISK_API_RATE_LIMIT_WINDOW_SECONDS=60
```

Use gateway-level limits for horizontally scaled clusters when exact
global limits are required.

Optional Sentry-compatible error tracking is disabled by default and
uses `send_default_pii=false` when enabled:

```bash
ROAD_RISK_API_ERROR_TRACKING_ENABLED=true
ROAD_RISK_API_SENTRY_DSN=https://public-key@sentry.example.gov/project
ROAD_RISK_API_SENTRY_ENVIRONMENT=staging
```

## First backend job

The first production job wrapper covers the published-refresh and dashboard-refresh workflow.

- `POST /v1/jobs/published-refresh` creates a persisted job record and either enqueues it through Celery or runs it inline when the worker runtime is unavailable
- `GET /v1/jobs/{job_id}` returns the persisted status, artifact list, manifest/error URIs, and access snapshots
- the worker task name is `services.workers.tasks.published_refresh.run_job`
- generated outputs are persisted both locally for the analytics engine and remotely through the object-storage contract from `apps/api/services/artifact_storage.py`

## Upload-center ingestion contract

The browser-oriented ingestion flow is backed by an executable worker path:

- `POST /v1/ingestion-jobs/uploads` registers a governed upload slot for a configured `data_source`, creates the ingestion job record, and returns the direct object-storage upload URL
- `POST /v1/ingestion-jobs/{job_id}/validate` reads the uploaded object back from storage, runs governance-aware preflight checks, previews row-level/schema errors, and persists a manifest, error summary, and execution log as linked artifacts
- `GET /v1/ingestion-jobs/upload-center` returns the browser upload-center bundle: uploadable sources, supported formats, recent jobs, and operator actions
- `GET /v1/ingestion-jobs` and `GET /v1/ingestion-jobs/{job_id}` expose list/detail state without requiring direct CLI access
- `GET /v1/ingestion-jobs/{job_id}/errors`, `/manifest`, and `/logs` return the preview payloads plus presigned/public access contracts for the stored JSON artifacts
- `POST /v1/ingestion-jobs/{job_id}/approve` moves validated jobs into the queued/runnable handoff state
- `POST /v1/ingestion-jobs/{job_id}/run` dispatches the executable ingestion worker through Celery or runs inline when requested
- `POST /v1/ingestion-jobs/{job_id}/retry` moves failed/cancelled/manual-review executions back to the queued state
- `POST /v1/ingestion-jobs/{job_id}/cancel` records a best-effort cancellation for queued/running jobs
- `POST /v1/ingestion-jobs/{job_id}/reject` records an operator rejection and leaves an audit trail

Validated uploads now have a two-step contract: validation artifacts explain whether the payload is acceptable, while execution artifacts capture engine outputs, rejected rows, logs, lineage, dashboard refresh triggers, and optional PostGIS domain sync. The v1 executable adapters cover generic crash CSV normalization, Bari open-data crash ingestion when `engine_adapter=bari_open_data_crashes`, and exposure connector uploads through the existing connector normalization engine.

## Operational metadata split

The product shell keeps a deliberate split between:

- operational product metadata in PostgreSQL/PostGIS: organizations, memberships, municipality access, user profiles, data sources, ingestion jobs, reports, and audit logs
- analytics artifacts in object storage or local files, referenced through `artifact_references` instead of embedding raw bundle payloads into the operational tables

This lets future API/UI work query stable operational entities without turning the database into a duplicate of the analytics artifact store.

## Local seed fixture

The service layer includes a deterministic local-development seed plan and fixture flow in `apps/api/services/operational_metadata.py`.

- `build_local_development_seed_plan()` builds a repeatable demo organization, municipality, user, data-source, report, and audit-log bundle
- `seed_local_development_fixture(session)` materializes that bundle through the repository layer
- `build_organization_operational_snapshot(session, organization_id)` returns an organization-scoped view with operational metadata and analytics artifact references kept separate

## Endpoints

- `GET /healthz`
- `GET /v1/healthz`
- `GET /v1/public/health`
- `GET /v1/auth/me`
- `GET /v1/auth/role-matrix`
- `GET /v1/auth/organizations/{organization_id}/access`
- `GET /v1/auth/municipalities/{municipality_id}/access`
- `POST /v1/ingestion-jobs/uploads`
- `POST /v1/ingestion-jobs/{job_id}/validate`
- `GET /v1/ingestion-jobs/upload-center`
- `POST /v1/ingestion-jobs/{job_id}/approve`
- `POST /v1/ingestion-jobs/{job_id}/run`
- `POST /v1/ingestion-jobs/{job_id}/retry`
- `POST /v1/ingestion-jobs/{job_id}/cancel`
- `POST /v1/ingestion-jobs/{job_id}/reject`
- `GET /v1/ingestion-jobs`
- `GET /v1/ingestion-jobs/{job_id}`
- `GET /v1/ingestion-jobs/{job_id}/errors`
- `GET /v1/ingestion-jobs/{job_id}/manifest`
- `GET /v1/ingestion-jobs/{job_id}/logs`
- `POST /v1/jobs/published-refresh`
- `GET /v1/jobs/{job_id}`
- `POST /v1/storage/uploads/presign`
- `POST /v1/storage/reports/presign`
- `GET /v1/storage/artifacts/access`
- `GET /v1/published-index`
- `GET /v1/dashboard-summary`
- `GET /v1/public/cities`
- `GET /v1/public/cities/{city_key}/risk-map`
- `GET /v1/public/cities/{city_key}/risk-tiles`
- `GET /v1/public/cities/{city_key}/interventions`
- `GET /v1/analyst/cities/{city_key}/risk-map`
- `GET /v1/admin/postgis-domain/sync-plan`
- `POST /v1/admin/postgis-domain/sync`
- `GET /v1/admin/control-center`
- `GET /v1/admin/governance-matrix`
- `GET /v1/admin/automations`
- `GET /v1/admin/user-roster`
- `POST /v1/admin/data-sources`
- `PATCH /v1/admin/data-sources/{source_id}`
- `POST /v1/admin/data-sources/{source_id}/archive`
- `POST /v1/admin/users/link`
- `PATCH /v1/admin/memberships/{membership_id}`
- `POST /v1/admin/municipality-access`
- `GET /v1/published-resource/latest`
- `GET /v1/published-resource/query`
- `GET /dashboard/*` (static dashboard assets)

The `/v1/admin/*` surfaces are organization-scoped, require the `admin`
role, and compose a control-center for the admin workspace (governance
matrix, automations roster, user roster, recent audit). Data-source
write actions let admins create governed sources, approve/block/update
publication policy, set refresh cadence, archive sources, and record an
audit event for each decision. Access-management actions link OIDC
subjects to organization memberships, update roles/status, assign
municipality access, and preserve a last-active-admin guardrail.

- `GET /v1/scenarios/catalog`
- `GET /v1/scenarios/intervention-library`
- `GET /v1/scenarios/drafts`
- `POST /v1/scenarios/drafts`
- `GET /v1/scenarios/drafts/{scenario_draft_id}`
- `PATCH /v1/scenarios/drafts/{scenario_draft_id}`
- `POST /v1/scenarios/drafts/{scenario_draft_id}/validate`
- `POST /v1/scenarios/drafts/{scenario_draft_id}/run`
- `GET /v1/scenarios/runs`
- `GET /v1/scenarios/cities/{city_key}`
- `GET /v1/scenarios/cities/{city_key}/portfolios`
- `GET /v1/scenarios/cities/{city_key}/scenarios/{scenario_id}`
- `GET /v1/interventions/portfolio`
- `POST /v1/interventions/portfolio`
- `PATCH /v1/interventions/portfolio/{intervention_id}`
- `POST /v1/interventions/portfolio/{intervention_id}/remove`
- `GET /v1/interventions/portfolio/export`

The `/v1/scenarios/*` surfaces are restricted to analyst-capable roles and
publish the existing scenario-countermeasure bundles plus an organization-scoped
authoring workspace. Draft/run endpoints persist a lightweight before/after
history in `ROAD_RISK_API_SCENARIO_WORKSPACE_PATH`, using the generated scenario
bundle and intervention library as the baseline rather than requiring CLI
execution from the browser.

The `/v1/interventions/portfolio*` surfaces are analyst-capable,
organization-scoped portfolio lifecycle APIs. They persist managed municipal
interventions in PostgreSQL, support scenario-run candidate creation,
status/owner/date/note updates, removal, audit logs, cost-benefit ranking, and a
report-ready export used by the `intervention_portfolio` report template.

- `GET /v1/vru/cities/{city_key}/summary`
- `GET /v1/vru/cities/{city_key}/top-corridors`
- `GET /v1/traffic-operations/cities/{city_key}/capabilities`
- `GET /v1/signal-phase/cities/{city_key}/coverage`
- `GET /v1/signal-phase/cities/{city_key}/targets`
- `GET /v1/signal-phase/cities/{city_key}/operator-board`
- `GET /v1/signal-phase/cities/{city_key}/overview`

The VRU and signal-phase routes expose the current Bari-focused operational
artifacts as traffic-operations product contracts. The capabilities endpoint is
the v1.0 production boundary: Bari VRU priorities are v1-supported with
proxy/confidence/governance labels, Bari signal-phase coverage and operator
queues are preview/read-only, and unsupported cities return an explicit
no-data/gated policy rather than misleading artifact failures. Signal-phase
routes require `traffic_engineer`, `admin`, or `super_admin`; VRU summary and
corridor routes remain analyst-readable but still enforce municipality scope.
Set `ROAD_RISK_API_TRAFFIC_OPERATIONS_SIGNAL_PREVIEW_ENABLED=false` to hide the
Bari signal-phase preview and defer it fully to v1.5.

- `GET /v1/automation/schedules`
- `PATCH /v1/automation/schedules/{schedule_name}`
- `GET /v1/automation/runs`
- `POST /v1/automation/runs/trigger`
- `GET /v1/automation/notifications`
- `POST /v1/automation/notifications/deliver`
- `GET /v1/automation/stale-sources`
- `GET /v1/automation/overview`
- `GET /v1/reports/overview`
- `GET /v1/reports`
- `POST /v1/reports/generate`
- `GET /v1/reports/{report_id}`
- `PATCH /v1/reports/{report_id}/lifecycle`
- `GET /v1/reports/{report_id}/download`
- `GET /v1/public/cities/{city_key}/reports`
- `GET /v1/public/cities/{city_key}/reports/{report_id}/download`
- `GET /v1/observability/info`
- `GET /v1/observability/readiness`
- `GET /v1/observability/metrics`

The `/v1/automation/*` surfaces are organization-scoped, require the `admin`
role, and turn the scheduler, recent refresh runs, stale-source checks, delivery
dry-runs, and relevant audit events into a product-facing operations bundle.
Production cadences are environment-backed through
`ROAD_RISK_AUTOMATION_PUBLISHED_REFRESH_INTERVAL_S`,
`ROAD_RISK_AUTOMATION_DASHBOARD_REFRESH_INTERVAL_S`,
`ROAD_RISK_AUTOMATION_STALE_SOURCE_CHECK_INTERVAL_S`,
`ROAD_RISK_AUTOMATION_DATA_QUALITY_CHECK_INTERVAL_S`, and
`ROAD_RISK_AUTOMATION_MONTHLY_REPORT_INTERVAL_S`; pause/resume/update controls
are persisted as audit-log-backed v1 overrides.

The `/v1/reports/*` surfaces are organization-scoped and expose the production
reporting workflow: executive, technical, intervention-portfolio,
data-quality/governance, and public-transparency templates; inline or queued
generation; review/publish/archive lifecycle actions; and governed download
access for generated exports.
When the API is running in a local dev setup without Postgres, inline report
generation degrades to a transient export response instead of failing the UI.
The `/v1/public/cities/{city_key}/reports/*` surfaces expose only published
public-transparency reports and never include internal storage URIs in list
responses.

The `/v1/observability/*` surfaces provide the production operations baseline:
public identity/readiness probes plus an admin-only organization metrics rollup.
Responses are wrapped by security headers from `apps/api/middleware`.

The map endpoints are intentionally product-shaped:

- the public surface resolves municipality runs, public score tiles, and shortlist-backed interventions without exposing raw internal contracts in the browser
- the analyst surface combines published segment geometry, analyst detail rows, and the first Bari-specific junction and crossing support layers

Local development now also enables CORS for `http://localhost:3000` and `http://127.0.0.1:3000` through `ROAD_RISK_API_CORS_ALLOWED_ORIGINS`, so the Next.js shell can call the API directly while running on a separate port.

## Backend tests

```bash
python3 -m pip install -e '.[api,dev]'
pytest tests/test_api_app.py tests/test_api_auth.py -q
```

## Core operational tables

The baseline schema includes:

- `organizations`
- `users`
- `organization_memberships`
- `municipalities`
- `organization_municipalities`
- `data_sources`
- `ingestion_jobs`
- `audit_logs`
- `reports`
- `artifact_references`
