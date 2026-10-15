"""Countermeasure knowledge base demo harness.

Loads and validates the versioned CMF evidence library under
``data/knowledge/countermeasures/``, exports the governed JSON library +
lineage manifest, and demonstrates precondition-driven applicability for two
example assets (an unsignalized four-arm junction and a rural undivided
segment) plus the evidence-derived scenario intervention bounds.

Run::

    PYTHONPATH=src python3 tools/countermeasure_knowledge_demo.py

Deterministic; reads only the committed seed CSV.
"""

from __future__ import annotations

from road_risk_modeling.countermeasure_knowledge import (
    build_scenario_intervention_library,
    export_countermeasure_library,
    load_countermeasure_library,
    select_applicable_countermeasures,
)

EXAMPLE_ASSETS = {
    "unsignalized_four_arm_urban_junction": {
        "object_type": "node",
        "signal_control": "unsignalized",
        "arm_count": 4,
        "major_aadt": 12000,
        "area_type": "urban",
        "pedestrian_volume": "present",
    },
    "rural_undivided_segment_with_curves": {
        "object_type": "segment",
        "area_type": "rural",
        "carriageway": "undivided",
        "curve_radius": 180,
        "maxspeed": 90,
        "paved_shoulder": "present",
        "wet_crash_share": 35,
    },
}


def main() -> None:
    library = load_countermeasure_library()
    categories: dict[str, int] = {}
    for countermeasure in library:
        categories[countermeasure.category] = categories.get(countermeasure.category, 0) + 1
    print(f"Loaded {len(library)} validated countermeasures:")
    for category, count in sorted(categories.items()):
        print(f"  {category:<10} {count}")
    print(f"  evidence sources: {len({c.source for c in library})}")

    for label, features in EXAMPLE_ASSETS.items():
        applicable = select_applicable_countermeasures(features, countermeasures=library)
        print(f"\nApplicable countermeasures for {label} ({len(applicable)}):")
        for countermeasure in applicable[:5]:
            print(
                f"  {countermeasure.countermeasure_id}  CMF {countermeasure.cmf:.2f} "
                f"[{countermeasure.cmf_ci_low:.2f}, {countermeasure.cmf_ci_high:.2f}]  "
                f"{countermeasure.name}"
            )

    print("\nEvidence-derived scenario intervention bounds:")
    for record in build_scenario_intervention_library(library):
        bounds = record["baseline_reduction_bounds"]
        supporting = record["evidence"]["supporting_countermeasure_ids"]
        print(
            f"  {record['intervention_code']:<20} "
            f"low {bounds['low']:.3f}  central {bounds['central']:.3f}  high {bounds['high']:.3f}  "
            f"({len(supporting)} supporting CMFs)"
        )

    result = export_countermeasure_library()
    print(f"\nExported library: {result['library_path']}")
    print(f"Manifest:         {result['manifest_path']}")


if __name__ == "__main__":
    main()
