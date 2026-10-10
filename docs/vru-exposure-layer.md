# VRU Exposure Layer

This document covers the first reusable VRU exposure-layer artifact for the exposure backbone.

The executable entrypoint is:

- `road-risk build-vru-exposure-bundle`

The default output bundle lives under:

- `data/planning/vru_exposure/`

## Purpose

This layer turns the existing Bari published run plus movement-object model into reusable exposure outputs instead of only planning rankings.

It writes:

- segment-level VRU exposure outputs with proxy-backed demand, barrier, crossing-gap, and priority fields
- crossing-level VRU exposure outputs linked back to Bari pedestrian-crossing movement objects
- corridor-level VRU exposure profiles derived from the same segment and crossing layer
- bundle JSON, Markdown, manifest, and repo-level index outputs that the run registry can trace

## Build

Generate the Bari pilot bundle:

```bash
python3 - <<'PY'
from road_risk_modeling.vru_exposure import build_vru_exposure_bundle

build_vru_exposure_bundle(
    dashboard_summary_path="data/dashboard/dashboard_summary.json",
    prediction_run_labels=["bari_frequency_baseline_context_v2"],
    movement_objects_path="data/processed/movement_objects/bari/road_movement_objects.geojson",
    output_dir="data/planning/vru_exposure",
)
PY
```

## Outputs

Per run, the bundle writes:

- `vru_exposure_bundle.json`
- `vru_exposure_bundle.md`
- `segment_vru_exposure.geojson`
- `segment_vru_exposure.csv`
- `crossing_vru_exposure.geojson`
- `crossing_vru_exposure.csv`
- `corridor_vru_exposure.csv`
- `vru_exposure_bundle.manifest.json`

Repo-level:

- `vru_exposure_index.json`

## Current Bari Pilot

The current Bari pilot now materializes:

- `13,769` segment exposure features
- `6,146` crossing exposure features
- `822` corridor profiles

Top current priorities are:

- pedestrian segment: `Corso Senatore Antonio De Tullio`
- cyclist segment: `Viale Giuseppe Tatarella`
- crossing candidate: `Via Giuseppe Capruzzi`
- walkability corridor: `Lungomare Imperatore Augusto`

## Interpretation

This bundle is intentionally explicit about its boundary:

- it is `proxy_backed`, not an observed pedestrian-count or micromobility-count program
- it reuses schools, retail, transit, healthcare, built-environment context, and Bari crossing geometry as structured exposure evidence
- it does not change the connector-readiness status for real motor-flow, observed-speed, or counted VRU feeds

That makes it suitable for screening, corridor/crossing prioritization, and repeatable artifact lineage, while the broader Issue 16 backlog still needs real counted exposure feeds.
