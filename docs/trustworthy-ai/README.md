# Trustworthy AI Pack — EU AI Act, ALTAI, Model Cards

This directory is the **trustworthy-AI dossier** for the Road Accidents Risk
Modeling platform. It documents how the platform's models are classified under
the **EU AI Act** (Regulation (EU) 2024/1689), assessed against the
**ALTAI** (Assessment List for Trustworthy AI) seven requirements, and
documented through **model cards**, covering
explainability, KPI transparency, and bias review.

## Contents

| Document | Purpose |
| --- | --- |
| [eu-ai-act-classification.md](eu-ai-act-classification.md) | Risk classification of each model under the EU AI Act, with justification and the obligations that follow. |
| [altai-assessment.md](altai-assessment.md) | Self-assessment across the seven ALTAI requirements, with status and gaps. |
| [model-cards.md](model-cards.md) | Model cards for every shipped model (frequency, severity, transferability, scenario ranking), grounded in real metrics. |
| [bias-fairness-review.md](bias-fairness-review.md) | Bias/fairness review — under-reporting, exposure bias, urban/rural and VRU disparities. |
| [uncertainty-reporting.md](uncertainty-reporting.md) | How uncertainty/confidence is computed and surfaced in published outputs. |

## What the platform actually ships

Three distinct decision-support components, only two of which are statistical
models:

1. **Crash-frequency model** — `segment_frequency_baseline`, a Random Forest
   Poisson regressor predicting expected crash counts per road segment-year.
2. **Crash-severity model** — `crash_severity_baseline`, a Random Forest
   classifier estimating the probability a crash is fatal.
3. **Scenario & countermeasure ranking** — `scenario_countermeasure_bundle`, a
   **rule-based** decision-support layer that ranks segments and proposes
   interventions from a fixed library on top of the published risk surface. It
   is not a learned model.

A fourth component, the **transferability evaluation**, is a research/validation
harness rather than a deployed predictor and is documented for completeness.

## Relationship to the rest of the governance stack

This pack is the **AI-assurance layer**. It sits on top of:

- [docs/ethics/](../ethics/) — GDPR / DPIA / data-protection legal layer.
- [docs/data-governance.md](../data-governance.md) — per-field classification and aggregation floors.
- [docs/reproducibility.md](../reproducibility.md) — lineage contracts and manifest hashing that make every metric in the model cards reproducible.

## Scope and status

- This dossier is a **living document**. Any new model, a change of estimator,
  or deployment in a new jurisdiction requires a model-card update and an ALTAI
  review pass before go-live.
- Nothing here is legal advice. The AI Act classification is the platform's
  good-faith self-classification; each deploying controller must confirm it for
  its own operational context (the **intended purpose** drives the legal class).
- The honest headline: the **frequency model is production-grade** for hot-spot
  ranking; the **severity model is a weak, high-uncertainty screen** on sparse
  fatal-crash data and is documented as such rather than oversold.
