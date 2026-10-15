"""Versioned, machine-checkable planning and safe-siting standards (SIT-01)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


SITING_STANDARDS_VERSION = "siting_standards_v1"
SITING_RULE_SCHEMA_VERSION = "siting_standard_rule_v1"
# Shipped inside the package so it resolves under a plain `pip install`.
DEFAULT_SITING_STANDARDS_PATH = Path(__file__).resolve().parent / "reference_data" / "siting_standards_v1.yaml"
VALID_RULE_TYPES = {"quantitative_threshold", "spatial_constraint", "capacity_ratio"}
VALID_SEVERITIES = {"mandatory", "advisory"}
VALID_OPERATORS = {"gte", "lte", "eq", "not_in", "exists"}


@dataclass(frozen=True)
class SitingRule:
    rule_id: str
    jurisdiction: str
    asset_types: tuple[str, ...]
    citation: str
    source_url: str
    rule_type: str
    severity: str
    description: str
    predicate: dict[str, Any]
    school_grades: tuple[str, ...] = ()


class CountrySitingAdapter:
    """Jurisdiction hook for extending the shared rule library."""

    jurisdiction: str

    def applies(self, rule: SitingRule) -> bool:
        return rule.jurisdiction in {self.jurisdiction, "EU", "GLOBAL", "RARM"}


class ItalySitingAdapter(CountrySitingAdapter):
    jurisdiction = "IT"


def load_siting_standards(
    path: str | Path = DEFAULT_SITING_STANDARDS_PATH,
) -> list[SitingRule]:
    """Load JSON-compatible YAML without adding a runtime YAML dependency."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SITING_RULE_SCHEMA_VERSION:
        raise RuntimeError("Unsupported siting-rule schema version.")
    if payload.get("library_version") != SITING_STANDARDS_VERSION:
        raise RuntimeError("Unsupported siting-standards library version.")
    rows = payload.get("rules")
    if not isinstance(rows, list):
        raise RuntimeError("Siting standards must contain a rules list.")

    rules: list[SitingRule] = []
    seen: set[str] = set()
    for row in rows:
        identifier = str(row.get("id") or "")
        predicate = row.get("predicate")
        if not identifier or identifier in seen:
            raise RuntimeError(f"Missing or duplicate siting rule id: {identifier!r}")
        if row.get("rule_type") not in VALID_RULE_TYPES:
            raise RuntimeError(f"{identifier}: invalid rule type.")
        if row.get("severity") not in VALID_SEVERITIES:
            raise RuntimeError(f"{identifier}: invalid severity.")
        if not isinstance(predicate, dict) or predicate.get("operator") not in VALID_OPERATORS:
            raise RuntimeError(f"{identifier}: invalid predicate.")
        if not row.get("citation") or not row.get("source_url"):
            raise RuntimeError(f"{identifier}: citation and source_url are required.")
        seen.add(identifier)
        rules.append(
            SitingRule(
                rule_id=identifier,
                jurisdiction=str(row["jurisdiction"]),
                asset_types=tuple(str(value) for value in row["asset_types"]),
                citation=str(row["citation"]),
                source_url=str(row["source_url"]),
                rule_type=str(row["rule_type"]),
                severity=str(row["severity"]),
                description=str(row["description"]),
                predicate=dict(predicate),
                school_grades=tuple(str(value) for value in row.get("school_grades", [])),
            )
        )
    return rules


def applicable_rules(
    rules: Iterable[SitingRule],
    *,
    asset_type: str,
    school_grade: str | None = None,
    adapter: CountrySitingAdapter | None = None,
) -> list[SitingRule]:
    selected = []
    for rule in rules:
        if adapter and not adapter.applies(rule):
            continue
        if asset_type not in rule.asset_types:
            continue
        if rule.school_grades and school_grade not in rule.school_grades:
            continue
        selected.append(rule)
    return selected


def check_siting_compliance(
    rule: SitingRule, facts: Mapping[str, Any]
) -> dict[str, Any]:
    predicate = rule.predicate
    field = str(predicate["field"])
    if field not in facts or facts[field] is None:
        status = "insufficient_data"
        actual = None
    else:
        actual = facts[field]
        expected = predicate.get("value")
        operator = predicate["operator"]
        try:
            if operator == "gte":
                passed = float(actual) >= float(expected)
            elif operator == "lte":
                passed = float(actual) <= float(expected)
            elif operator == "eq":
                passed = actual == expected
            elif operator == "not_in":
                passed = actual not in expected
            else:
                passed = bool(actual)
        except (TypeError, ValueError):
            status = "insufficient_data"
        else:
            status = "pass" if passed else "fail"
    return {
        "rule_id": rule.rule_id,
        "status": status,
        "severity": rule.severity,
        "citation": rule.citation,
        "source_url": rule.source_url,
        "description": rule.description,
        "field": field,
        "operator": predicate["operator"],
        "expected": predicate.get("value"),
        "unit": predicate.get("unit"),
        "actual": actual,
    }


def evaluate_site(
    facts: Mapping[str, Any],
    *,
    asset_type: str,
    school_grade: str | None = None,
    rules: Iterable[SitingRule] | None = None,
    adapter: CountrySitingAdapter | None = None,
) -> dict[str, Any]:
    selected = applicable_rules(
        rules or load_siting_standards(),
        asset_type=asset_type,
        school_grade=school_grade,
        adapter=adapter or ItalySitingAdapter(),
    )
    results = [check_siting_compliance(rule, facts) for rule in selected]
    mandatory_failures = [
        result for result in results
        if result["severity"] == "mandatory" and result["status"] == "fail"
    ]
    mandatory_unknown = [
        result for result in results
        if result["severity"] == "mandatory" and result["status"] == "insufficient_data"
    ]
    overall = (
        "fail"
        if mandatory_failures
        else "insufficient_data"
        if mandatory_unknown
        else "pass"
    )
    return {
        "siting_standards_version": SITING_STANDARDS_VERSION,
        "asset_type": asset_type,
        "school_grade": school_grade,
        "overall_status": overall,
        "rule_count": len(results),
        "mandatory_failure_count": len(mandatory_failures),
        "mandatory_insufficient_data_count": len(mandatory_unknown),
        "results": results,
    }
