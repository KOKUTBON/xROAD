# Intervention Feature Store — Dataset Card

The supervised training dataset for infrastructure-change recommendation:
object-level features joined with intervention labels and outcome targets
("site condition → intervention → outcome"). Built by
`src/road_risk_modeling/intervention_feature_store.py`; one command produces
the full matrix for all pilot cities:

```bash
PYTHONPATH=src python3 tools/build_intervention_feature_store.py
```

Outputs land under `data/processed/intervention_feature_store/`: the matrix
(Parquet when a pandas Parquet engine is installed, CSV fallback otherwise —
the manifest records which), a generated `dataset_card.json` with the
run-specific statistics, and a lineage-hashed manifest.

## Provenance

- **Features** — the per-city `*_context_v2/segment_year_metrics.csv`
  aggregates (static enrichment/topology/geometry, land-use and
  built-environment v2 context, exposure-policy indices, and historical crash
  aggregates per object-year). Every feature column is prefixed `feature_`
  and is taken from the last object-year strictly *before* the intervention
  year.
- **Observed intervention labels** (`label_source=observed_attribute_change`)
  are mined from year-over-year changes in the OSM-derived enrichment
  attributes: posted-speed reduction ≥ 10 km/h (`speed_management`), lane
  count reduced ≥ 1 (`lane_reallocation`), and roundabout conversion
  (`roundabout_conversion`). Note: the currently committed aggregates carry a
  single OSM vintage per city, so attribute history is flat and observed
  labels are absent until multi-vintage aggregates are rebuilt.
- **Synthetic counterfactual labels** (`label_source=synthetic_cmf`,
  `is_synthetic=true`) cover a deterministic 1-in-5 hash sample of untreated
  objects. Each is labeled with a precondition-checked countermeasure from
  the CMF knowledge base (`src/road_risk_modeling/reference_data/countermeasures_v1.csv`), and the
  outcome is the CMF point estimate applied to the observed before-period.
  Synthetic rows must never be evaluated as observed outcomes.

## Outcome targets

Exposure-adjusted (per-km) after-period measurements, in the
`outcome_`-prefixed columns: after-period crash density, crash-density change
and ratio vs the before-period, and severity density (fatalities + injuries
per km) change. Before-period baselines are kept in `before_`-prefixed
columns and may be used as features.

## Split discipline

Reuses the transferability-benchmark conventions
(`split_strategy=leave_one_jurisdiction_out_temporal_holdout`):

- `temporal_split` — by intervention year within each city: latest year =
  `test`, second-latest = `validation`, earlier = `train`.
- `city_fold` — the city key, for leave-one-jurisdiction-out cold-start
  evaluation as in `transferability.py`.

## Leakage checks

Enforced at build time (the build fails on violation) and covered by
`tests/test_intervention_feature_store.py`:

1. No `outcome_` column appears inside the `feature_` block.
2. Every record's baseline feature year is strictly before its intervention
   year.
3. Within each city, train intervention years strictly precede test years.

## Class balance

See `stats.label_counts` / `stats.label_source_counts` /
`stats.synthetic_share` in the generated `dataset_card.json`. As of v1 the
matrix is 100% synthetic (see provenance note above), dominated by
`speed_management` — the recommendation model trained on it must treat the synthetic
share as a prior encoding of the CMF evidence, not as observed effects.

## Known biases

- **Crash reporting bias** — minor and vulnerable-road-user crashes are
  under-reported; outcome densities understate true frequency.
- **Regression to the mean** — observed interventions cluster on recent
  high-crash sites; naive before/after deltas overstate treatment effects.
- **OSM edit-history bias** — attribute changes reflect mapping activity as
  well as physical works; some detected events are map corrections.
- **Synthetic-label circularity** — synthetic outcomes are generated from the
  CMF library; a model evaluated on synthetic rows partially recovers the
  library by construction. Guardrail evaluation must use observed
  rows and external benchmarks only.
