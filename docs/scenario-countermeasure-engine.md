# Scenario Countermeasure Engine

This document covers the rule-based scenario and countermeasure layer built on top of the published risk surfaces.

The executable entrypoint is:

- `road-risk build-scenario-countermeasure-bundle`

The default output bundle lives under:

- `data/planning/scenario_countermeasures/`

## Purpose

This layer turns hotspot and corridor rankings into reproducible intervention candidates.

It adds:

- a scenario specification schema with explicit `segment`, `crossing`, `junction`, and `signal` target assets
- a typed intervention library for speed management, crossing protection, signal timing, cycling protection, lighting upgrades, and traffic calming
- rule-based counterfactual feature adjustments over the current published segment scores
- ranked scenario outputs with central, low, and high expected safety deltas
- ranked multi-scenario portfolios that compound effects on overlapping segments without double counting

## Build

Generate bundles for every published run:

```bash
road-risk build-scenario-countermeasure-bundle \
  --dashboard-summary-path data/dashboard/dashboard_summary.json \
  --output-dir data/planning/scenario_countermeasures
```

Generate only the Bari pilot bundle:

```bash
road-risk build-scenario-countermeasure-bundle \
  --dashboard-summary-path data/dashboard/dashboard_summary.json \
  --prediction-run-label bari_frequency_baseline_context_v2 \
  --signal-nodes-path data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson \
  --node-objects-path data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson \
  --output-dir data/planning/scenario_countermeasures
```

## Outputs

The bundle writes a repo-level intervention library plus one run folder per prediction surface.

Repo-level artifacts:

- `intervention_library.json`
- `scenario_countermeasure_index.json`

Per-run artifacts:

- `scenario_spec.json`
- `scenario_bundle.json`
- `scenario_bundle.md`
- `scenario_rankings.csv`
- `portfolio_rankings.csv`
- `scenario_segment_deltas.csv`
- `scenario_bundle.manifest.json`

## Planning Brief Integration

`road-risk build-intervention-briefs` now accepts:

- `--scenario-bundle-root`

When a matching `scenario_bundle.json` exists for a prediction run, the intervention brief includes:

- the top scenario candidates
- the top portfolio candidates
- an additional recommended action sourced from the scenario engine

That keeps the brief layer aligned with the current shortlist and countermeasure reasoning instead of stopping at hotspot identification.
