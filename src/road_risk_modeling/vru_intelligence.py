"""Build dedicated VRU and micromobility planning artifacts from published risk surfaces."""

from __future__ import annotations

import ast
import csv
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any

from .dashboard_summary import _resolve_reference_path
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


VRU_INTELLIGENCE_VERSION = "vru_intelligence_bundle_v1"
VRU_INTELLIGENCE_CONTRACT_VERSION = "vru_intelligence_bundle_public_v1"
DEFAULT_VRU_OUTPUT_DIR = Path("data/planning/vru_intelligence")
DEFAULT_VRU_INDEX_PATH = DEFAULT_VRU_OUTPUT_DIR / "vru_intelligence_index.json"
DEFAULT_BARI_MOVEMENT_OBJECTS_PATH = Path("data/processed/movement_objects/bari/road_movement_objects.geojson")

_USER_GROUPS: tuple[str, ...] = (
    "pedestrian",
    "cyclist",
    "ageing_user",
    "micromobility",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_feature_collection(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"Expected FeatureCollection at: {path}")
    return list(payload.get("features", []))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _find_by_key(records: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for record in records:
        if str(record.get(key)) == value:
            return record
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _flatten_literal(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text[0:1] in {"[", "(", "{", '"', "'"}:
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return [text.strip("[]'\"")]
            return _flatten_literal(parsed)
        return [text]
    if isinstance(value, (list, tuple, set)):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_literal(item))
        return flattened
    if value is None:
        return []
    return [str(value)]


def _normalize_literal_text(value: Any) -> str | None:
    tokens = [token for token in _flatten_literal(value) if token and token.lower() != "nan"]
    if not tokens:
        return None
    return " / ".join(list(dict.fromkeys(tokens)))


def _literal_numeric_values(value: Any) -> list[float]:
    values: list[float] = []
    for token in _flatten_literal(value):
        try:
            values.append(float(str(token).strip()))
        except (TypeError, ValueError):
            continue
    return values


def _max_literal_numeric(value: Any, default: float) -> float:
    numeric_values = _literal_numeric_values(value)
    if not numeric_values:
        return default
    return max(numeric_values)


def _index_from_weighted_sum(weighted_sum: float, *, scale: float = 2.5, cap: float = 4.0) -> float:
    value = 1.0 + (math.log1p(max(weighted_sum, 0.0)) / scale)
    return round(min(cap, value), 6)


def _stress_from_speed(speed_kph: float) -> float:
    return round(max(0.0, min(1.0, (float(speed_kph) - 20.0) / 70.0)), 6)


def _stress_from_lanes(lanes: float) -> float:
    return round(max(0.0, min(1.0, (float(lanes) - 1.0) / 3.0)), 6)


def _road_class_label(row: dict[str, Any]) -> str | None:
    highway = _normalize_literal_text(row.get("highway"))
    if highway:
        return highway.split(" / ")[0]
    return None


def _corridor_label_from_row(row: dict[str, Any]) -> str | None:
    for key in ("name", "ref"):
        text = _normalize_literal_text(row.get(key))
        if text:
            return text
    return None


def _segment_label_from_row(row: dict[str, Any]) -> str:
    return (
        _normalize_literal_text(row.get("name"))
        or _normalize_literal_text(row.get("ref"))
        or _road_class_label(row)
        or str(row.get("segment_score_id") or row.get("segment_id") or "Unnamed segment")
    )


def _priority_reason_tags(record: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if float(record.get("school_frontage_index") or 0.0) >= 1.4:
        tags.append("school_frontage")
    if float(record.get("retail_frontage_index") or 0.0) >= 1.4:
        tags.append("retail_frontage")
    if float(record.get("transit_access_index") or 0.0) >= 1.35:
        tags.append("transit_access")
    if float(record.get("micromobility_corridor_index") or 0.0) >= 1.35:
        tags.append("micromobility_demand")
    if float(record.get("segment_crossing_gap_index") or 0.0) >= 0.5:
        tags.append("protected_crossing_gap")
    if float(record.get("speed_stress_index") or 0.0) >= 0.6:
        tags.append("speed_stress")
    return tags


def _segment_base_records(analyst_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in analyst_rows:
        segment_score_id = _clean_text(row.get("segment_score_id"))
        if not segment_score_id:
            continue
        speed_kph = _max_literal_numeric(row.get("maxspeed"), 30.0)
        lanes = _max_literal_numeric(row.get("lanes"), 1.0)
        road_class_rank = max(0.0, min(8.0, _safe_float(row.get("road_class_rank"))))
        school_frontage_index = _index_from_weighted_sum(
            (1.8 * _safe_float(row.get("poi_education_count")))
            + (1.2 * _safe_float(row.get("landuse_residential_count")))
            + (0.8 * _safe_float(row.get("building_residential_count")))
        )
        retail_frontage_index = _index_from_weighted_sum(
            (1.6 * _safe_float(row.get("poi_retail_count")))
            + (1.1 * _safe_float(row.get("building_commercial_count")))
            + (1.1 * _safe_float(row.get("landuse_commercial_count")))
            + (0.5 * _safe_float(row.get("poi_hospitality_count")))
        )
        transit_access_index = _index_from_weighted_sum(
            (1.8 * _safe_float(row.get("poi_transit_count")))
            + (0.4 * _safe_float(row.get("poi_any_count"))),
            scale=2.3,
        )
        ageing_user_exposure_index = _index_from_weighted_sum(
            (1.6 * _safe_float(row.get("poi_healthcare_count")))
            + (1.4 * _safe_float(row.get("poi_transit_count")))
            + (0.8 * _safe_float(row.get("building_residential_count")))
        )
        micromobility_corridor_index = _index_from_weighted_sum(
            (1.2 * _safe_float(row.get("poi_retail_count")))
            + (1.0 * _safe_float(row.get("poi_transit_count")))
            + (0.8 * _safe_float(row.get("poi_leisure_count")))
            + (0.6 * _safe_float(row.get("poi_hospitality_count")))
            + (0.4 * _safe_float(row.get("poi_any_count")))
        )
        vru_proxy_exposure_index = round(
            (
                school_frontage_index
                + retail_frontage_index
                + transit_access_index
                + ageing_user_exposure_index
            )
            / 4.0,
            6,
        )
        records.append(
            {
                "segment_score_id": segment_score_id,
                "segment_id": _clean_text(row.get("segment_id")),
                "segment_label": _segment_label_from_row(row),
                "corridor_label": _corridor_label_from_row(row),
                "road_class_label": _road_class_label(row),
                "public_score_band": _clean_text(row.get("public_score_band")),
                "public_score_index": round(_safe_float(row.get("public_score_index")), 6),
                "predicted_crash_count": round(_safe_float(row.get("predicted_crash_count")), 6),
                "observed_crash_count": round(_safe_float(row.get("observed_crash_count")), 6),
                "score_rank_desc": _safe_int(row.get("score_rank_desc")),
                "segment_length_m": round(
                    _safe_float(row.get("segment_length_m") or row.get("length")),
                    6,
                ),
                "maxspeed_kph": round(speed_kph, 6),
                "lanes_count": round(lanes, 6),
                "road_class_rank": round(road_class_rank, 6),
                "school_frontage_index": school_frontage_index,
                "retail_frontage_index": retail_frontage_index,
                "transit_access_index": transit_access_index,
                "ageing_user_exposure_index": ageing_user_exposure_index,
                "micromobility_corridor_index": micromobility_corridor_index,
                "vru_proxy_exposure_index": vru_proxy_exposure_index,
                "speed_stress_index": _stress_from_speed(speed_kph),
                "lane_stress_index": _stress_from_lanes(lanes),
                "poi_education_count": _safe_int(row.get("poi_education_count")),
                "poi_retail_count": _safe_int(row.get("poi_retail_count")),
                "poi_transit_count": _safe_int(row.get("poi_transit_count")),
                "poi_healthcare_count": _safe_int(row.get("poi_healthcare_count")),
            }
        )
    return records


def _crossing_rows(
    *,
    movement_features: list[dict[str, Any]],
    segment_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in movement_features:
        properties = feature.get("properties") or {}
        if _clean_text(properties.get("movement_role")) != "pedestrian_crossing":
            continue
        segment_id = _clean_text(properties.get("segment_id"))
        linked_segment = segment_by_id.get(segment_id or "")
        control_state = _clean_text(properties.get("control_state")) or "unknown"
        protection_state = _clean_text(properties.get("crossing_protection_state")) or control_state
        rows.append(
            {
                "crossing_id": str(properties.get("node_object_id") or properties.get("junction_id")),
                "junction_id": _clean_text(properties.get("junction_id")),
                "crossing_name": _clean_text(properties.get("name"))
                or str(properties.get("node_object_id") or properties.get("junction_id")),
                "control_state": control_state,
                "crossing_protection_state": protection_state,
                "priority_rule": _clean_text(properties.get("priority_rule")),
                "phase_priority_group": _clean_text(properties.get("phase_priority_group")),
                "segment_id": segment_id,
                "segment_score_id": (linked_segment or {}).get("segment_score_id"),
                "segment_label": (linked_segment or {}).get("segment_label")
                or _clean_text(properties.get("segment_name"))
                or segment_id,
                "corridor_label": (linked_segment or {}).get("corridor_label"),
                "road_class_label": (linked_segment or {}).get("road_class_label")
                or _clean_text(properties.get("segment_highway")),
                "public_score_index": round(float((linked_segment or {}).get("public_score_index") or 0.0), 6),
                "predicted_crash_count": round(float((linked_segment or {}).get("predicted_crash_count") or 0.0), 6),
                "observed_crash_count": round(float((linked_segment or {}).get("observed_crash_count") or 0.0), 6),
                "maxspeed_kph": round(float((linked_segment or {}).get("maxspeed_kph") or 30.0), 6),
                "lanes_count": round(float((linked_segment or {}).get("lanes_count") or 1.0), 6),
                "road_class_rank": round(float((linked_segment or {}).get("road_class_rank") or 0.0), 6),
                "school_frontage_index": round(float((linked_segment or {}).get("school_frontage_index") or 1.0), 6),
                "retail_frontage_index": round(float((linked_segment or {}).get("retail_frontage_index") or 1.0), 6),
                "transit_access_index": round(float((linked_segment or {}).get("transit_access_index") or 1.0), 6),
                "ageing_user_exposure_index": round(
                    float((linked_segment or {}).get("ageing_user_exposure_index") or 1.0),
                    6,
                ),
                "micromobility_corridor_index": round(
                    float((linked_segment or {}).get("micromobility_corridor_index") or 1.0),
                    6,
                ),
            }
        )
    return rows


def _crossing_feature_enrichment(crossings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    count_by_segment: dict[str, int] = {}
    protected_by_segment: dict[str, int] = {}
    count_by_corridor: dict[str, int] = {}
    protected_by_corridor: dict[str, int] = {}
    for row in crossings:
        segment_id = str(row.get("segment_id") or "")
        corridor_label = str(row.get("corridor_label") or "")
        count_by_segment[segment_id] = count_by_segment.get(segment_id, 0) + 1
        count_by_corridor[corridor_label] = count_by_corridor.get(corridor_label, 0) + 1
        if row.get("crossing_protection_state") == "signalized":
            protected_by_segment[segment_id] = protected_by_segment.get(segment_id, 0) + 1
            protected_by_corridor[corridor_label] = protected_by_corridor.get(corridor_label, 0) + 1

    enriched_rows: list[dict[str, Any]] = []
    for row in crossings:
        segment_id = str(row.get("segment_id") or "")
        corridor_label = str(row.get("corridor_label") or "")
        demand_norm = min(
            1.0,
            (
                float(row.get("school_frontage_index") or 1.0)
                + float(row.get("retail_frontage_index") or 1.0)
                + float(row.get("transit_access_index") or 1.0)
                + float(row.get("ageing_user_exposure_index") or 1.0)
                - 4.0
            )
            / 8.0,
        )
        speed_stress = _stress_from_speed(float(row.get("maxspeed_kph") or 30.0))
        lane_stress = _stress_from_lanes(float(row.get("lanes_count") or 1.0))
        road_class_stress = min(1.0, float(row.get("road_class_rank") or 0.0) / 8.0)
        crossing_barrier_index = round(
            (0.5 * speed_stress) + (0.3 * lane_stress) + (0.2 * road_class_stress),
            6,
        )
        protection_state = str(row.get("crossing_protection_state") or "")
        protection_penalty = {
            "signalized": 0.25,
            "marked_unsignalized": 0.55,
            "uncontrolled": 0.9,
        }.get(protection_state, 0.7)
        continuity_penalty = 1.0
        if count_by_segment.get(segment_id, 0) >= 2:
            continuity_penalty = 0.7
        if protected_by_corridor.get(corridor_label, 0) == 0:
            continuity_penalty += 0.15
        crossing_continuity_gap_index = round(min(1.0, demand_norm * continuity_penalty), 6)
        crossing_protection_gap_index = round(
            min(
                1.0,
                (0.45 * crossing_barrier_index)
                + (0.35 * protection_penalty)
                + (0.20 * demand_norm),
            ),
            6,
        )
        pedestrian_crossing_priority_score = round(
            100.0
            * (
                (0.35 * (float(row.get("public_score_index") or 0.0) / 100.0))
                + (0.25 * crossing_protection_gap_index)
                + (0.20 * crossing_continuity_gap_index)
                + (0.20 * demand_norm)
            ),
            6,
        )
        ageing_crossing_priority_score = round(
            100.0
            * (
                (0.30 * (float(row.get("public_score_index") or 0.0) / 100.0))
                + (0.25 * crossing_protection_gap_index)
                + (0.20 * crossing_continuity_gap_index)
                + (
                    0.25
                    * min(1.0, (float(row.get("ageing_user_exposure_index") or 1.0) - 1.0) / 3.0)
                )
            ),
            6,
        )
        enriched = dict(row)
        enriched.update(
            {
                "same_segment_crossing_count": count_by_segment.get(segment_id, 0),
                "same_segment_protected_crossing_count": protected_by_segment.get(segment_id, 0),
                "same_corridor_crossing_count": count_by_corridor.get(corridor_label, 0),
                "same_corridor_protected_crossing_count": protected_by_corridor.get(corridor_label, 0),
                "crossing_barrier_index": crossing_barrier_index,
                "crossing_continuity_gap_index": crossing_continuity_gap_index,
                "crossing_protection_gap_index": crossing_protection_gap_index,
                "pedestrian_crossing_priority_score": pedestrian_crossing_priority_score,
                "ageing_crossing_priority_score": ageing_crossing_priority_score,
            }
        )
        enriched_rows.append(enriched)

    enriched_rows.sort(
        key=lambda item: (
            -float(item["pedestrian_crossing_priority_score"]),
            -float(item["ageing_crossing_priority_score"]),
            str(item["crossing_id"]),
        )
    )
    for rank, row in enumerate(enriched_rows, start=1):
        row["pedestrian_crossing_priority_rank"] = rank
    ageing_ranked = sorted(
        enriched_rows,
        key=lambda item: (
            -float(item["ageing_crossing_priority_score"]),
            -float(item["pedestrian_crossing_priority_score"]),
            str(item["crossing_id"]),
        ),
    )
    for rank, row in enumerate(ageing_ranked, start=1):
        row["ageing_crossing_priority_rank"] = rank
    return enriched_rows


def _apply_segment_vru_scores(
    *,
    segment_records: list[dict[str, Any]],
    crossing_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    max_crossing_gap_by_segment: dict[str, float] = {}
    max_barrier_by_segment: dict[str, float] = {}
    crossing_count_by_segment: dict[str, int] = {}
    protected_count_by_segment: dict[str, int] = {}
    for row in crossing_rows:
        segment_id = str(row.get("segment_id") or "")
        crossing_count_by_segment[segment_id] = crossing_count_by_segment.get(segment_id, 0) + 1
        if row.get("crossing_protection_state") == "signalized":
            protected_count_by_segment[segment_id] = protected_count_by_segment.get(segment_id, 0) + 1
        max_crossing_gap_by_segment[segment_id] = max(
            float(row.get("crossing_protection_gap_index") or 0.0),
            max_crossing_gap_by_segment.get(segment_id, 0.0),
        )
        max_barrier_by_segment[segment_id] = max(
            float(row.get("crossing_barrier_index") or 0.0),
            max_barrier_by_segment.get(segment_id, 0.0),
        )

    scored_rows: list[dict[str, Any]] = []
    for row in segment_records:
        segment_id = str(row.get("segment_id") or "")
        demand_norm = min(
            1.0,
            (
                float(row.get("school_frontage_index") or 1.0)
                + float(row.get("retail_frontage_index") or 1.0)
                + float(row.get("transit_access_index") or 1.0)
                + float(row.get("ageing_user_exposure_index") or 1.0)
                - 4.0
            )
            / 8.0,
        )
        ageing_norm = min(1.0, (float(row.get("ageing_user_exposure_index") or 1.0) - 1.0) / 3.0)
        micromobility_norm = min(1.0, (float(row.get("micromobility_corridor_index") or 1.0) - 1.0) / 3.0)
        base_risk = min(1.0, float(row.get("public_score_index") or 0.0) / 100.0)
        barrier_proxy = max(
            float(row.get("speed_stress_index") or 0.0),
            float(row.get("lane_stress_index") or 0.0),
            max_barrier_by_segment.get(segment_id, 0.0),
        )
        segment_crossing_gap_index = max_crossing_gap_by_segment.get(segment_id, 0.0)
        pedestrian_priority_score = round(
            100.0
            * (
                (0.34 * base_risk)
                + (0.26 * demand_norm)
                + (0.22 * segment_crossing_gap_index)
                + (0.18 * barrier_proxy)
            ),
            6,
        )
        cyclist_priority_score = round(
            100.0
            * (
                (0.38 * base_risk)
                + (0.22 * micromobility_norm)
                + (0.22 * float(row.get("speed_stress_index") or 0.0))
                + (0.18 * float(row.get("lane_stress_index") or 0.0))
            ),
            6,
        )
        ageing_user_priority_score = round(
            100.0
            * (
                (0.30 * base_risk)
                + (0.24 * ageing_norm)
                + (0.24 * segment_crossing_gap_index)
                + (0.22 * barrier_proxy)
            ),
            6,
        )
        micromobility_priority_score = round(
            100.0
            * (
                (0.34 * base_risk)
                + (0.28 * micromobility_norm)
                + (0.20 * float(row.get("speed_stress_index") or 0.0))
                + (0.18 * float(row.get("lane_stress_index") or 0.0))
            ),
            6,
        )
        scored = dict(row)
        scored.update(
            {
                "segment_crossing_count": crossing_count_by_segment.get(segment_id, 0),
                "segment_protected_crossing_count": protected_count_by_segment.get(segment_id, 0),
                "segment_crossing_gap_index": round(segment_crossing_gap_index, 6),
                "segment_barrier_index": round(barrier_proxy, 6),
                "pedestrian_priority_score": pedestrian_priority_score,
                "cyclist_priority_score": cyclist_priority_score,
                "ageing_user_priority_score": ageing_user_priority_score,
                "micromobility_priority_score": micromobility_priority_score,
            }
        )
        scored["priority_reason_tags"] = " | ".join(_priority_reason_tags(scored)) or None
        scored_rows.append(scored)

    for user_group in _USER_GROUPS:
        score_key = f"{user_group}_priority_score"
        ranked = sorted(
            scored_rows,
            key=lambda item: (-float(item[score_key]), str(item["segment_score_id"])),
        )
        for rank, row in enumerate(ranked, start=1):
            row[f"{user_group}_priority_rank"] = rank
    return scored_rows


def _corridor_profiles(
    *,
    segment_rows: list[dict[str, Any]],
    crossing_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    segment_groups: dict[str, list[dict[str, Any]]] = {}
    for row in segment_rows:
        corridor_label = _clean_text(row.get("corridor_label"))
        if corridor_label:
            segment_groups.setdefault(corridor_label, []).append(row)

    crossings_by_corridor: dict[str, list[dict[str, Any]]] = {}
    for row in crossing_rows:
        corridor_label = _clean_text(row.get("corridor_label"))
        if corridor_label:
            crossings_by_corridor.setdefault(corridor_label, []).append(row)

    profiles: list[dict[str, Any]] = []
    for corridor_label, rows in segment_groups.items():
        if len(rows) < 3:
            continue
        crossings = crossings_by_corridor.get(corridor_label, [])
        crossing_count = len(crossings)
        signalized_crossing_count = sum(
            1 for row in crossings if row.get("crossing_protection_state") == "signalized"
        )
        uncontrolled_crossing_count = sum(
            1 for row in crossings if row.get("crossing_protection_state") == "uncontrolled"
        )
        protected_crossing_gap_count = sum(
            1 for row in crossings if float(row.get("crossing_protection_gap_index") or 0.0) >= 0.55
        )
        walkability_gap_score = round(
            min(
                100.0,
                (0.55 * sum(float(row["pedestrian_priority_score"]) for row in rows) / len(rows))
                + (0.25 * sum(float(row["ageing_user_priority_score"]) for row in rows) / len(rows))
                + (
                    20.0
                    * (
                        float(protected_crossing_gap_count) / float(crossing_count)
                        if crossing_count
                        else 0.0
                    )
                ),
            ),
            6,
        )
        rideability_gap_score = round(
            min(
                100.0,
                (0.55 * sum(float(row["cyclist_priority_score"]) for row in rows) / len(rows))
                + (0.25 * sum(float(row["micromobility_priority_score"]) for row in rows) / len(rows))
                + (20.0 * sum(float(row["speed_stress_index"]) for row in rows) / len(rows)),
            ),
            6,
        )
        micromobility_gap_score = round(
            sum(float(row["micromobility_priority_score"]) for row in rows) / len(rows),
            6,
        )
        profiles.append(
            {
                "corridor_label": corridor_label,
                "segment_count": len(rows),
                "predicted_crash_total": round(
                    sum(float(row["predicted_crash_count"]) for row in rows),
                    6,
                ),
                "crossing_count": crossing_count,
                "signalized_crossing_count": signalized_crossing_count,
                "uncontrolled_crossing_count": uncontrolled_crossing_count,
                "protected_crossing_gap_count": protected_crossing_gap_count,
                "school_frontage_segment_count": sum(
                    1 for row in rows if float(row["school_frontage_index"]) >= 1.4
                ),
                "retail_frontage_segment_count": sum(
                    1 for row in rows if float(row["retail_frontage_index"]) >= 1.4
                ),
                "transit_access_segment_count": sum(
                    1 for row in rows if float(row["transit_access_index"]) >= 1.35
                ),
                "micromobility_corridor_segment_count": sum(
                    1 for row in rows if float(row["micromobility_corridor_index"]) >= 1.35
                ),
                "walkability_gap_score": walkability_gap_score,
                "rideability_gap_score": rideability_gap_score,
                "micromobility_gap_score": micromobility_gap_score,
                "top_segment_score_ids": [
                    row["segment_score_id"]
                    for row in sorted(
                        rows,
                        key=lambda item: (
                            -float(item["pedestrian_priority_score"]),
                            -float(item["micromobility_priority_score"]),
                            str(item["segment_score_id"]),
                        ),
                    )[:5]
                ],
            }
        )
    profiles.sort(
        key=lambda item: (
            -float(item["walkability_gap_score"]),
            -float(item["rideability_gap_score"]),
            str(item["corridor_label"]),
        )
    )
    return profiles


def _top_rows(
    rows: list[dict[str, Any]],
    *,
    score_key: str,
    limit: int = 15,
) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda item: (-float(item[score_key]), str(item.get("segment_score_id") or item.get("crossing_id") or "")),
    )
    return ordered[:limit]


def _bundle_markdown(bundle: dict[str, Any]) -> str:
    summary = bundle["planning_summary"]
    lines = [
        f"# {bundle['display_name']} VRU Intelligence",
        "",
        f"- Run label: `{bundle['prediction_run_label']}`",
        f"- Generated: `{bundle['generated_at_utc']}`",
        "",
        "## Top Priorities",
        "",
        f"- Top crossing candidate: `{summary['top_crossing_candidate'].get('crossing_name')}`",
        f"- Top walkability corridor: `{summary['top_walkability_corridor'].get('corridor_label')}`",
        f"- Top rideability corridor: `{summary['top_rideability_corridor'].get('corridor_label')}`",
        f"- Top micromobility corridor: `{summary['top_micromobility_corridor'].get('corridor_label')}`",
        "",
        "## Exposure Layer Coverage",
        "",
        f"- School-frontage segments: `{bundle['stats']['school_frontage_segment_count']}`",
        f"- Retail-frontage segments: `{bundle['stats']['retail_frontage_segment_count']}`",
        f"- Transit-access segments: `{bundle['stats']['transit_access_segment_count']}`",
        f"- Micromobility-corridor segments: `{bundle['stats']['micromobility_corridor_segment_count']}`",
        f"- Crossing profiles: `{bundle['stats']['crossing_profile_count']}`",
        "",
        "## Uncertainty",
        "",
    ]
    for item in bundle.get("uncertainty_notes", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _build_bundle_for_run(
    *,
    dashboard_summary_path: Path,
    run_record: dict[str, Any],
    movement_object_features: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    segment_manifest_path = _resolve_reference_path(
        str(run_record["segment_scores"]["manifest_path"]),
        anchor_path=dashboard_summary_path,
    )
    segment_manifest = _load_json(segment_manifest_path)
    analyst_csv_path = _resolve_reference_path(
        str(segment_manifest["outputs"]["analyst_csv_path"]),
        anchor_path=segment_manifest_path,
    )
    analyst_rows = _load_csv_rows(analyst_csv_path)
    segment_rows = _segment_base_records(analyst_rows)
    segment_by_id = {
        str(row["segment_id"]): row
        for row in segment_rows
        if row.get("segment_id")
    }
    crossing_rows = _crossing_rows(
        movement_features=movement_object_features if str(run_record.get("city_key")) == "bari" else [],
        segment_by_id=segment_by_id,
    )
    crossing_rows = _crossing_feature_enrichment(crossing_rows)
    segment_rows = _apply_segment_vru_scores(
        segment_records=segment_rows,
        crossing_rows=crossing_rows,
    )
    corridor_profiles = _corridor_profiles(
        segment_rows=segment_rows,
        crossing_rows=crossing_rows,
    )

    user_group_views = {
        user_group: {
            "top_segments": _top_rows(
                segment_rows,
                score_key=f"{user_group}_priority_score",
            ),
        }
        for user_group in _USER_GROUPS
    }

    planning_summary = {
        "top_crossing_candidate": crossing_rows[0] if crossing_rows else {},
        "top_walkability_corridor": corridor_profiles[0] if corridor_profiles else {},
        "top_rideability_corridor": max(
            corridor_profiles,
            key=lambda item: (float(item["rideability_gap_score"]), str(item["corridor_label"])),
            default={},
        ),
        "top_micromobility_corridor": max(
            corridor_profiles,
            key=lambda item: (float(item["micromobility_gap_score"]), str(item["corridor_label"])),
            default={},
        ),
    }
    bundle = {
        "vru_intelligence_bundle_version": VRU_INTELLIGENCE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_dashboard_summary_path": str(dashboard_summary_path),
        "city_key": run_record["city_key"],
        "display_name": run_record["display_name"],
        "prediction_run_label": run_record["prediction_run_label"],
        "user_group_views": user_group_views,
        "top_crossing_priorities": crossing_rows[:25],
        "top_corridor_profiles": corridor_profiles[:25],
        "planning_summary": planning_summary,
        "uncertainty_notes": [
            "Current VRU demand is still proxy-based and uses schools, retail, transit, healthcare, and built-environment context rather than observed pedestrian or micromobility counts.",
            "Crossing continuity and barrier indicators are derived from the Bari object model and linked segment features, not from trajectory or signal-compliance sensing.",
        ],
        "stats": {
            "segment_count": len(segment_rows),
            "crossing_profile_count": len(crossing_rows),
            "corridor_profile_count": len(corridor_profiles),
            "school_frontage_segment_count": sum(
                1 for row in segment_rows if float(row["school_frontage_index"]) >= 1.4
            ),
            "retail_frontage_segment_count": sum(
                1 for row in segment_rows if float(row["retail_frontage_index"]) >= 1.4
            ),
            "transit_access_segment_count": sum(
                1 for row in segment_rows if float(row["transit_access_index"]) >= 1.35
            ),
            "micromobility_corridor_segment_count": sum(
                1 for row in segment_rows if float(row["micromobility_corridor_index"]) >= 1.35
            ),
        },
    }
    return bundle, segment_rows, crossing_rows, corridor_profiles, [segment_manifest_path, analyst_csv_path]


def build_vru_intelligence_bundle(
    *,
    dashboard_summary_path: str | Path = "data/dashboard/dashboard_summary.json",
    output_dir: str | Path = DEFAULT_VRU_OUTPUT_DIR,
    prediction_run_labels: list[str] | None = None,
    movement_objects_path: str | Path = DEFAULT_BARI_MOVEMENT_OBJECTS_PATH,
) -> dict[str, Any]:
    dashboard_summary_input = Path(dashboard_summary_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    summary = _load_json(dashboard_summary_input)
    published_runs = list(summary.get("published_runs", []))
    if prediction_run_labels:
        wanted = {str(label) for label in prediction_run_labels}
        published_runs = [
            record
            for record in published_runs
            if str(record.get("prediction_run_label")) in wanted
        ]
    if not published_runs:
        raise RuntimeError("No published runs matched the requested VRU-intelligence filters.")

    movement_objects_input = Path(movement_objects_path)
    movement_object_features = (
        _load_feature_collection(movement_objects_input)
        if movement_objects_input.exists()
        else []
    )

    bundle_outputs: list[dict[str, Any]] = []
    for run_record in published_runs:
        prediction_run_label = str(run_record["prediction_run_label"])
        run_output_dir = output_root / prediction_run_label
        run_output_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = run_output_dir / "vru_intelligence_bundle.json"
        markdown_path = run_output_dir / "vru_intelligence_bundle.md"
        segment_scores_path = run_output_dir / "segment_vru_scores.csv"
        crossing_profiles_path = run_output_dir / "crossing_priority_profiles.csv"
        corridor_profiles_path = run_output_dir / "corridor_vru_profiles.csv"
        manifest_path = run_output_dir / "vru_intelligence_bundle.manifest.json"

        bundle, segment_rows, crossing_rows, corridor_profiles, upstream_paths = _build_bundle_for_run(
            dashboard_summary_path=dashboard_summary_input,
            run_record=run_record,
            movement_object_features=movement_object_features,
        )

        bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(_bundle_markdown(bundle), encoding="utf-8")
        _write_csv(segment_scores_path, segment_rows)
        _write_csv(crossing_profiles_path, crossing_rows)
        _write_csv(corridor_profiles_path, corridor_profiles)

        upstream_inputs = [
            _artifact_reference(
                "dashboard_summary_json",
                dashboard_summary_input,
                _sha256(dashboard_summary_input),
            ),
        ]
        for path in upstream_paths:
            upstream_inputs.append(
                _artifact_reference(
                    "published_vru_input",
                    path,
                    _sha256(path),
                )
            )
        if movement_object_features and str(run_record.get("city_key")) == "bari":
            upstream_inputs.append(
                _artifact_reference(
                    "movement_object_layer",
                    movement_objects_input,
                    _sha256(movement_objects_input),
                )
            )

        manifest = {
            "vru_intelligence_bundle_version": VRU_INTELLIGENCE_VERSION,
            "inputs": {
                "dashboard_summary_path": str(dashboard_summary_input),
                "dashboard_summary_sha256": _sha256(dashboard_summary_input),
                "prediction_run_label": prediction_run_label,
                "movement_objects_path": str(movement_objects_input) if movement_object_features else None,
            },
            "outputs": {
                "bundle_path": str(bundle_path),
                "bundle_sha256": _sha256(bundle_path),
                "markdown_path": str(markdown_path),
                "markdown_sha256": _sha256(markdown_path),
                "segment_scores_path": str(segment_scores_path),
                "crossing_profiles_path": str(crossing_profiles_path),
                "corridor_profiles_path": str(corridor_profiles_path),
                "manifest_path": str(manifest_path),
            },
            "contract": {
                "resource_name": "vru_intelligence_bundle",
                "public_contract_version": VRU_INTELLIGENCE_CONTRACT_VERSION,
                "vru_intelligence_bundle_version": VRU_INTELLIGENCE_VERSION,
            },
            "stats": bundle["stats"],
            "lineage": _build_lineage_contract(
                run_record_path=manifest_path,
                upstream_inputs=upstream_inputs,
                publishable_outputs=[
                    _artifact_reference(
                        "vru_intelligence_bundle_json",
                        bundle_path,
                        _sha256(bundle_path),
                    ),
                    _artifact_reference(
                        "vru_intelligence_bundle_markdown",
                        markdown_path,
                        _sha256(markdown_path),
                    ),
                    _artifact_reference(
                        "segment_vru_scores_csv",
                        segment_scores_path,
                        _sha256(segment_scores_path),
                    ),
                    _artifact_reference(
                        "crossing_priority_profiles_csv",
                        crossing_profiles_path,
                        _sha256(crossing_profiles_path),
                    ),
                    _artifact_reference(
                        "corridor_vru_profiles_csv",
                        corridor_profiles_path,
                        _sha256(corridor_profiles_path),
                    ),
                ],
                supporting_outputs=[],
            ),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        bundle_outputs.append(
            {
                "city_key": run_record["city_key"],
                "display_name": run_record["display_name"],
                "prediction_run_label": prediction_run_label,
                "bundle_path": str(bundle_path),
                "markdown_path": str(markdown_path),
                "manifest_path": str(manifest_path),
            }
        )

    index_payload = {
        "vru_intelligence_bundle_version": VRU_INTELLIGENCE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_dashboard_summary_path": str(dashboard_summary_input),
        "vru_bundles": sorted(bundle_outputs, key=lambda item: str(item["display_name"])),
        "stats": {
            "bundle_count": len(bundle_outputs),
        },
    }
    index_path = output_root / "vru_intelligence_index.json"
    index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "vru_intelligence_bundle_version": VRU_INTELLIGENCE_VERSION,
        "index_path": str(index_path),
        "bundle_count": len(bundle_outputs),
        "bundles": sorted(bundle_outputs, key=lambda item: str(item["display_name"])),
        "stats": index_payload["stats"],
    }
