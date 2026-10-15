"""Standards-gated multi-criteria siting suitability engine (SIT-02)."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .siting_standards import SitingRule, evaluate_site, load_siting_standards


SITING_SUITABILITY_VERSION = "siting_suitability_v1"
DEFAULT_MCA_WEIGHTS = {
    "population_served": 0.28,
    "provision_gap": 0.24,
    "access_route_safety": 0.20,
    "accessibility": 0.16,
    "equity": 0.12,
}
ML_REFINEMENT_WEIGHT = 0.20
MODEL_FEATURES = (
    "population_served_score",
    "provision_gap_score",
    "access_route_safety_score",
    "accessibility_score",
    "equity_score",
)


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    unknown = set(weights) - set(DEFAULT_MCA_WEIGHTS)
    if unknown:
        raise ValueError(f"Unknown MCA criteria: {sorted(unknown)}")
    resolved = {**DEFAULT_MCA_WEIGHTS, **weights}
    if any(float(value) < 0 for value in resolved.values()):
        raise ValueError("MCA weights cannot be negative.")
    total = sum(float(value) for value in resolved.values())
    if total <= 0:
        raise ValueError("At least one MCA weight must be positive.")
    return {key: float(value) / total for key, value in resolved.items()}


@dataclass(frozen=True)
class DemandBenefitModel:
    """Deterministic k-nearest-neighbour benefit model."""

    training_rows: tuple[dict[str, float], ...]
    neighbour_count: int = 5

    def predict(self, candidate: Mapping[str, Any]) -> float:
        if not self.training_rows:
            return 0.5
        distances: list[tuple[float, float]] = []
        for row in self.training_rows:
            distance = math.sqrt(
                sum(
                    (_clamp(candidate.get(feature)) - float(row[feature])) ** 2
                    for feature in MODEL_FEATURES
                )
            )
            distances.append((distance, float(row["observed_benefit"])))
        nearest = sorted(distances, key=lambda pair: (pair[0], -pair[1]))[
            : self.neighbour_count
        ]
        exact = [benefit for distance, benefit in nearest if distance == 0]
        if exact:
            return round(sum(exact) / len(exact), 6)
        weighted = [(1.0 / max(distance, 1e-9), benefit) for distance, benefit in nearest]
        return round(
            sum(weight * benefit for weight, benefit in weighted)
            / sum(weight for weight, _ in weighted),
            6,
        )


def train_demand_benefit_model(
    existing_facilities: Iterable[Mapping[str, Any]],
    *,
    neighbour_count: int = 5,
) -> DemandBenefitModel:
    rows = []
    for facility in existing_facilities:
        if facility.get("observed_benefit") is None:
            continue
        rows.append(
            {
                **{feature: _clamp(facility.get(feature)) for feature in MODEL_FEATURES},
                "observed_benefit": _clamp(facility["observed_benefit"]),
            }
        )
    return DemandBenefitModel(tuple(rows), max(1, int(neighbour_count)))


def _criteria(candidate: Mapping[str, Any]) -> dict[str, float]:
    return {
        criterion: _clamp(candidate.get(f"{criterion}_score"))
        for criterion in DEFAULT_MCA_WEIGHTS
    }


def _companion_interventions(
    compliance_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    recommendations = {
        "RARM-CROSSING-SCHOOL-26": (
            "CM-CRX-001",
            "Add a protected or raised crossing near the school entrance.",
        ),
        "RARM-CROSSING-PARK-27": (
            "CM-CRX-002",
            "Add a protected crossing near the park entrance.",
        ),
        "RARM-SPEED-SCHOOL-29": (
            "CM-SPD-001",
            "Introduce a 30 km/h school approach and speed-management treatment.",
        ),
        "RARM-RISK-ENTRANCE-25": (
            "CM-SPD-001",
            "Relocate the entrance or mitigate the frontage risk before reconsideration.",
        ),
    }
    return [
        {"countermeasure_id": recommendations[result["rule_id"]][0], "reason": recommendations[result["rule_id"]][1]}
        for result in compliance_results
        if result["status"] == "fail" and result["rule_id"] in recommendations
    ]


def rank_candidate_sites(
    candidates: Iterable[Mapping[str, Any]],
    *,
    asset_type: str,
    school_grade: str | None = None,
    rules: Iterable[SitingRule] | None = None,
    weights: Mapping[str, float] = DEFAULT_MCA_WEIGHTS,
    model: DemandBenefitModel | None = None,
) -> dict[str, Any]:
    resolved_rules = list(rules or load_siting_standards())
    resolved_weights = normalize_weights(weights)
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for candidate in candidates:
        compliance = evaluate_site(
            candidate.get("facts", {}),
            asset_type=asset_type,
            school_grade=school_grade,
            rules=resolved_rules,
        )
        criteria = _criteria(candidate)
        mca_score = sum(
            criteria[key] * resolved_weights[key] for key in resolved_weights
        )
        ml_score = model.predict(candidate) if model else 0.5
        combined = (1 - ML_REFINEMENT_WEIGHT) * mca_score + ML_REFINEMENT_WEIGHT * ml_score
        row = {
            **dict(candidate),
            "asset_type": asset_type,
            "school_grade": school_grade,
            "criteria_scores": criteria,
            "mca_score": round(mca_score, 6),
            "ml_benefit_score": round(ml_score, 6),
            "suitability_score": round(combined, 6),
            "compliance": compliance,
            "companion_interventions": _companion_interventions(compliance["results"]),
        }
        if compliance["overall_status"] == "pass":
            eligible.append(row)
        else:
            row["exclusion_reason"] = compliance["overall_status"]
            excluded.append(row)
    eligible.sort(
        key=lambda row: (-row["suitability_score"], str(row.get("candidate_id")))
    )
    for rank, row in enumerate(eligible, start=1):
        row["rank"] = rank
    return {
        "siting_suitability_version": SITING_SUITABILITY_VERSION,
        "asset_type": asset_type,
        "school_grade": school_grade,
        "weights": resolved_weights,
        "ml_refinement_weight": ML_REFINEMENT_WEIGHT,
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "ranked_candidates": eligible,
        "excluded_candidates": excluded,
    }


def weight_sensitivity_analysis(
    candidates: Iterable[Mapping[str, Any]],
    *,
    asset_type: str,
    school_grade: str | None = None,
    rules: Iterable[SitingRule] | None = None,
    model: DemandBenefitModel | None = None,
    perturbation: float = 0.20,
    top_k: int = 10,
) -> dict[str, Any]:
    candidate_rows = list(candidates)
    resolved_rules = list(rules or load_siting_standards())
    baseline = rank_candidate_sites(
        candidate_rows,
        asset_type=asset_type,
        school_grade=school_grade,
        rules=resolved_rules,
        model=model,
    )
    baseline_ids = [
        row["candidate_id"] for row in baseline["ranked_candidates"][:top_k]
    ]
    scenarios = []
    for criterion in DEFAULT_MCA_WEIGHTS:
        for direction, multiplier in (("down", 1 - perturbation), ("up", 1 + perturbation)):
            changed = dict(DEFAULT_MCA_WEIGHTS)
            changed[criterion] *= multiplier
            result = rank_candidate_sites(
                candidate_rows,
                asset_type=asset_type,
                school_grade=school_grade,
                rules=resolved_rules,
                weights=changed,
                model=model,
            )
            ids = [row["candidate_id"] for row in result["ranked_candidates"][:top_k]]
            overlap = len(set(baseline_ids) & set(ids))
            scenarios.append(
                {
                    "criterion": criterion,
                    "direction": direction,
                    "top_k_overlap": overlap,
                    "top_k_overlap_share": round(overlap / len(baseline_ids), 6)
                    if baseline_ids
                    else None,
                    "top_candidate_id": ids[0] if ids else None,
                }
            )
    return {
        "perturbation": perturbation,
        "top_k": top_k,
        "baseline_top_candidate_ids": baseline_ids,
        "scenarios": scenarios,
        "minimum_top_k_overlap_share": min(
            (
                scenario["top_k_overlap_share"]
                for scenario in scenarios
                if scenario["top_k_overlap_share"] is not None
            ),
            default=None,
        ),
    }


def export_siting_bundle(
    result: Mapping[str, Any],
    *,
    output_dir: str | Path,
    name: str,
    limit: int,
    sensitivity: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = list(result["ranked_candidates"])[:limit]
    geojson_path = output / f"{name}.geojson"
    report_path = output / f"{name}.json"
    markdown_path = output / f"{name}.md"
    geojson_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": row.get("geometry"),
                        "properties": {
                            key: value
                            for key, value in row.items()
                            if key not in {"geometry", "facts"}
                        },
                    }
                    for row in rows
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    report_payload = {
        **{key: value for key, value in result.items() if key not in {"ranked_candidates", "excluded_candidates"}},
        "top_candidates": rows,
        "sensitivity_analysis": sensitivity,
    }
    report_path.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    markdown = [
        f"# {name.replace('_', ' ').title()}",
        "",
        f"- eligible candidates: `{result['eligible_count']}`",
        f"- excluded candidates: `{result['excluded_count']}`",
        f"- exported candidates: `{len(rows)}`",
        "",
        "## Ranking",
        "",
        *[
            f"- `{row['rank']}` `{row['candidate_id']}` — score `{row['suitability_score']:.3f}`, "
            f"served population `{row.get('served_population_estimate', 0)}`, "
            f"access-route risk `{row.get('access_route_risk_percentile', 'n/a')}`"
            for row in rows
        ],
        "",
        "Mandatory rules are fail-closed filters. The demand model refines but cannot override compliance.",
        "",
    ]
    markdown_path.write_text("\n".join(markdown), encoding="utf-8")
    return {
        "geojson_path": str(geojson_path),
        "report_path": str(report_path),
        "markdown_path": str(markdown_path),
    }
