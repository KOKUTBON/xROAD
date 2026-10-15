# Kubernetes Deployment Package

This directory contains the default self-hosted Kubernetes package for
the Road Risk municipal road-safety intelligence platform. It is
intended for staging and production environments where PostgreSQL,
Redis, object storage, DNS, TLS, and OIDC are provided as external
platform services.

## Files

| File | Purpose |
| --- | --- |
| `namespace.yaml` | Base `road-risk` namespace and labels. |
| `configmap.template.yaml` | Non-secret API, worker, scheduler, storage, auth, and web runtime configuration. Copy per environment before applying. |
| `secrets.external-secret.example.yaml` | External Secrets Operator example for database, Redis, storage, and OIDC client secrets. |
| `secrets.sealed-secret.example.yaml` | Bitnami Sealed Secrets alternative for locked-down self-hosted clusters. |
| `api.deployment.yaml` | FastAPI backend deployment and ClusterIP service. |
| `worker.deployment.yaml` | Celery worker deployment for ingestion, refresh, and report queues. |
| `scheduler.deployment.yaml` | Celery beat scheduler deployment with exactly one replica. |
| `web.deployment.yaml` | Next.js web deployment and ClusterIP service. |
| `ingress.yaml` | nginx ingress with cert-manager TLS for the web and API hosts. |
| `hpa.yaml` | API, worker, and web HorizontalPodAutoscalers. Scheduler is intentionally excluded. |
| `pdb.yaml` | PodDisruptionBudgets for API, worker, web, and scheduler. |
| `environments/staging.env.example` | Staging host, image, namespace, and smoke-test values. |
| `environments/production.env.example` | Production host, image, namespace, and smoke-test values. |

## Prerequisites

Prepare these outside the application manifests:

- Kubernetes 1.27+ with a default StorageClass
- ingress-nginx or compatible ingress controller
- cert-manager ClusterIssuer named in `ingress.yaml`
- External Secrets Operator or Bitnami Sealed Secrets
- PostgreSQL/PostGIS connection string
- Redis broker/result backend URLs
- S3-compatible object storage bucket and credentials
- Keycloak-compatible OIDC issuer, API client, and web client
- container registry images for `api`, `worker`, and `web`

The Terraform scaffold in
[`../terraform/self-hosted-k8s`](../terraform/self-hosted-k8s) can
prepare the namespace plus ingress-nginx, cert-manager, and
external-secrets when the cluster does not already provide them.

## Environment Separation

Keep staging and production separate at all boundaries:

- different namespaces, for example `road-risk-staging` and
  `road-risk-production`
- different databases and Redis instances
- different object-storage buckets
- different OIDC realm/client credentials or at least separate clients
- different TLS hosts and certificates
- different image tags; production should use immutable release tags
- different smoke-test tokens

Start from `environments/staging.env.example` and
`environments/production.env.example`, then copy the manifest templates
to deployment-owned files outside the repository or to a private
environment repository.

## Image Registry And Rollout

Build and push immutable tags from CI/CD:

```bash
export REGISTRY=registry.example.gov/road-risk
export RELEASE_TAG=1.0.0

docker build -f infra/docker/Dockerfile.api -t "$REGISTRY/api:$RELEASE_TAG" .
docker build -f infra/docker/Dockerfile.worker -t "$REGISTRY/worker:$RELEASE_TAG" .
docker build -f infra/docker/Dockerfile.web -t "$REGISTRY/web:$RELEASE_TAG" .

docker push "$REGISTRY/api:$RELEASE_TAG"
docker push "$REGISTRY/worker:$RELEASE_TAG"
docker push "$REGISTRY/web:$RELEASE_TAG"
```

Create a pull secret when the registry is private:

```bash
kubectl -n road-risk create secret docker-registry road-risk-registry-pull \
  --docker-server=registry.example.gov \
  --docker-username="$REGISTRY_USER" \
  --docker-password="$REGISTRY_PASSWORD"
```

Then update the deployments:

```bash
kubectl -n road-risk set image deployment/road-risk-api api="$REGISTRY/api:$RELEASE_TAG"
kubectl -n road-risk set image deployment/road-risk-worker worker="$REGISTRY/worker:$RELEASE_TAG"
kubectl -n road-risk set image deployment/road-risk-scheduler scheduler="$REGISTRY/worker:$RELEASE_TAG"
kubectl -n road-risk set image deployment/road-risk-web web="$REGISTRY/web:$RELEASE_TAG"

kubectl -n road-risk rollout status deployment/road-risk-api
kubectl -n road-risk rollout status deployment/road-risk-worker
kubectl -n road-risk rollout status deployment/road-risk-scheduler
kubectl -n road-risk rollout status deployment/road-risk-web
```

If admission policy enforces signed images, sign the same immutable tags
with the municipal Sigstore/Cosign workflow before rollout.

## Apply Order

Replace template values before applying to a real cluster. The commands
below use the default namespace name for readability.

```bash
kubectl apply -f infra/k8s/namespace.yaml

# Use one secret strategy.
kubectl -n road-risk apply -f infra/k8s/configmap.template.yaml
kubectl -n road-risk apply -f infra/k8s/secrets.external-secret.example.yaml
# or:
# kubectl -n road-risk apply -f infra/k8s/secrets.sealed-secret.example.yaml

kubectl -n road-risk apply -f infra/k8s/api.deployment.yaml
kubectl -n road-risk apply -f infra/k8s/worker.deployment.yaml
kubectl -n road-risk apply -f infra/k8s/scheduler.deployment.yaml
kubectl -n road-risk apply -f infra/k8s/web.deployment.yaml
kubectl -n road-risk apply -f infra/k8s/hpa.yaml
kubectl -n road-risk apply -f infra/k8s/pdb.yaml
kubectl -n road-risk apply -f infra/k8s/ingress.yaml
```

When using namespace names other than `road-risk`, update the
`metadata.namespace` fields, in-cluster service URLs, and ExternalSecret
remote keys in the environment-owned copies before applying.

## TLS And Ingress

`ingress.yaml` assumes:

- `ingressClassName: nginx`
- a cert-manager ClusterIssuer named `letsencrypt-production`
- hosts for both web and API traffic
- a shared TLS Secret named `road-risk-platform-tls`

For staging, use a staging issuer and staging hostnames until DNS,
certificates, and smoke checks are stable.

## Remote Staging Smoke

After rollout, use the same standard-library smoke runner used by local
staging:

```bash
python3 infra/staging/smoke_staging.py \
  --api-base-url https://api.staging.road-risk.example.gov \
  --web-base-url https://staging.road-risk.example.gov \
  --city-key bari \
  --require-ready \
  --json-output /tmp/road-risk-staging-smoke.json
```

For OIDC-protected staging, pass a short-lived smoke token:

```bash
python3 infra/staging/smoke_staging.py \
  --api-base-url "$SMOKE_API_BASE_URL" \
  --web-base-url "$SMOKE_WEB_BASE_URL" \
  --bearer-token "$ROAD_RISK_STAGING_SMOKE_TOKEN" \
  --city-key "$SMOKE_CITY_KEY" \
  --require-ready
```

Use `--skip-mutating` only for read-only health checks. A release proof
should run the upload, validation, job, report, and download checks.

## Rollback

```bash
kubectl -n road-risk rollout undo deployment/road-risk-api
kubectl -n road-risk rollout undo deployment/road-risk-worker
kubectl -n road-risk rollout undo deployment/road-risk-scheduler
kubectl -n road-risk rollout undo deployment/road-risk-web
```

Rerun the remote smoke command after rollback. If the scheduler rollback
is involved, confirm only one `road-risk-scheduler` pod is running before
unpausing automations.
