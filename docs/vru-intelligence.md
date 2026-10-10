# VRU Intelligence

This document covers the dedicated VRU and micromobility layer built on top of the published segment scores and Bari object model.

The executable entrypoint is:

- `road-risk build-vru-intelligence-bundle`

The default output bundle lives under:

- `data/planning/vru_intelligence/`

## Purpose

This layer specialises the planning outputs for pedestrian, cyclist, ageing-user, and micromobility questions.

It adds:

- segment-level exposure layers for school frontage, retail frontage, transit access, and micromobility corridor demand
- crossing-level continuity, barrier, and protection-gap indicators derived from the Bari movement object model
- user-group segment rankings for pedestrian, cyclist, ageing-user, and micromobility views
- corridor walkability and rideability profiles with protected-crossing gap counts

## Build

Generate the Bari pilot bundle:

```bash
road-risk build-vru-intelligence-bundle \
  --dashboard-summary-path data/dashboard/dashboard_summary.json \
  --prediction-run-label bari_frequency_baseline_context_v2 \
  --movement-objects-path data/processed/movement_objects/bari/road_movement_objects.geojson \
  --output-dir data/planning/vru_intelligence
```

## Outputs

Per run, the bundle writes:

- `vru_intelligence_bundle.json`
- `vru_intelligence_bundle.md`
- `segment_vru_scores.csv`
- `crossing_priority_profiles.csv`
- `corridor_vru_profiles.csv`
- `vru_intelligence_bundle.manifest.json`

Repo-level:

- `vru_intelligence_index.json`

## Current Interpretation

The current Bari pilot still uses proxy VRU demand from schools, retail, transit, healthcare, and built-environment context. It does not yet use observed pedestrian or micromobility counts.

That means the layer is suitable for prioritisation and screening, with explicit uncertainty notes, while the exposure backbone for real VRU counts remains a separate backlog item.
