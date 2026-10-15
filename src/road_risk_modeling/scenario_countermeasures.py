"""Build scenario and countermeasure bundles from published risk surfaces."""

from __future__ import annotations

import ast
import csv
from datetime import UTC, datetime
import itertools
import json
import math
from pathlib import Path
from typing import Any

try:
    from shapely.geometry import shape as _shapely_shape
except Exception:  # pragma: no cover - optional import fallback
    _shapely_shape = None

from .countermeasure_knowledge import (
    COUNTERMEASURE_KNOWLEDGE_VERSION,
    build_scenario_intervention_library,
)
from .dashboard_summary import _resolve_reference_path
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SCENARIO_COUNTERMEASURE_VERSION = "scenario_countermeasure_bundle_v1"
SCENARIO_COUNTERMEASURE_CONTRACT_VERSION = "scenario_countermeasure_bundle_public_v1"
SCENARIO_SPEC_VERSION = "scenario_spec_v1"
INTERVENTION_LIBRARY_VERSION = "scenario_intervention_library_v2"

DEFAULT_SCENARIO_OUTPUT_DIR = Path("data/planning/scenario_countermeasures")
DEFAULT_SCENARIO_INDEX_PATH = DEFAULT_SCENARIO_OUTPUT_DIR / "scenario_countermeasure_index.json"
DEFAULT_SCENARIO_LIBRARY_PATH = DEFAULT_SCENARIO_OUTPUT_DIR / "intervention_library.json"
DEFAULT_BARI_SIGNAL_NODES_PATH = Path(
    "data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson"
)
DEFAULT_BARI_NODE_OBJECTS_PATH = Path(
    "data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson"
)

# The intervention library is derived from the countermeasure knowledge base
# (AI-01): descriptive templates live in `countermeasure_knowledge.py` and the
# reduction bounds are aggregated from the seeded CMF evidence, with the
# supporting countermeasure ids and citations attached to each record.
_INTERVENTION_LIBRARY: tuple[dict[str, Any], ...] = build_scenario_intervention_library()


_SPEC_SCHEMA = {
    "scenario_spec_version": SCENARIO_SPEC_VERSION,
    "required_top_level_fields": [
        "scenario_spec_version",
        "generated_at_utc",
        "city_key",
        "display_name",
        "prediction_run_label",
        "target_context",
        "scenarios",
    ],
    "scenario_fields": [
        "scenario_id",
        "title",
        "intervention_code",
        "target_context_key",
        "target_context_label",
        "selection_rationale",
        "target_assets",
        "assumptions",
        "uncertainty_flags",
    ],
    "target_asset_fields": [
        "asset_type",
        "asset_id",
        "asset_label",
        "linked_segment_score_ids",
        "selection_source",
        "asset_metadata",
    ],
}

_SCENARIO_TEMPLATE_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        "scenario_slug": "corridor_speed_management",
        "intervention_code": "speed_management",
        "asset_group_key": "corridor_segments",
        "target_context_key": "top_corridor",
        "target_context_label_key": "corridor_label",
        "title_template": "Reduce operating speeds on {context_label}",
        "selection_rationale_template": "Apply speed management to the lead corridor shortlist from the published dashboard summary.",
    },
    {
        "scenario_slug": "corridor_signal_timing",
        "intervention_code": "signal_timing",
        "asset_group_key": "signal_assets",
        "target_context_key": "lead_signalized_nodes",
        "target_context_label_key": "corridor_label",
        "title_template": "Retune nearby signal timing around {context_label}",
        "selection_rationale_template": "Use the nearest signalized Bari nodes linked back to the lead corridor risk surface.",
    },
    {
        "scenario_slug": "hotspot_crossing_protection",
        "intervention_code": "crossing_protection",
        "asset_group_key": "crossing_assets",
        "target_context_key": "top_hotspot_tile",
        "target_context_label_key": "tile_label",
        "title_template": "Protect the lead hotspot crossings near {context_label}",
        "selection_rationale_template": "Target the nearest pedestrian crossings to the lead hotspot tile and its supporting high-score segments.",
    },
    {
        "scenario_slug": "corridor_cycling_protection",
        "intervention_code": "cycling_protection",
        "asset_group_key": "corridor_segments",
        "target_context_key": "top_corridor",
        "target_context_label_key": "corridor_label",
        "title_template": "Add cycling protection along {context_label}",
        "selection_rationale_template": "Use the corridor shortlist as a candidate for lane reallocation or a protected cycle facility.",
    },
    {
        "scenario_slug": "hotspot_lighting_upgrade",
        "intervention_code": "lighting_upgrade",
        "asset_group_key": "hotspot_segments",
        "target_context_key": "top_hotspot_tile",
        "target_context_label_key": "tile_label",
        "title_template": "Upgrade supporting lighting in hotspot {context_label}",
        "selection_rationale_template": "Use the lead hotspot tile and its supporting segments for a lower-cost visibility package.",
    },
    {
        "scenario_slug": "junction_traffic_calming",
        "intervention_code": "traffic_calming",
        "asset_group_key": "junction_assets",
        "target_context_key": "lead_junction_cluster",
        "target_context_label_key": "tile_label",
        "title_template": "Apply traffic calming near {context_label}",
        "selection_rationale_template": "Use the nearest unsignalized junction cluster as a neighbourhood-scale calming candidate.",
    },
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


def _max_literal_numeric(value: Any) -> float | None:
    numeric_values = _literal_numeric_values(value)
    if not numeric_values:
        return None
    return max(numeric_values)


def _index_features_by_property(
    features: list[dict[str, Any]],
    *,
    property_name: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        identifier = properties.get(property_name)
        if identifier:
            indexed[str(identifier)] = feature
    return indexed


def _geometry_bounds(geometry: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    if not isinstance(geometry, dict):
        return None
    coordinates = geometry.get("coordinates")
    pairs: list[tuple[float, float]] = []

    def _collect_pairs(value: Any) -> None:
        if isinstance(value, (list, tuple)):
            if len(value) == 2 and all(isinstance(item, (int, float)) for item in value):
                pairs.append((float(value[0]), float(value[1])))
                return
            for item in value:
                _collect_pairs(item)

    _collect_pairs(coordinates)
    if not pairs:
        return None
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    return min(xs), min(ys), max(xs), max(ys)


def _bounds_distance(
    left: tuple[float, float, float, float] | None,
    right: tuple[float, float, float, float] | None,
) -> float:
    if left is None or right is None:
        return 10**9
    dx = max(right[0] - left[2], left[0] - right[2], 0.0)
    dy = max(right[1] - left[3], left[1] - right[3], 0.0)
    return math.hypot(dx, dy)


def _feature_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    if _shapely_shape is not None:
        try:
            return float(
                _shapely_shape(left.get("geometry")).distance(_shapely_shape(right.get("geometry")))
            )
        except Exception:  # nosec B110 # optional conversion/geometry fallback continues below
            pass
    return _bounds_distance(_geometry_bounds(left.get("geometry")), _geometry_bounds(right.get("geometry")))


def _segment_label_from_row(row: dict[str, Any]) -> str:
    for key in ("segment_label", "name", "ref", "highway", "segment_id"):
        value = _normalize_literal_text(row.get(key))
        if value:
            return value
    return str(row.get("segment_score_id") or row.get("segment_id") or "Unnamed segment")


def _build_segment_asset(
    *,
    row: dict[str, Any],
    selection_source: str,
) -> dict[str, Any]:
    score_id = str(row.get("segment_score_id"))
    return {
        "asset_type": "segment",
        "asset_id": score_id,
        "asset_label": _segment_label_from_row(row),
        "linked_segment_score_ids": [score_id],
        "selection_source": selection_source,
        "asset_metadata": {
            "segment_id": row.get("segment_id"),
            "public_score_band": row.get("public_score_band"),
            "public_score_index": round(_safe_float(row.get("public_score_index")), 3),
            "predicted_crash_count": round(_safe_float(row.get("predicted_crash_count")), 6),
        },
    }


def _select_linked_segments_for_asset(
    *,
    asset_feature: dict[str, Any],
    asset_segment_id: str | None,
    asset_type: str,
    analyst_rows_by_score_id: dict[str, dict[str, Any]],
    analyst_rows_by_segment_id: dict[str, dict[str, Any]],
    public_segment_by_score_id: dict[str, dict[str, Any]],
    preferred_segment_score_ids: list[str],
    limit: int = 4,
) -> list[str]:
    linked_score_ids: list[str] = []
    if asset_segment_id:
        direct_match = analyst_rows_by_segment_id.get(asset_segment_id)
        if direct_match is not None and direct_match.get("segment_score_id"):
            linked_score_ids.append(str(direct_match["segment_score_id"]))

    candidate_score_ids = [
        str(score_id)
        for score_id in preferred_segment_score_ids
        if str(score_id) in public_segment_by_score_id and str(score_id) in analyst_rows_by_score_id
    ]
    if not candidate_score_ids:
        candidate_score_ids = list(public_segment_by_score_id.keys())

    scored_candidates: list[tuple[int, float, float, str]] = []
    preferred = {str(score_id) for score_id in preferred_segment_score_ids}
    for segment_score_id in candidate_score_ids:
        feature = public_segment_by_score_id.get(segment_score_id)
        if feature is None:
            continue
        row = analyst_rows_by_score_id.get(segment_score_id)
        if row is None:
            continue
        distance = _feature_distance(asset_feature, feature)
        preference = 0 if segment_score_id in preferred else 1
        scored_candidates.append(
            (
                preference,
                distance,
                -_safe_float(row.get("public_score_index")),
                segment_score_id,
            )
        )
    for _, _, _, segment_score_id in sorted(scored_candidates):
        if segment_score_id in linked_score_ids:
            continue
        linked_score_ids.append(segment_score_id)
        if len(linked_score_ids) >= limit:
            break

    if not linked_score_ids and asset_type == "crossing":
        return preferred_segment_score_ids[:limit]
    return linked_score_ids[:limit]


def _build_node_asset(
    *,
    asset_type: str,
    feature: dict[str, Any],
    selection_source: str,
    analyst_rows_by_score_id: dict[str, dict[str, Any]],
    analyst_rows_by_segment_id: dict[str, dict[str, Any]],
    public_segment_by_score_id: dict[str, dict[str, Any]],
    preferred_segment_score_ids: list[str],
    selection_distance: float,
) -> dict[str, Any]:
    properties = feature.get("properties") or {}
    linked_segment_score_ids = _select_linked_segments_for_asset(
        asset_feature=feature,
        asset_segment_id=_clean_text(properties.get("segment_id")),
        asset_type=asset_type,
        analyst_rows_by_score_id=analyst_rows_by_score_id,
        analyst_rows_by_segment_id=analyst_rows_by_segment_id,
        public_segment_by_score_id=public_segment_by_score_id,
        preferred_segment_score_ids=preferred_segment_score_ids,
    )
    return {
        "asset_type": asset_type,
        "asset_id": str(properties.get("node_object_id") or properties.get("junction_id")),
        "asset_label": _clean_text(properties.get("name"))
        or str(properties.get("node_object_id") or properties.get("junction_id") or asset_type),
        "linked_segment_score_ids": linked_segment_score_ids,
        "selection_source": selection_source,
        "asset_metadata": {
            "junction_id": properties.get("junction_id"),
            "node_role": properties.get("node_role"),
            "object_type": properties.get("object_type"),
            "segment_id": properties.get("segment_id"),
            "signal_type": properties.get("signal_type"),
            "crossing_type": properties.get("crossing_type"),
            "crossing_markings": properties.get("crossing_markings"),
            "crossing_signals": properties.get("crossing_signals"),
            "selection_distance": round(selection_distance, 6),
        },
    }


def _select_nearest_node_assets(
    *,
    features: list[dict[str, Any]],
    feature_filter: Any,
    focus_features: list[dict[str, Any]],
    asset_type: str,
    selection_source: str,
    analyst_rows_by_score_id: dict[str, dict[str, Any]],
    analyst_rows_by_segment_id: dict[str, dict[str, Any]],
    public_segment_by_score_id: dict[str, dict[str, Any]],
    preferred_segment_score_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    ranked_features: list[tuple[float, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for feature in features:
        properties = feature.get("properties") or {}
        if not feature_filter(properties):
            continue
        asset_id = str(properties.get("node_object_id") or properties.get("junction_id") or "")
        if not asset_id or asset_id in seen_ids:
            continue
        if focus_features:
            distance = min(_feature_distance(feature, focus_feature) for focus_feature in focus_features)
        else:
            distance = 10**9
        ranked_features.append((distance, feature))
        seen_ids.add(asset_id)

    ranked_features.sort(
        key=lambda item: (
            item[0],
            str((item[1].get("properties") or {}).get("name") or ""),
        )
    )
    candidate_features = ranked_features[: max(limit * 6, limit)]

    ranked_assets: list[tuple[float, dict[str, Any]]] = []
    for distance, feature in candidate_features:
        ranked_assets.append(
            (
                distance,
                _build_node_asset(
                    asset_type=asset_type,
                    feature=feature,
                    selection_source=selection_source,
                    analyst_rows_by_score_id=analyst_rows_by_score_id,
                    analyst_rows_by_segment_id=analyst_rows_by_segment_id,
                    public_segment_by_score_id=public_segment_by_score_id,
                    preferred_segment_score_ids=preferred_segment_score_ids,
                    selection_distance=distance,
                ),
            )
        )

    ranked_assets.sort(
        key=lambda item: (
            item[0],
            -len(item[1]["linked_segment_score_ids"]),
            str(item[1]["asset_label"]),
        )
    )
    return [asset for _, asset in ranked_assets[:limit]]


def _scenario_target_context(
    *,
    prediction_run_label: str,
    top_corridor: dict[str, Any] | None,
    top_tile: dict[str, Any] | None,
) -> dict[str, Any]:
    corridor_label = (
        str(top_corridor.get("corridor_label"))
        if isinstance(top_corridor, dict) and top_corridor.get("corridor_label")
        else prediction_run_label
    )
    tile_label = (
        str(top_tile.get("tile_score_id"))
        if isinstance(top_tile, dict) and top_tile.get("tile_score_id")
        else prediction_run_label
    )
    return {
        "corridor_label": corridor_label,
        "tile_label": tile_label,
    }


def _prepare_default_assets(
    *,
    run_record: dict[str, Any],
    shortlist_record: dict[str, Any] | None,
    analyst_rows_by_score_id: dict[str, dict[str, Any]],
    analyst_rows_by_segment_id: dict[str, dict[str, Any]],
    public_segment_by_score_id: dict[str, dict[str, Any]],
    signal_node_features: list[dict[str, Any]],
    node_object_features: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    top_corridor = ((shortlist_record or {}).get("top_corridors") or [None])[0]
    top_tile = ((shortlist_record or {}).get("hotspot_tiles") or [None])[0]
    corridor_ids = [
        str(score_id)
        for score_id in (top_corridor or {}).get("focus_segment_score_ids", [])
        if str(score_id) in analyst_rows_by_score_id
    ]
    hotspot_ids = [
        str(score_id)
        for score_id in (top_tile or {}).get("focus_segment_score_ids", [])
        if str(score_id) in analyst_rows_by_score_id
    ]
    preferred_segment_score_ids = list(dict.fromkeys(corridor_ids + hotspot_ids))

    corridor_segments = [
        _build_segment_asset(
            row=analyst_rows_by_score_id[score_id],
            selection_source="dashboard_top_corridor",
        )
        for score_id in corridor_ids[:5]
    ]
    hotspot_segments = [
        _build_segment_asset(
            row=analyst_rows_by_score_id[score_id],
            selection_source="dashboard_top_hotspot_tile",
        )
        for score_id in hotspot_ids[:5]
    ]
    focus_features = [
        public_segment_by_score_id[score_id]
        for score_id in preferred_segment_score_ids
        if score_id in public_segment_by_score_id
    ]

    signal_assets: list[dict[str, Any]] = []
    crossing_assets: list[dict[str, Any]] = []
    junction_assets: list[dict[str, Any]] = []
    if str(run_record.get("city_key")) == "bari":
        signal_assets = _select_nearest_node_assets(
            features=signal_node_features,
            feature_filter=lambda props: props.get("object_type") == "traffic_signal",
            focus_features=focus_features,
            asset_type="signal",
            selection_source="nearest_bari_signal_node",
            analyst_rows_by_score_id=analyst_rows_by_score_id,
            analyst_rows_by_segment_id=analyst_rows_by_segment_id,
            public_segment_by_score_id=public_segment_by_score_id,
            preferred_segment_score_ids=preferred_segment_score_ids,
            limit=2,
        )
        crossing_assets = _select_nearest_node_assets(
            features=node_object_features,
            feature_filter=lambda props: props.get("object_type") == "crossing",
            focus_features=focus_features,
            asset_type="crossing",
            selection_source="nearest_bari_crossing_node",
            analyst_rows_by_score_id=analyst_rows_by_score_id,
            analyst_rows_by_segment_id=analyst_rows_by_segment_id,
            public_segment_by_score_id=public_segment_by_score_id,
            preferred_segment_score_ids=preferred_segment_score_ids,
            limit=2,
        )
        junction_assets = _select_nearest_node_assets(
            features=node_object_features,
            feature_filter=lambda props: props.get("object_type") in {"unsignalized_junction", "roundabout"},
            focus_features=focus_features,
            asset_type="junction",
            selection_source="nearest_bari_junction_node",
            analyst_rows_by_score_id=analyst_rows_by_score_id,
            analyst_rows_by_segment_id=analyst_rows_by_segment_id,
            public_segment_by_score_id=public_segment_by_score_id,
            preferred_segment_score_ids=preferred_segment_score_ids,
            limit=2,
        )

    return {
        "corridor_segments": corridor_segments,
        "hotspot_segments": hotspot_segments,
        "signal_assets": signal_assets,
        "crossing_assets": crossing_assets,
        "junction_assets": junction_assets,
    }


def _build_scenario_spec(
    *,
    run_record: dict[str, Any],
    shortlist_record: dict[str, Any] | None,
    assets: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    prediction_run_label = str(run_record["prediction_run_label"])
    top_corridor = ((shortlist_record or {}).get("top_corridors") or [None])[0]
    top_tile = ((shortlist_record or {}).get("hotspot_tiles") or [None])[0]
    target_context = _scenario_target_context(
        prediction_run_label=prediction_run_label,
        top_corridor=top_corridor,
        top_tile=top_tile,
    )
    scenarios: list[dict[str, Any]] = []
    library_by_code = {
        record["intervention_code"]: record
        for record in _INTERVENTION_LIBRARY
    }
    for template in _SCENARIO_TEMPLATE_DEFINITIONS:
        target_assets = list(assets.get(template["asset_group_key"], []))
        if not target_assets:
            continue
        intervention = library_by_code[template["intervention_code"]]
        context_label = target_context[template["target_context_label_key"]]
        scenarios.append(
            {
                "scenario_id": f"{prediction_run_label}:{template['scenario_slug']}",
                "title": template["title_template"].format(context_label=context_label),
                "intervention_code": template["intervention_code"],
                "target_context_key": template["target_context_key"],
                "target_context_label": context_label,
                "selection_rationale": template["selection_rationale_template"],
                "target_assets": target_assets,
                "assumptions": list(intervention["default_assumptions"]),
                "uncertainty_flags": [
                    "heuristic_counterfactual_only",
                    "published_risk_surface_not_refit",
                ],
            }
        )
    return {
        "scenario_spec_version": SCENARIO_SPEC_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "schema": _SPEC_SCHEMA,
        "city_key": run_record["city_key"],
        "display_name": run_record["display_name"],
        "prediction_run_label": prediction_run_label,
        "target_context": {
            "top_corridor": top_corridor,
            "top_hotspot_tile": top_tile,
        },
        "scenarios": scenarios,
    }


def _adjustment_target_value(
    *,
    intervention_code: str,
    row: dict[str, Any],
    template: dict[str, Any],
) -> Any:
    feature_name = template["feature_name"]
    if intervention_code == "speed_management" and feature_name == "maxspeed":
        current_speed = _max_literal_numeric(row.get("maxspeed"))
        return int(min(current_speed, 50.0)) if current_speed is not None else 50
    return template["target_value"]


def _scenario_reduction_fraction(
    *,
    intervention_code: str,
    row: dict[str, Any],
    asset_type: str,
    asset_metadata: dict[str, Any],
) -> float:
    library = {
        record["intervention_code"]: record
        for record in _INTERVENTION_LIBRARY
    }[intervention_code]
    bounds = library["baseline_reduction_bounds"]
    reduction = float(bounds["central"])
    maxspeed = _max_literal_numeric(row.get("maxspeed")) or 0.0
    lanes = _max_literal_numeric(row.get("lanes")) or 1.0
    length_m = _safe_float(row.get("segment_length_m") or row.get("length"))
    public_score_index = _safe_float(row.get("public_score_index"))
    highway = (_normalize_literal_text(row.get("highway")) or "").lower()

    if intervention_code == "speed_management":
        if maxspeed > 50:
            reduction += min(maxspeed - 50.0, 40.0) * 0.0025
        if lanes >= 3:
            reduction += 0.025
        if "trunk" in highway or "primary" in highway:
            reduction += 0.015
    elif intervention_code == "crossing_protection":
        if str(asset_metadata.get("crossing_type") or "").lower() in {"uncontrolled", "marked", "zebra"}:
            reduction += 0.03
        if not _clean_text(asset_metadata.get("crossing_signals")):
            reduction += 0.02
        if maxspeed >= 50:
            reduction += 0.025
    elif intervention_code == "signal_timing":
        if public_score_index >= 95:
            reduction += 0.025
        if lanes >= 2:
            reduction += 0.015
        if asset_type == "signal" and _clean_text(asset_metadata.get("signal_type")):
            reduction += 0.01
    elif intervention_code == "cycling_protection":
        if lanes >= 2:
            reduction += 0.03
        if any(token in highway for token in ("trunk", "primary", "secondary")):
            reduction += 0.025
        if maxspeed >= 50:
            reduction += 0.015
    elif intervention_code == "lighting_upgrade":
        if length_m >= 250:
            reduction += 0.015
        if public_score_index >= 90:
            reduction += 0.01
        if any(token in highway for token in ("trunk", "primary", "secondary")):
            reduction += 0.005
    elif intervention_code == "traffic_calming":
        if maxspeed and maxspeed <= 50:
            reduction += 0.03
        if any(token in highway for token in ("residential", "tertiary", "secondary", "primary")):
            reduction += 0.02
        if asset_type == "junction":
            reduction += 0.015

    return max(float(bounds["low"]), min(float(bounds["high"]), reduction))


def _scenario_uncertainty_note(
    *,
    scenario: dict[str, Any],
    linked_segment_count: int,
) -> str:
    asset_types = sorted({asset["asset_type"] for asset in scenario.get("target_assets", [])})
    if any(asset_type in {"signal", "crossing", "junction"} for asset_type in asset_types):
        return (
            "Benefit range is heuristic and depends on nearest-geometry linkage between node assets "
            f"and {linked_segment_count} published segment scores."
        )
    return (
        "Benefit range is heuristic and derived from published segment features without rerunning the model."
    )


def _scenario_evaluation(
    *,
    scenario: dict[str, Any],
    analyst_rows_by_score_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    segment_delta_rows: list[dict[str, Any]] = []
    baseline_total = 0.0
    counterfactual_total = 0.0
    low_counterfactual_total = 0.0
    high_counterfactual_total = 0.0
    linked_segment_ids: list[str] = []

    for asset in scenario.get("target_assets", []):
        asset_type = str(asset.get("asset_type"))
        asset_id = str(asset.get("asset_id"))
        asset_label = str(asset.get("asset_label"))
        asset_metadata = dict(asset.get("asset_metadata") or {})
        for segment_score_id in asset.get("linked_segment_score_ids", []):
            row = analyst_rows_by_score_id.get(str(segment_score_id))
            if row is None:
                continue
            baseline_prediction = _safe_float(row.get("predicted_crash_count"))
            reduction_fraction = _scenario_reduction_fraction(
                intervention_code=str(scenario["intervention_code"]),
                row=row,
                asset_type=asset_type,
                asset_metadata=asset_metadata,
            )
            lower_fraction = max(0.0, reduction_fraction - 0.04)
            upper_fraction = min(0.95, reduction_fraction + 0.04)
            baseline_total += baseline_prediction
            counterfactual_total += baseline_prediction * (1.0 - reduction_fraction)
            low_counterfactual_total += baseline_prediction * (1.0 - lower_fraction)
            high_counterfactual_total += baseline_prediction * (1.0 - upper_fraction)
            linked_segment_ids.append(str(segment_score_id))

            for template in next(
                record["feature_adjustments"]
                for record in _INTERVENTION_LIBRARY
                if record["intervention_code"] == scenario["intervention_code"]
            ):
                segment_delta_rows.append(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "intervention_code": scenario["intervention_code"],
                        "asset_type": asset_type,
                        "asset_id": asset_id,
                        "asset_label": asset_label,
                        "linked_segment_score_id": segment_score_id,
                        "linked_segment_id": row.get("segment_id"),
                        "linked_segment_label": _segment_label_from_row(row),
                        "predicted_crash_count_before": round(baseline_prediction, 6),
                        "expected_reduction_fraction": round(reduction_fraction, 6),
                        "predicted_crash_count_after": round(
                            baseline_prediction * (1.0 - reduction_fraction),
                            6,
                        ),
                        "feature_name": template["feature_name"],
                        "feature_value_before": _normalize_literal_text(row.get(template["feature_name"]))
                        or row.get(template["feature_name"]),
                        "feature_value_after": _adjustment_target_value(
                            intervention_code=scenario["intervention_code"],
                            row=row,
                            template=template,
                        ),
                    }
                )

    unique_linked_segment_ids = list(dict.fromkeys(linked_segment_ids))
    baseline_total = round(baseline_total, 6)
    counterfactual_total = round(counterfactual_total, 6)
    low_counterfactual_total = round(low_counterfactual_total, 6)
    high_counterfactual_total = round(high_counterfactual_total, 6)
    expected_reduction = round(baseline_total - counterfactual_total, 6)
    expected_relative_reduction = round(
        expected_reduction / baseline_total,
        6,
    ) if baseline_total > 0 else 0.0
    evaluation = {
        "scenario_id": scenario["scenario_id"],
        "title": scenario["title"],
        "intervention_code": scenario["intervention_code"],
        "target_context_key": scenario["target_context_key"],
        "target_context_label": scenario["target_context_label"],
        "target_asset_types": sorted({asset["asset_type"] for asset in scenario.get("target_assets", [])}),
        "target_asset_count": len(scenario.get("target_assets", [])),
        "linked_segment_count": len(unique_linked_segment_ids),
        "linked_segment_score_ids": unique_linked_segment_ids,
        "baseline_predicted_crash_total": baseline_total,
        "counterfactual_predicted_crash_total": counterfactual_total,
        "expected_crash_reduction": expected_reduction,
        "expected_relative_reduction": expected_relative_reduction,
        "expected_crash_reduction_low": round(baseline_total - low_counterfactual_total, 6),
        "expected_crash_reduction_high": round(baseline_total - high_counterfactual_total, 6),
        "assumptions": list(scenario.get("assumptions", [])),
        "uncertainty_note": _scenario_uncertainty_note(
            scenario=scenario,
            linked_segment_count=len(unique_linked_segment_ids),
        ),
        "affected_assets": [
            {
                "asset_type": asset["asset_type"],
                "asset_id": asset["asset_id"],
                "asset_label": asset["asset_label"],
                "linked_segment_score_ids": list(asset.get("linked_segment_score_ids", [])),
            }
            for asset in scenario.get("target_assets", [])
        ],
    }
    return evaluation, segment_delta_rows


def _rank_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        scenarios,
        key=lambda item: (
            -float(item["expected_crash_reduction"]),
            -float(item["expected_relative_reduction"]),
            -int(item["linked_segment_count"]),
            str(item["title"]),
        ),
    )
    for index, scenario in enumerate(ranked, start=1):
        scenario["scenario_rank"] = index
    return ranked


def _portfolio_evaluation(
    *,
    scenarios: list[dict[str, Any]],
    segment_delta_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_scenario_and_segment: dict[tuple[str, str], dict[str, Any]] = {}
    for row in segment_delta_rows:
        key = (str(row["scenario_id"]), str(row["linked_segment_score_id"]))
        current = by_scenario_and_segment.get(key)
        if current is None or float(row["expected_reduction_fraction"]) > float(current["expected_reduction_fraction"]):
            by_scenario_and_segment[key] = row

    scenario_lookup = {scenario["scenario_id"]: scenario for scenario in scenarios}
    portfolio_rows: list[dict[str, Any]] = []
    for size in (2, 3):
        for scenario_ids in itertools.combinations([scenario["scenario_id"] for scenario in scenarios], size):
            segment_effects: dict[str, dict[str, Any]] = {}
            total_assignments = 0
            for scenario_id in scenario_ids:
                for row in segment_delta_rows:
                    if row["scenario_id"] != scenario_id:
                        continue
                    total_assignments += 1
                    segment_score_id = str(row["linked_segment_score_id"])
                    segment_bucket = segment_effects.setdefault(
                        segment_score_id,
                        {
                            "baseline": float(row["predicted_crash_count_before"]),
                            "fractions": [],
                        },
                    )
                    segment_bucket["fractions"].append(float(row["expected_reduction_fraction"]))
            if not segment_effects:
                continue

            baseline_total = 0.0
            counterfactual_total = 0.0
            for bucket in segment_effects.values():
                baseline = float(bucket["baseline"])
                combined_multiplier = 1.0
                for fraction in bucket["fractions"]:
                    combined_multiplier *= max(0.0, 1.0 - fraction)
                baseline_total += baseline
                counterfactual_total += baseline * combined_multiplier
            expected_reduction = baseline_total - counterfactual_total
            overlap_segment_count = total_assignments - len(segment_effects)
            portfolio_rows.append(
                {
                    "portfolio_id": f"portfolio:{'__'.join(scenario_ids)}",
                    "scenario_ids": list(scenario_ids),
                    "scenario_titles": [scenario_lookup[scenario_id]["title"] for scenario_id in scenario_ids],
                    "scenario_count": len(scenario_ids),
                    "distinct_segment_count": len(segment_effects),
                    "overlap_segment_count": overlap_segment_count,
                    "baseline_predicted_crash_total": round(baseline_total, 6),
                    "counterfactual_predicted_crash_total": round(counterfactual_total, 6),
                    "expected_crash_reduction": round(expected_reduction, 6),
                    "expected_relative_reduction": round(
                        expected_reduction / baseline_total,
                        6,
                    ) if baseline_total > 0 else 0.0,
                    "portfolio_note": (
                        "Sequentially compounds scenario effects on overlapping segments."
                    ),
                }
            )

    ranked = sorted(
        portfolio_rows,
        key=lambda item: (
            -float(item["expected_crash_reduction"]),
            -float(item["expected_relative_reduction"]),
            int(item["overlap_segment_count"]),
            str(item["portfolio_id"]),
        ),
    )
    for index, row in enumerate(ranked, start=1):
        row["portfolio_rank"] = index
    return ranked[:5]


def _bundle_markdown(
    *,
    bundle: dict[str, Any],
) -> str:
    lines = [
        f"# {bundle['display_name']} Scenario Countermeasure Bundle",
        "",
        f"- Run label: `{bundle['prediction_run_label']}`",
        f"- Generated: `{bundle['generated_at_utc']}`",
        f"- Scenario count: `{len(bundle['scenario_rankings'])}`",
        f"- Portfolio count: `{len(bundle['portfolio_rankings'])}`",
        "",
        "## Top Scenarios",
        "",
    ]
    for scenario in bundle["scenario_rankings"][:5]:
        lines.append(
            f"1. **{scenario['title']}**. Expected crash reduction "
            f"`{scenario['expected_crash_reduction']}` over `{scenario['linked_segment_count']}` linked segments. "
            f"Range: `{scenario['expected_crash_reduction_low']} .. {scenario['expected_crash_reduction_high']}`."
        )
    if bundle["portfolio_rankings"]:
        lines.extend(["", "## Top Portfolios", ""])
        for portfolio in bundle["portfolio_rankings"][:5]:
            lines.append(
                f"1. **{'; '.join(portfolio['scenario_titles'])}**. Expected crash reduction "
                f"`{portfolio['expected_crash_reduction']}` across `{portfolio['distinct_segment_count']}` distinct segments."
            )
    lines.extend(
        [
            "",
            "## Planning Brief Handoff",
            "",
            f"- Recommended scenario: `{bundle['planning_brief_summary']['recommended_scenario']['title']}`",
            f"- Recommended portfolio: `{bundle['planning_brief_summary']['recommended_portfolio']['title']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _bundle_for_run(
    *,
    dashboard_summary_path: Path,
    run_record: dict[str, Any],
    shortlist_record: dict[str, Any] | None,
    signal_node_features: list[dict[str, Any]],
    node_object_features: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    segment_manifest_path = _resolve_reference_path(
        str(run_record["segment_scores"]["manifest_path"]),
        anchor_path=dashboard_summary_path,
    )
    segment_manifest = _load_json(segment_manifest_path)
    analyst_csv_path = _resolve_reference_path(
        str(segment_manifest["outputs"]["analyst_csv_path"]),
        anchor_path=segment_manifest_path,
    )
    public_geojson_path = _resolve_reference_path(
        str(segment_manifest["outputs"]["public_geojson_path"]),
        anchor_path=segment_manifest_path,
    )
    analyst_rows = _load_csv_rows(analyst_csv_path)
    analyst_rows_by_score_id = {
        str(row.get("segment_score_id")): row
        for row in analyst_rows
        if row.get("segment_score_id")
    }
    analyst_rows_by_segment_id = {
        str(row.get("segment_id")): row
        for row in analyst_rows
        if row.get("segment_id")
    }
    public_segment_features = _load_feature_collection(public_geojson_path)
    public_segment_by_score_id = _index_features_by_property(
        public_segment_features,
        property_name="segment_score_id",
    )
    assets = _prepare_default_assets(
        run_record=run_record,
        shortlist_record=shortlist_record,
        analyst_rows_by_score_id=analyst_rows_by_score_id,
        analyst_rows_by_segment_id=analyst_rows_by_segment_id,
        public_segment_by_score_id=public_segment_by_score_id,
        signal_node_features=signal_node_features,
        node_object_features=node_object_features,
    )
    spec = _build_scenario_spec(
        run_record=run_record,
        shortlist_record=shortlist_record,
        assets=assets,
    )

    scenario_rows: list[dict[str, Any]] = []
    segment_delta_rows: list[dict[str, Any]] = []
    for scenario in spec["scenarios"]:
        evaluation, delta_rows = _scenario_evaluation(
            scenario=scenario,
            analyst_rows_by_score_id=analyst_rows_by_score_id,
        )
        scenario_rows.append(evaluation)
        segment_delta_rows.extend(delta_rows)
    ranked_scenarios = _rank_scenarios(scenario_rows)
    ranked_portfolios = _portfolio_evaluation(
        scenarios=ranked_scenarios,
        segment_delta_rows=segment_delta_rows,
    )
    recommended_scenario = ranked_scenarios[0] if ranked_scenarios else {}
    recommended_portfolio = ranked_portfolios[0] if ranked_portfolios else {
        "title": "No multi-scenario portfolio available",
        "expected_crash_reduction": 0.0,
    }
    if recommended_portfolio and "title" not in recommended_portfolio:
        recommended_portfolio = dict(recommended_portfolio)
        recommended_portfolio["title"] = "; ".join(recommended_portfolio.get("scenario_titles", []))

    bundle = {
        "scenario_countermeasure_bundle_version": SCENARIO_COUNTERMEASURE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_dashboard_summary_path": str(dashboard_summary_path),
        "city_key": run_record["city_key"],
        "display_name": run_record["display_name"],
        "prediction_run_label": run_record["prediction_run_label"],
        "scenario_spec_version": spec["scenario_spec_version"],
        "intervention_library_version": INTERVENTION_LIBRARY_VERSION,
        "scenario_rankings": ranked_scenarios,
        "portfolio_rankings": ranked_portfolios,
        "planning_brief_summary": {
            "recommended_scenario": {
                "scenario_id": recommended_scenario.get("scenario_id"),
                "title": recommended_scenario.get("title"),
                "intervention_code": recommended_scenario.get("intervention_code"),
                "expected_crash_reduction": recommended_scenario.get("expected_crash_reduction"),
                "expected_relative_reduction": recommended_scenario.get("expected_relative_reduction"),
            },
            "recommended_portfolio": {
                "portfolio_id": recommended_portfolio.get("portfolio_id"),
                "title": recommended_portfolio.get("title"),
                "scenario_ids": recommended_portfolio.get("scenario_ids", []),
                "expected_crash_reduction": recommended_portfolio.get("expected_crash_reduction", 0.0),
                "expected_relative_reduction": recommended_portfolio.get("expected_relative_reduction", 0.0),
            },
        },
        "stats": {
            "scenario_count": len(ranked_scenarios),
            "portfolio_count": len(ranked_portfolios),
            "linked_segment_delta_rows": len(segment_delta_rows),
            "recommended_scenario_expected_reduction": recommended_scenario.get("expected_crash_reduction", 0.0),
            "recommended_portfolio_expected_reduction": recommended_portfolio.get(
                "expected_crash_reduction",
                0.0,
            ),
        },
    }
    return (
        spec,
        bundle,
        ranked_scenarios,
        ranked_portfolios,
        segment_delta_rows,
        [segment_manifest_path, analyst_csv_path, public_geojson_path],
    )


def build_scenario_countermeasure_bundle(
    *,
    dashboard_summary_path: str | Path = "data/dashboard/dashboard_summary.json",
    output_dir: str | Path = DEFAULT_SCENARIO_OUTPUT_DIR,
    prediction_run_labels: list[str] | None = None,
    signal_nodes_path: str | Path = DEFAULT_BARI_SIGNAL_NODES_PATH,
    node_objects_path: str | Path = DEFAULT_BARI_NODE_OBJECTS_PATH,
) -> dict[str, Any]:
    dashboard_summary_input = Path(dashboard_summary_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    signal_nodes_input = Path(signal_nodes_path)
    node_objects_input = Path(node_objects_path)
    signal_node_features = (
        _load_feature_collection(signal_nodes_input)
        if signal_nodes_input.exists()
        else []
    )
    node_object_features = (
        _load_feature_collection(node_objects_input)
        if node_objects_input.exists()
        else []
    )

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
        raise RuntimeError("No published runs matched the requested scenario-countermeasure filters.")

    shortlist_records = list(summary.get("intervention_shortlists", []))
    library_payload = {
        "intervention_library_version": INTERVENTION_LIBRARY_VERSION,
        "countermeasure_knowledge_version": COUNTERMEASURE_KNOWLEDGE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "interventions": list(_INTERVENTION_LIBRARY),
        "scenario_spec_schema": _SPEC_SCHEMA,
    }
    library_path = output_root / "intervention_library.json"
    library_path.write_text(json.dumps(library_payload, indent=2, sort_keys=True), encoding="utf-8")

    bundle_outputs: list[dict[str, Any]] = []
    for run_record in published_runs:
        prediction_run_label = str(run_record["prediction_run_label"])
        shortlist_record = _find_by_key(
            shortlist_records,
            "prediction_run_label",
            prediction_run_label,
        )
        run_output_dir = output_root / prediction_run_label
        run_output_dir.mkdir(parents=True, exist_ok=True)
        scenario_spec_path = run_output_dir / "scenario_spec.json"
        bundle_path = run_output_dir / "scenario_bundle.json"
        markdown_path = run_output_dir / "scenario_bundle.md"
        scenario_csv_path = run_output_dir / "scenario_rankings.csv"
        portfolio_csv_path = run_output_dir / "portfolio_rankings.csv"
        delta_csv_path = run_output_dir / "scenario_segment_deltas.csv"
        manifest_path = run_output_dir / "scenario_bundle.manifest.json"

        (
            scenario_spec,
            bundle,
            scenario_rows,
            portfolio_rows,
            segment_delta_rows,
            additional_inputs,
        ) = _bundle_for_run(
            dashboard_summary_path=dashboard_summary_input,
            run_record=run_record,
            shortlist_record=shortlist_record,
            signal_node_features=signal_node_features,
            node_object_features=node_object_features,
        )

        scenario_spec_path.write_text(json.dumps(scenario_spec, indent=2, sort_keys=True), encoding="utf-8")
        bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(_bundle_markdown(bundle=bundle), encoding="utf-8")
        _write_csv(scenario_csv_path, scenario_rows)
        _write_csv(portfolio_csv_path, portfolio_rows)
        _write_csv(delta_csv_path, segment_delta_rows)

        upstream_inputs = [
            _artifact_reference(
                "dashboard_summary_json",
                dashboard_summary_input,
                _sha256(dashboard_summary_input),
            ),
            _artifact_reference(
                "scenario_intervention_library",
                library_path,
                _sha256(library_path),
            ),
        ]
        for path in additional_inputs:
            upstream_inputs.append(
                _artifact_reference(
                    "published_scenario_input",
                    path,
                    _sha256(path),
                )
            )
        if str(run_record.get("city_key")) == "bari":
            for path in (signal_nodes_input, node_objects_input):
                if path.exists():
                    upstream_inputs.append(
                        _artifact_reference(
                            "node_asset_layer",
                            path,
                            _sha256(path),
                        )
                    )

        manifest = {
            "scenario_countermeasure_bundle_version": SCENARIO_COUNTERMEASURE_VERSION,
            "inputs": {
                "dashboard_summary_path": str(dashboard_summary_input),
                "dashboard_summary_sha256": _sha256(dashboard_summary_input),
                "prediction_run_label": prediction_run_label,
                "signal_nodes_path": str(signal_nodes_input) if signal_node_features else None,
                "node_objects_path": str(node_objects_input) if node_object_features else None,
            },
            "outputs": {
                "scenario_spec_path": str(scenario_spec_path),
                "scenario_spec_sha256": _sha256(scenario_spec_path),
                "scenario_bundle_path": str(bundle_path),
                "scenario_bundle_sha256": _sha256(bundle_path),
                "scenario_markdown_path": str(markdown_path),
                "scenario_markdown_sha256": _sha256(markdown_path),
                "scenario_rankings_csv_path": str(scenario_csv_path),
                "portfolio_rankings_csv_path": str(portfolio_csv_path),
                "scenario_segment_deltas_csv_path": str(delta_csv_path),
                "manifest_path": str(manifest_path),
            },
            "contract": {
                "resource_name": "scenario_countermeasure_bundle",
                "public_contract_version": SCENARIO_COUNTERMEASURE_CONTRACT_VERSION,
                "scenario_countermeasure_bundle_version": SCENARIO_COUNTERMEASURE_VERSION,
            },
            "stats": bundle["stats"],
            "lineage": _build_lineage_contract(
                run_record_path=manifest_path,
                upstream_inputs=upstream_inputs,
                publishable_outputs=[
                    _artifact_reference(
                        "scenario_spec_json",
                        scenario_spec_path,
                        _sha256(scenario_spec_path),
                    ),
                    _artifact_reference(
                        "scenario_bundle_json",
                        bundle_path,
                        _sha256(bundle_path),
                    ),
                    _artifact_reference(
                        "scenario_bundle_markdown",
                        markdown_path,
                        _sha256(markdown_path),
                    ),
                    _artifact_reference(
                        "scenario_rankings_csv",
                        scenario_csv_path,
                        _sha256(scenario_csv_path),
                    ),
                    _artifact_reference(
                        "portfolio_rankings_csv",
                        portfolio_csv_path,
                        _sha256(portfolio_csv_path),
                    ),
                ],
                supporting_outputs=[
                    _artifact_reference(
                        "scenario_segment_deltas_csv",
                        delta_csv_path,
                        _sha256(delta_csv_path),
                    ),
                ],
            ),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        bundle_outputs.append(
            {
                "city_key": run_record["city_key"],
                "display_name": run_record["display_name"],
                "prediction_run_label": prediction_run_label,
                "scenario_spec_path": str(scenario_spec_path),
                "scenario_bundle_path": str(bundle_path),
                "scenario_markdown_path": str(markdown_path),
                "manifest_path": str(manifest_path),
            }
        )

    index_payload = {
        "scenario_countermeasure_bundle_version": SCENARIO_COUNTERMEASURE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_dashboard_summary_path": str(dashboard_summary_input),
        "intervention_library_path": str(library_path),
        "scenario_bundles": sorted(bundle_outputs, key=lambda item: str(item["display_name"])),
        "stats": {
            "scenario_bundle_count": len(bundle_outputs),
            "library_intervention_count": len(_INTERVENTION_LIBRARY),
        },
    }
    index_path = output_root / "scenario_countermeasure_index.json"
    index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "scenario_countermeasure_bundle_version": SCENARIO_COUNTERMEASURE_VERSION,
        "intervention_library_path": str(library_path),
        "index_path": str(index_path),
        "scenario_bundle_count": len(bundle_outputs),
        "bundles": sorted(bundle_outputs, key=lambda item: str(item["display_name"])),
        "stats": index_payload["stats"],
    }
