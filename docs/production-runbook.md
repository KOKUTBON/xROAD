# Public deployment and operations guide

This is a public deployment checklist for the example API and web services. It
does not describe any private tenant, municipality, dataset, or production
endpoint. Supply secrets through an external secret manager and keep all source
data outside the repository.

Before deployment, verify `/v1/observability/readiness`, security headers,
non-root containers, read-only filesystems, and the checks in
`tools/security_release_checks.py`. The Kubernetes examples include
`web.deployment.yaml`, readiness probes, `RequestObservabilityMiddleware`,
and `SecurityHeadersMiddleware`; review the manifests before use.

For stateful deployments, design backup and restore procedures around the
operator's own PostgreSQL and object-storage policies. The example script
names are `backup_postgres.sh`, `backup_minio.sh`, `restore_postgres.sh`, and
`restore_minio.sh`; test restores in an isolated environment before changing
a live deployment. A failed release can be rolled back with the platform's
normal deployment controller (for example, `kubectl rollout undo`); never
restore private data into a public checkout.

Record an incident in [incident-response.md](incident-response.md), including
the release SHA and relevant logs.

The public validation path is `make security`, `make docker-build`, and the
Python, web, API, model, and pipeline tests described in the README.

For a separately managed environment, a remote staging smoke test may be run
against synthetic data after the local checks pass.
