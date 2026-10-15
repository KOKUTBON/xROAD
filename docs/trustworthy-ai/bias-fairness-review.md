# Bias and Fairness Review

Covers bias and fairness. Because the
platform scores **infrastructure (road segments), not natural persons**, the
classical protected-attribute fairness frame applies only indirectly — but the
data-generating process carries strong biases that can systematically
**under-serve communities** if left unexamined.

## 1. Crash under-reporting bias (dominant)

- **What:** police-reported crash data systematically under-records minor,
  single-vehicle, and especially **vulnerable-road-user (VRU)** crashes
  (pedestrians, cyclists). Severity skews what is captured.
- **Impact:** a frequency model trained on under-reported data will
  under-prioritise areas whose crashes are under-recorded — potentially
  lower-income or peripheral areas with weaker reporting.
- **Mitigation:** exposure proxy index and built-environment features partially
  decouple risk from raw counts; the VRU exposure layer
  ([docs/vru-exposure-layer.md](../vru-exposure-layer.md),
  [docs/vru-intelligence.md](../vru-intelligence.md)) exists specifically to
  counter VRU under-representation. *Open action:* publish capture-rate by area
  type in the QA pack.

## 2. Exposure bias (urban vs rural)

- **What:** raw crash counts conflate risk with traffic volume. Urban segments
  accrue more crashes through exposure, not necessarily higher per-trip risk.
- **Impact:** without exposure normalisation, rural high-severity sites are
  under-ranked — a material concern for rural road safety.
- **Evidence in the platform:** the cross-border run
  ([european-generalisation.md](../european-generalisation.md)) shows the
  **rural-skewed French data is the hardest to transfer to** (cold-start
  deviance 0.231 vs Italian 0.13–0.14) — a measured exposure/regime bias, not a
  hypothetical one.
- **Mitigation:** `exposure_proxy_index` and the exposure policy/connector layer;
  France's explicit `agg` urban/rural flag now enables stratified evaluation.

## 3. Severity-model sparsity bias

- **What:** with only **10 fatal positives** in the Bari test window, the
  severity model's per-segment probabilities are noisy and not calibrated.
- **Impact:** acting on individual severity scores would amplify noise into
  resource-allocation decisions.
- **Mitigation:** the [model card](model-cards.md) caps the severity model's
  use to coarse top-decile weighting; ALTAI action gates it behind a minimum
  positive-count threshold. Pooling across jurisdictions (transferability work)
  is the structural fix.

## 4. Geographic / training-distribution bias

- **What:** models are trained predominantly on **Puglia** municipalities;
  performance elsewhere degrades measurably.
- **Mitigation:** transferability is **explicitly measured** rather than
  assumed; deployment guidance recommends a local calibration period over
  zero-shot use in a new jurisdiction.

## Fairness stance

- The platform makes **no decision about any individual** and uses **no
  protected attributes**, so individual-fairness and disparate-treatment claims
  do not arise at the model level.
- The relevant fairness question is **distributional**: does the tool direct
  safety investment equitably across area types and road-user groups? The
  actions above (capture-rate parity reporting, exposure normalisation, VRU
  layer) are the operational answers.

## Tracked actions

| Action | Owner | Status |
| --- | --- | --- |
| Publish urban/rural crash capture-rate parity in QA pack | platform | open |
| Gate severity outputs behind minimum positive-count threshold | platform | open (ALTAI R2) |
| Stratified cross-border evaluation by `agg` (urban/rural) | platform | enabled; to schedule |
