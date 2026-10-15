# Model Cards

Model cards for every shipped model, following the Mitchell et al. (2019)
structure and EU AI Act Annex IV documentation expectations. Metrics are quoted
from the committed Bari reference run (`holdout_year = 2021`) and are
reproducible via the lineage manifests in each `data/models/.../*.metrics.json`.

---

## Model Card 1 — Crash-Frequency Baseline

| Field | Value |
| --- | --- |
| **Model name** | `segment_frequency_baseline` |
| **Task** | `segment_frequency_baseline` — predict expected crash count per road segment-year |
| **Architecture** | Random Forest Poisson regressor (scikit-learn), with linear-Poisson, last-year, and naive-mean baselines reported alongside |
| **Inputs** | 28 segment features: geometry (length, lanes, max speed, width), network topology (node degrees, intersection/dead-end flags, sinuosity), road class, POI/built-environment counts, an exposure proxy index, and temporal-history features |
| **Target** | `crash_count` (non-negative integer) |
| **Output** | Expected crash count; used to rank segments (top-k hot-spot capture) |
| **Split** | Temporal holdout (train < holdout year ≤ test) |

**Performance (Bari, holdout 2021, 13 769 test segment-years):**

| Metric | RF Poisson | Linear Poisson | Naive mean |
| --- | --- | --- | --- |
| Mean Poisson deviance (↓) | **0.392** | 0.529 | 0.605 |
| MAE (↓) | 0.135 | — | — |
| RMSE (↓) | 0.629 | — | — |
| Top-5% crash capture (↑) | **0.432** | — | — |

**Reading:** the RF model captures **43% of crashes in its top-5% highest-risk
segments** and beats both the linear and naive baselines on deviance — it is
production-grade for hot-spot prioritisation.

- **Intended use:** prioritising road segments for inspection/intervention.
- **Out of scope:** predicting individual crashes, real-time control, causal
  attribution of any single segment's risk.
- **Limitations:** depends on crash **under-reporting** patterns and exposure
  proxy quality (see [bias-fairness-review.md](bias-fairness-review.md)).
- **AI Act class:** minimal/limited risk (see [eu-ai-act-classification.md](eu-ai-act-classification.md)).
- **Uncertainty:** see [uncertainty-reporting.md](uncertainty-reporting.md).

---

## Model Card 2 — Crash-Severity Baseline

| Field | Value |
| --- | --- |
| **Model name** | `crash_severity_baseline` |
| **Task** | `crash_severity_baseline` — probability a segment's crashes are fatal |
| **Architecture** | Random Forest classifier, with logistic-regression, naive-fatal-rate, and prior-segment-fatality baselines |
| **Label** | fatal crash if `severity_level == 'fatal'` or `fatalities > 0` |
| **Output** | Fatal-crash probability; used for severity-weighted triage |

**Performance (Bari, holdout 2021; only 10 fatal positives, base rate 0.71%):**

| Metric | RF classifier | Logistic regression |
| --- | --- | --- |
| ROC-AUC (↑) | **0.654** | 0.471 |
| Average precision (↑) | 0.017 | 0.008 |
| Brier score (↓) | **0.028** | 0.118 |
| Top-10% fatal recall (↑) | 0.40 | 0.10 |
| Top-20% fatal recall (↑) | 0.50 | 0.30 |

> **Honest limitation — this is a weak, high-uncertainty screen.** With only
> **10 fatal crashes** in the test window, average precision is near the base
> rate and per-segment probabilities are not calibrated for individual decisions.
> The model is usable **only** as a coarse severity-weighting signal layered on
> the frequency ranking (it does recover 50% of fatal crashes in its top 20%),
> **not** as a standalone fatality predictor. Severity modelling improves only
> with more years and cross-jurisdiction pooling (the transferability work).

- **Intended use:** severity-weighting of frequency hot-spots.
- **Out of scope:** any individual-level or standalone fatality prediction.
- **AI Act class:** minimal/limited risk.

---

## Model Card 3 — Cross-Jurisdiction Transferability Evaluation

| Field | Value |
| --- | --- |
| **Model name** | `frequency_transferability_evaluation` |
| **Task** | measure how the frequency model degrades when applied to an unseen jurisdiction |
| **Method** | leave-one-jurisdiction-out temporal holdout across 4 modes: within, cross-temporal, cold-start, history-free |
| **Status** | research/validation harness — **not deployed for prediction** |

**Headline cross-border result (IT Puglia + FR BAAC):** French target
deviance degrades 0.124 (within) → 0.186 (cross-border) → 0.231 (cold-start).
See [docs/european-generalisation.md](../european-generalisation.md).

- **Intended use:** quantify portability and motivate local calibration.
- **Out of scope:** producing operational risk scores.

---

## Model Card 4 — Scenario & Countermeasure Ranking

| Field | Value |
| --- | --- |
| **Component name** | `scenario_countermeasure_bundle` |
| **Type** | **Rule-based** decision-support layer (not a learned model) |
| **Method** | ranks segments from the published risk surface and maps each to interventions from a fixed `intervention_library` (e.g. speed management) using deterministic rules |
| **Output** | scenario + countermeasure bundles for human planners |

- **Intended use:** translate risk surfaces into reviewable intervention options.
- **Why documented here:** transparency — reviewers must see that intervention
  recommendations are **deterministic and auditable**, not a black box.
- **Human oversight:** every bundle is a proposal to a road authority.
- **AI Act class:** rule-based; minimal risk.
