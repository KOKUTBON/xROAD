"""Countermeasure knowledge base & CMF evidence library.

The knowledge foundation the recommendation AI trains against: a structured,
versioned library of road-safety countermeasures with evidence-backed effect
sizes. Crash Modification Factors (CMFs) are the standard currency — each
countermeasure carries a multiplicative effect on crash frequency/severity
with a confidence interval and a citation to a public evidence base (FHWA CMF
Clearinghouse, Elvik's Handbook of Road Safety Measures, iRAP Safer Roads
Toolkit, EU RISM Directive 2019/1936 annexes).

It provides:

1. **A validating loader** for the versioned CSV seed under
   ``data/knowledge/countermeasures/`` — entries without an evidence source,
   with an unknown category, or with an inconsistent CMF interval are
   rejected.
2. **Machine-checkable preconditions** expressed over enrichment features
   (e.g. ``object_type=node|signal_control=unsignalized|arm_count>=3``) with
   an evaluator, so downstream recommendation logic can test applicability.
3. **Data-governance classifications** for the new record kind, mirroring the
   climate layer.
4. **A scenario intervention-library builder** so
   ``scenario_countermeasures.py`` derives its reduction bounds from the CMF
   evidence instead of hard-coded numbers.


"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from .data_governance import (
    CLASSIFICATION_INTERNAL,
    CLASSIFICATION_PUBLIC,
    FieldClassification,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256

COUNTERMEASURE_KNOWLEDGE_VERSION = "countermeasure_knowledge_v1"
COUNTERMEASURE_CONTRACT_VERSION = "countermeasure_knowledge_public_v1"

_REPO_ROOT = Path(__file__).resolve().parents[2]
# The curated seed ships inside the package so it resolves under a plain
# `pip install`, not only from a repository checkout.
DEFAULT_COUNTERMEASURES_PATH = Path(__file__).resolve().parent / "reference_data" / "countermeasures_v1.csv"
DEFAULT_EXPORT_DIR = _REPO_ROOT / "data" / "knowledge" / "countermeasures"

# The six countermeasure families named in AI-01.
COUNTERMEASURE_CATEGORIES: tuple[str, ...] = (
    "junction",
    "segment",
    "crossing",
    "speed",
    "lighting",
    "roadside",
)

# Object layers the platform already models (segment / node / movement /
# conflict-zone); each countermeasure declares which it can attach to.
APPLICABLE_OBJECT_TYPES: tuple[str, ...] = (
    "segment",
    "node",
    "movement",
    "conflict_zone",
)

COST_BANDS: tuple[str, ...] = ("low", "medium", "high")

_MULTI_VALUE_SEPARATOR = "|"

_REQUIRED_COLUMNS: tuple[str, ...] = (
    "countermeasure_id",
    "name",
    "category",
    "applicable_object_types",
    "cmf",
    "cmf_ci_low",
    "cmf_ci_high",
    "crash_types",
    "severities",
    "cost_band",
    "lead_time_months",
    "preconditions",
    "source",
    "source_ref",
)

# Comparison operators for precondition expressions, longest first so that
# ">=" is matched before ">".
_PRECONDITION_OPERATORS: tuple[str, ...] = (">=", "<=", "!=", ">", "<", "=")


@dataclass(frozen=True)
class Precondition:
    """One machine-checkable applicability condition over enrichment features."""

    feature_name: str
    operator: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "feature_name": self.feature_name,
            "operator": self.operator,
            "value": self.value,
        }


@dataclass(frozen=True)
class Countermeasure:
    """One evidence-backed road-safety countermeasure."""

    countermeasure_id: str
    name: str
    category: str
    applicable_object_types: tuple[str, ...]
    cmf: float
    cmf_ci_low: float
    cmf_ci_high: float
    crash_types: tuple[str, ...]
    severities: tuple[str, ...]
    cost_band: str
    lead_time_months: int
    preconditions: tuple[Precondition, ...]
    source: str
    source_ref: str
    intervention_code: str | None = None
    notes: str | None = None

    @property
    def expected_reduction(self) -> float:
        """Central expected crash-reduction fraction implied by the CMF."""
        return round(1.0 - self.cmf, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "countermeasure_id": self.countermeasure_id,
            "name": self.name,
            "category": self.category,
            "applicable_object_types": list(self.applicable_object_types),
            "cmf": self.cmf,
            "cmf_ci_low": self.cmf_ci_low,
            "cmf_ci_high": self.cmf_ci_high,
            "expected_reduction": self.expected_reduction,
            "crash_types": list(self.crash_types),
            "severities": list(self.severities),
            "cost_band": self.cost_band,
            "lead_time_months": self.lead_time_months,
            "preconditions": [p.to_dict() for p in self.preconditions],
            "source": self.source,
            "source_ref": self.source_ref,
            "intervention_code": self.intervention_code,
            "notes": self.notes,
        }


class CountermeasureValidationError(ValueError):
    """The seed file contains entries that violate the schema."""


def parse_precondition(expression: str) -> Precondition:
    """Parse one ``feature<op>value`` expression into a Precondition."""
    text = expression.strip()
    for operator in _PRECONDITION_OPERATORS:
        # "=" must not split ">=", "<=", "!=" (handled first by ordering).
        index = text.find(operator)
        if index > 0:
            feature_name = text[:index].strip()
            value = text[index + len(operator):].strip()
            if feature_name and value:
                return Precondition(feature_name=feature_name, operator=operator, value=value)
    raise CountermeasureValidationError(f"Unparseable precondition expression: {expression!r}")


def _coerce_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_precondition(precondition: Precondition, features: Mapping[str, Any]) -> bool:
    """Evaluate one precondition against a feature mapping.

    A missing feature fails the condition (conservative: the countermeasure is
    only recommended when applicability is demonstrable).
    """
    actual = features.get(precondition.feature_name)
    if actual is None:
        return False
    actual_number = _coerce_number(actual)
    expected_number = _coerce_number(precondition.value)
    if actual_number is not None and expected_number is not None:
        if precondition.operator == "=":
            return actual_number == expected_number
        if precondition.operator == "!=":
            return actual_number != expected_number
        if precondition.operator == ">=":
            return actual_number >= expected_number
        if precondition.operator == "<=":
            return actual_number <= expected_number
        if precondition.operator == ">":
            return actual_number > expected_number
        if precondition.operator == "<":
            return actual_number < expected_number
    actual_text = str(actual).strip().lower()
    expected_text = precondition.value.strip().lower()
    if precondition.operator == "=":
        return actual_text == expected_text
    if precondition.operator == "!=":
        return actual_text != expected_text
    # Ordered comparison of non-numeric values is undecidable — fail closed.
    return False


def countermeasure_is_applicable(
    countermeasure: Countermeasure,
    features: Mapping[str, Any],
) -> bool:
    """True when every precondition holds for the candidate asset features."""
    return all(
        evaluate_precondition(precondition, features)
        for precondition in countermeasure.preconditions
    )


def _split_multi(value: str) -> tuple[str, ...]:
    return tuple(
        token.strip()
        for token in str(value or "").split(_MULTI_VALUE_SEPARATOR)
        if token.strip()
    )


def _validate_row(row: Mapping[str, str], line_number: int) -> list[str]:
    errors: list[str] = []
    identifier = str(row.get("countermeasure_id") or f"line {line_number}")

    for column in _REQUIRED_COLUMNS:
        if not str(row.get(column) or "").strip() and column != "preconditions":
            errors.append(f"{identifier}: missing required field {column!r}")

    if not str(row.get("source") or "").strip():
        errors.append(f"{identifier}: entry has no evidence source and must be rejected")

    category = str(row.get("category") or "").strip()
    if category and category not in COUNTERMEASURE_CATEGORIES:
        errors.append(f"{identifier}: unknown category {category!r}")

    for object_type in _split_multi(row.get("applicable_object_types", "")):
        if object_type not in APPLICABLE_OBJECT_TYPES:
            errors.append(f"{identifier}: unknown applicable object type {object_type!r}")

    cost_band = str(row.get("cost_band") or "").strip()
    if cost_band and cost_band not in COST_BANDS:
        errors.append(f"{identifier}: unknown cost band {cost_band!r}")

    cmf = _coerce_number(row.get("cmf"))
    ci_low = _coerce_number(row.get("cmf_ci_low"))
    ci_high = _coerce_number(row.get("cmf_ci_high"))
    if cmf is None or not 0.0 < cmf <= 2.0:
        errors.append(f"{identifier}: cmf must be a number in (0, 2]")
    if ci_low is None or ci_high is None or cmf is None or not ci_low <= cmf <= ci_high:
        errors.append(f"{identifier}: cmf confidence interval must satisfy ci_low <= cmf <= ci_high")

    lead_time = _coerce_number(row.get("lead_time_months"))
    if lead_time is None or lead_time < 0:
        errors.append(f"{identifier}: lead_time_months must be a non-negative number")

    return errors


def load_countermeasure_library(
    path: str | Path = DEFAULT_COUNTERMEASURES_PATH,
) -> tuple[Countermeasure, ...]:
    """Load and validate the versioned countermeasure seed.

    Raises :class:`CountermeasureValidationError` listing every violation when
    any entry breaks the schema (including entries without an evidence
    source), and on duplicate identifiers.
    """
    seed_path = Path(path)
    with seed_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise CountermeasureValidationError(f"Empty countermeasure seed: {seed_path}")

    errors: list[str] = []
    seen_ids: set[str] = set()
    countermeasures: list[Countermeasure] = []
    for line_number, row in enumerate(rows, start=2):
        row_errors = _validate_row(row, line_number)
        identifier = str(row.get("countermeasure_id") or "").strip()
        if identifier in seen_ids:
            row_errors.append(f"{identifier}: duplicate countermeasure_id")
        seen_ids.add(identifier)

        preconditions: list[Precondition] = []
        for expression in _split_multi(row.get("preconditions", "")):
            try:
                preconditions.append(parse_precondition(expression))
            except CountermeasureValidationError as exc:
                row_errors.append(f"{identifier}: {exc}")

        if row_errors:
            errors.extend(row_errors)
            continue

        countermeasures.append(
            Countermeasure(
                countermeasure_id=identifier,
                name=str(row["name"]).strip(),
                category=str(row["category"]).strip(),
                applicable_object_types=_split_multi(row["applicable_object_types"]),
                cmf=float(row["cmf"]),
                cmf_ci_low=float(row["cmf_ci_low"]),
                cmf_ci_high=float(row["cmf_ci_high"]),
                crash_types=_split_multi(row["crash_types"]),
                severities=_split_multi(row["severities"]),
                cost_band=str(row["cost_band"]).strip(),
                lead_time_months=int(float(row["lead_time_months"])),
                preconditions=tuple(preconditions),
                source=str(row["source"]).strip(),
                source_ref=str(row["source_ref"]).strip(),
                intervention_code=str(row.get("intervention_code") or "").strip() or None,
                notes=str(row.get("notes") or "").strip() or None,
            )
        )

    if errors:
        raise CountermeasureValidationError(
            "Countermeasure seed validation failed:\n" + "\n".join(sorted(errors))
        )
    return tuple(countermeasures)


@lru_cache(maxsize=1)
def _cached_default_library() -> tuple[Countermeasure, ...]:
    return load_countermeasure_library(DEFAULT_COUNTERMEASURES_PATH)


def select_applicable_countermeasures(
    features: Mapping[str, Any],
    *,
    countermeasures: Sequence[Countermeasure] | None = None,
) -> list[Countermeasure]:
    """Countermeasures whose preconditions all hold, strongest effect first."""
    library = countermeasures if countermeasures is not None else _cached_default_library()
    applicable = [
        countermeasure
        for countermeasure in library
        if countermeasure_is_applicable(countermeasure, features)
    ]
    return sorted(applicable, key=lambda c: (c.cmf, c.countermeasure_id))


# Data-governance classifications for the new knowledge record kind, mirroring
# the climate layer. The evidence library itself is public knowledge; cost
# banding is kept internal as procurement-sensitive guidance.
COUNTERMEASURE_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="cmf",
        record_kind="countermeasure_knowledge",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Published crash-modification factor from a public evidence base; non-personal.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="source",
        record_kind="countermeasure_knowledge",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Citation to the public evidence base backing the effect size; required for auditability.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="cost_band",
        record_kind="countermeasure_knowledge",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Indicative cost banding informs procurement negotiation; internal until a brief is published.",
    ),
)


# Descriptive metadata for the six scenario intervention codes. Reduction
# bounds are NOT declared here — they are derived from the CMF evidence of the
# countermeasures tagged with each code.
_SCENARIO_INTERVENTION_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "intervention_code": "speed_management",
        "category": "speed",
        "label": "Speed management",
        "description": "Lower operating speeds on high-risk links with signed, geometric, and enforcement measures.",
        "supported_asset_types": ["segment"],
        "default_assumptions": [
            "Posted or operating speed can be reduced toward a 50 km/h corridor target.",
            "Gateway signing or enforcement keeps the speed change credible in operation.",
        ],
        "rule_summary": [
            "Cap maxspeed-derived exposure for treated segments.",
            "Increase expected benefit when the current corridor is wide, multilane, or posted above 50 km/h.",
        ],
        "feature_adjustments": [
            {"feature_name": "maxspeed", "adjustment_type": "cap_numeric", "target_value": 50},
            {
                "feature_name": "speed_management_package",
                "adjustment_type": "set_literal",
                "target_value": "gateway_signing_plus_enforcement",
            },
        ],
    },
    {
        "intervention_code": "crossing_protection",
        "category": "crossing_protection",
        "label": "Crossing protection",
        "description": "Upgrade pedestrian crossings with refuge, signal support, or high-visibility protection.",
        "supported_asset_types": ["crossing"],
        "default_assumptions": [
            "The municipality can upgrade the selected crossing to a protected configuration.",
            "Approach-speed management can be paired with the crossing treatment where needed.",
        ],
        "rule_summary": [
            "Increase benefit where crossings are uncontrolled or lack signal support.",
            "Carry some benefit onto the linked approach segments around the crossing.",
        ],
        "feature_adjustments": [
            {
                "feature_name": "crossing_control",
                "adjustment_type": "set_literal",
                "target_value": "protected_crossing",
            },
            {
                "feature_name": "crossing_signals",
                "adjustment_type": "set_literal",
                "target_value": "pedestrian_priority_supported",
            },
        ],
    },
    {
        "intervention_code": "signal_timing",
        "category": "signal_timing",
        "label": "Signal timing",
        "description": "Retune signal phasing and clearance to reduce conflict-heavy exposure at signalized junctions.",
        "supported_asset_types": ["signal"],
        "default_assumptions": [
            "Timing changes can be applied without rebuilding the junction geometry.",
            "Protected turns or a leading pedestrian interval are feasible at the selected signal.",
        ],
        "rule_summary": [
            "Improve the safety posture of linked segments around a signalized node.",
            "Increase benefit when the node links several high-scored segments.",
        ],
        "feature_adjustments": [
            {
                "feature_name": "signal_phase_strategy",
                "adjustment_type": "set_literal",
                "target_value": "protected_turns_plus_lpi",
            },
            {
                "feature_name": "clearance_policy",
                "adjustment_type": "set_literal",
                "target_value": "safety_balanced",
            },
        ],
    },
    {
        "intervention_code": "cycling_protection",
        "category": "cycling",
        "label": "Cycling protection",
        "description": "Reallocate space or parallel-route priority to reduce mixed-traffic conflict for cycle movements.",
        "supported_asset_types": ["segment"],
        "default_assumptions": [
            "A protected lane, separator, or parallel-route reallocation is feasible on the treated corridor.",
            "The treatment mainly changes conflict exposure on multilane or arterial segments.",
        ],
        "rule_summary": [
            "Increase benefit on multilane links and higher-order roads where reallocation is meaningful.",
            "Preserve the corridor-level risk ordering while improving vulnerable-road-user protection.",
        ],
        "feature_adjustments": [
            {
                "feature_name": "cycling_facility",
                "adjustment_type": "set_literal",
                "target_value": "protected_lane_or_parallel_route",
            },
            {
                "feature_name": "general_traffic_lane_reallocation",
                "adjustment_type": "set_literal",
                "target_value": "candidate",
            },
        ],
    },
    {
        "intervention_code": "lighting_upgrade",
        "category": "lighting",
        "label": "Lighting upgrade",
        "description": "Upgrade lighting and conspicuity in hotspot approaches where visibility is a plausible risk amplifier.",
        "supported_asset_types": ["segment"],
        "default_assumptions": [
            "Lighting upgrades are corridor- or area-wide and do not require a geometric rebuild.",
            "The treatment acts as a lower-confidence supporting measure rather than a stand-alone redesign.",
        ],
        "rule_summary": [
            "Provide modest benefit on long, high-scored approach segments.",
            "Use as a supporting treatment where hotspot coverage is broad but geometry changes need more design time.",
        ],
        "feature_adjustments": [
            {
                "feature_name": "lighting_standard",
                "adjustment_type": "set_literal",
                "target_value": "upgraded_led_uniformity",
            },
            {
                "feature_name": "night_visibility_support",
                "adjustment_type": "set_literal",
                "target_value": "enhanced",
            },
        ],
    },
    {
        "intervention_code": "traffic_calming",
        "category": "traffic_calming",
        "label": "Traffic calming",
        "description": "Apply raised tables, gateways, and junction-calming packages around conflict-heavy local approaches.",
        "supported_asset_types": ["junction"],
        "default_assumptions": [
            "The target area is locally redesignable and can tolerate a lower operating speed.",
            "The treatment package is suited to junction or neighbourhood-entry conditions rather than limited-access segments.",
        ],
        "rule_summary": [
            "Increase benefit where current operating speeds are already urban and geometry change is plausible.",
            "Carry the effect onto linked segments around the target junction rather than across the whole city.",
        ],
        "feature_adjustments": [
            {
                "feature_name": "traffic_calming_package",
                "adjustment_type": "set_literal",
                "target_value": "raised_table_gateway_chicane",
            },
            {
                "feature_name": "operating_speed_target",
                "adjustment_type": "set_literal",
                "target_value": "30_kmh",
            },
        ],
    },
)

# Scenario-level reductions are damped relative to raw site-level CMFs: a
# scenario applies an intervention family across heuristically linked assets,
# not a fully engineered single-site treatment. Bounds are also clamped so the
# heuristic counterfactual stays conservative.
_SCENARIO_EFFECT_DAMPING = 0.6
_SCENARIO_REDUCTION_FLOOR = 0.02
_SCENARIO_REDUCTION_CEILING = 0.45


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def derive_reduction_bounds(
    countermeasures: Sequence[Countermeasure],
) -> dict[str, float]:
    """Fold a group of CMF estimates into damped low/central/high reduction bounds."""
    if not countermeasures:
        raise CountermeasureValidationError(
            "Cannot derive reduction bounds from an empty countermeasure group."
        )
    central = _median([1.0 - c.cmf for c in countermeasures]) * _SCENARIO_EFFECT_DAMPING
    low = min(1.0 - c.cmf_ci_high for c in countermeasures) * _SCENARIO_EFFECT_DAMPING
    high = max(1.0 - c.cmf_ci_low for c in countermeasures) * _SCENARIO_EFFECT_DAMPING

    low = max(_SCENARIO_REDUCTION_FLOOR, low)
    high = min(_SCENARIO_REDUCTION_CEILING, high)
    central = max(low, min(high, central))
    return {
        "low": round(low, 4),
        "central": round(central, 4),
        "high": round(high, 4),
    }


def build_scenario_intervention_library(
    countermeasures: Sequence[Countermeasure] | None = None,
) -> tuple[dict[str, Any], ...]:
    """The scenario intervention library, with evidence-derived reduction bounds.

    Each of the six intervention codes aggregates the CMFs of the seeded
    countermeasures tagged with that code, and records the supporting
    countermeasure ids and citations so scenario outputs stay auditable.
    """
    library = countermeasures if countermeasures is not None else _cached_default_library()
    by_code: dict[str, list[Countermeasure]] = {}
    for countermeasure in library:
        if countermeasure.intervention_code:
            by_code.setdefault(countermeasure.intervention_code, []).append(countermeasure)

    records: list[dict[str, Any]] = []
    for template in _SCENARIO_INTERVENTION_TEMPLATES:
        code = str(template["intervention_code"])
        supporting = by_code.get(code)
        if not supporting:
            raise CountermeasureValidationError(
                f"No seeded countermeasures back intervention code {code!r}."
            )
        record = dict(template)
        record["baseline_reduction_bounds"] = derive_reduction_bounds(supporting)
        record["evidence"] = {
            "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
            "supporting_countermeasure_ids": [c.countermeasure_id for c in supporting],
            "sources": sorted({c.source for c in supporting}),
        }
        records.append(record)
    return tuple(records)


def export_countermeasure_library(
    *,
    seed_path: str | Path = DEFAULT_COUNTERMEASURES_PATH,
    output_dir: str | Path = DEFAULT_EXPORT_DIR,
) -> dict[str, Any]:
    """Write the validated library as JSON with governance and a lineage manifest."""
    seed_input = Path(seed_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    countermeasures = load_countermeasure_library(seed_input)

    category_counts: dict[str, int] = {}
    for countermeasure in countermeasures:
        category_counts[countermeasure.category] = (
            category_counts.get(countermeasure.category, 0) + 1
        )

    library_payload = {
        "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "seed_path": str(seed_input),
        "countermeasures": [c.to_dict() for c in countermeasures],
        "governance": [c.to_dict() for c in COUNTERMEASURE_FIELD_CLASSIFICATIONS],
        "stats": {
            "countermeasure_count": len(countermeasures),
            "category_counts": category_counts,
            "source_count": len({c.source for c in countermeasures}),
        },
    }
    library_path = output_root / "countermeasure_library.json"
    library_path.write_text(
        json.dumps(library_payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    manifest_path = output_root / "countermeasure_library.manifest.json"
    manifest = {
        "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
        "inputs": {
            "seed_path": str(seed_input),
            "seed_sha256": _sha256(seed_input),
        },
        "outputs": {
            "library_path": str(library_path),
            "library_sha256": _sha256(library_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "countermeasure_knowledge_library",
            "public_contract_version": COUNTERMEASURE_CONTRACT_VERSION,
            "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
        },
        "stats": library_payload["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(
                    "countermeasure_seed_csv",
                    seed_input,
                    _sha256(seed_input),
                ),
            ],
            publishable_outputs=[
                _artifact_reference(
                    "countermeasure_library_json",
                    library_path,
                    _sha256(library_path),
                ),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
        "library_path": str(library_path),
        "manifest_path": str(manifest_path),
        "stats": library_payload["stats"],
    }
