# Institution product and implementation model

xROAD uses one maintained application core and a reviewed configuration for each
institution. Each installation has its own infrastructure, database, storage,
identity integration, jurisdiction catalog, enabled workflows, and local model
acceptance. Avoid maintaining a source-code fork for each institution.

This document describes the implemented configuration foundation and the
implementation work that must accompany it. It does not claim that every module
is production-validated or that selecting a profile completes an implementation.

## Product configuration

The institution TOML file now includes a versioned `[deployment]` section.
Version 1 defines the product profile, enabled modules, organizations, and
jurisdictions. Example:

```toml
[deployment]
schema_version = 1
profile = "municipality"
enabled_modules = ["public_portal", "risk_analysis", "reporting", "interventions", "data_ingestion", "administration"]

[[deployment.organizations]]
id = "city-safety-office"
name = "City Road Safety Office"
short_label = "Safety Office"
municipality_ids = ["pilot-city"]

[[deployment.jurisdictions]]
id = "pilot-city"
name = "Pilot City"
region_label = "Pilot Region"
coverage_label = "Awaiting validated data"
```

IDs must match identity-provider claims and the ingested/published data's city
keys. The `municipality_ids` field is retained for compatibility with the existing
API; a configured jurisdiction can represent the institution's operational area.
Every jurisdiction must belong to an organization. Configuration is not evidence
that a source, model, or operational feed is available.

| Profile | Default workflows |
| --- | --- |
| `municipality` | Public transparency, risk analysis, reporting, interventions, ingestion, administration |
| `regional_authority` | Municipality workflows plus automation |
| `transport_ministry` | Regional workflows plus research |
| `police` | Risk analysis, reporting, ingestion, administration, crash reconstruction; public transparency disabled |
| `highway_operator` | Risk analysis, reporting, interventions, ingestion, administration, traffic operations, incident coordination |
| `custom` | Administration only; explicitly select additional modules |

Profiles are starting points, not product maturity or licensing declarations.
`enabled_modules` replaces a profile's default selection; `--enable-module` adds
modules when generating a profile. Invalid names, duplicated IDs, unsupported
schema versions, missing dependencies, and references to unconfigured
jurisdictions are rejected. Administration is always required. Specialized modules
may still be research, preview, or dependent on local feeds; review their existing
capability/model documentation before enabling them for institutional use.

## Create an installation configuration

Install the API or geospatial extras for projection verification:

```bash
python -m pip install -e '.[api,dev]'

python infra/scripts/configure_institution.py \
  --profile municipality \
  --institution-id city-safety-office \
  --institution-name "City Road Safety Office" \
  --jurisdiction-id pilot-city \
  --jurisdiction-name "Pilot City" \
  --country-code IT --timezone Europe/Rome --language it \
  --output configs/pilot-city.toml
```

The command creates a configuration without overwriting an existing file. Review
branding, driving side, units, currency, road-network source, privacy settings,
data mappings, and enabled modules. Add organizations/jurisdictions to the TOML
catalog for a larger institutional footprint.

Country/currency checks use [pycountry's ISO registries](https://pypi.org/project/pycountry/),
timezones use `zoneinfo`, and projection checks use `pyproj` rather than checking
only an `EPSG:` prefix. These checks establish configuration validity, not
regulatory compliance or spatial accuracy of a dataset.

Run the bootstrapper to record configuration readiness and provision deployment
settings/secrets. Create the report's parent directory first:

```bash
mkdir -p output/implementation
python infra/scripts/bootstrap_institution.py \
  --config configs/pilot-city.toml \
  --generate-env --generate-secrets \
  --env-output infra/docker/.env.pilot-city \
  --readiness-report output/implementation/pilot-city-readiness.json
```

Generated settings use a unique Compose project name, dedicated data directory,
and institution-specific secret directory. Use a separate `--env-output` file
for every installation, and pass that file to all Compose commands. Multiple
installations on one host also need different gateway ports or separately
allocated host IPs/front-door routing. Do not point different institutions at the
same data directory, database volume, or secret files. Prepare the generated
`ROAD_RISK_INSTITUTION_BRAND_DIR` directory even when using the built-in logo.
To customize the logo with the same application image, put the approved public
asset there and set `brand_logo_url = "/institution-brand/logo.svg"` (or the
corresponding PNG filename). Only approved public brand assets belong in that
read-only web mount; it must not contain institution data or secrets.

Existing settings and secrets are preserved. The readiness record explicitly
marks runtime acceptance unverified and does not assert regulatory certification.
Follow [institutional deployment](institutional-deployment-guide.md) for actual
TLS, SSO, migrations, service launch, and acceptance checks.

## Runtime behavior

- Public branding publishes identity, units, language, module selection, and a
  configuration revision. It does not publish the private organization catalog.
- The default language follows the institution; a user's explicit saved language
  choice takes precedence. Navigation text has five language dictionaries, while
  deeper screens still need translation and institution-specific review.
- The navigation rail and command palette include enabled workflows visible to
  the user's role. Directly visiting a disabled workspace displays an unavailable
  module state; disabled API workflows return 404 before their handlers execute.
- If public transparency is disabled, the home page presents the institutional
  sign-in portal instead of a public map.
- API token organization/jurisdiction claims are intersected with the installed
  catalog. The authenticated scope catalog then populates the workspace selectors.
  Missing assignments do not grant default access or select a sample city.
- The admin workspace displays installed settings and modules. Platform
  administrators can inspect `/v1/admin/institution-deployment`; ordinary analysts
  cannot read the complete installation catalog.
- Production requires an explicit versioned institution configuration. A missing
  or malformed configured file fails startup rather than falling back to another
  identity. Legacy local configurations remain usable for research/development.

Feature selection supplements existing permissions; it never grants a role,
organization membership, data license, or authority to publish/actuate.

## Configuration change procedure

1. Record the current release, configuration revision, model versions, and backups.
2. Review the TOML change with the institution's product/data owner.
3. Stop new work and drain or cancel affected queued workflows before disabling
   modules. API module gates do not cancel already queued background tasks.
4. Run configuration validation, review the readiness report, and rehearse the
   change in staging with synthetic or approved test data.
5. Apply the same reviewed configuration to API/worker processes and restart them.
   Configuration is loaded once per API process; all replicas must be restarted.
6. Verify identity, language, scope, module visibility, denied requests, and local
   model/data behavior. Archive the new release/configuration acceptance record.

The configuration revision is a deterministic fingerprint of parsed settings,
not a digital signature or an approval log. Keep review and release records in the
institution's controlled change-management system.

## Implementation and acceptance package

Each institution needs an accountable sponsor, data owner, IT operator, safety
lead, and support owner. Complete these deliverables before live acceptance:

| Workstream | Evidence required |
| --- | --- |
| Discovery and scope | Institution footprint, users/roles, chosen modules, operational use cases, exclusions |
| Data onboarding | Source terms/ownership, field mappings, severity/timezone/CRS crosswalks, sample quality checks, refresh cadence |
| Infrastructure | TLS/SSO acceptance, service permissions, approved network exposure, secret management, storage/backup policy |
| Analytics | Local training/calibration, temporal/spatial holdouts, evaluation gates, limitations, approved model versions |
| Workflow acceptance | Role-based scenarios for ingestion, analysis, reports, interventions, approval/publication, denial and recovery |
| Operations | Tested restoration, upgrades/rollback, load expectations, monitoring/alerts, support escalation and maintenance responsibilities |
| Governance and accessibility | Reviewed publication privacy policy, jurisdiction-specific governance decisions, accessibility/language acceptance |

A configuration profile is a repeatable starting point for this implementation
package. The next product milestones are a complete end-to-end pilot on an
institution's infrastructure, reliable upgrade/restore evidence, private/offline
map provisioning, stronger database/service identity isolation, complete
translations, and a managed configuration approval/history workflow. Shared
multi-institution SaaS remains a separate isolation project; this release uses
dedicated installations.
