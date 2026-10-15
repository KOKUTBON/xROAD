# Infrastructure

This directory groups deployment and runtime infrastructure assets for the production platform.

Subdirectories:

- `docker/` - local and production-like container runtime: API/worker/web Dockerfiles, base `docker-compose.yml`, `.env.example`, `.dockerignore`; see `docker/README.md`.
- `staging/` - local production-like staging harness with env defaults, seed data, rebuild script, and API/web/job/report smoke checks.
- `k8s/` - production deployment package for API, worker, scheduler, web, environment config, secret-manager templates, ingress/TLS, HPA/PDB, and staging/production sample values.
- `scripts/` - backup scripts for Postgres and MinIO/object-storage mirrors.
- `terraform/` - Terraform scaffolding for the default EU/self-hosted Kubernetes target.

## CI/CD coverage

The container runtime is guarded by two GitHub Actions workflows in `.github/workflows/`:

- `docker-build.yml` builds the API, worker, and web images for every PR and push to `main`.
- `compose-validate.yml` runs `docker compose ... config --quiet` against the base stack and the `worker` + `web` profile combination.
