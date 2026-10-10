# Recommendation Model — Model Card

`src/road_risk_modeling/recommendation_model.py`, version
`recommendation_model_v1`. Trains the model that proposes ranked
infrastructure changes per high-risk object, with expected crash reduction
and cost-benefit. Demo:

Serving follows the
[ML training and serving ADR](adr-ml-training-serving-architecture.md):
recommendations are batch-materialized with model and feature-snapshot
lineage, then read by the Proposed Changes workspace rather than inferred inside an API
request.

```bash
PYTHONPATH=src python3 tools/recommendation_model_demo.py
```

## Intended use

Decision support for municipal road-safety planning: shortlisting
evidence-backed countermeasure candidates for high-risk segments/junctions,
with expected annual crashes prevented, an uncertainty interval, and a
benefit-cost ratio. Outputs feed the human-in-the-loop governance review and the
"Proposed Changes" workspace. **Not** a substitute for a road-safety
audit or detailed engineering design; every recommendation cites its CMF
evidence source and must be validated on site.

## Architecture (two-stage, evidence-constrained)

1. **Risk stage (existing):** published frequency/severity risk surfaces and
   the NWRSA ranking (Directive 2019/1936) select high-risk objects.
2. **Recommendation stage:** applicable countermeasures are enumerated from
   the CMF library by precondition matching (a recommendation whose
   precondition check fails is *never* emitted — candidates only exist
   through the check). A seeded `GradientBoostingRegressor` trained on the
   intervention feature store predicts a *residual on top of the log CMF prior*.
   The residual's weight is `n/(n+25)` for `n` training rows of that
   intervention code, and the final estimate is clamped to a slightly relaxed
   CMF confidence envelope — sparse data therefore collapses to the published
   prior, never to an implausible effect.
3. **Cold start:** for cities absent from training, the residual weight is
   halved and the uncertainty interval widened ×1.5 (it widens, never
   vanishes), following the transferability-harness conventions.

## Economics

Severity-weighted social cost per crash from EU appraisal conventions
(VSL €4.3M, serious injury €0.66M, slight €0.025M; Italian urban severity
shares 2% / 25% / 73%) ≈ €269k per injury crash. Benefit-cost ratio uses
indicative capital-cost midpoints per cost band (low €60k / medium €450k /
high €2.5M) over a 10-year horizon discounted at 3%. These are screening
values, not project appraisals.

## Training data & evaluation

- Trained on the intervention feature store (see
  `docs/intervention-feature-store.md`); deterministic with `seed=42`.
- Evaluated against a **CMF-prior-only baseline** (MAE on the outcome
  crash-density ratio) on the held-out temporal test split. On the current
  100%-synthetic store both MAEs are ≈0 by construction (synthetic outcomes
  *are* the prior); the model's ability to beat the prior on genuinely
  observed before/after cases is demonstrated in
  `tests/test_recommendation_model.py`, which constructs observed
  interventions whose true effect varies with site features.

## Explainability

Each recommendation carries `top_risk_factors`: the site features with the
largest importance-weighted deviation from the training mean (direction +
z-score) — a transparent, auditable "why" in lieu of SHAP (no extra
dependency).

## Limits & failure modes

- **Synthetic circularity:** while observed intervention labels remain
  sparse, the learned residual is near zero and outputs effectively reproduce
  the CMF prior — safe, but not yet site-adaptive. Do not read model/baseline
  parity on synthetic data as skill.
- **Regression to the mean:** high-risk sites are selected on observed
  history; expected reductions are optimistic without empirical-Bayes
  adjustment of the baseline.
- **Cost bands are indicative;** BCRs shift materially with real quantities.
- **Precondition coverage:** sites missing the attributes a precondition
  needs are conservatively skipped (fail-closed), so sparse OSM tagging
  reduces recall, not correctness.
- **Transfer:** CMFs are mostly US/Northern-European evidence; local
  calibration (governance guardrails, observed after-periods) is required before
  operational use.
