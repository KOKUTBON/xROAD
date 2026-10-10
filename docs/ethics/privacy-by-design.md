# Data Protection by Design and by Default

**Regulation:** GDPR (EU) 2016/679, Article 25.
**Status:** 2026-06-17.

This note documents how data-protection-by-design is **already implemented**
in the platform's technical governance layer, and what remains to be added
for the roadmap. It is the bridge between the legal DPIA and the working code
described in [data-governance.md](../data-governance.md).

## Design principles, as implemented

1. **Score places, not people.** The platform's outputs are risk scores for
   segments, junctions, and crossings — never person-level predictions. There
   is no automated decision producing legal effects on an individual
   (GDPR Art. 22). This is an architectural constraint, not a setting.

2. **Fail-closed publication surface.** Every field must carry a
   classification (`public` / `internal` / `restricted` / `sensitive`).
   `field_classification_for` raises `KeyError` for any unclassified field, so
   a new field cannot reach a public surface by omission. The CI test suite
   pins the artifact-generator whitelists (`PUBLIC_SCORE_FIELDS`,
   `ANALYST_CORE_FIELDS`, `PUBLIC_TILE_FIELDS`) as subsets of the matrix.

3. **Data minimisation by default.** Precise `latitude`/`longitude` and
   `fatalities`/`injuries` counts are `restricted`; the source `extra` blob is
   `sensitive` and never published row-level. Public surfaces expose only
   banded/indexed scores and relative reductions.

4. **Aggregation floor.** Every public surface is gated by a minimum
   aggregation floor (currently **5**) defined in `public_map_policy.csv`,
   with a positive publishable-field whitelist *and* an explicit redacted-field
   list (defence in depth). The three current public surfaces
   (`public_segment_score_map`, `public_score_tiles`,
   `public_intervention_brief`) are all matrix-tracked and test-enforced.

5. **Synthetic public identifiers.** Internal `segment_id` is never exposed;
   the synthetic `segment_score_id` is the only public surface identifier —
   preventing stable joins back to internal lineage.

6. **Storage limitation by default.** Retention is bounded per data class;
   provider raw exports are purged after normalisation (+30-day quarantine);
   audit logs capped at 24 months.

7. **Purpose limitation enforced organisationally.** The DPIA and the Art. 28
   processor agreement prohibit reuse for individual enforcement, insurance,
   or any non-safety purpose.

8. **Accountability & reproducibility.** The run registry indexes manifests
   and metrics with captured `training_config` and `lineage`, so any
   derived aggregate can be regenerated after a source-level erasure.

## Default settings

- New public surface → blocked until a `public_map_policy` row exists.
- New field → blocked from publication until classified.
- New source → blocked from go-live until it has a legal-basis row
  (RoPA) and a licensing row (register).

## Gaps to close for the roadmap (design-stage)

- **VRU / trajectory / sensing inputs (Issues 21–22):** require
  edge-side anonymisation, no raw-track retention, and k-anonymity / spatial
  generalisation before any pilot — see [anonymisation-policy.md](anonymisation-policy.md).
- **Fairness-by-design:** under-reporting and exposure-bias controls and
  model cards.
- **Cross-border defaults:** prefer open/aggregated data when validating on a
  second Member State.
