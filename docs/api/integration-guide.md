# Municipal And Frontend Integration Guide

This guide describes the minimum integration path for municipal IT
teams, partner systems, and the Road Risk web frontend.

## 1. Environment Setup

1. Request API base URL, OIDC issuer, client id, and allowed redirect
   origins from the platform operator.
2. Configure exact HTTPS CORS origins through
   `ROAD_RISK_API_CORS_ALLOWED_ORIGINS`.
3. Confirm your OIDC token contains role claims matching the v1 role
   matrix, `organization_ids`, and `municipality_ids`.
4. Confirm object-storage publication policy for public, internal, and
   restricted artifacts.

## 2. Public Dashboard Integration

Use unauthenticated public endpoints only:

```bash
curl "$API_BASE_URL/v1/public/health"
curl "$API_BASE_URL/v1/public/cities"
curl "$API_BASE_URL/v1/public/cities/bari/risk-map?limit=100"
curl "$API_BASE_URL/v1/public/cities/bari/risk-tiles?limit=100"
curl "$API_BASE_URL/v1/public/cities/bari/reports"
```

Public data is aggregated/governed and suitable for citizen-facing
views. Do not infer restricted raw source access from public map
availability.

## 3. Internal Frontend Integration

The web app should call its own `/api/backend/*` proxy. The proxy sends
the secure bearer token cookie to the backend and keeps tokens out of
browser JavaScript.

Frontend clients should:

- call `GET /v1/auth/me` after login to hydrate roles and scopes
- route analysts to city-scoped risk/scenario/report surfaces
- route data operators to upload and ingestion-job workflows
- route admins to data-source, user, governance, automation, and
  observability surfaces

## 4. Upload And Ingestion Integration

1. `GET /v1/ingestion-jobs/upload-center` to discover upload-enabled
   data sources.
2. `POST /v1/ingestion-jobs/uploads` to reserve an object-storage upload
   and create the ingestion job.
3. Upload the file to the returned `upload_url`.
4. `POST /v1/ingestion-jobs/{job_id}/validate`.
5. `POST /v1/ingestion-jobs/{job_id}/approve`.
6. `POST /v1/ingestion-jobs/{job_id}/run`.
7. Poll `GET /v1/ingestion-jobs/{job_id}` and inspect manifest/error/log
   endpoints.

## 5. Scenario And Reporting Integration

Scenario workflow:

1. `GET /v1/scenarios/catalog`
2. `GET /v1/scenarios/intervention-library`
3. `POST /v1/scenarios/drafts`
4. `POST /v1/scenarios/drafts/{scenario_draft_id}/validate`
5. `POST /v1/scenarios/drafts/{scenario_draft_id}/run`

Reporting workflow:

1. `GET /v1/reports/overview`
2. `POST /v1/reports/generate`
3. `GET /v1/reports/{report_id}`
4. `GET /v1/reports/{report_id}/download`
5. `PATCH /v1/reports/{report_id}/lifecycle` for publish/archive
   decisions

## 6. Operational Monitoring

Use:

- `GET /v1/observability/info` for deployed version/build metadata
- `GET /v1/observability/readiness` for load-balancer and smoke checks
- `GET /v1/observability/metrics` for admin-scoped incident metrics

Correlate API responses and logs with `X-Request-ID`.

## 7. Breaking Change Process

If a client needs a new field or route:

1. Prefer additive response fields or new paths.
2. Do not change required fields in existing v1 request bodies.
3. Regenerate `docs/api/openapi-v1.json` and
   `docs/api/v1-route-contract.json`.
4. Add request/response examples.
5. Run `python3 -m pytest tests/test_api_contract.py -q`.
