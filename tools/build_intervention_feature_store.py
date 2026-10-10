"""Build the intervention-labeled feature store for all pilot cities.

One command assembles the full supervised training matrix — features,
intervention labels (observed + flagged synthetic), exposure-adjusted
outcomes, and transferability-style splits — with a lineage-hashed manifest
and a generated dataset card under
``data/processed/intervention_feature_store/``.

Run::

    PYTHONPATH=src python3 tools/build_intervention_feature_store.py

Deterministic; reads the committed context-v2 segment-year aggregates and the
AI-01 countermeasure knowledge base.
"""

from __future__ import annotations

from road_risk_modeling.intervention_feature_store import build_intervention_feature_store


def main() -> None:
    result = build_intervention_feature_store()
    stats = result["stats"]
    print(f"Built intervention feature store ({result['matrix_format']}):")
    print(f"  matrix:       {result['matrix_path']}")
    print(f"  dataset card: {result['dataset_card_path']}")
    print(f"  manifest:     {result['manifest_path']}")
    print(f"  records:      {stats['record_count']}")
    print(f"  cities:       {stats['city_counts']}")
    print(f"  labels:       {stats['label_counts']}")
    print(f"  sources:      {stats['label_source_counts']}")
    print(f"  splits:       {stats['temporal_split_counts']}")
    print(f"  synthetic:    {stats['synthetic_share']:.1%}")


if __name__ == "__main__":
    main()
