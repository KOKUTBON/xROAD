# Docker Runtime

This directory contains the local and production-like container runtime
definitions for the Road Risk product platform. Supply-chain hardening
(image scans, signed artifacts, attestations) is handled by the CI and
Kubernetes layers rather than here.

## Files

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Base local stack: API, Postgres+PostGIS, Redis, MinIO, plus profile-gated `worker` and `web` services. |
| `Dockerfile.api` | Runtime image for `apps/api` (FastAPI + uvicorn, non-root user, healthcheck). |
| `Dockerfile.worker` | Runtime image for `services/workers` and `services/scheduler`, with the Celery/Redis worker foundation. |
| `Dockerfile.web` | Runtime image for `apps/web` (Next.js production shell). |
| `../../.dockerignore` | Active root build-context exclusions used by Compose because the build context is the repository root. |
| `.dockerignore` | Historical infra-local exclusion reference; keep aligned with the root ignore file when editing image inputs. |
| `.env.example` | Sample environment file consumed by compose; copy to `.env` before launch. |

## Institutional deployment

For the dedicated institutional stack, follow
[`docs/institutional-deployment-guide.md`](../../docs/institutional-deployment-guide.md).
It requires institution-issued TLS, SSO, and mounted secret files, and publishes
only the HTTPS gateway. The local stack below retains development defaults.

## Quick start

```bash
# 1. Copy the sample env file (or export the variables directly).
cp infra/docker/.env.example infra/docker/.env

# 2. Build and start the API + infra services.
docker compose -f infra/docker/docker-compose.yml up --build api

# 3. Start the web shell as well.
docker compose -f infra/docker/docker-compose.yml --profile web up --build web
# 4. Sanity-check the API.
curl http://localhost:8000/healthz
```

The stack publishes the following local endpoints by default:

- API: <http://localhost:8000>
- Web: <http://localhost:3000>
- MinIO API: <http://localhost:9000>
- MinIO console: <http://localhost:9001>
- Postgres: `localhost:5432` (user/db `postgres` / `road_risk`)
- Redis: `localhost:6379`

## Profiles

The compose file uses [profiles](https://docs.docker.com/compose/profiles/)
to keep half-finished services out of the default `docker compose up`
flow:

- `worker` enables the Celery worker container.
- `scheduler` enables the Celery beat scheduler container.
- `web` enables the Next.js frontend shell.
- `all` enables the worker, scheduler, and web runtime family.

Enable them explicitly with:

```bash
docker compose -f infra/docker/docker-compose.yml --profile worker --profile scheduler --profile web up --build
```

The API and worker services mount `../../data` read-only at `/app/data`
so published map, dashboard, scenario, and report artifacts are
available at runtime without baking the large analytics output tree into
container images.

## Staging smoke

The staging directory provides a reproducible local staging harness:

```bash
STAGING_RESET=1 infra/staging/run_staging_smoke.sh
```

Use the local `docker compose config` check and the public `make docker-build`
target to validate container definitions without private data.

## Environment variables

All variables are documented in `.env.example`. Variables that override
defaults baked into the API image use the existing `ROAD_RISK_*`
namespace from `apps/api/README.md` so the same environment file works
in both local-process and container-based runs.

## CI/CD

Two GitHub Actions workflows guard this layout:

- `.github/workflows/docker-build.yml` builds the API, worker, and web
  images on every PR and push to `main` that touches `infra/docker/`,
  `apps/`, `services/`, `src/`, or `pyproject.toml`.
- `.github/workflows/compose-validate.yml` runs
  `docker compose ... config --quiet` against the base file and the
  `worker` + `scheduler` + `web` profile combination plus the staging
  env file so broken compose edits cannot
  reach `main` silently.

## Tests

`tests/test_infra_docker_assets.py` asserts that the files in this
directory stay structurally correct (compose service list, Dockerfile
existence, `.dockerignore` exclusions, workflow wiring). The full test
suite is run by `python -m pytest -q` in CI.

## Scope of this issue

This scaffold currently provides:

- one runnable API image
- one runnable worker/scheduler image family
- one runnable frontend shell image
- a base compose stack plus a documented `.env.example`
- CI workflows for compose, Docker image builds, and frontend checks
- structural tests for the Docker assets

Production hardening - image scanning, multi-arch builds, registry
publication, supply-chain attestations, Kubernetes manifests - belongs
to the CI and Kubernetes layers and is intentionally out of scope here.
