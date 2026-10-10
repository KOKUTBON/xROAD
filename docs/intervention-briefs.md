# Intervention Briefs

The repo now has a static intervention-brief layer built on top of the dashboard summary artifact.

## Purpose

This is the first export-oriented planning artifact in the stack.

It is intended for:

- municipal road-safety planning reviews
- corridor-by-corridor triage
- hotspot-tile review sessions
- lightweight sharing outside the dashboard

It is intentionally derived from published artifacts, transferability outputs, and, when available, the scenario-countermeasure bundle. It does not retrain or replace the published modeling surface.

## Build

Generate briefs for every published run in the dashboard summary:

```bash
road-risk build-intervention-briefs \
  --dashboard-summary-path data/dashboard/dashboard_summary.json \
  --output-dir data/intervention_briefs
```

Generate briefs for only selected runs:

```bash
road-risk build-intervention-briefs \
  --dashboard-summary-path data/dashboard/dashboard_summary.json \
  --prediction-run-label bari_frequency_baseline_context_v2 \
  --prediction-run-label lecce_municipality_frequency_baseline_context \
  --output-dir data/intervention_briefs
```

Generate briefs with scenario-countermeasure recommendations folded in:

```bash
road-risk build-intervention-briefs \
  --dashboard-summary-path data/dashboard/dashboard_summary.json \
  --scenario-bundle-root data/planning/scenario_countermeasures \
  --output-dir data/intervention_briefs
```

## Outputs

For each prediction run label, the builder writes:

- `intervention_brief.json`
- `intervention_brief.md`
- `intervention_brief.manifest.json`

Example paths:

- `data/intervention_briefs/bari_frequency_baseline_context_v2/intervention_brief.json`
- `data/intervention_briefs/bari_frequency_baseline_context_v2/intervention_brief.md`
- `data/intervention_briefs/bari_frequency_baseline_context_v2/intervention_brief.manifest.json`

## Current Content

Each brief includes:

- published holdout overview metrics
- transferability metrics for temporal, cold-start, and history-free settings
- a planning profile for concentration, transfer dependency, and hotspot-surface intensity
- recommended actions derived from the current top corridor and top hotspot tile
- top corridor shortlist entries with supporting segments
- top hotspot-tile shortlist entries with supporting segments
- optional scenario and portfolio recommendations when a matching scenario bundle exists

## Current State

The current four-city build writes briefs for:

- Bari
- Foggia municipality
- Taranto municipality
- Lecce municipality

These artifacts are also tracked by the run registry as a `reporting` stage artifact kind: `intervention_brief`.
