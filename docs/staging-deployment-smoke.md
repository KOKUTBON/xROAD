# Local staging smoke test

## Remote Kubernetes Staging

The staging manifests are examples for validating service wiring with empty
stores and synthetic inputs. Run configuration checks before applying them:

The broader infrastructure package also documents `infra/staging/smoke_staging.py`
and `terraform/self-hosted-k8s`; use those examples with the Kubernetes
`cert-manager` setup and deployment rollout checks when operating your own
environment. A web rollout can be inspected with `rollout status
deployment/road-risk-web` after applying an image with
`kubectl -n road-risk set image`.

```bash
docker compose --env-file infra/docker/.env.example \
  -f infra/docker/docker-compose.yml config --quiet
make demo
```

Do not point this smoke test at private crash records, production databases,
restricted geospatial sources, or customer credentials. Keep staging data
outside Git and destroy local state after the test.
