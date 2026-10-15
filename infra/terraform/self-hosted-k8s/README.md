# Self-Hosted Kubernetes Terraform Scaffold

This scaffold prepares the default EU/self-hosted Kubernetes target for
Road Risk. It assumes a Kubernetes cluster already exists and that the
data plane is supplied externally:

- PostgreSQL/PostGIS
- Redis
- S3-compatible object storage or MinIO
- Keycloak-compatible OIDC realm
- DNS zone for the web and API hosts

The Terraform state does not contain application database passwords,
OIDC client secrets, or storage keys. Store those in the platform secret
manager and expose them to Kubernetes with External Secrets Operator or
Sealed Secrets.

## Bootstrap

```bash
cd infra/terraform/self-hosted-k8s
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

The default plan creates the `road-risk` namespace and installs:

- `ingress-nginx`
- `cert-manager`
- `external-secrets`

Disable any controller that already exists on the cluster through
`terraform.tfvars`.

## Deploy Application Manifests

After the bootstrap finishes:

```bash
kubectl apply -f ../../k8s/namespace.yaml
kubectl -n road-risk apply -f ../../k8s/configmap.template.yaml
kubectl -n road-risk apply -f ../../k8s/secrets.external-secret.example.yaml
kubectl -n road-risk apply -f ../../k8s/api.deployment.yaml
kubectl -n road-risk apply -f ../../k8s/worker.deployment.yaml
kubectl -n road-risk apply -f ../../k8s/scheduler.deployment.yaml
kubectl -n road-risk apply -f ../../k8s/web.deployment.yaml
kubectl -n road-risk apply -f ../../k8s/hpa.yaml
kubectl -n road-risk apply -f ../../k8s/pdb.yaml
kubectl -n road-risk apply -f ../../k8s/ingress.yaml
```

For staging or production, copy the templates first and replace hosts,
issuer names, storage endpoints, image tags, and secret remote keys.

## Remote Smoke

Run the release smoke against the deployed API and web hosts:

```bash
python3 ../../../infra/staging/smoke_staging.py \
  --api-base-url https://api.staging.road-risk.example.gov \
  --web-base-url https://staging.road-risk.example.gov \
  --city-key bari \
  --require-ready
```

Add `--bearer-token "$ROAD_RISK_STAGING_SMOKE_TOKEN"` when the staging
API enforces OIDC for all internal checks.
