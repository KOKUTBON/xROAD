# EU AI Act Risk Classification

Classification of each platform component under **Regulation (EU) 2024/1689**
(the EU AI Act). The Act assigns obligations by *intended purpose*, not by
technique, so the classification below is tied to how each model is **used** in
a municipal road-safety deployment: as **decision support for road authorities**,
never as an automated decision affecting an individual.

## Summary

| Component | Intended purpose | AI Act class | Rationale |
| --- | --- | --- | --- |
| Crash-frequency model | Rank road segments by expected crash count to prioritise inspections/interventions | **Minimal / limited risk** | Not in any Annex III high-risk area; operates on infrastructure aggregates, not natural persons; output informs human planning decisions only |
| Crash-severity model | Estimate probability a segment's crashes are fatal, for triage | **Minimal / limited risk** | Same basis; aggregate segment-level risk, no individual profiling |
| Scenario & countermeasure ranking | Propose interventions from a fixed library | **Not an AI system in the Act's sense** (rule-based) / minimal risk | Deterministic rules over published risk surfaces; no learning |
| Transferability evaluation | Research validation of model portability | **Minimal risk** (not deployed) | Internal benchmark harness |

**No component is high-risk under Annex III** and none is a prohibited practice
(Art. 5). The platform performs no biometric identification, no social scoring,
no individual risk assessment of natural persons, and no use in law enforcement
or migration. Output is **infrastructure risk at the road-segment level**.

## Why not high-risk

Annex III high-risk categories that a road-safety tool could be mistaken for,
and why they do **not** apply:

- **"Safety component of a product" (Annex III(2), e.g. road traffic
  management)** — the Act's concern is AI acting as a *safety component* in the
  real-time operation of critical infrastructure (e.g. live signal control that
  could endanger people if it fails). This platform produces **offline,
  retrospective planning analytics**; it does not control traffic, signals, or
  any actuator. The signal-phase tooling in the repo is data acquisition and
  operator workflow, not autonomous control. *If* a future deployment wired a
  model into live traffic actuation, that deployment would re-trigger this
  classification and require a high-risk conformity assessment.
- **Law-enforcement / individual risk (Annex III(6))** — the platform never
  scores individuals; enforcement-analytics inputs are aggregate exposure, not
  person-level profiling.

## Obligations the platform meets voluntarily

Even as a minimal/limited-risk system, the platform adopts high-risk-grade
practices because trustworthy-AI guidance expects them:

- **Transparency (Art. 50 spirit)** — published outputs are labelled as
  model-derived estimates with uncertainty; see [uncertainty-reporting.md](uncertainty-reporting.md).
- **Technical documentation** — [model-cards.md](model-cards.md) mirrors
  the relevant Annex IV structure.
- **Data governance (Art. 10 spirit)** — provenance, licensing, and bias
  review are documented in [data governance](../data-governance.md) and
  [bias-fairness-review.md](bias-fairness-review.md).
- **Record-keeping / traceability (Art. 12 spirit)** — every artifact carries a
  lineage contract and SHA-256 manifest ([docs/reproducibility.md](../reproducibility.md)).
- **Human oversight (Art. 14 spirit)** — all outputs are recommendations to a
  human road authority; no automated action. See ALTAI Requirement 1 in
  [altai-assessment.md](altai-assessment.md).

## Re-classification triggers

A deployment must re-run this classification (and likely become high-risk) if it:

1. wires any model into **real-time control** of traffic signals or actuators;
2. introduces **person-level** data (driver/VRU identity, telematics tied to
   individuals) — this also re-triggers the [DPIA](../ethics/dpia.md);
3. is used for **enforcement decisions about identifiable individuals**.
