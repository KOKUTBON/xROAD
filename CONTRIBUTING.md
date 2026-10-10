# Contributing to Road Accidents Risk Modeling

Thank you for helping improve Road Accidents Risk Modeling. Contributions are welcome across data ingestion, geospatial processing, machine learning, API services, the web application, accessibility, testing, and documentation.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Before you start

Open an issue before making a substantial change to a data contract, canonical schema, model behavior, public API, database migration, user workflow, or deployment architecture. Small fixes and documentation improvements can go directly to a pull request.

Never commit private crash records, personal information, credentials, tokens, production exports, vendor datasets, or data whose redistribution rights are unclear. Use small synthetic fixtures in tests and record the source, license, attribution, and publication tier of new datasets or assets.

## Development setup

Install Python 3.11 or newer and the development dependencies:

```bash
python3 -m pip install -e '.[analytics,geospatial,ml,api,worker,dev]'
```

For web changes:

```bash
cd apps/web
npm ci
```

For container changes, copy `infra/docker/.env.example` to the ignored local file `infra/docker/.env`.

## Make a focused change

- Keep each pull request limited to one coherent problem.
- Preserve compatibility identifiers, migrations, API paths, and data contracts unless the change includes a safe migration.
- Add or update tests when behavior changes.
- Update documentation and examples when commands, configuration, or APIs change.
- Preserve copyright, license, font, and dataset attribution notices.
- Do not commit generated build output, local environments, test reports, caches, or unrestricted analytical exports.

## Required checks

Run the checks relevant to your change. The complete local baseline is:

```bash
PYTHONPATH=src python3 -m pytest -q
python3 tools/security_release_checks.py --summary
make docker-config-all

cd apps/web
npm run typecheck
npm test
npm run build
npm run e2e
npm audit --audit-level=high
```

If the FastAPI surface changes, regenerate the checked-in contract:

```bash
PYTHONPATH=src python3 tools/export_openapi_contract.py --output-dir docs/api
```

For database changes, include an Alembic migration and explain the upgrade and rollback impact. For model or data changes, report the dataset scope, evaluation method, metrics, lineage, and known limitations.

## Pull-request checklist

Describe:

- the problem and the intended outcome;
- the implementation and important tradeoffs;
- the tests and validation performed;
- data, privacy, security, compatibility, or migration effects;
- screenshots or recordings for visible interface changes;
- remaining limitations or follow-up work.

All CI checks must pass. Reviewers may ask for a smaller change, additional evidence, accessibility improvements, or clarification of data rights before merging.

## Licensing

The code is licensed under the [Apache License 2.0](LICENSE). By contributing, you represent that you have the right to submit the contribution under the repository's applicable license. Identify copied or adapted third-party code and preserve its notices.

## Community participation

Follow the [communication guidelines](COMMUNICATION.md) and [organizational governance](GOVERNANCE.md). Keep security and conduct reports confidential and use a verified private channel; never include sensitive details in a public issue. Maintainers verify the reporting contacts and channels listed in the [readiness checklist](RELEASE_CHECKLIST.md).

## KOKUTBON contribution principles

Contribute under the existing **Apache-2.0** license in [LICENSE](LICENSE). You retain copyright in your work. Submit only work you are entitled to share, identify third-party sources and preserve their notices. No copyright assignment or paid membership is required.

Open an issue for substantial proposals, then submit a focused pull request from a branch or fork. Describe the problem, implementation, relevant checks and any privacy, accessibility, migration or safety impact. Use synthetic fixtures and sanitized logs. Maintainer review and passing relevant CI checks are expected before merging. A sole maintainer may merge their own change after checks pass and must record the rationale; no fictitious second reviewer is required.

Small documentation, translation, accessibility and reproducibility improvements are welcome. Funding does not determine review priority. Follow [communication guidelines](COMMUNICATION.md) and [the sponsorship policy](SPONSORSHIP.md).
