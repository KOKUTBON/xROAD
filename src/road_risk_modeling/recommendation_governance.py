"""Safety guardrails and calibration benchmarks for AI recommendations."""

from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Iterable, Mapping


RECOMMENDATION_GOVERNANCE_VERSION = "recommendation_governance_v1"


def validate_recommendation_guardrails(
    recommendation: Mapping[str, Any],
    *,
    site_features: Mapping[str, Any],
) -> list[str]:
    """Return fail-closed guardrail violations for one proposed treatment."""
    violations: list[str] = []
    required = (
        "countermeasure_id",
        "countermeasure_name",
        "effect_ratio_low",
        "effect_ratio_central",
        "effect_ratio_high",
        "benefit_cost_ratio",
        "evidence_source",
    )
    for field in required:
        if recommendation.get(field) in (None, ""):
            violations.append(f"missing:{field}")

    try:
        low = float(recommendation["effect_ratio_low"])
        central = float(recommendation["effect_ratio_central"])
        high = float(recommendation["effect_ratio_high"])
        if not all(math.isfinite(value) and value >= 0 for value in (low, central, high)):
            violations.append("invalid:effect_ratio")
        elif not low <= central <= high:
            violations.append("invalid:effect_interval_order")
    except (KeyError, TypeError, ValueError):
        violations.append("invalid:effect_ratio")

    try:
        bcr = float(recommendation["benefit_cost_ratio"])
        if not math.isfinite(bcr) or bcr < 0:
            violations.append("invalid:benefit_cost_ratio")
    except (KeyError, TypeError, ValueError):
        violations.append("invalid:benefit_cost_ratio")

    name = str(recommendation.get("countermeasure_name", "")).lower()
    road_class = str(site_features.get("road_class", "")).lower()
    if "roundabout" in name and road_class in {"motorway", "motorway_link"}:
        violations.append("sanity:roundabout_on_motorway")
    if "raised pedestrian crossing" in name:
        try:
            if float(site_features.get("maxspeed", 0)) > 50:
                violations.append("sanity:raised_crossing_above_50_kmh")
        except (TypeError, ValueError):
            violations.append("sanity:unknown_speed_for_raised_crossing")
    return sorted(set(violations))


def assert_recommendation_safe(
    recommendation: Mapping[str, Any],
    *,
    site_features: Mapping[str, Any],
) -> None:
    violations = validate_recommendation_guardrails(
        recommendation, site_features=site_features
    )
    if violations:
        raise ValueError("Recommendation failed guardrails: " + ", ".join(violations))


def calibration_report(
    cases: Iterable[Mapping[str, Any]],
    *,
    bins: int = 5,
) -> dict[str, Any]:
    """Predicted-vs-observed reduction reliability data, overall and by category."""
    rows = list(cases)
    if bins < 1:
        raise ValueError("bins must be positive.")
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("category") or "unknown")].append(row)

    def summarize(group: list[Mapping[str, Any]]) -> dict[str, Any]:
        bucket_rows: list[dict[str, Any]] = []
        absolute_errors: list[float] = []
        for index in range(bins):
            lower = index / bins
            upper = (index + 1) / bins
            selected = []
            for row in group:
                predicted = float(row["predicted_crash_reduction"])
                if lower <= predicted < upper or (index == bins - 1 and predicted == 1.0):
                    selected.append(row)
            if not selected:
                continue
            predicted_mean = sum(
                float(row["predicted_crash_reduction"]) for row in selected
            ) / len(selected)
            observed_mean = sum(
                float(row["observed_crash_reduction"]) for row in selected
            ) / len(selected)
            absolute_errors.extend(
                abs(
                    float(row["predicted_crash_reduction"])
                    - float(row["observed_crash_reduction"])
                )
                for row in selected
            )
            bucket_rows.append(
                {
                    "bin_lower": round(lower, 4),
                    "bin_upper": round(upper, 4),
                    "count": len(selected),
                    "predicted_mean": round(predicted_mean, 6),
                    "observed_mean": round(observed_mean, 6),
                    "calibration_gap": round(predicted_mean - observed_mean, 6),
                }
            )
        return {
            "case_count": len(group),
            "mean_absolute_calibration_error": round(
                sum(absolute_errors) / len(absolute_errors), 6
            )
            if absolute_errors
            else None,
            "reliability_bins": bucket_rows,
        }

    return {
        "recommendation_governance_version": RECOMMENDATION_GOVERNANCE_VERSION,
        "overall": summarize(rows),
        "by_category": {
            category: summarize(group) for category, group in sorted(grouped.items())
        },
    }


def benchmark_recommendations(
    *,
    irap_cases: Iterable[Mapping[str, Any]],
    historical_cases: Iterable[Mapping[str, Any]],
    minimum_irap_directional_accuracy: float = 0.8,
    minimum_historical_recall: float = 0.6,
) -> dict[str, Any]:
    """Evaluate iRAP improvement direction and historical intervention retrodiction."""
    irap = list(irap_cases)
    history = list(historical_cases)
    directional_hits = sum(
        (float(row["predicted_improvement"]) > 0)
        == (float(row["irap_star_improvement"]) > 0)
        for row in irap
    )
    irap_accuracy = directional_hits / len(irap) if irap else 0.0
    history_hits = sum(
        str(row["actual_countermeasure_id"])
        in {str(value) for value in row.get("recommended_countermeasure_ids", [])}
        for row in history
    )
    history_recall = history_hits / len(history) if history else 0.0
    passed = (
        bool(irap)
        and bool(history)
        and irap_accuracy >= minimum_irap_directional_accuracy
        and history_recall >= minimum_historical_recall
    )
    return {
        "recommendation_governance_version": RECOMMENDATION_GOVERNANCE_VERSION,
        "irap": {
            "case_count": len(irap),
            "directional_accuracy": round(irap_accuracy, 6),
            "threshold": minimum_irap_directional_accuracy,
        },
        "historical_retrodiction": {
            "case_count": len(history),
            "top_k_recall": round(history_recall, 6),
            "threshold": minimum_historical_recall,
        },
        "passed": passed,
    }
