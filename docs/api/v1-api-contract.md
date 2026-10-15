# V1 API Contract

The Road Risk v1 API is a REST-style FastAPI surface for public
dashboards, municipal analysts, data operators, traffic engineers,
administrators, automation operators, and deployment monitors.

Generated contract files:

- OpenAPI: [openapi-v1.json](openapi-v1.json)
- Route snapshot: [v1-route-contract.json](v1-route-contract.json)

## Base URLs

| Environment | API base URL |
| --- | --- |
| Local Compose | `http://localhost:8000` |
| Local staging | `http://localhost:18000` |
| Remote staging | `https://api.staging.road-risk.example.gov` |
| Production | `https://api.road-risk.example.gov` |

## Authentication

Public endpoints do not require a token. Internal endpoints require an
OIDC/JWKS-validated bearer token when `ROAD_RISK_API_AUTH_ENABLED=true`.

| Role | Access intent |
| --- | --- |
| `public` | Public map, public reports, public health checks. |
| `municipality_viewer` | Read-only internal scoped dashboard access. |
| `analyst` | Risk-map, segment, scenario, intervention, and report workflows. |
| `data_operator` | Upload center, ingestion jobs, validation, execution. |
| `traffic_engineer` | VRU and signal-phase operational workflows. |
| `admin` | Users, data sources, governance, automation, observability metrics. |
| `super_admin` | Platform-wide administration. |

Every scoped internal request must include the relevant
`organization_id`, and city/municipality operations require a token with
matching organization and municipality scope claims.

## Publication Tiers

| Tier | Serving behavior |
| --- | --- |
| `public` | Aggregated or governed outputs safe for citizen-facing dashboards. |
| `internal` | Municipality/operator data visible to scoped authenticated users. |
| `restricted` | Uploads, raw artifacts, manifests, and sensitive operational outputs. |

Artifact download endpoints resolve publication-tier policy before
returning direct public URLs or presigned restricted URLs.

## Route Groups

The route snapshot is generated from the app and currently contains 88
paths and 91 operations.

| Group | Representative paths | Auth/roles |
| --- | --- | --- |
| Public | `GET /v1/public/health`, `GET /v1/public/cities`, `GET /v1/public/cities/{city_key}/risk-map`, `GET /v1/public/cities/{city_key}/risk-tiles`, `GET /v1/public/cities/{city_key}/reports` | none |
| Auth | `GET /v1/auth/me`, `GET /v1/auth/role-matrix`, `GET /v1/auth/organizations/{organization_id}/access` | bearer when auth enabled |
| Analyst | `GET /v1/analyst/cities/{city_key}/risk-map`, `GET /v1/analyst/cities/{city_key}/segments/{segment_score_id}` | `analyst`+ |
| Admin/Governance | `GET /v1/admin/control-center`, `GET /v1/admin/governance-matrix`, `POST /v1/admin/data-sources`, `POST /v1/admin/users/link` | `admin`+ |
| Ingestion | `POST /v1/ingestion-jobs/uploads`, `POST /v1/ingestion-jobs/{job_id}/validate`, `POST /v1/ingestion-jobs/{job_id}/run` | `data_operator` or `admin` |
| Scenario | `GET /v1/scenarios/catalog`, `POST /v1/scenarios/drafts`, `POST /v1/scenarios/drafts/{scenario_draft_id}/run` | `analyst`+ |
| Intervention | `GET /v1/interventions/portfolio`, `POST /v1/interventions/portfolio`, `PATCH /v1/interventions/portfolio/{intervention_id}` | `analyst`+ |
| Reporting | `GET /v1/reports`, `POST /v1/reports/generate`, `GET /v1/reports/{report_id}/download` | `analyst`+ |
| Automation | `GET /v1/automation/overview`, `PATCH /v1/automation/schedules/{schedule_name}`, `POST /v1/automation/runs/trigger` | `admin`+ |
| Traffic Ops | `GET /v1/vru/cities/{city_key}/summary`, `GET /v1/signal-phase/cities/{city_key}/operator-board` | `traffic_engineer`+ |
| Observability | `GET /v1/observability/info`, `GET /v1/observability/readiness`, `GET /v1/observability/metrics` | public for info/readiness, `admin`+ for metrics |

## Product-Plan Reconciliation

| Product-plan route | V1 stable implementation |
| --- | --- |
| `GET /v1/public/health` | Added as a stable alias for `/healthz` and `/v1/healthz`. |
| `GET /v1/public/cities/{city_id}/risk-tiles` | Added as a stable alias for `GET /v1/public/cities/{city_key}/risk-map`. The path parameter is named `city_key` in OpenAPI. |
| `POST /v1/auth/login`, `POST /v1/auth/logout`, `POST /v1/auth/refresh` | Auth is delegated to the OIDC provider and the web OIDC bridge. Backend API clients send bearer tokens directly. |
| `GET /v1/segments`, `GET /v1/junctions`, `GET /v1/crossings` | V1 exposes city-scoped analyst map and segment detail APIs. Generic unscoped collection routes are deferred to v1.1 to avoid cross-municipality leakage. |
| `POST /v1/scenarios` | V1 uses `POST /v1/scenarios/drafts`, then validates and runs the draft. |
| `GET /v1/governance/sources` | V1 governance is available through `GET /v1/admin/governance-matrix` and data-source admin routes. |

## Workflow Examples

Public map:

```bash
curl "$API_BASE_URL/v1/public/cities/bari/risk-map?limit=25"
curl "$API_BASE_URL/v1/public/cities/bari/risk-tiles?limit=25"
```

Register and validate an upload:

```bash
curl -X POST "$API_BASE_URL/v1/ingestion-jobs/uploads" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @docs/api/examples/ingestion-upload-request.json
```

Generate a report:

```bash
curl -X POST "$API_BASE_URL/v1/reports/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @docs/api/examples/report-generate-request.json
```

Run observability metrics:

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$API_BASE_URL/v1/observability/metrics?organization_id=$ORG_ID"
```

## Backward Compatibility Gate

Run locally:

```bash
python3 tools/export_openapi_contract.py --output-dir docs/api
git diff --exit-code docs/api/openapi-v1.json docs/api/v1-route-contract.json
python3 -m pytest tests/test_api_contract.py -q
```

The Python CI workflow runs the same export/diff check.
