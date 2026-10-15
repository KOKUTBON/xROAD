# Road Risk API Contracts

This directory is the stable v1 API contract package for municipal,
partner, and internal frontend integrations.

## Artifacts

| File | Purpose |
| --- | --- |
| [`openapi-v1.json`](openapi-v1.json) | Checked-in OpenAPI schema exported from `apps.api.main:create_app`. |
| [`v1-route-contract.json`](v1-route-contract.json) | Compact route snapshot with method, category, auth, role, and publication-tier metadata. |
| [`v1-api-contract.md`](v1-api-contract.md) | Human-readable API guide, route groups, auth rules, and product-plan reconciliation. |
| [`integration-guide.md`](integration-guide.md) | Municipal and frontend integration workflow guide. |
| [`examples/`](examples/) | Minimal request/response payload examples for key workflows. |

## Regenerate

```bash
python3 tools/export_openapi_contract.py --output-dir docs/api
```

The CI contract gate regenerates these files and fails if the checked-in
snapshots drift from the FastAPI app.

## Compatibility Policy

- Existing v1 paths and methods are stable for the v1.0 release line.
- Additive fields are allowed in response objects.
- Removing paths, changing HTTP methods, renaming required request fields,
  or changing role/publication-tier behavior is a breaking change.
- Deprecated aliases remain documented until the next major API version.
