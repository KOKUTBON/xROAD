"""Match canonical crash points to node-like road objects."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_geo_stack() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        from shapely.geometry import Point  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and Shapely are required for node matching. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, Point


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) else value
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            return _json_safe_value(value.item())
        except Exception:  # nosec B110 # optional conversion/geometry fallback continues below
            pass
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        try:
            return _json_safe_value(value.tolist())
        except Exception:  # nosec B110 # optional conversion/geometry fallback continues below
            pass
    if isinstance(value, (list, tuple, set)):
        normalized = [_json_safe_value(item) for item in value]
        scalar_items = [item for item in normalized if item not in {None, ""}]
        if all(not isinstance(item, (list, dict)) for item in scalar_items):
            return " | ".join(str(item) for item in scalar_items) or None
        return normalized
    return value


NODE_JOIN_COLUMNS = [
    "node_object_id",
    "junction_id",
    "source_system",
    "object_type",
    "node_role",
    "zone_type",
    "parent_object_id",
    "parent_object_type",
    "name",
    "signal_type",
    "crossing_type",
    "crossing_markings",
    "crossing_signals",
    "movement_family",
    "control_state",
    "crossing_protection_state",
    "turn_path_class",
    "movement_arm_count",
    "priority_rule",
    "control_detail",
    "approach_node_ref",
    "approach_arm_id",
    "approach_bearing_deg",
    "approach_compass",
    "connected_arm_count",
    "arm_compass_catalog",
    "turn_option_catalog",
    "turn_option_count",
    "maneuver_complexity",
    "roundabout_component_role",
    "movement_role",
    "movement_turn",
    "movement_resolution_state",
    "movement_resolution_method",
    "movement_target_rank",
    "movement_target_score",
    "movement_target_heading_delta_deg",
    "movement_target_continuity_flags",
    "signal_priority_variant",
    "phase_priority_group",
    "movement_source_zone_id",
    "movement_source_zone_type",
    "movement_source_parent_object_id",
    "incoming_arm_id",
    "incoming_bearing_deg",
    "incoming_compass",
    "outgoing_arm_id",
    "outgoing_bearing_deg",
    "outgoing_compass",
    "candidate_target_arm_count",
    "candidate_target_arm_catalog",
    "junction_phase_provider_available",
    "junction_phase_provider_record_count",
    "junction_phase_provider_profiles",
    "junction_phase_control_modes",
    "junction_phase_latest_end_utc",
    "movement_phase_mapping_available",
    "movement_phase_mapping_count",
    "movement_phase_id_catalog",
    "movement_stage_id_catalog",
    "movement_protection_state_catalog",
    "movement_pedestrian_stage_flag",
    "movement_phase_join_resolution",
    "movement_phase_provider_record_count",
    "movement_phase_source_profiles",
    "movement_phase_control_modes",
    "movement_phase_latest_end_utc",
    "movement_phase_timing_available",
    "movement_phase_cycle_length_s_mean",
    "movement_phase_green_s_mean",
    "movement_phase_amber_s_mean",
    "movement_phase_all_red_s_mean",
    "movement_phase_pedestrian_walk_s_mean",
    "movement_phase_pedestrian_clearance_s_mean",
    "segment_id",
    "segment_highway",
    "segment_name",
    "segment_ref",
    "segment_junction",
    "nearest_segment_distance_m",
    "signal_distance_m",
    "approach_distance_m",
    "approach_endpoint_role",
    "source_record_id",
    "zone_radius_m",
    "zone_length_m",
    "zone_width_m",
    "network_node_ref",
    "incident_edge_count",
    "major_edge_count",
    "roundabout_edge_count",
]


def match_canonical_records_to_node_objects(
    records_path: str | Path,
    node_objects_path: str | Path,
    output_dir: str | Path,
    *,
    max_distance_m: float = 35.0,
) -> dict[str, Any]:
    gpd, Point = _load_geo_stack()

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    records_input_path = Path(records_path)
    node_objects_input_path = Path(node_objects_path)
    matched_path = output_root / "matched_node_records.jsonl"
    unmatched_path = output_root / "unmatched_node_records.jsonl"
    manifest_path = output_root / "matched_node_records.manifest.json"

    nodes = gpd.read_file(node_objects_input_path)
    if "node_object_id" not in nodes.columns:
        raise RuntimeError(
            f"Node-object file does not contain required 'node_object_id' column: {node_objects_input_path}"
        )
    join_columns = [column for column in NODE_JOIN_COLUMNS if column in nodes.columns]
    if "node_object_id" not in join_columns:
        join_columns = ["node_object_id", *join_columns]

    records: list[dict[str, Any]] = []
    with records_input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            records.append(json.loads(line))

    point_records = [
        record
        for record in records
        if record.get("latitude") is not None and record.get("longitude") is not None
    ]
    for index, record in enumerate(point_records):
        record["_match_row_id"] = index
    points = gpd.GeoDataFrame(
        point_records,
        geometry=[
            Point(float(record["longitude"]), float(record["latitude"]))
            for record in point_records
        ],
        crs="EPSG:4326",
    )

    local_crs = nodes.estimate_utm_crs() or "EPSG:3857"
    projected_nodes = nodes.to_crs(local_crs)
    projected_points = points.to_crs(local_crs)

    joined = gpd.sjoin_nearest(
        projected_points,
        projected_nodes[join_columns + ["geometry"]],
        how="left",
        distance_col="node_match_distance_m",
    )
    joined = joined.sort_values(by=["_match_row_id", "node_match_distance_m", "node_object_id"], kind="stable")
    joined = joined.drop_duplicates(subset="_match_row_id", keep="first")

    matched_count = 0
    unmatched_count = 0

    with (
        matched_path.open("w", encoding="utf-8") as matched_handle,
        unmatched_path.open("w", encoding="utf-8") as unmatched_handle,
    ):
        for _, row in joined.iterrows():
            record = {
                key: _json_safe_value(value)
                for key, value in row.drop(labels=["geometry"]).items()
                if key not in {"index_right", "_match_row_id"}
            }
            distance = row.get("node_match_distance_m")
            node_object_id = row.get("node_object_id")
            if node_object_id is not None and distance is not None and float(distance) <= max_distance_m:
                record["node_object_id"] = str(node_object_id)
                record["junction_id"] = str(row.get("junction_id")) if row.get("junction_id") is not None else None
                record["node_match_distance_m"] = float(distance)
                matched_handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
                matched_count += 1
            else:
                record["node_match_distance_m"] = float(distance) if distance is not None else None
                unmatched_handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
                unmatched_count += 1

    manifest = {
        "inputs": {
            "records_path": str(records_input_path),
            "records_sha256": _sha256(records_input_path),
            "node_objects_path": str(node_objects_input_path),
            "node_objects_sha256": _sha256(node_objects_input_path),
        },
        "outputs": {
            "matched_path": str(matched_path),
            "matched_sha256": _sha256(matched_path),
            "unmatched_path": str(unmatched_path),
            "unmatched_sha256": _sha256(unmatched_path),
            "manifest_path": str(manifest_path),
        },
        "policy": {
            "max_distance_m": max_distance_m,
        },
        "stats": {
            "input_records_with_coordinates": len(point_records),
            "matched_records": matched_count,
            "unmatched_records": unmatched_count,
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
