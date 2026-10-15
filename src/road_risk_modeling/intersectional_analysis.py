"""Gender-sensitive and intersectional crash analysis (privacy-careful).

Horizon Europe requires *"gender-sensitive and intersectional approaches"* — the
gender dimension is an award criterion by default. This module adds
sex/gender-disaggregated and **intersectional** (gender × age × rural location ×
disability) crash analysis, with strict small-cell suppression so that
small-cell disaggregation does not reveal individual records.

The deliberate tension here is real: the call demands disaggregation, the
[anonymisation policy](../ethics/anonymisation-policy.md) demands protection of
sparse cells. The resolution is **aggregate stratified counts with a k-anonymity
floor** — any stratum below the floor is suppressed, never published or modelled
at the individual level.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _artifact_reference, _build_lineage_contract, _sha256

INTERSECTIONAL_VERSION = "intersectional_analysis_v1"
INTERSECTIONAL_CONTRACT_VERSION = "intersectional_analysis_public_v1"

# k-anonymity floor: strata with fewer casualties than this are suppressed.
DEFAULT_MIN_CELL = 10

# The intersectional dimensions, in the order the call frames them.
INTERSECTIONAL_DIMENSIONS = ("sex", "age_band", "area_type", "disability")

_SUPPRESSED = "suppressed"


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dimension_value(row: Mapping[str, Any], dimension: str) -> str:
    value = row.get(dimension)
    text = str(value).strip() if value is not None else ""
    return text or "unknown"


def _is_fatal(row: Mapping[str, Any]) -> bool:
    severity = str(row.get("severity_level") or "").strip().lower()
    if severity:
        return severity == "fatal"
    return (_to_float(row.get("fatalities")) or 0.0) > 0.0


def stratify(
    rows: Sequence[Mapping[str, Any]],
    dimensions: Sequence[str],
    *,
    min_cell: int = DEFAULT_MIN_CELL,
) -> dict[str, Any]:
    """Aggregate casualties and fatal-share over a tuple of dimensions, then
    suppress any stratum below the anonymity floor.

    Returns surviving strata (each a dimension-value map + count + fatal share)
    plus the suppression accounting. Never emits individual records.
    """
    buckets: dict[tuple[str, ...], dict[str, float]] = {}
    for row in rows:
        key = tuple(_dimension_value(row, dim) for dim in dimensions)
        bucket = buckets.setdefault(key, {"count": 0.0, "fatal": 0.0})
        bucket["count"] += 1.0
        if _is_fatal(row):
            bucket["fatal"] += 1.0

    surviving: list[dict[str, Any]] = []
    suppressed = 0
    suppressed_total = 0
    for key, bucket in buckets.items():
        count = int(bucket["count"])
        if count < min_cell:
            suppressed += 1
            suppressed_total += count
            continue
        surviving.append(
            {
                **{dim: value for dim, value in zip(dimensions, key)},
                "casualty_count": count,
                "fatal_count": int(bucket["fatal"]),
                "fatal_share": round(bucket["fatal"] / count, 4) if count else 0.0,
            }
        )
    surviving.sort(key=lambda stratum: stratum["casualty_count"], reverse=True)
    return {
        "dimensions": list(dimensions),
        "strata": surviving,
        "strata_total": len(buckets),
        "strata_suppressed": suppressed,
        "suppressed_casualties": suppressed_total,
        "min_cell": min_cell,
    }


def run_intersectional_analysis(
    *,
    casualties_path: str | Path,
    output_dir: str | Path,
    min_cell: int = DEFAULT_MIN_CELL,
) -> dict[str, Any]:
    """Read a casualty table and write sex-disaggregated and intersectional
    stratified aggregates (suppressed), plus a manifest."""
    casualties_file = Path(casualties_path)
    with casualties_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Casualty table is empty.")

    # Three views: sex only, sex x age, and the full intersectional stack.
    sex_view = stratify(rows, ["sex"], min_cell=min_cell)
    sex_age_view = stratify(rows, ["sex", "age_band"], min_cell=min_cell)
    intersectional_view = stratify(rows, list(INTERSECTIONAL_DIMENSIONS), min_cell=min_cell)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "intersectional_strata.csv"
    json_path = output_root / "intersectional_analysis.json"
    manifest_path = output_root / "intersectional_analysis.manifest.json"

    fieldnames = [*INTERSECTIONAL_DIMENSIONS, "casualty_count", "fatal_count", "fatal_share"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(intersectional_view["strata"])

    payload = {
        "intersectional_version": INTERSECTIONAL_VERSION,
        "privacy": {
            "aggregate_only": True,
            "k_anonymity_min_cell": min_cell,
            "basis": "anonymisation-policy small-cell suppression; no individual records emitted.",
        },
        "casualty_count": len(rows),
        "sex_disaggregated": sex_view,
        "sex_by_age": sex_age_view,
        "intersectional": intersectional_view,
        "lineage": _build_lineage_contract(
            run_record_path=json_path,
            upstream_inputs=[_artifact_reference("intersectional_casualties", casualties_file, _sha256(casualties_file))],
            publishable_outputs=[_artifact_reference("intersectional_strata_csv", csv_path, None)],
        ),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "intersectional_version": INTERSECTIONAL_VERSION,
        "contract": {
            "resource_name": "intersectional_analysis",
            "public_contract_version": INTERSECTIONAL_CONTRACT_VERSION,
        },
        "outputs": {
            "strata_csv_path": str(csv_path),
            "strata_csv_sha256": _sha256(csv_path),
            "summary_json_path": str(json_path),
            "summary_json_sha256": _sha256(json_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "strata_csv_path": str(csv_path),
        "summary_json_path": str(json_path),
        "manifest_path": str(manifest_path),
        "sex_strata": len(sex_view["strata"]),
        "intersectional_strata": len(intersectional_view["strata"]),
        "intersectional_suppressed": intersectional_view["strata_suppressed"],
    }
