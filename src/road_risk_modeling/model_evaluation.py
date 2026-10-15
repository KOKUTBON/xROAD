"""Unified model evaluation and promotion quality gates (ML-02)."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .recommendation_governance import validate_recommendation_guardrails


EVALUATION_REPORT_VERSION = "model_evaluation_v1"
OPERATORS = {
    "<=": lambda actual, threshold: actual <= threshold,
    ">=": lambda actual, threshold: actual >= threshold,
}


def _metric(payload: Mapping[str, Any], dotted_path: str) -> float:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise KeyError(dotted_path)
        value = value[part]
    return float(value)


def _auc(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    ordered = sorted(zip(scores, labels), key=lambda row: row[0])
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2
        rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _average_precision(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    positives = sum(labels)
    if not positives:
        return None
    hits = 0
    precision_sum = 0.0
    for rank, (_, label) in enumerate(
        sorted(zip(scores, labels), key=lambda row: row[0], reverse=True), start=1
    ):
        if label:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / positives


def _ece(labels: Sequence[int], probabilities: Sequence[float], bins: int = 10) -> float:
    weighted_gap = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [
            (label, probability)
            for label, probability in zip(labels, probabilities)
            if lower <= probability < upper or (index == bins - 1 and probability == 1)
        ]
        if selected:
            observed = sum(label for label, _ in selected) / len(selected)
            predicted = sum(probability for _, probability in selected) / len(selected)
            weighted_gap += len(selected) / len(labels) * abs(observed - predicted)
    return weighted_gap


def _check(
    *,
    check_id: str,
    category: str,
    actual: float | None,
    operator: str,
    threshold: float,
    detail: str = "",
) -> dict[str, Any]:
    if operator not in OPERATORS:
        raise ValueError(f"Unsupported threshold operator: {operator}")
    passed = actual is not None and math.isfinite(actual) and OPERATORS[operator](
        actual, threshold
    )
    return {
        "id": check_id,
        "category": category,
        "actual": actual,
        "operator": operator,
        "threshold": threshold,
        "passed": passed,
        "detail": detail,
    }


def _read_observations(config: Mapping[str, Any], base_dir: Path) -> list[dict[str, str]]:
    path = Path(str(config["observations_path"]))
    if not path.is_absolute():
        path = base_dir / path
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_model(
    record: Mapping[str, Any],
    suite: Mapping[str, Any],
    *,
    suite_dir: str | Path = ".",
) -> dict[str, Any]:
    """Evaluate one registry record using a declarative, model-specific suite."""
    checks: list[dict[str, Any]] = []
    base_dir = Path(suite_dir)
    predictive = suite.get("predictive", {})
    observations: list[dict[str, str]] = []
    labels: list[int] = []
    scores: list[float] = []
    probabilities: list[float] = []
    if predictive.get("observations_path"):
        observations = _read_observations(predictive, base_dir)
        target = str(predictive["target_column"])
        score = str(predictive["score_column"])
        cutoff = float(predictive.get("positive_cutoff", 0))
        labels = [int(float(row[target]) > cutoff) for row in observations]
        scores = [float(row[score]) for row in observations]
        maximum = max(scores, default=0)
        probabilities = [
            min(1.0, max(0.0, value / maximum)) if maximum > 0 else 0.0
            for value in scores
        ]
        thresholds = predictive.get("thresholds", {})
        for metric_name, actual in (
            ("roc_auc", _auc(labels, scores)),
            ("average_precision", _average_precision(labels, scores)),
            ("expected_calibration_error", _ece(labels, probabilities)),
        ):
            if metric_name in thresholds:
                config = thresholds[metric_name]
                checks.append(
                    _check(
                        check_id=f"predictive.{metric_name}",
                        category="predictive",
                        actual=actual,
                        operator=str(config["operator"]),
                        threshold=float(config["value"]),
                    )
                )
    for config in predictive.get("registered_metric_checks", []):
        path = str(config["metric"])
        try:
            actual = _metric(record["metrics"], path)
        except (KeyError, TypeError, ValueError):
            actual = None
        checks.append(
            _check(
                check_id=f"predictive.{path}",
                category="predictive",
                actual=actual,
                operator=str(config["operator"]),
                threshold=float(config["value"]),
                detail="registered metric",
            )
        )

    guardrail = suite.get("guardrail", {})
    for index, case in enumerate(guardrail.get("recommendation_cases", []), start=1):
        violations = validate_recommendation_guardrails(
            case["recommendation"], site_features=case.get("site_features", {})
        )
        expected = bool(case.get("should_pass", True))
        actual_pass = not violations
        checks.append(
            {
                "id": f"guardrail.case_{index}",
                "category": "guardrail",
                "actual": actual_pass,
                "operator": "==",
                "threshold": expected,
                "passed": actual_pass == expected,
                "detail": ", ".join(violations),
            }
        )

    fairness = suite.get("fairness", {})
    if fairness and observations:
        target = str(predictive["target_column"])
        score = str(predictive["score_column"])
        for group_column in fairness.get("group_columns", []):
            group_errors: dict[str, list[float]] = {}
            for row in observations:
                group_errors.setdefault(row[group_column], []).append(
                    abs(float(row[target]) - float(row[score]))
                )
            maes = {
                group: sum(errors) / len(errors)
                for group, errors in group_errors.items()
                if len(errors) >= int(fairness.get("minimum_group_rows", 1))
            }
            ratio = max(maes.values()) / max(min(maes.values()), 1e-12) if len(maes) >= 2 else None
            gap = max(maes.values()) - min(maes.values()) if len(maes) >= 2 else None
            if "maximum_mae_ratio" in fairness:
                checks.append(
                    _check(
                        check_id=f"fairness.{group_column}.mae_ratio",
                        category="fairness",
                        actual=ratio,
                        operator="<=",
                        threshold=float(fairness["maximum_mae_ratio"]),
                        detail=json.dumps(maes, sort_keys=True),
                    )
                )
            if "maximum_mae_gap" in fairness:
                checks.append(
                    _check(
                        check_id=f"fairness.{group_column}.mae_gap",
                        category="fairness",
                        actual=gap,
                        operator="<=",
                        threshold=float(fairness["maximum_mae_gap"]),
                        detail=json.dumps(maes, sort_keys=True),
                    )
                )

    production = suite.get("_production_record")
    for config in suite.get("regression", {}).get("metric_checks", []):
        path = str(config["metric"])
        candidate = _metric(record["metrics"], path)
        baseline = _metric(production["metrics"], path) if production else None
        direction = str(config["direction"])
        tolerance = float(config.get("tolerance", 0))
        if baseline is None:
            passed_value = 0.0
            threshold = tolerance
            detail = "no production baseline; non-regression check is not applicable"
        else:
            degradation = (
                (candidate - baseline) / max(abs(baseline), 1e-12)
                if direction == "lower"
                else (baseline - candidate) / max(abs(baseline), 1e-12)
            )
            passed_value = degradation
            threshold = tolerance
            detail = f"candidate={candidate}; production={baseline}; direction={direction}"
        checks.append(
            _check(
                check_id=f"regression.{path}",
                category="regression",
                actual=passed_value,
                operator="<=",
                threshold=threshold,
                detail=detail,
            )
        )

    categories = {}
    for category in ("predictive", "guardrail", "fairness", "regression"):
        category_checks = [row for row in checks if row["category"] == category]
        categories[category] = {
            "passed": bool(category_checks) and all(row["passed"] for row in category_checks),
            "check_count": len(category_checks),
        }
    return {
        "evaluation_report_version": EVALUATION_REPORT_VERSION,
        "model_name": suite["model_name"],
        "model_version": record["version"],
        "run_id": record["run_id"],
        "suite_name": suite["suite_name"],
        "evaluated_at_utc": datetime.now(UTC).isoformat(),
        "passed": all(summary["passed"] for summary in categories.values()),
        "categories": categories,
        "checks": checks,
    }


def report_markdown(report: Mapping[str, Any]) -> str:
    status = "PASS" if report["passed"] else "FAIL"
    lines = [
        f"# Model evaluation: {report['model_name']} v{report['model_version']}",
        "",
        f"**Result: {status}**",
        "",
        "| Gate | Actual | Requirement | Result |",
        "|---|---:|---:|---|",
    ]
    for check in report["checks"]:
        result = "PASS" if check["passed"] else "FAIL"
        lines.append(
            f"| `{check['id']}` | {check['actual']} | "
            f"{check['operator']} {check['threshold']} | {result} |"
        )
    return "\n".join(lines) + "\n"
