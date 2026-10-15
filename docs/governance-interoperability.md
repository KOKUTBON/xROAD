# Governance And Interoperability

This document covers the repo-level governance layer for live traffic, signal-phase, crash, and published-risk artifacts.

For the crash-layer data boundary, see [data governance](data-governance.md).
DATEX II (below) covers live traffic/event feeds; source-specific crash
schemas remain local and must be licensed before use.

The executable entrypoint is:

- `road-risk build-governance-interoperability-bundle`

The default output bundle lives under:

- `data/planning/governance_interoperability/`

That bundle now contains:

- a source-governance matrix spanning exposure connectors, signal-phase deliveries, crash feeds, and future live traffic/event feeds
- artifact-role policies that define which artifact families are public, analyst-only, partner-restricted, or internal-only
- DATEX II alignment rows for the currently planned live source families
- mobility-data-space handoff patterns and required metadata

## Current Role Boundary

The first published-risk boundary is now explicit and machine-readable:

- `segment_scores_public_geojson`
  public users see only indexed and banded segment scores
- `segment_scores_analyst_csv`
  analysts can see modeled and observed crash counts, but not restricted source feeds
- `segment_score_tiles_public_geojson`
  public users can access only aggregated tile-level risk

## Downstream References

The following artifacts now reference the governance bundle directly:

- exposure connector intake packs and mapping stubs
- exposure connector observation manifests
- Bari signal-phase intake packs and mapping stubs
- signal-phase record ingestion manifests
- published segment-score manifests
- public tile manifests

That means downstream onboarding, ingestion, serving, and resolution steps can follow stable governance IDs instead of relying on free-text notes inside individual docs.
