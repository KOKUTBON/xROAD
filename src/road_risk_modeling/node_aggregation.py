"""Aggregate matched crash records into node-object-year tables."""

from __future__ import annotations

import hashlib
import json
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
        import pandas as pd  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and pandas are required for node aggregation. Install geospatial and ml extras with: "
            "python3 -m pip install -e '.[geospatial,ml]'"
        ) from exc
    return gpd, pd


NODE_BASE_COLUMNS = [
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


def aggregate_node_year_metrics(
    matched_path: str | Path,
    node_objects_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    gpd, pd = _load_geo_stack()

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    matched_input = Path(matched_path)
    nodes_input = Path(node_objects_path)
    csv_path = output_root / "node_year_metrics.csv"
    geojson_path = output_root / "node_year_metrics.geojson"
    manifest_path = output_root / "node_year_metrics.manifest.json"

    rows: list[dict[str, Any]] = []
    with matched_input.open("r", encoding="utf-8") as handle:
        for line in handle:
            rows.append(json.loads(line))

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError(f"No matched node records found in: {matched_input}")

    required_columns = {"node_object_id", "occurred_year"}
    missing = required_columns - set(frame.columns)
    if missing:
        raise RuntimeError(f"Matched node records are missing required columns: {sorted(missing)}")

    frame["fatal_crash_count"] = (frame["severity_level"] == "fatal").astype(int)
    frame["injury_crash_count"] = (frame["severity_level"] == "injury").astype(int)
    frame["fatalities"] = pd.to_numeric(frame["fatalities"], errors="coerce").fillna(0).astype(int)
    frame["injuries"] = pd.to_numeric(frame["injuries"], errors="coerce").fillna(0).astype(int)
    frame["node_match_distance_m"] = pd.to_numeric(frame["node_match_distance_m"], errors="coerce")

    grouped = (
        frame.groupby(["node_object_id", "occurred_year"], as_index=False)
        .agg(
            crash_count=("crash_id", "size"),
            fatal_crash_count=("fatal_crash_count", "sum"),
            injury_crash_count=("injury_crash_count", "sum"),
            fatalities_total=("fatalities", "sum"),
            injuries_total=("injuries", "sum"),
            mean_node_match_distance_m=("node_match_distance_m", "mean"),
        )
    )

    nodes = gpd.read_file(nodes_input)
    required_node_columns = {"node_object_id", "geometry"}
    node_missing = required_node_columns - set(nodes.columns)
    if node_missing:
        raise RuntimeError(f"Node-object file is missing required columns: {sorted(node_missing)}")

    base_columns = ["node_object_id", "geometry"] + [
        column for column in NODE_BASE_COLUMNS if column in nodes.columns and column != "node_object_id"
    ]
    base_nodes = nodes[base_columns].copy()

    observed_years = sorted(int(value) for value in grouped["occurred_year"].dropna().unique())
    combinations = pd.MultiIndex.from_product(
        [base_nodes["node_object_id"].astype(str), observed_years],
        names=["node_object_id", "occurred_year"],
    ).to_frame(index=False)

    model_frame = combinations.merge(grouped, on=["node_object_id", "occurred_year"], how="left")
    for column in [
        "crash_count",
        "fatal_crash_count",
        "injury_crash_count",
        "fatalities_total",
        "injuries_total",
    ]:
        model_frame[column] = model_frame[column].fillna(0).astype(int)
    model_frame["mean_node_match_distance_m"] = model_frame["mean_node_match_distance_m"].fillna(0.0)
    model_frame = model_frame.merge(base_nodes, on="node_object_id", how="left")

    metric_gdf = gpd.GeoDataFrame(model_frame, geometry="geometry", crs=nodes.crs)
    metric_gdf.to_file(geojson_path, driver="GeoJSON")
    metric_gdf.drop(columns=["geometry"]).to_csv(csv_path, index=False)

    manifest = {
        "inputs": {
            "matched_path": str(matched_input),
            "matched_sha256": _sha256(matched_input),
            "node_objects_path": str(nodes_input),
            "node_objects_sha256": _sha256(nodes_input),
        },
        "outputs": {
            "csv_path": str(csv_path),
            "csv_sha256": _sha256(csv_path),
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "observed_years": observed_years,
            "node_object_count": int(base_nodes["node_object_id"].nunique()),
            "node_year_rows": int(len(model_frame)),
            "node_year_rows_with_crashes": int((model_frame["crash_count"] > 0).sum()),
            "node_year_rows_without_crashes": int((model_frame["crash_count"] == 0).sum()),
            "total_crashes": int(model_frame["crash_count"].sum()),
            "total_fatalities": int(model_frame["fatalities_total"].sum()),
            "total_injuries": int(model_frame["injuries_total"].sum()),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
