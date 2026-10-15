# Data Governance And Usage Rights

This document is the canonical narrative behind Issue 01 of the
analytics-engine backlog: it defines which datasets the platform can
store, which fields it can expose to which audience, how long
artifacts are retained, and what may appear on a public map.

The GDPR/ethics layer that sits on top of this technical governance —
the DPIA, Record of Processing Activities, data-protection-by-design
note, and anonymisation policy — lives in [ethics/](ethics/). This
document answers "which role sees which field, at what aggregation?";
the ethics pack answers "on what legal basis, with what risk to data
subjects, and how mitigated?".

The machine-readable artifacts that operationalize this document are
materialized by:

- `road-risk build-data-governance-bundle`

The default output bundle lives under:

- `data/governance/data_governance_bundle/`

That bundle contains:

- `data_classification_matrix.csv`: per-canonical-field classification
  with rationale, aggregation policy, and per-role visibility
- `source_licensing_register.csv`: per-source license register with
  legal status, attribution requirements, redistribution rules, and a
  pointer to the relevant terms
- `retention_rules.csv`: per-data-class retention target, rationale,
  and deletion trigger
- `public_map_policy.csv`: per-public-surface aggregation floor,
  publishable fields, and redacted fields
- `data_governance_bundle.json`: the union of the four matrices plus
  rollup stats
- `data_governance_bundle.manifest.json`: a manifest that points
  downstream consumers (run registry, dashboard, automation) at the
  bundle

The new bundle is deliberately complementary to the existing
`docs/governance-interoperability.md` / `governance_interoperability`
bundle. The governance-interop bundle covers source-family-level
governance, DATEX-II alignment, and mobility-data-space patterns; this
bundle covers the finer-grained per-field / per-source / per-class
matrices that the rest of the analytics engine relies on every time it
writes a row.

## Classification levels

| Level | Definition | Public exposure |
| --- | --- | --- |
| `public` | Safe to publish at any aggregation level. | Direct |
| `internal` | Safe inside the platform for analyst + data-operator roles; aggregable into public when the aggregation floor is met. | Aggregate-only |
| `restricted` | Released under a provider contract or municipal agreement. | Aggregate-only with provider review |
| `sensitive` | Personally identifying or commercially confidential. | Never published, even in aggregate |

## Field classification matrix

The classification matrix now covers seven record kinds, registered
as a single `RECORD_KIND_CLASSIFICATIONS` map:

| Record kind | Source | Anchor module |
| --- | --- | --- |
| `canonical_crash` | `CanonicalCrashRecord` (#2) | `canonical_schema.py` |
| `segment_score` | Published per-segment scores (#12) | `prediction_store.py` |
| `score_tile` | Published score-tile aggregates (#12) | `public_score_tiles.py` |
| `node_year_metric` | Per-junction / per-crossing rollups (#17) | `node_aggregation.py` |
| `crossing_priority` | Bari crossing VRU exposure layer (#20) | `vru_exposure.py` |
| `scenario` | Scenario / countermeasure records (#19) | `scenario_countermeasures.py` |
| `report` | Operational report metadata (#95) | `apps/api/db/models.py::Report` |

Programmatic access:

- `field_classification_for(name, record_kind="...")` returns one entry
  or raises `KeyError`
- `classifications_for_record_kind(kind)` returns the full matrix for
  one record kind
- `is_field_publishable_for_role(name, record_kind="...", role="...")`
  returns a bool; raises `KeyError` for unknown fields rather than
  silently defaulting to `True`
- `publishable_fields_for_role(kind, role)` returns the positive
  whitelist of fields a role can see
- `record_kind_index()` returns a nested
  `kind -> field_name -> FieldClassification` map
- `field_classification_index()` returns the flat
  `{kind}.{name} -> FieldClassification` map spanning every record
  kind

Highlights per record kind:

- `canonical_crash`: exact `latitude` / `longitude` are `restricted`;
  `fatalities` / `injuries` are `restricted` with a five-row aggregation
  floor; `extra` is `sensitive` and never published row-level; year /
  city / roadway category are `public`.
- `segment_score`: banded `public_score_band`, `public_score_index`, and
  `score_decile` are `public`; `predicted_crash_count` is `internal`;
  `observed_crash_count` is `restricted` with a five-row floor;
  `segment_id` is `internal` (the synthetic `segment_score_id` is the
  public surface).
- `node_year_metric`: all crash, injury, and fatality counts are
  `restricted`; junction / crossing identity, role, and signal type are
  `public`; quality-control distances stay `internal`.
- `scenario`: `expected_relative_reduction` is `public` (designed for
  intervention briefs); the absolute `expected_crash_reduction` and its
  confidence interval are `internal`; `affected_assets` and
  `linked_segment_score_ids` are `internal` (analyst-only lineage).
- `report`: report identifiers, types, and statuses are `internal`; the
  `file_storage_uri` is `restricted` and only visible to
  `data_operator` + `admin`.

Adding a new field of any kind requires a corresponding classification
entry; missing entries raise `KeyError` in `field_classification_for`
so the publication surface fails closed.

## Source licensing register

The register lists every active or planned source with:

- `license_id`, `license_name`, `license_url`
- `attribution_required`, `attribution_text`
- `share_alike`, `commercial_use`, `redistribution`
- `terms_summary`
- `publication_status` (aligned with `governance_interoperability`)
- `legal_status` (`approved`, `approved_internal`, `approved_per_request`, `pending_provider_terms`, `pending_operator_terms`)

The register seeds four "approved" or "approved_per_request" sources
(Bari open data crashes, Puglia cleaned legacy, OSM road network,
Bari signal-phase provider deliveries) plus three sources whose
contracts are still pending (motor-flow connector, observed-speed
connector, DATEX-II live event feed). The `pending_*` rows are the
explicit gating list for any future "go live" decision.

## Retention rules

| Data class | Retention target |
| --- | --- |
| `canonical_crash_rows` | indefinite with governance review |
| `provider_raw_exports` | purge after normalization (+30 days quarantine) |
| `motor_flow_observations` | provider terms or 24 months max |
| `observed_speed_observations` | provider terms or 24 months max |
| `signal_phase_provider_data` | while plan is current; 12-month inactivity cap |
| `published_artifacts` | indefinite with lineage |
| `audit_logs` | 24 months |
| `ingestion_job_records` | indefinite with aggregation after 24 months |

## Public-map policy

Every public-facing surface is gated by an entry in
`public_map_policy.csv`. Each entry pins:

- a `record_kind` discriminator anchoring the policy to one of the
  matrices above (e.g. `segment_score`, `scenario`)
- the minimum aggregation floor (currently five)
- the explicit list of publishable fields (positive whitelist)
- the explicit list of redacted fields (defense in depth)
- a free-form notes column describing the surface's redaction logic

The three current public surfaces and their record-kind anchors are:

| surface_id | record_kind | matrix-tracked |
| --- | --- | :---: |
| `public_segment_score_map` | `segment_score` | ✓ |
| `public_score_tiles` | `score_tile` | ✓ |
| `public_intervention_brief` | `scenario` | ✓ |

For policies marked matrix-tracked, the test suite enforces that:

- every publishable field that is in the matrix for the policy's
  `record_kind` is classified `public` in the matrix
- every redacted field that is in the matrix is NOT classified
  `public`
- publishable and redacted lists are disjoint

Policies can list auxiliary fields not registered in the matrix (e.g.
GeoJSON geometry, synthetic identifier hashes); the cross-policy check
only fires for matrix-known fields, so adding a new auxiliary field is
not blocked. All three current public surfaces are matrix-tracked,
including `public_score_tiles` which is now backed by the
`SCORE_TILE_FIELD_CLASSIFICATIONS` registry (10 fields, all public).

Adding a new public surface requires a new policy row (with its
`record_kind`) before the surface ships.

## Artifact-generator constants

Three artifact generators in `road_risk_modeling` declare their own
field whitelists that get baked into each manifest's
`contract.public_fields` / `analyst_csv` headers:

- `road_risk_modeling.prediction_store.PUBLIC_SCORE_FIELDS` —
  controls the public segment-score GeoJSON.
- `road_risk_modeling.prediction_store.ANALYST_CORE_FIELDS` —
  controls the analyst segment-score CSV.
- `road_risk_modeling.public_score_tiles.PUBLIC_TILE_FIELDS` —
  controls the public score-tile GeoJSON.

`tests/test_data_governance.py::ArtifactConstantSubsetTests` pins all
three lists as subsets of the matrix's `'public'` or `'analyst'` role
visibility for their respective record kinds. The tests catch the
kind of drift that produced two earlier divergences:

1. `segment_id` was listed as a public field by the artifact generator
   while the matrix marked it `internal`. The fix: drop `segment_id`
   from `PUBLIC_SCORE_FIELDS`; the synthetic `segment_score_id` is the
   public surface identifier.
2. `prediction_column`, `score_percentile`, and `score_rank_desc`
   appeared in `ANALYST_CORE_FIELDS` (the analyst CSV) but were not
   registered in the `segment_score` matrix at all. The fix: register
   all three as `internal` segment-score fields with `analyst`+ role
   visibility.

After these fixes the `segment_score` matrix is **16 fields** (9
public, 6 internal, 1 restricted), and every entry that appears in
any artifact generator's whitelist is classified.

Once every `ANALYST_CORE_FIELDS` column was matrix-registered, the
analyst view became safe to default-deny too. `VIEW_ROLE_POLICY` in
`road_risk_modeling.published_queries` now filters both the public
and analyst segment-score views (symmetric with the public + analyst
score-tile and Bari junction/crossing layers in `risk_map.py`).

The same pattern is now applied to the scenario-planner surface.
`apps.api.services.scenario_planner` projects every scenario record
through `publishable_fields_for_role("scenario", role)` via
`_scenario_record_for_role`. Both `build_city_scenario_bundle` and
`build_scenario_detail` take a `role` parameter (default `"analyst"`
because the routes are analyst-gated today) and attach a
`redaction_policy` block to the response. Adding a `scenario_rank`
matrix entry was a one-time drift fix (it was emitted by
`_scenario_summary_row` without a classification). A future public
mirror of the scenario endpoints can pass `role="public"` and
inherit the same default-deny gate; every `internal` scenario field
is automatically stripped.

The reporting-hub surface closes the chain. `_full_report_record`
emits 18 fields; the report matrix now classifies all 18 (eight
previously-unclassified entries were registered as `internal`).
Every read endpoint (`list_public_reports`, `list_report_history`,
`get_report_detail`) routes through `_serialize_report_for_role`
and attaches a `redaction_policy` audit block. The public listing
projects through `role="public"`, which default-denies
`organization_id`, `audience`, `summary`, `review_state`,
`lifecycle_actions`, `created_at`, and `file_storage_uri` — closing
a real leak where the public surface previously surfaced the
producing-organization id to anonymous callers. Authenticated
endpoints derive the matrix role from the caller's auth context via
`resolve_report_role_for_auth`, which walks
`(admin, data_operator, analyst, municipality_viewer)` precedence
and falls back to `"public"`.

## Done criteria

Per `docs/implementation-issues.md` Issue 01:

- every source has an explicit legal and publication status ✓
  (`source_licensing_register.csv`, `legal_status`)
- the project knows what can appear in public maps ✓
  (`public_map_policy.csv`)

The remaining work is operational: keeping the matrices current as
new sources are onboarded. The CI test suite asserts the bundle
contract; downstream code paths that emit public artifacts read the
policy before writing.
