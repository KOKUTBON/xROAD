# Uncertainty and Confidence Reporting

How the platform represents and surfaces **uncertainty** in its published
outputs. The guiding principle is **honest imprecision**: road-safety estimates
on sparse crash data are uncertain, so outputs are framed as **rankings and risk
tiers**, not as precise point predictions of how many crashes a segment will have.

## What is surfaced today

1. **Risk tiers, not point counts.** Published surfaces expose ordinal risk
   bands (e.g. `tiles_very_high`) and a `public_score_index` rather than raw
   predicted counts as ground truth. This communicates *relative* risk where the
   model is strong (ranking) and avoids implying *absolute* precision where it
   is weak.
2. **Rank fields.** `score_rank_desc`, `top_5_share_rank`, and per-group
   `best_rank` ([dashboard](../dashboard.md), prediction store)
   present each segment's standing rather than a fragile numeric estimate.
3. **Top-k capture as the headline metric.** Model cards lead with *top-5%
   crash capture* (frequency) and *top-decile fatal recall* (severity) — metrics
   that are meaningful precisely because they target the well-estimated tail and
   are robust to point-estimate noise.
4. **Calibration baselines.** Every model ships naive-mean, last-year, and
   linear baselines so a reader can see the **margin** of the model over chance —
   an uncertainty floor.
5. **Cross-jurisdiction / cold-start gap as transfer uncertainty.** The
   `cold_start_gap_vs_temporal` signal and its rank quantify how much *less*
   confident a prediction is in a jurisdiction the model has not learned —
   directly from the [transferability](../european-generalisation.md) work.
6. **Severity caveat propagated.** The severity model's sparsity is documented
   in its [model card](model-cards.md) and its outputs are scoped to coarse
   weighting, not standalone probabilities.

## What is intentionally not claimed

- **No per-segment confidence intervals are published as calibrated.** The
  Random Forest can produce per-tree prediction variance, but it is **not yet
  surfaced** and would need calibration before being shown as an interval.
  Presenting an uncalibrated interval would be worse than presenting none.
- **No causal claim.** Risk scores are associational; the platform does not
  claim a segment's score is the *cause* of crashes.

## Recommended additions (tracked)

| Addition | Why | Status |
| --- | --- | --- |
| RF per-tree variance → published prediction interval (after calibration) | Per-segment confidence bands for planners | proposed |
| Minimum positive-count gate on severity outputs | Suppress noise-driven severity scores | proposed (ALTAI R2) |
| Stability flag for low-history / cold-start segments | Mark segments where the cold-start gap is large | enabled by transferability signals |

## Why this satisfies trustworthy-AI expectations

ALTAI Requirement 2 (robustness) and Requirement 4 (transparency) ask that a
system **communicate its reliability**. The platform does this by leading with
**ranks and tiers**, **disclosing the severity model's weakness in writing**,
and **quantifying transfer uncertainty** via the cold-start gap — rather than
emitting a single confident-looking number. The honest framing is itself the
uncertainty control.
