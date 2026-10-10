<p align="center">
  <img src="apps/web/public/brand/road-accidents-risk-modeling-icon.svg" alt="xROAD logo" width="112">
</p>

<h1 align="center">xROAD</h1>

<p align="center">Open road-safety analytics for reproducible risk screening and intervention research.</p>

<p align="center">
  <img src="assets/screenshots/01-home-hero.png" alt="xROAD research dashboard showing a synthetic road-risk screening workflow" width="820">
</p>

xROAD is a public research codebase for road-risk modeling, geospatial feature engineering, safety-performance evaluation, and decision-support prototypes. It includes a Python library, FastAPI service, Next.js interface, reproducible demos, and governance documentation.

This public release contains source code, tests, documentation, branding, and synthetic examples only. It does not contain crash records, private municipality exports, production databases, restricted geospatial data, paid datasets, credentials, or trained private model artifacts.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make demo
```

`make demo` generates deterministic synthetic inputs under ignored `data/` paths and writes aggregate demonstration outputs. No private or downloaded dataset is required.

## Public commands

```bash
make demo                 # synthetic reproducibility demo
make institutional-demo   # white-label institutional onboarding demo
make test                 # Python tests
make security             # release hygiene and secret checks
make frontend-test        # web tests and type checking
make frontend-build       # production web build
make docker-build         # API and web container builds
make reproducibility      # run the demo twice and compare manifests
```

Optional public-data adapters accept datasets only when you have verified their terms. See [`DATA_LICENSES.md`](DATA_LICENSES.md) and [`data/README.md`](data/README.md) before adding any local source.

## White-Label Institutional Architecture

xROAD is designed as a sovereign, turnkey white-label platform for ministries of transport, police agencies, and highway authorities across different jurisdictions:

- **Institutional Product Profiles**: Versioned municipality, regional authority, transport ministry, police, highway operator, and custom profiles control modules and organization/jurisdiction catalogs. See [implementation guide](docs/institution-product-implementation.md).
- **Institutional Tenant Configuration**: Declarative configuration ([`configs/institutional_tenant.example.toml`](configs/institutional_tenant.example.toml)) decouples administrative jurisdiction, branding (name, mark, color scheme), localization (metric/imperial units, languages), and coordinate systems.
- **Universal Coordinate Transformation**: Ingestion engine automatically reprojects native projected coordinate systems (e.g., Lambert-93 `EPSG:2154`, British National Grid `EPSG:27700`, Monte Mario `EPSG:3003`, State Plane) to standard `EPSG:4326` WGS84 without code changes.
- **Declarative Ingestion Adapters**: Flexible schema mapping (`road-risk ingest-declarative`) with built-in presets for UK STATS19, US MMUCC, and custom CSV/JSON/GeoJSON feeds.
- **Dynamic Frontend Theming & I18n**: Next.js client dynamically loads tenant branding at runtime via CSS variable injection with full multi-language localization (EN, IT, FR, ES, DE) and distance/speed unit formatting.
- **Dedicated Institutional Deployments**: HTTPS gateway, mandatory API authentication, mounted secret files, and a configuration bootstrapper ([deployment guide](docs/institutional-deployment-guide.md)). Institution-issued TLS and SSO configuration are required; offline map operation remains unfinished.

Run the institutional onboarding demo:
```bash
make institutional-demo
```

## What is included

- `src/road_risk_modeling/` — modeling, validation, aggregation, evaluation, and declarative ingestion adapters.
- `apps/api/` and `apps/web/` — API and white-label web interfaces.
- `infra/` — sovereign container topologies, Docker compose stacks, and institutional bootstrapping scripts.
- `tools/` — deterministic synthetic demos, institutional onboarding harness, and release checks.
- `docs/` — architecture, methodology, reproducibility, institutional deployment, pilot playbooks, model cards, and data governance.
- `data/` — public layout placeholders only; populated data remains local and ignored.

The strongest reproducible entry points are [`tools/institutional_onboarding_demo.py`](tools/institutional_onboarding_demo.py), [`tools/nwrsa_demo.py`](tools/nwrsa_demo.py), [`tools/scientific_benchmark_demo.py`](tools/scientific_benchmark_demo.py), and `make demo`.

## Data boundary

The repository deliberately tracks no data rows under `data/`. Public examples use synthetic data or documented, legally redistributable sources. Row-level crash records, precise locations, personal data, private exports, production stores, and trained private artifacts must stay outside this repository. Only governance-approved aggregate outputs may be published.

## Documentation

Start with:

- [Institution product and implementation model](docs/institution-product-implementation.md)
- [White-label institutional deployment](docs/institutional-deployment-guide.md)
- [Institutional pilot playbook](docs/institutional-pilot-playbook.md)
- [Architecture](docs/architecture.md)
- [Methodology and reproducibility](docs/reproducibility.md)
- [Model evaluation gates](docs/model-evaluation-gates.md)
- [Ethics and privacy](docs/ethics/README.md)
- [API guide](docs/api/README.md)
- [Data governance](docs/data-governance.md)
- [Dataset and output licensing](DATA_LICENSES.md)

## License and attribution

The source code is licensed under the [Apache License 2.0](LICENSE). Dataset terms are separate and are documented in [`DATA_LICENSES.md`](DATA_LICENSES.md). Third-party notices and attribution requirements must be preserved when redistributing adapted code, maps, or outputs.

Copyright 2026 Rei Doda.

## KOKUTBON community and support

Open technology for the benefit of humankind — built by people, for people, and freely reusable by everyone.

Read [Contributing](CONTRIBUTING.md), [Code of Conduct](CODE_OF_CONDUCT.md), [Support](SUPPORT.md), [Governance](GOVERNANCE.md) and [Security](SECURITY.md). Help sustain the work through [GitHub Sponsors and other contributions](SPONSORSHIP.md). Maintainer release requirements are documented in [Release checklist](RELEASE_CHECKLIST.md).

## Source publication

See [source publication status](SOURCE_PUBLICATION.md) and [local validation record](PUBLICATION_VALIDATION.md) for the initial distribution and remaining release checks.
