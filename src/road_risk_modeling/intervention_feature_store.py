"""Intervention-labeled feature store for infrastructure recommendations.

Assembles the supervised training dataset the recommendation model learns
from: object-level features joined with intervention labels and observed
outcomes ("site condition → intervention → outcome").

It stacks the per-city ``segment_year_metrics`` context-v2 aggregates (static
enrichment, land-use/built-environment context, exposure-policy features, and
historical crash aggregates per object-year) and derives:

1. **Observed intervention labels** mined from year-over-year attribute
   changes in the OSM-derived enrichment (posted-speed reductions, lane
   reallocation, roundabout conversion) with before/after periods per object.
2. **Synthetic counterfactual labels** from the CMF knowledge base
   where observed interventions are sparse — deterministically sampled,
   precondition-checked, and explicitly flagged ``label_source=synthetic_cmf``.
3. **Outcome targets**: exposure-adjusted crash-frequency and severity change
   in the after-period.
4. **Split discipline** reusing the transferability conventions
   (``leave_one_jurisdiction_out_temporal_holdout``): a temporal
   train/validation/test split by intervention year plus a per-city fold for
   cold-start evaluation.
5. **Leakage checks** and a generated dataset card (provenance, class
   balance, synthetic share, known biases).

Output is a versioned matrix (Parquet when a pandas Parquet engine is
available, CSV fallback otherwise) under the existing artifact/lineage
conventions. See ``docs/intervention-feature-store.md``.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .countermeasure_knowledge import (
    COUNTERMEASURE_KNOWLEDGE_VERSION,
    Countermeasure,
    load_countermeasure_library,
    select_applicable_countermeasures,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256

INTERVENTION_FEATURE_STORE_VERSION = "intervention_feature_store_v1"
INTERVENTION_FEATURE_STORE_CONTRACT_VERSION = "intervention_feature_store_public_v1"
SPLIT_STRATEGY = "leave_one_jurisdiction_out_temporal_holdout"

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "processed" / "intervention_feature_store"

# The pilot-city context-v2 segment-year aggregates the matrix stacks.
DEFAULT_CITY_DATASETS: dict[str, Path] = {
    "bari": _REPO_ROOT / "data/processed/aggregates/bari_context_v2/segment_year_metrics.csv",
    "brindisi": _REPO_ROOT
    / "data/processed/aggregates/brindisi_municipality_context_v2/segment_year_metrics.csv",
    "foggia": _REPO_ROOT
    / "data/processed/aggregates/foggia_municipality_context_v2/segment_year_metrics.csv",
    "lecce": _REPO_ROOT
    / "data/processed/aggregates/lecce_municipality_context_v2/segment_year_metrics.csv",
    "taranto": _REPO_ROOT
    / "data/processed/aggregates/taranto_municipality_context_v2/segment_year_metrics.csv",
}

LABEL_SOURCE_OBSERVED = "observed_attribute_change"
LABEL_SOURCE_SYNTHETIC = "synthetic_cmf"

# Outcome columns are strictly after-period measurements and must never leak
# into the feature block; the leakage checks enforce this by name.
OUTCOME_COLUMNS: tuple[str, ...] = (
    "outcome_after_crash_density_per_km",
    "outcome_crash_density_change_per_km",
    "outcome_crash_density_ratio",
    "outcome_after_severity_density_per_km",
    "outcome_severity_density_change_per_km",
)

LABEL_COLUMNS: tuple[str, ...] = (
    "intervention_code",
    "label_source",
    "is_synthetic",
    "countermeasure_id",
    "intervention_year",
)

SPLIT_COLUMNS: tuple[str, ...] = ("temporal_split", "city_fold", "split_strategy")

_IDENTITY_COLUMNS: tuple[str, ...] = ("object_id", "object_type", "city_key")

# Share of untreated objects (deterministic by id hash) that receive a
# synthetic counterfactual label; keeps class balance workable while flagging
# every synthetic row.
_SYNTHETIC_SAMPLING_MODULUS = 5


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _segment_years(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group per-year rows by segment, ordered by year."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        segment_id = str(row.get("segment_id") or "").strip()
        year = _to_int(row.get("occurred_year"))
        if not segment_id or year is None:
            continue
        grouped.setdefault(segment_id, []).append({**row, "occurred_year": year})
    for series in grouped.values():
        series.sort(key=lambda item: item["occurred_year"])
    return grouped


def detect_observed_interventions(
    series: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Mine intervention events from year-over-year attribute changes.

    The enrichment attributes are OSM-derived per aggregate vintage, so a
    change between consecutive observed years is the committed edit-history
    signal for an infrastructure change on that object. Detected families:

    - posted-speed reduction of ≥10 km/h → ``speed_management``
    - lane count reduced by ≥1 (space reallocation / road diet) →
      ``lane_reallocation``
    - roundabout conversion (``is_roundabout`` 0 → 1) →
      ``roundabout_conversion``
    """
    events: list[dict[str, Any]] = []
    for previous, current in zip(series, series[1:]):
        year = int(current["occurred_year"])
        prev_speed = _to_float(previous.get("maxspeed_numeric"))
        curr_speed = _to_float(current.get("maxspeed_numeric"))
        if prev_speed is not None and curr_speed is not None and prev_speed - curr_speed >= 10:
            events.append({"intervention_code": "speed_management", "intervention_year": year})
        prev_lanes = _to_float(previous.get("lanes_numeric"))
        curr_lanes = _to_float(current.get("lanes_numeric"))
        if prev_lanes is not None and curr_lanes is not None and prev_lanes - curr_lanes >= 1:
            events.append({"intervention_code": "lane_reallocation", "intervention_year": year})
        prev_roundabout = _to_float(previous.get("is_roundabout")) or 0.0
        curr_roundabout = _to_float(current.get("is_roundabout")) or 0.0
        if prev_roundabout == 0.0 and curr_roundabout == 1.0:
            events.append({"intervention_code": "roundabout_conversion", "intervention_year": year})
    return events


def _period_outcomes(
    series: Sequence[Mapping[str, Any]],
    intervention_year: int,
) -> dict[str, float] | None:
    """Exposure-adjusted before/after outcome aggregates around an event.

    Uses the per-km crash and severity densities (already normalised by
    segment length); requires at least one observed year on each side.
    """
    before = [row for row in series if row["occurred_year"] < intervention_year]
    after = [row for row in series if row["occurred_year"] >= intervention_year]
    if not before or not after:
        return None

    def _mean(rows: Sequence[Mapping[str, Any]], column: str) -> float:
        values = [_to_float(row.get(column)) or 0.0 for row in rows]
        return sum(values) / len(values)

    def _severity_density(rows: Sequence[Mapping[str, Any]]) -> float:
        return _mean(rows, "fatalities_per_km") + _mean(rows, "injuries_per_km")

    before_density = _mean(before, "crash_density_per_km")
    after_density = _mean(after, "crash_density_per_km")
    before_severity = _severity_density(before)
    after_severity = _severity_density(after)
    return {
        "before_crash_density_per_km": round(before_density, 6),
        "outcome_after_crash_density_per_km": round(after_density, 6),
        "outcome_crash_density_change_per_km": round(after_density - before_density, 6),
        "outcome_crash_density_ratio": round(after_density / before_density, 6)
        if before_density > 0
        else None,
        "before_severity_density_per_km": round(before_severity, 6),
        "outcome_after_severity_density_per_km": round(after_severity, 6),
        "outcome_severity_density_change_per_km": round(after_severity - before_severity, 6),
    }


def _feature_block(row: Mapping[str, Any]) -> dict[str, Any]:
    """Pre-intervention features for one object-year (all aggregate columns)."""
    return {
        f"feature_{key}": value
        for key, value in row.items()
        if key not in {"segment_id"}
    }


def _synthetic_candidate_features(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map an aggregate row onto the CMF-library precondition vocabulary."""
    features: dict[str, Any] = {
        "object_type": "segment",
        "area_type": "urban",
    }
    maxspeed = _to_float(row.get("maxspeed_numeric"))
    if maxspeed is not None:
        features["maxspeed"] = maxspeed
    lanes = _to_float(row.get("lanes_numeric"))
    if lanes is not None:
        features["lane_count"] = lanes
    length = _to_float(row.get("segment_length_m"))
    if length is not None:
        features["segment_length_m"] = length
    highway = str(row.get("highway") or "").strip().lower()
    if highway:
        features["road_class"] = highway
    return features


def _stable_bucket(object_id: str) -> int:
    digest = hashlib.sha256(object_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % _SYNTHETIC_SAMPLING_MODULUS


def _synthetic_label(
    *,
    object_id: str,
    latest_row: Mapping[str, Any],
    library: Sequence[Countermeasure],
) -> Countermeasure | None:
    """Deterministically pick one applicable countermeasure for an object."""
    if _stable_bucket(object_id) != 0:
        return None
    applicable = select_applicable_countermeasures(
        _synthetic_candidate_features(latest_row),
        countermeasures=library,
    )
    segment_applicable = [
        countermeasure
        for countermeasure in applicable
        if "segment" in countermeasure.applicable_object_types
        and countermeasure.intervention_code
    ]
    if not segment_applicable:
        return None
    index = int(hashlib.sha256(f"pick:{object_id}".encode("utf-8")).hexdigest()[:8], 16)
    return segment_applicable[index % len(segment_applicable)]


def assign_temporal_split(intervention_year: int, *, max_year: int) -> str:
    """Year-based split: last year test, second-last validation, earlier train."""
    if intervention_year >= max_year:
        return "test"
    if intervention_year == max_year - 1:
        return "validation"
    return "train"


def build_city_records(
    *,
    city_key: str,
    rows: Sequence[Mapping[str, Any]],
    library: Sequence[Countermeasure],
) -> list[dict[str, Any]]:
    """Intervention-labeled records for one city's segment-year aggregates."""
    grouped = _segment_years(rows)
    all_years = [row["occurred_year"] for series in grouped.values() for row in series]
    if not all_years:
        return []
    max_year = max(all_years)

    records: list[dict[str, Any]] = []
    for segment_id, series in sorted(grouped.items()):
        observed_events = detect_observed_interventions(series)
        for event in observed_events:
            intervention_year = int(event["intervention_year"])
            outcomes = _period_outcomes(series, intervention_year)
            if outcomes is None:
                continue
            baseline_row = next(
                row for row in reversed(series) if row["occurred_year"] < intervention_year
            )
            records.append(
                {
                    "object_id": segment_id,
                    "object_type": "segment",
                    "city_key": city_key,
                    "intervention_code": event["intervention_code"],
                    "label_source": LABEL_SOURCE_OBSERVED,
                    "is_synthetic": False,
                    "countermeasure_id": None,
                    "intervention_year": intervention_year,
                    "temporal_split": assign_temporal_split(
                        intervention_year, max_year=max_year
                    ),
                    "city_fold": city_key,
                    "split_strategy": SPLIT_STRATEGY,
                    **outcomes,
                    **_feature_block(baseline_row),
                }
            )

        if observed_events or len(series) < 2:
            continue
        # Synthetic counterfactual for a deterministic slice of untreated
        # objects: apply the CMF centrally to the observed before-period.
        countermeasure = _synthetic_label(
            object_id=f"{city_key}:{segment_id}",
            latest_row=series[-1],
            library=library,
        )
        if countermeasure is None:
            continue
        # Spread synthetic intervention years deterministically across the
        # observed panel (any year with at least one before-year), so the
        # temporal splits carry validation/test synthetic rows too.
        year_pick = int(
            hashlib.sha256(f"year:{city_key}:{segment_id}".encode("utf-8")).hexdigest()[:8], 16
        )
        intervention_year = series[1 + year_pick % (len(series) - 1)]["occurred_year"]
        before = [row for row in series if row["occurred_year"] < intervention_year]
        if not before:
            continue
        before_density = sum(
            _to_float(row.get("crash_density_per_km")) or 0.0 for row in before
        ) / len(before)
        before_severity = sum(
            (_to_float(row.get("fatalities_per_km")) or 0.0)
            + (_to_float(row.get("injuries_per_km")) or 0.0)
            for row in before
        ) / len(before)
        after_density = before_density * countermeasure.cmf
        after_severity = before_severity * countermeasure.cmf
        records.append(
            {
                "object_id": segment_id,
                "object_type": "segment",
                "city_key": city_key,
                "intervention_code": countermeasure.intervention_code,
                "label_source": LABEL_SOURCE_SYNTHETIC,
                "is_synthetic": True,
                "countermeasure_id": countermeasure.countermeasure_id,
                "intervention_year": intervention_year,
                "temporal_split": assign_temporal_split(intervention_year, max_year=max_year),
                "city_fold": city_key,
                "split_strategy": SPLIT_STRATEGY,
                "before_crash_density_per_km": round(before_density, 6),
                "outcome_after_crash_density_per_km": round(after_density, 6),
                "outcome_crash_density_change_per_km": round(after_density - before_density, 6),
                "outcome_crash_density_ratio": round(countermeasure.cmf, 6)
                if before_density > 0
                else None,
                "before_severity_density_per_km": round(before_severity, 6),
                "outcome_after_severity_density_per_km": round(after_severity, 6),
                "outcome_severity_density_change_per_km": round(
                    after_severity - before_severity, 6
                ),
                **_feature_block(before[-1]),
            }
        )
    return records


def run_leakage_checks(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Structural leakage checks over the assembled matrix.

    Raises ``RuntimeError`` on any violation:

    1. No outcome column may appear inside the feature block.
    2. Every record's feature block must be measured strictly before the
       intervention year (the baseline object-year).
    3. Temporal splits must be consistent: no train record may carry an
       intervention year later than any test record within the same city.
    """
    violations: list[str] = []
    for record in records:
        feature_keys = {key for key in record if key.startswith("feature_")}
        for outcome_column in OUTCOME_COLUMNS:
            if f"feature_{outcome_column}" in feature_keys or outcome_column in feature_keys:
                violations.append(
                    f"{record.get('object_id')}: outcome column {outcome_column!r} leaked into features"
                )
        feature_year = _to_int(record.get("feature_occurred_year"))
        intervention_year = _to_int(record.get("intervention_year"))
        if feature_year is None or intervention_year is None or feature_year >= intervention_year:
            violations.append(
                f"{record.get('object_id')}: baseline feature year {feature_year} is not "
                f"strictly before intervention year {intervention_year}"
            )

    by_city: dict[str, dict[str, list[int]]] = {}
    for record in records:
        city_bucket = by_city.setdefault(str(record.get("city_key")), {})
        city_bucket.setdefault(str(record.get("temporal_split")), []).append(
            int(record["intervention_year"])
        )
    for city_key, splits in by_city.items():
        train_years = splits.get("train", [])
        test_years = splits.get("test", [])
        if train_years and test_years and max(train_years) >= min(test_years):
            violations.append(
                f"{city_key}: train intervention years overlap the test period "
                f"(max train {max(train_years)} >= min test {min(test_years)})"
            )

    if violations:
        raise RuntimeError(
            "Intervention feature-store leakage checks failed:\n" + "\n".join(sorted(violations))
        )
    return {
        "checked_records": len(records),
        "checks": [
            "outcome_columns_not_in_feature_block",
            "baseline_features_precede_intervention_year",
            "train_years_precede_test_years_per_city",
        ],
        "violations": 0,
    }


def _dataset_card(
    *,
    records: Sequence[Mapping[str, Any]],
    city_inputs: Mapping[str, Path],
    leakage_report: Mapping[str, Any],
) -> dict[str, Any]:
    label_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    split_counts: dict[str, int] = {}
    city_counts: dict[str, int] = {}
    for record in records:
        label_counts[str(record["intervention_code"])] = (
            label_counts.get(str(record["intervention_code"]), 0) + 1
        )
        source_counts[str(record["label_source"])] = (
            source_counts.get(str(record["label_source"]), 0) + 1
        )
        split_counts[str(record["temporal_split"])] = (
            split_counts.get(str(record["temporal_split"]), 0) + 1
        )
        city_counts[str(record["city_key"])] = city_counts.get(str(record["city_key"]), 0) + 1
    synthetic_count = source_counts.get(LABEL_SOURCE_SYNTHETIC, 0)
    return {
        "intervention_feature_store_version": INTERVENTION_FEATURE_STORE_VERSION,
        "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "provenance": {
            "city_inputs": {city: str(path) for city, path in city_inputs.items()},
            "observed_label_definition": (
                "Year-over-year OSM-derived attribute changes: posted-speed reduction >=10 km/h, "
                "lane count reduced >=1, roundabout conversion."
            ),
            "synthetic_label_definition": (
                "Deterministic 1-in-"
                f"{_SYNTHETIC_SAMPLING_MODULUS} sample of untreated objects, labeled with a "
                "precondition-checked countermeasure from the CMF library; outcomes are "
                "the CMF applied to the observed before-period and are flagged is_synthetic."
            ),
            "split_strategy": SPLIT_STRATEGY,
        },
        "stats": {
            "record_count": len(records),
            "label_counts": dict(sorted(label_counts.items())),
            "label_source_counts": dict(sorted(source_counts.items())),
            "temporal_split_counts": dict(sorted(split_counts.items())),
            "city_counts": dict(sorted(city_counts.items())),
            "synthetic_share": round(synthetic_count / len(records), 4) if records else 0.0,
        },
        "leakage_checks": dict(leakage_report),
        "known_biases": [
            "Crash reporting bias: minor and vulnerable-road-user crashes are under-reported, so outcome densities understate true frequency.",
            "Regression to the mean: observed interventions cluster on recent high-crash sites; naive before/after deltas overstate treatment effect.",
            "OSM edit-history bias: attribute changes reflect mapping activity as well as physical works; some detected events are map corrections.",
            "Synthetic labels inherit the CMF library's transferability assumptions and must never be evaluated as observed outcomes.",
        ],
    }


def _write_matrix(records: Sequence[Mapping[str, Any]], output_dir: Path) -> tuple[Path, str]:
    """Write the matrix as Parquet when a pandas engine exists, else CSV."""
    columns: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    try:
        import pandas as pd

        frame = pd.DataFrame(list(records), columns=columns)
        parquet_path = output_dir / "intervention_feature_store.parquet"
        frame.to_parquet(parquet_path, index=False)
        return parquet_path, "parquet"
    except Exception:
        csv_path = output_dir / "intervention_feature_store.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for record in records:
                writer.writerow(record)
        return csv_path, "csv"


def build_intervention_feature_store(
    *,
    city_datasets: Mapping[str, str | Path] | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    countermeasure_seed_path: str | Path | None = None,
) -> dict[str, Any]:
    """One command: build the full labeled matrix for all pilot cities."""
    inputs = {
        city: Path(path)
        for city, path in (city_datasets or DEFAULT_CITY_DATASETS).items()
        if Path(path).exists()
    }
    if not inputs:
        raise RuntimeError("No pilot-city segment-year aggregates found to build the feature store.")

    library = (
        load_countermeasure_library(countermeasure_seed_path)
        if countermeasure_seed_path is not None
        else load_countermeasure_library()
    )

    records: list[dict[str, Any]] = []
    for city_key, path in sorted(inputs.items()):
        records.extend(
            build_city_records(
                city_key=city_key,
                rows=_load_csv_rows(path),
                library=library,
            )
        )
    if not records:
        raise RuntimeError("Feature-store build produced no labeled records.")

    leakage_report = run_leakage_checks(records)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    matrix_path, matrix_format = _write_matrix(records, output_root)

    card = _dataset_card(records=records, city_inputs=inputs, leakage_report=leakage_report)
    card_path = output_root / "dataset_card.json"
    card_path.write_text(json.dumps(card, indent=2, sort_keys=True), encoding="utf-8")

    manifest_path = output_root / "intervention_feature_store.manifest.json"
    manifest = {
        "intervention_feature_store_version": INTERVENTION_FEATURE_STORE_VERSION,
        "inputs": {
            city: {"path": str(path), "sha256": _sha256(path)} for city, path in sorted(inputs.items())
        },
        "outputs": {
            "matrix_path": str(matrix_path),
            "matrix_format": matrix_format,
            "matrix_sha256": _sha256(matrix_path),
            "dataset_card_path": str(card_path),
            "dataset_card_sha256": _sha256(card_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "intervention_feature_store",
            "public_contract_version": INTERVENTION_FEATURE_STORE_CONTRACT_VERSION,
            "intervention_feature_store_version": INTERVENTION_FEATURE_STORE_VERSION,
            "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
            "split_strategy": SPLIT_STRATEGY,
        },
        "stats": card["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference(f"segment_year_metrics_{city}", path, _sha256(path))
                for city, path in sorted(inputs.items())
            ],
            publishable_outputs=[
                _artifact_reference("intervention_feature_matrix", matrix_path, _sha256(matrix_path)),
                _artifact_reference("dataset_card_json", card_path, _sha256(card_path)),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "intervention_feature_store_version": INTERVENTION_FEATURE_STORE_VERSION,
        "matrix_path": str(matrix_path),
        "matrix_format": matrix_format,
        "dataset_card_path": str(card_path),
        "manifest_path": str(manifest_path),
        "stats": card["stats"],
    }
