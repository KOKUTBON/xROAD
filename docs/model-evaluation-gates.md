# Model evaluation and promotion gates

The evaluation-gate layer provides one evaluation contract for recommendation, siting, weather,
and predictive risk models. A suite is declarative JSON; the harness resolves
the requested registry version, scores every configured gate, writes JSON and
Markdown reports, and records the result in the MLOps registry.
Its role in batch scoring, stage resolution, queue isolation, and graceful
degradation is defined by the
[ML training and serving ADR](adr-ml-training-serving-architecture.md).

Run the Bari reference workflow locally:

```bash
make mlops-frequency-reference
make eval
make mlops-stage-reference
make mlops-promote-reference
```

`staging` and `production` transitions require the latest evaluation for that
model version to pass. A failed or missing report blocks promotion. Emergency
exceptions must be explicit and attributable:

```bash
PYTHONPATH=src python tools/set_model_stage.py \
  bari_frequency_baseline staging \
  --actor incident-commander \
  --reason "controlled incident deployment" \
  --waive "INC-123: approved until 2026-07-06"
```

The waiver reason, actor, model version, target stage, and timestamp are
appended to `waiver_events` in the registry. A waiver does not alter the
failed report.

## Gate families

- **Predictive:** binary risk-banding ROC AUC and average precision, expected
  calibration error, and declarative registered-metric checks. Transferability
  temporal, cold-start, and history-free metrics use the same registered
  metric checks rather than a separate evaluator.
- **Guardrail:** executable recommendation-governance cases assert both valid and
  prohibited behavior.
- **Fairness/equity:** per-group MAE ratio or absolute-gap parity for any
  suite-provided, pre-banded district
  demographic or proxy column. Suites should use elderly/children density and
  income-proxy bands when those governed attributes are available. The Bari
  reference currently uses road class because its baseline matrix contains no
  district demographics; this is a documented evidence limitation, not a
  fairness claim.
- **Regression:** relative degradation against the current production version,
  with metric direction and tolerance declared per suite. With no production
  version, the check is reported as not applicable and passes at zero
  degradation.

## Reference thresholds

The versioned suite is
[`config/evaluation-suites/bari-frequency-baseline.json`](../config/evaluation-suites/bari-frequency-baseline.json).
It requires ROC AUC ≥ 0.55, average precision ≥ 0.20, ECE ≤ 0.35, MAE ≤ 2.5,
top-5% crash capture ≥ 0.05, road-class MAE gap ≤ 0.65, and no more than 5%
regression against production. Ratio parity remains available for demographic
bands where near-zero group error does not make it numerically unstable.
Threshold changes require review alongside the suite diff; they must not be
changed solely to make a candidate pass.

The harness returns exit code 1 on gate failure, so the same command works
locally, in pre-push automation, and in GitHub Actions once account billing is
restored.
