"""Bari network-recommendation demo.

Trains the seeded recommendation model on the intervention feature store, compares
it against the CMF-prior-only baseline on the held-out split, and exports the
top-20 Bari network recommendations with benefit-cost ratios as GeoJSON + a
CSV brief under ``data/planning/recommendations/bari/``.

Run::

    PYTHONPATH=src python3 tools/recommendation_model_demo.py

Deterministic (seed 42).
"""

from __future__ import annotations

from road_risk_modeling.recommendation_model import build_network_recommendations


def main() -> None:
    result = build_network_recommendations()
    print(f"Built {result['recommendation_count']} network recommendations for {result['city_key']}:")
    print(f"  csv:      {result['recommendations_csv_path']}")
    print(f"  geojson:  {result['recommendations_geojson_path']}")
    print(f"  metrics:  {result['model_metrics_path']}")
    print(f"  manifest: {result['manifest_path']}")
    comparison = result["baseline_comparison"]
    print(
        f"  held-out MAE: model {comparison['model_mae']} vs "
        f"CMF-prior baseline {comparison['cmf_prior_baseline_mae']} "
        f"({comparison['evaluated_records']} records)"
    )
    print("\nTop 5 recommendations:")
    for recommendation in result["top_recommendations"][:5]:
        print(
            f"  #{recommendation['recommendation_rank']} {recommendation['segment_label']}: "
            f"{recommendation['countermeasure_name']} "
            f"(prevents {recommendation['expected_annual_crashes_prevented']:.3f} crashes/yr "
            f"[{recommendation['expected_annual_crashes_prevented_low']:.3f}"
            f"..{recommendation['expected_annual_crashes_prevented_high']:.3f}], "
            f"BCR {recommendation['benefit_cost_ratio']:.2f})"
        )


if __name__ == "__main__":
    main()
