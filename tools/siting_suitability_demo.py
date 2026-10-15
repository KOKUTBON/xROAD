#!/usr/bin/env python3
"""Build deterministic Bari park and primary-school siting demo bundles."""

from __future__ import annotations

import random
from pathlib import Path

from road_risk_modeling.siting_standards import applicable_rules, load_siting_standards
from road_risk_modeling.siting_suitability import (
    export_siting_bundle,
    rank_candidate_sites,
    train_demand_benefit_model,
    weight_sensitivity_analysis,
)


ROOT = Path(__file__).resolve().parents[1]


def passing_facts(asset_type: str, school_grade: str | None) -> dict:
    facts = {}
    for rule in applicable_rules(
        load_siting_standards(), asset_type=asset_type, school_grade=school_grade
    ):
        predicate = rule.predicate
        operator = predicate["operator"]
        expected = predicate.get("value")
        if operator in {"gte", "lte", "eq"}:
            facts[predicate["field"]] = expected
        elif operator == "exists":
            facts[predicate["field"]] = True
        else:
            facts[predicate["field"]] = "__allowed__"
    return facts


def candidate_rows(asset_type: str, school_grade: str | None, count: int, seed: int) -> list[dict]:
    randomizer = random.Random(seed)
    rows = []
    for index in range(count):
        lon = 16.82 + (index % 8) * 0.018
        lat = 41.075 + (index // 8) * 0.018
        scores = {
            "population_served_score": randomizer.uniform(0.35, 1),
            "provision_gap_score": randomizer.uniform(0.25, 1),
            "access_route_safety_score": randomizer.uniform(0.35, 1),
            "accessibility_score": randomizer.uniform(0.3, 1),
            "equity_score": randomizer.uniform(0.25, 1),
        }
        facts = passing_facts(asset_type, school_grade)
        rows.append(
            {
                "candidate_id": f"bari-{asset_type}-{index + 1:02d}",
                "parcel_source": "built_environment_v2_demo_grid",
                "served_population_estimate": int(900 + 5200 * scores["population_served_score"]),
                "access_route_risk_percentile": round(
                    100 * (1 - scores["access_route_safety_score"]), 2
                ),
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "facts": facts,
                **scores,
            }
        )
    return rows


def training_rows(seed: int = 42) -> list[dict]:
    randomizer = random.Random(seed)
    rows = []
    for _ in range(30):
        values = {feature: randomizer.random() for feature in (
            "population_served_score",
            "provision_gap_score",
            "access_route_safety_score",
            "accessibility_score",
            "equity_score",
        )}
        values["observed_benefit"] = min(
            1.0,
            0.30 * values["population_served_score"]
            + 0.25 * values["provision_gap_score"]
            + 0.20 * values["access_route_safety_score"]
            + 0.15 * values["accessibility_score"]
            + 0.10 * values["equity_score"],
        )
        rows.append(values)
    return rows


def run() -> None:
    model = train_demand_benefit_model(training_rows())
    output = ROOT / "data" / "planning" / "siting" / "bari"
    for asset_type, school_grade, count, limit, seed, name in (
        ("park", None, 24, 10, 101, "top_park_sites"),
        ("school", "primaria", 18, 5, 202, "top_primary_school_sites"),
    ):
        candidates = candidate_rows(asset_type, school_grade, count, seed)
        result = rank_candidate_sites(
            candidates,
            asset_type=asset_type,
            school_grade=school_grade,
            model=model,
        )
        sensitivity = weight_sensitivity_analysis(
            candidates,
            asset_type=asset_type,
            school_grade=school_grade,
            model=model,
            top_k=limit,
        )
        export_siting_bundle(
            result,
            output_dir=output,
            name=name,
            limit=limit,
            sensitivity=sensitivity,
        )


if __name__ == "__main__":
    run()
