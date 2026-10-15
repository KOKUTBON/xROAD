# Incident Response Checklist

Use this checklist for production and staging incidents affecting the
Road Risk platform.

## Severity

| Severity | Definition | Initial response target |
| --- | --- | --- |
| SEV1 | Public or internal platform unavailable, data exposure suspected, or ingestion/reporting corrupts production records. | 15 minutes |
| SEV2 | Core workflow degraded, repeated job failures, stale high-priority data, or auth disruption for one organization. | 1 hour |
| SEV3 | Isolated endpoint/job issue with workaround and no data-integrity risk. | 1 business day |

## First 15 Minutes

1. Declare the incident in the municipal operations channel.
2. Assign incident commander, technical lead, communications owner, and scribe.
3. Capture the current release tag, build SHA, namespace, and environment.
4. Check `/v1/observability/readiness` and `/v1/observability/metrics`.
5. Search JSON request logs by `request_id`, route, status, and job/report id.
6. Check error tracking for the same `request_id` and route.
7. Freeze non-essential deploys and manual ingestion runs.
8. Decide whether to roll back, pause workers, or isolate one data source.

## Investigation Commands

```bash
kubectl -n road-risk get deploy,pods,hpa,pdb
kubectl -n road-risk rollout status deployment/road-risk-api
kubectl -n road-risk logs deployment/road-risk-api --since=30m
kubectl -n road-risk logs deployment/road-risk-worker --since=30m

curl -fsS "$API_BASE_URL/v1/observability/readiness"
curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$API_BASE_URL/v1/observability/metrics?organization_id=$ORG_ID"
```

## Rollback Drill

```bash
kubectl -n road-risk rollout undo deployment/road-risk-api
kubectl -n road-risk rollout undo deployment/road-risk-worker
kubectl -n road-risk rollout undo deployment/road-risk-scheduler
kubectl -n road-risk rollout undo deployment/road-risk-web

python3 infra/staging/smoke_staging.py \
  --api-base-url "$SMOKE_API_BASE_URL" \
  --web-base-url "$SMOKE_WEB_BASE_URL" \
  --bearer-token "$ROAD_RISK_STAGING_SMOKE_TOKEN" \
  --city-key "$SMOKE_CITY_KEY" \
  --require-ready
```

## Data-Integrity Response

1. Stop scheduled ingestion and report generation.
2. Snapshot the affected database and object-storage bucket.
3. Identify affected `organization_id`, `source_id`, `job_id`, and artifact URIs.
4. Use audit logs to identify publication/download actions during the incident window.
5. Restore into a rehearsal environment first with `infra/scripts/restore_postgres.sh` and `infra/scripts/restore_minio.sh`.
6. Run staging smoke and targeted data-quality checks against the rehearsal restore.
7. Restore production only after the incident commander approves the evidence.

## Post-Incident

1. Publish user-facing status update if public or municipal stakeholders were affected.
2. Add follow-up issues for missing alerts, dashboards, docs, or tests.
3. Review whether RPO/RTO targets were met.
4. Attach request IDs, job IDs, release SHA, logs, metrics snapshots, and smoke output to the incident record.
