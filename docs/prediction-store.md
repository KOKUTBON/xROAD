# Prediction Store And Segment-Score Contracts

The project now has a first prediction-store layer for publishable segment scores.

## Purpose

The modeling layer already writes metrics, predictions, and lineage. The prediction store is the next step: it reshapes those model outputs into artifacts that dashboards and future APIs can consume directly.

This first implementation is focused on segment-level score publishing, not on running a web server.

## Command

Build a prediction-store snapshot from a frequency-model run:

```bash
road-risk publish-segment-scores \
  data/models/bari_frequency_baseline_context_v2/holdout_predictions.csv \
  data/processed/segments/bari_context_v2/road_segments_context.geojson \
  data/models/bari_frequency_baseline_context_v2/frequency_baseline.metrics.json \
  --output-dir data/prediction_store/bari_frequency_baseline_context_v2
```

## Current Bari Snapshot

The first live store is:

- [segment_scores.manifest.json](../data/prediction_store/bari_frequency_baseline_context_v2/segment_scores.manifest.json)
- [segment_scores_public.geojson](../data/prediction_store/bari_frequency_baseline_context_v2/segment_scores_public.geojson)
- [segment_scores_analyst.geojson](../data/prediction_store/bari_frequency_baseline_context_v2/segment_scores_analyst.geojson)
- [segment_scores_analyst.csv](../data/prediction_store/bari_frequency_baseline_context_v2/segment_scores_analyst.csv)

Current published stats:

- run label: `bari_frequency_baseline_context_v2`
- task: `segment_frequency_baseline`
- rows: `13,769`
- holdout year: `2021`
- predicted crash total: `1160.847539`
- observed crash total: `1415`
- top-5% observed crash share: `0.439576`

That top-5 figure matches the source frequency model because the store is a publication transform, not a new model.

## Public Tile Aggregation

The first tile-style public aggregation now exists on top of the Bari segment-score store.

Build it with:

```bash
road-risk aggregate-public-score-tiles \
  data/prediction_store/bari_frequency_baseline_context_v2/segment_scores_public.geojson \
  data/prediction_store/bari_frequency_baseline_context_v2/segment_scores.manifest.json \
  --output-dir data/prediction_store/bari_frequency_baseline_context_v2_tiles_500m \
  --tile-size-m 500
```

Current Bari tile artifacts:

- [score_tiles.manifest.json](../data/prediction_store/bari_frequency_baseline_context_v2_tiles_500m/score_tiles.manifest.json)
- [score_tiles_public.geojson](../data/prediction_store/bari_frequency_baseline_context_v2_tiles_500m/score_tiles_public.geojson)
- [score_tiles_summary.csv](../data/prediction_store/bari_frequency_baseline_context_v2_tiles_500m/score_tiles_summary.csv)

Current Bari 500 m tile stats:

- covered segment rows: `13,769`
- tile rows: `417`
- max tile public score index: `100.0`
- mean tile public score index: `51.761282`
- tiles marked `high` or `very_high`: `306`
- tiles marked `very_high`: `196`

This tile layer is intentionally public-scoped. It aggregates the published segment-score surface without carrying analyst-only fields such as predicted crash count or observed crash count.

## Read-Only Query Shim

The repo now has a read-only query layer over published manifests. This is not an HTTP service yet, but it matches the contract shape a read-only endpoint would return.

Query the Bari public segment-score store:

```bash
road-risk query-published-resource \
  data/prediction_store/bari_frequency_baseline_context_v2/segment_scores.manifest.json \
  --view public_segments \
  --occurred-year 2021 \
  --min-score-band high \
  --limit 3
```

Query the Bari public tile store:

```bash
road-risk query-published-resource \
  data/prediction_store/bari_frequency_baseline_context_v2_tiles_500m/score_tiles.manifest.json \
  --occurred-year 2021 \
  --min-score-band very_high \
  --limit 3
```

Current verified Bari query counts:

- public segment scores with `high` or `very_high` band: `2,754`
- public tiles with `very_high` band: `196`

The response includes:

- contract version
- manifest path
- applied query filters
- source artifact stats
- filtered result stats
- contract-shaped data payload

## Latest Resource Resolver

The repo now also has a registry-backed resolver so downstream consumers do not need to hard-code the newest manifest path.

Resolve the latest Bari published segment-score store:

```bash
road-risk resolve-latest-published-resource \
  segment_scores \
  --registry-path data/registry/run_registry.jsonl \
  --view public_segments \
  --prediction-run-label bari_frequency_baseline_context_v2 \
  --occurred-year 2021
```

Resolve the latest Bari 500 m public tile store:

```bash
road-risk resolve-latest-published-resource \
  segment_score_tiles \
  --registry-path data/registry/run_registry.jsonl \
  --prediction-run-label bari_frequency_baseline_context_v2 \
  --occurred-year 2021 \
  --tile-size-m 500
```

Current verified resolutions:

- latest published Bari segment-score public path:
  [segment_scores_public.geojson](../data/prediction_store/bari_frequency_baseline_context_v2/segment_scores_public.geojson)
- latest published Bari 500 m public tile path:
  [score_tiles_public.geojson](../data/prediction_store/bari_frequency_baseline_context_v2_tiles_500m/score_tiles_public.geojson)

## Static Published Index

The repo now also has a dashboard-friendly export index on top of the registry-backed resolver. This is the first artifact that lets a consumer read the newest published resources directly from JSON without shelling out to the CLI.

Build it with:

```bash
road-risk build-published-resource-index \
  --registry-path data/registry/run_registry.jsonl \
  --output-dir data/published_index
```

The index writes:

- `published_resources.json`
- `published_resources.manifest.json`

The first live index is:

- [published_resources.json](../data/published_index/published_resources.json)
- [published_resources.manifest.json](../data/published_index/published_resources.manifest.json)

It precomputes latest pointers at four levels:

- by `resource_name`
- by `resource_name` and `prediction_run_label`
- by `resource_name`, `prediction_run_label`, and `occurred_year`
- by `resource_name`, `prediction_run_label`, `occurred_year`, and `tile_size_m`

That means a dashboard can resolve “latest Bari 2021 public tiles at 500 m” or “latest published public segment scores for run X” by reading one static JSON file.

Current live index stats:

- registry entries scanned: `102`
- serving entries scanned: `10`
- catalog records: `8`
- resource count: `2`
- prediction run labels: `4`

Current published run labels:

- `bari_frequency_baseline_context_v2`
- `foggia_municipality_frequency_baseline_context`
- `taranto_municipality_frequency_baseline_context`
- `lecce_municipality_frequency_baseline_context`

## Read-Only HTTP Shim

The repo now also has a minimal local HTTP layer for those published artifacts. It is intentionally small: it serves the published index, latest-resource resolution, and manifest-backed query responses through GET-only endpoints.

Start it with:

```bash
road-risk serve-published-api \
  --host 127.0.0.1 \
  --port 8000 \
  --published-index-path data/published_index/published_resources.json \
  --root-dir . \
  --dashboard-dir dashboard \
  --dashboard-summary-path data/dashboard/dashboard_summary.json
```

Current endpoints:

- `GET /v1/healthz`
- `GET /v1/published-index`
- `GET /v1/dashboard-summary`
- `GET /v1/published-resource/latest`
- `GET /v1/published-resource/query`

Example latest-resource request:

```bash
curl "http://127.0.0.1:8000/v1/published-resource/latest?resource_name=segment_score_tiles&prediction_run_label=bari_frequency_baseline_context_v2&occurred_year=2021&tile_size_m=500"
```

Example query request:

```bash
curl "http://127.0.0.1:8000/v1/published-resource/query?resource_name=segment_score_tiles&prediction_run_label=bari_frequency_baseline_context_v2&occurred_year=2021&tile_size_m=500&min_score_band=very_high&limit=3"
```

This shim is still read-only. It does not introduce a new storage layer, and it resolves everything from the published index plus the existing manifest-backed query contract.

## First Dashboard

The same API process now serves the first dashboard client from `/dashboard/`.

Open:

- `http://127.0.0.1:8000/dashboard/`

This client currently:

- loads the published-resource index from `/v1/published-index`
- loads the dashboard summary from `/v1/dashboard-summary`
- queries the latest matching public tiles or public segments
- renders the response through the MapLibre web map surface in `apps/web`, with the SVG surface retained only as a no-WebGL fallback
- compares all published municipality runs in a side-panel summary
- shows intervention shortlists for the selected city using published analyst segment scores and public tile summaries
- expands selected shortlist items into top supporting segment detail while keeping the browser on manifest-backed published artifacts
- shows top-ranked features and request-trace details

The dashboard remains public-contract only. Analyst-only and municipality-scoped interfaces still belong to later work.

## Contract Split

Two output contracts now exist:

- public: `segment_scores_public_v1`
- analyst: `segment_scores_analyst_v1`
- public tiles: `segment_score_tiles_public_v1`

### Public contract

The public GeoJSON keeps only scoped fields needed for map display and ranking:

- `segment_score_id`
- `segment_id`
- `occurred_year`
- `prediction_run_label`
- `prediction_task`
- `public_score_index`
- `public_score_band`
- `score_decile`

### Analyst contract

The analyst artifacts carry the public fields plus model-facing detail:

- prediction column name
- predicted crash count
- observed crash count
- descending rank
- percentile
- segment context properties already present in the source segment layer

## Lineage Behavior

The published manifest carries its own lineage contract and also embeds the source model run metadata.

Upstream inputs for the Bari store currently include:

- model metrics JSON
- model prediction CSV
- source segment layer

Publishable outputs currently include:

- public segment-score GeoJSON
- analyst segment-score CSV

This is enough for downstream dashboard or API work to reference a single published artifact and still trace it back to the exact source run.

## Current Limit

This is not yet a production prediction service.

- no tile endpoint yet
- no HTTP API yet
- no municipality authorization layer yet
- no time-window query layer yet

It is the first storage and contract layer that those components can build on.
