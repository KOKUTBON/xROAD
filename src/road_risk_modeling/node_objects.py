"""Build node-like road objects such as signals, crossings, junctions, and roundabouts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


DEFAULT_BARI_SIGNAL_SOURCE = {
    "label": "bari_semafori",
    "url": (
        "https://opendata.comune.bari.it/dataset/9a56ef55-abea-42ab-b208-fc8afb85dbcd/"
        "resource/1b76f2d0-4a6c-4e8a-b31d-d006fbd42f7e/download/_ivop_semafori__202501150954.csv"
    ),
}

MAJOR_HIGHWAY_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = " ".join(str(value).replace("\ufeff", "").strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _normalize_tag_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        parts = [_clean_text(item) for item in value]
        normalized_parts = [part for part in parts if part]
        return " | ".join(normalized_parts) or None
    text = _clean_text(value)
    if not text:
        return None
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return None
        parts = [_clean_text(part.strip("'\" ")) for part in inner.split(",")]
        normalized_parts = [part for part in parts if part]
        return " | ".join(normalized_parts) or None
    return text


def _parse_float(value: Any) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    normalized = text.replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    numeric = _parse_float(value)
    if numeric is None:
        return None
    return int(numeric)


def _is_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"}


def _read_remote_bytes(url: str) -> bytes:
    if not _is_url(url):
        raise ValueError("Remote sources must use HTTP or HTTPS.")
    with urlopen(url, timeout=60) as response:  # nosec B310 # scheme checked above
        return response.read()


def _load_source_bytes(source: str | Path) -> tuple[str, bytes]:
    source_text = str(source)
    if _is_url(source_text):
        return source_text, _read_remote_bytes(source_text)
    path = Path(source_text)
    return str(path), path.read_bytes()


def _load_geo_stack() -> tuple[Any, Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import pandas as pd  # type: ignore
        from shapely.geometry import Point  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas, pandas, and Shapely are required for node-object building. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, pd, Point


def _load_osm_stack() -> Any:
    try:
        import osmnx as ox  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "OSMnx is required for crossing extraction. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return ox


def _normalize_signal_type(value: str | None) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    return text.rstrip(".")


def _highway_classes(value: Any) -> list[str]:
    text = _normalize_tag_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def _zone_half_width_for_highway(segment_highway: Any, default_half_width_m: float) -> float:
    classes = set(_highway_classes(segment_highway))
    base = float(default_half_width_m)
    if {"motorway", "trunk"} & classes:
        return max(base, 9.0)
    if {"primary", "secondary"} & classes:
        return max(base, 7.0)
    if "tertiary" in classes:
        return max(base, 6.0)
    return base


def _lower_text(value: Any) -> str:
    text = _clean_text(value)
    return text.lower() if text else ""


def _classify_crossing_protection_state(
    *,
    signal_type: Any,
    crossing_type: Any,
    crossing_signals: Any,
    crossing_markings: Any,
) -> str:
    crossing_type_text = _lower_text(crossing_type)
    signal_text = _lower_text(crossing_signals)
    markings_text = _lower_text(crossing_markings)
    if (
        _clean_text(signal_type)
        or crossing_type_text in {"traffic_signals", "signals", "signalised", "signalized"}
        or signal_text in {"yes", "traffic_signals", "signalised", "signalized"}
    ):
        return "signalized"
    if markings_text and markings_text not in {"no", "none", "unmarked", "unknown"}:
        return "marked_unsignalized"
    return "uncontrolled"


def _crossing_priority_rule(crossing_protection_state: str) -> str:
    if crossing_protection_state == "signalized":
        return "controlled"
    if crossing_protection_state == "marked_unsignalized":
        return "pedestrian_priority_possible"
    return "driver_priority_or_ambiguous"


def _bearing_degrees(from_coord: tuple[float, float], to_coord: tuple[float, float]) -> float | None:
    dx = float(to_coord[0]) - float(from_coord[0])
    dy = float(to_coord[1]) - float(from_coord[1])
    if math.isclose(dx, 0.0) and math.isclose(dy, 0.0):
        return None
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _compass_from_bearing(bearing_deg: float | None) -> str | None:
    if bearing_deg is None:
        return None
    labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = int(((bearing_deg + 22.5) % 360.0) / 45.0)
    return labels[index]


def _classify_turn_direction(inbound_bearing_deg: float, outbound_bearing_deg: float) -> str:
    delta = (outbound_bearing_deg - inbound_bearing_deg + 360.0) % 360.0
    if delta < 45.0 or delta >= 315.0:
        return "straight"
    if delta < 150.0:
        return "right"
    if delta < 210.0:
        return "u_turn"
    return "left"


def _format_turn_catalog(turn_options: set[str]) -> str | None:
    if not turn_options:
        return None
    order = {"left": 0, "straight": 1, "right": 2, "u_turn": 3}
    return " | ".join(sorted(turn_options, key=lambda value: order.get(value, 99)))


def _classify_maneuver_complexity(turn_options: set[str], connected_arm_count: int | None) -> str:
    if not turn_options:
        return "single_path" if (connected_arm_count or 0) <= 1 else "ambiguous"
    if len(turn_options) == 1:
        return "single_choice"
    if len(turn_options) == 2:
        return "limited_choice"
    return "multi_choice"


def _split_turn_option_catalog(value: Any) -> list[str]:
    text = _normalize_tag_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def _sanitize_token(value: Any) -> str:
    text = _clean_text(value) or "unknown"
    return "".join(char if char.isalnum() else "_" for char in text).strip("_") or "unknown"


def _offset_point_by_bearing(Point: Any, origin: Any, bearing_deg: float | None, distance_m: float) -> Any:
    if bearing_deg is None or origin is None or origin.is_empty:
        return origin
    radians = math.radians(float(bearing_deg))
    dx = float(distance_m) * math.sin(radians)
    dy = float(distance_m) * math.cos(radians)
    return Point(origin.x + dx, origin.y + dy)


def _movement_heading_from_turn(source_bearing_deg: float | None, turn_label: str) -> float | None:
    if source_bearing_deg is None:
        return None
    outbound = float(source_bearing_deg)
    inbound = (outbound + 180.0) % 360.0
    if turn_label == "straight":
        return inbound
    if turn_label == "left":
        return (inbound - 90.0) % 360.0
    if turn_label == "right":
        return (inbound + 90.0) % 360.0
    if turn_label == "u_turn":
        return outbound
    if turn_label == "cross":
        return None
    if turn_label == "circulate":
        return outbound
    return inbound


def _target_arm_label(candidate: dict[str, Any]) -> str:
    endpoint_id = _clean_text(candidate.get("endpoint_id")) or "unknown"
    compass = _clean_text(candidate.get("endpoint_compass"))
    return f"{endpoint_id}@{compass}" if compass else endpoint_id


def _value_part_set(value: Any) -> set[str]:
    text = _normalize_tag_text(value)
    if not text:
        return set()
    return {part.strip().lower() for part in text.split("|") if part.strip()}


def _angular_distance_deg(a_deg: float | None, b_deg: float | None) -> float | None:
    if a_deg is None or b_deg is None:
        return None
    return abs((float(a_deg) - float(b_deg) + 180.0) % 360.0 - 180.0)


def _score_target_candidate(
    *,
    candidate: dict[str, Any],
    source_segment_highway: Any,
    source_segment_name: Any,
    source_segment_ref: Any,
    source_bearing_deg: float | None,
    turn_label: str,
) -> dict[str, Any]:
    ideal_heading = _movement_heading_from_turn(source_bearing_deg, turn_label)
    candidate_bearing = candidate.get("endpoint_bearing_deg")
    heading_delta_deg = _angular_distance_deg(
        float(candidate_bearing) if candidate_bearing is not None else None,
        ideal_heading,
    )
    score = -float(heading_delta_deg if heading_delta_deg is not None else 180.0)
    continuity_flags: list[str] = []

    shared_ref = _value_part_set(source_segment_ref) & _value_part_set(candidate.get("segment_ref"))
    if shared_ref:
        score += 60.0
        continuity_flags.append("shared_ref")

    shared_name = _value_part_set(source_segment_name) & _value_part_set(candidate.get("segment_name"))
    if shared_name:
        score += 35.0
        continuity_flags.append("shared_name")

    shared_highway = _value_part_set(source_segment_highway) & _value_part_set(candidate.get("segment_highway"))
    if shared_highway:
        score += 12.0 if turn_label in {"straight", "u_turn"} else 6.0
        continuity_flags.append("shared_highway")

    ranked_candidate = dict(candidate)
    ranked_candidate["movement_target_score"] = round(float(score), 3)
    ranked_candidate["movement_target_heading_delta_deg"] = (
        round(float(heading_delta_deg), 3) if heading_delta_deg is not None else None
    )
    ranked_candidate["movement_target_continuity_flags"] = " | ".join(continuity_flags) or None
    return ranked_candidate


def _rank_target_candidates_for_turn(
    *,
    target_candidates: list[dict[str, Any]],
    source_segment_highway: Any,
    source_segment_name: Any,
    source_segment_ref: Any,
    source_bearing_deg: float | None,
    turn_label: str,
) -> list[dict[str, Any]]:
    ranked = [
        _score_target_candidate(
            candidate=candidate,
            source_segment_highway=source_segment_highway,
            source_segment_name=source_segment_name,
            source_segment_ref=source_segment_ref,
            source_bearing_deg=source_bearing_deg,
            turn_label=turn_label,
        )
        for candidate in target_candidates
    ]
    ranked.sort(
        key=lambda candidate: (
            -float(candidate.get("movement_target_score") or -999.0),
            float(candidate.get("movement_target_heading_delta_deg") or 999.0),
            _clean_text(candidate.get("endpoint_id")) or "",
        )
    )
    for rank, candidate in enumerate(ranked, start=1):
        candidate["movement_target_rank"] = rank
    return ranked


def _resolve_ranked_target_candidates(
    ranked_candidates: list[dict[str, Any]],
    *,
    max_heading_delta_deg: float,
    min_score_gap: float,
) -> tuple[list[dict[str, Any]], str, str]:
    if not ranked_candidates:
        return [], "turn_only_fallback", "turn_heading_fallback"
    if len(ranked_candidates) == 1:
        return ranked_candidates, "explicit_target", "single_candidate_turn_match"

    best = ranked_candidates[0]
    second = ranked_candidates[1]
    best_heading_delta = best.get("movement_target_heading_delta_deg")
    best_score = float(best.get("movement_target_score") or 0.0)
    second_score = float(second.get("movement_target_score") or 0.0)
    strong_heading = best_heading_delta is not None and float(best_heading_delta) <= float(max_heading_delta_deg)
    score_gap = best_score - second_score

    if strong_heading and score_gap >= float(min_score_gap):
        return [best], "heuristic_target_resolution", "bearing_and_continuity_rank"
    return ranked_candidates, "ambiguous_target_variant", "bearing_and_continuity_unresolved"


def _signal_priority_variant(
    *,
    movement_role: str,
    crossing_protection_state: Any = None,
    priority_rule: Any = None,
) -> str:
    if movement_role == "pedestrian_crossing":
        state = _clean_text(crossing_protection_state) or "unknown"
        return f"pedestrian_{state}"
    if movement_role == "signalized_turn_movement":
        return "signal_phase_unknown"
    if movement_role == "roundabout_entry_movement":
        return "yield_entry"
    if movement_role == "roundabout_circulatory_movement":
        return "circulating_priority"
    return _clean_text(priority_rule) or "priority_unknown"


def _phase_priority_group(
    *,
    movement_role: str,
    movement_turn: str,
    crossing_protection_state: Any = None,
    priority_rule: Any = None,
) -> str:
    if movement_role == "pedestrian_crossing":
        state = _clean_text(crossing_protection_state) or "unknown"
        if state == "signalized":
            return "signalized_pedestrian_stage"
        if state == "marked_unsignalized":
            return "marked_crossing_priority"
        return "uncontrolled_crossing_gap_acceptance"
    if movement_role == "signalized_turn_movement":
        if movement_turn in {"left", "u_turn"}:
            return "signalized_crossing_turn_phase_unknown"
        return "signalized_aligned_turn_phase_unknown"
    if movement_role == "roundabout_entry_movement":
        return "roundabout_yield_entry"
    if movement_role == "roundabout_circulatory_movement":
        return "roundabout_circulatory_priority"
    rule = _clean_text(priority_rule) or "priority_unknown"
    if movement_turn in {"left", "u_turn"}:
        return f"{rule}_crossing_turn"
    return f"{rule}_aligned_turn"


def _candidate_targets_for_turn(
    *,
    connected_group: Any,
    source_endpoint_id: str,
    source_bearing_deg: float | None,
    turn_label: str,
) -> list[dict[str, Any]]:
    if connected_group is None or connected_group.empty or source_bearing_deg is None:
        return []
    inbound_bearing = (float(source_bearing_deg) + 180.0) % 360.0
    targets: list[dict[str, Any]] = []
    for _, candidate in connected_group.iterrows():
        candidate_endpoint_id = _clean_text(candidate.get("endpoint_id"))
        if candidate_endpoint_id == source_endpoint_id:
            continue
        candidate_bearing = candidate.get("endpoint_bearing_deg")
        if candidate_bearing is None:
            continue
        candidate_turn = _classify_turn_direction(inbound_bearing, float(candidate_bearing))
        if candidate_turn != turn_label:
            continue
        targets.append(dict(candidate))
    return targets


def _geometry_as_linestring(geometry: Any) -> Any:
    if geometry is None or geometry.is_empty:
        return geometry
    if geometry.geom_type == "MultiLineString":
        return max(geometry.geoms, key=lambda item: item.length)
    return geometry


def _projected_snap_to_segments(node_gdf: Any, segments: Any) -> tuple[Any, int, float | None]:
    if "segment_id" not in segments.columns:
        raise RuntimeError("Segments file does not contain required 'segment_id' column.")
    local_crs = segments.estimate_utm_crs() or "EPSG:3857"
    projected_nodes = node_gdf.to_crs(local_crs)
    projected_segments = segments.to_crs(local_crs)
    segment_columns = [
        column
        for column in ["segment_id", "highway", "ref", "junction", "name"]
        if column in projected_segments.columns
    ]
    joined = projected_nodes.sjoin_nearest(
        projected_segments[segment_columns + ["geometry"]],
        how="left",
        distance_col="nearest_segment_distance_m",
    ).to_crs(node_gdf.crs)
    joined = joined.drop(columns=["index_right"], errors="ignore")
    joined = joined.sort_values(
        by=["node_object_id", "nearest_segment_distance_m", "segment_id"],
        kind="stable",
    ).drop_duplicates(subset="node_object_id", keep="first")
    snapped_mask = joined["segment_id"].notna()
    snapped_count = int(snapped_mask.sum())
    mean_distance = None
    if snapped_count:
        mean_distance = float(joined.loc[snapped_mask, "nearest_segment_distance_m"].astype(float).mean())
    return joined, snapped_count, mean_distance


def _format_output_manifest(
    *,
    manifest_path: Path,
    source: dict[str, Any],
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Any]:
    manifest = {
        "source": source,
        "inputs": inputs,
        "outputs": outputs,
        "stats": stats,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _empty_geodataframe(gpd: Any, crs: Any) -> Any:
    return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=crs)


def build_bari_signal_nodes(
    output_dir: str | Path,
    *,
    segments_path: str | Path | None = None,
    source_url: str | Path | None = None,
    raw_dir: str | Path | None = "data/raw/bari_signal_nodes",
) -> dict[str, Any]:
    gpd, _pd, Point = _load_geo_stack()

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    source = dict(DEFAULT_BARI_SIGNAL_SOURCE)
    if source_url is not None:
        source["url"] = str(source_url)

    resolved_source, source_bytes = _load_source_bytes(source["url"])
    raw_root = Path(raw_dir) if raw_dir is not None else None
    raw_path = None
    if raw_root is not None:
        raw_root.mkdir(parents=True, exist_ok=True)
        raw_path = raw_root / f"{source['label']}.csv"
        raw_path.write_bytes(source_bytes)

    text = source_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    rows = list(reader)

    features: list[dict[str, Any]] = []
    signal_type_counts: dict[str, int] = {}
    coordinate_complete_count = 0
    for row in rows:
        latitude = _parse_float(row.get("LATITUDINE"))
        longitude = _parse_float(row.get("LONGITUDINE"))
        if latitude is None or longitude is None:
            continue
        coordinate_complete_count += 1
        signal_type = _normalize_signal_type(row.get("TIPO"))
        signal_type_counts[signal_type or "unknown"] = signal_type_counts.get(signal_type or "unknown", 0) + 1
        object_id = f"it-bari-signal-{_clean_text(row.get('id')) or len(features) + 1}"
        features.append(
            {
                "node_object_id": object_id,
                "junction_id": object_id,
                "source_system": "bari_open_data_semafori",
                "object_type": "traffic_signal",
                "node_role": "signalized_junction",
                "municipality_label": "bari",
                "country_code": "IT",
                "region_code": "PUGLIA",
                "province_code": "072",
                "city_code": "006",
                "city_name": "Bari",
                "source_record_id": _clean_text(row.get("id")),
                "name": _clean_text(row.get("name")),
                "signal_type": signal_type,
                "source_description": _clean_text(row.get("description")),
                "asset_code": _clean_text(row.get("Codice")),
                "latitude": latitude,
                "longitude": longitude,
                "geometry": Point(longitude, latitude),
            }
        )

    if not features:
        raise RuntimeError("No coordinate-complete signal rows were found in the Bari Semafori source.")

    node_gdf = gpd.GeoDataFrame(features, geometry="geometry", crs="EPSG:4326")

    snapped_node_count = 0
    mean_nearest_segment_distance_m = None
    if segments_path is not None:
        segments = gpd.read_file(segments_path)
        node_gdf, snapped_node_count, mean_nearest_segment_distance_m = _projected_snap_to_segments(node_gdf, segments)

    geojson_path = output_root / "traffic_signal_nodes.geojson"
    manifest_path = output_root / "traffic_signal_nodes.manifest.json"
    node_gdf.to_file(geojson_path, driver="GeoJSON")

    return _format_output_manifest(
        manifest_path=manifest_path,
        source={
            "adapter": "bari_open_data_semafori",
            "label": source["label"],
            "source_url": str(source["url"]),
            "resolved_source": resolved_source,
            "raw_path": str(raw_path) if raw_path else None,
            "raw_sha256": _sha256(raw_path) if raw_path else None,
        },
        inputs={
            "segments_path": str(segments_path) if segments_path else None,
            "segments_sha256": _sha256(Path(segments_path)) if segments_path else None,
        },
        outputs={
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "manifest_path": str(manifest_path),
        },
        stats={
            "raw_row_count": len(rows),
            "coordinate_complete_count": coordinate_complete_count,
            "node_object_count": int(len(node_gdf)),
            "snapped_node_count": snapped_node_count,
            "mean_nearest_segment_distance_m": mean_nearest_segment_distance_m,
            "signal_type_counts": dict(sorted(signal_type_counts.items())),
        },
    )


def _build_segment_endpoint_points(projected_segments: Any, Point: Any) -> tuple[Any, dict[str, Any]]:
    endpoint_records: list[dict[str, Any]] = []
    segment_geometry_by_id: dict[str, Any] = {}
    for _, row in projected_segments.iterrows():
        segment_id = str(row.get("segment_id"))
        geometry = _geometry_as_linestring(row.geometry)
        if geometry is None or geometry.is_empty:
            continue
        coords = list(geometry.coords)
        if len(coords) < 2:
            continue
        segment_geometry_by_id[segment_id] = geometry
        segment_name = _normalize_tag_text(row.get("name"))
        segment_highway = _normalize_tag_text(row.get("highway"))
        segment_ref = _normalize_tag_text(row.get("ref"))
        segment_junction = _normalize_tag_text(row.get("junction"))
        for endpoint_role, node_ref, coord in (
            ("start", row.get("u"), coords[0]),
            ("end", row.get("v"), coords[-1]),
        ):
            if endpoint_role == "start":
                bearing_deg = _bearing_degrees(coords[0], coords[1])
            else:
                bearing_deg = _bearing_degrees(coords[-1], coords[-2])
            endpoint_records.append(
                {
                    "endpoint_id": f"{segment_id}:{endpoint_role}",
                    "endpoint_role": endpoint_role,
                    "endpoint_node_ref": str(node_ref) if node_ref is not None else None,
                    "segment_id": segment_id,
                    "segment_length_m": float(row.get("segment_length_m") or geometry.length),
                    "segment_highway": segment_highway,
                    "segment_name": segment_name,
                    "segment_ref": segment_ref,
                    "segment_junction": segment_junction,
                    "endpoint_bearing_deg": bearing_deg,
                    "endpoint_compass": _compass_from_bearing(bearing_deg),
                    "geometry": Point(coord),
                }
            )
    endpoint_gdf = projected_segments.__class__(endpoint_records, geometry="geometry", crs=projected_segments.crs)
    return endpoint_gdf, segment_geometry_by_id


def _interpolate_approach_point(segment_geometry: Any, endpoint_role: str, approach_distance_m: float) -> tuple[Any, float]:
    geometry = _geometry_as_linestring(segment_geometry)
    if geometry is None or geometry.is_empty:
        return geometry, 0.0
    segment_length = float(geometry.length)
    if segment_length <= 0:
        return geometry.interpolate(0), 0.0
    effective_distance = min(float(approach_distance_m), segment_length / 2.0)
    if endpoint_role == "start":
        point = geometry.interpolate(effective_distance)
    else:
        point = geometry.interpolate(max(segment_length - effective_distance, 0.0))
    return point, effective_distance


def _build_endpoint_conflict_line(segment_geometry: Any, endpoint_role: str, zone_length_m: float) -> tuple[Any, float]:
    from shapely.geometry import LineString  # type: ignore

    geometry = _geometry_as_linestring(segment_geometry)
    if geometry is None or geometry.is_empty:
        return geometry, 0.0
    coords = list(geometry.coords)
    if len(coords) < 2:
        return geometry, 0.0
    endpoint = coords[0] if endpoint_role == "start" else coords[-1]
    zone_point, effective_length = _interpolate_approach_point(geometry, endpoint_role, zone_length_m)
    if zone_point is None or zone_point.is_empty:
        return geometry, 0.0
    return LineString([endpoint, zone_point.coords[0]]), effective_length


def _derive_turn_context(
    *,
    endpoint_groups: dict[str, Any],
    endpoint_lookup: dict[str, dict[str, Any]],
    segment_id: str | None = None,
    endpoint_role: str | None = None,
    network_node_ref: str | None = None,
) -> dict[str, Any]:
    endpoint_id = f"{segment_id}:{endpoint_role}" if segment_id and endpoint_role else None
    endpoint_record = endpoint_lookup.get(endpoint_id) if endpoint_id else None
    resolved_node_ref = _clean_text(network_node_ref) or (
        _clean_text(endpoint_record.get("endpoint_node_ref")) if endpoint_record else None
    )
    connected = endpoint_groups.get(resolved_node_ref) if resolved_node_ref else None
    connected_arm_count = int(len(connected)) if connected is not None else 0

    arm_compass_catalog = None
    if connected is not None and not connected.empty and "endpoint_compass" in connected.columns:
        compasses = [
            compass
            for compass in connected["endpoint_compass"].dropna().astype(str).tolist()
            if compass and compass.lower() != "nan"
        ]
        arm_compass_catalog = " | ".join(sorted(set(compasses))) or None

    approach_arm_id = None
    approach_bearing_deg = None
    approach_compass = None
    turn_options: set[str] = set()

    if endpoint_record is not None:
        approach_arm_id = (
            f"{resolved_node_ref}:{segment_id}:{endpoint_role}"
            if resolved_node_ref and segment_id and endpoint_role
            else endpoint_id
        )
        endpoint_bearing = endpoint_record.get("endpoint_bearing_deg")
        if endpoint_bearing is not None:
            approach_bearing_deg = float(endpoint_bearing)
            approach_compass = _clean_text(endpoint_record.get("endpoint_compass"))
            inbound_bearing = (approach_bearing_deg + 180.0) % 360.0
            if connected is not None:
                for _, candidate in connected.iterrows():
                    if _clean_text(candidate.get("endpoint_id")) == endpoint_id:
                        continue
                    candidate_bearing = candidate.get("endpoint_bearing_deg")
                    if candidate_bearing is None:
                        continue
                    turn_options.add(_classify_turn_direction(inbound_bearing, float(candidate_bearing)))
    elif connected is not None and connected_arm_count >= 2:
        for _, source_arm in connected.iterrows():
            source_bearing = source_arm.get("endpoint_bearing_deg")
            source_endpoint_id = _clean_text(source_arm.get("endpoint_id"))
            if source_bearing is None:
                continue
            inbound_bearing = (float(source_bearing) + 180.0) % 360.0
            for _, target_arm in connected.iterrows():
                if _clean_text(target_arm.get("endpoint_id")) == source_endpoint_id:
                    continue
                target_bearing = target_arm.get("endpoint_bearing_deg")
                if target_bearing is None:
                    continue
                turn_options.add(_classify_turn_direction(inbound_bearing, float(target_bearing)))

    turn_option_catalog = _format_turn_catalog(turn_options)
    return {
        "approach_node_ref": resolved_node_ref,
        "approach_arm_id": approach_arm_id,
        "approach_bearing_deg": approach_bearing_deg,
        "approach_compass": approach_compass,
        "connected_arm_count": connected_arm_count or None,
        "arm_compass_catalog": arm_compass_catalog,
        "turn_option_catalog": turn_option_catalog,
        "turn_option_count": len(turn_options) if turn_options else 0,
        "maneuver_complexity": _classify_maneuver_complexity(turn_options, connected_arm_count),
    }


def _build_signal_anchored_approach_objects(
    *,
    projected_signals: Any,
    projected_segments: Any,
    approach_distance_m: float,
    junction_buffer_m: float,
) -> Any:
    _gpd, pd, _Point = _load_geo_stack()

    endpoint_points, segment_geometry_by_id = _build_segment_endpoint_points(projected_segments, _Point)
    if endpoint_points.empty:
        return _empty_geodataframe(_gpd, projected_signals.crs)

    signal_join = endpoint_points.sjoin_nearest(
        projected_signals[["node_object_id", "name", "signal_type", "asset_code", "geometry"]],
        how="inner",
        max_distance=float(junction_buffer_m),
        distance_col="signal_distance_m",
    )
    signal_join = signal_join.drop(columns=["index_right"], errors="ignore")
    if signal_join.empty:
        return _empty_geodataframe(_gpd, projected_signals.crs)

    signal_join = signal_join.sort_values(
        by=["node_object_id", "segment_id", "signal_distance_m", "endpoint_role"],
        kind="stable",
    ).drop_duplicates(subset=["node_object_id", "segment_id"], keep="first")

    features: list[dict[str, Any]] = []
    for _, row in signal_join.iterrows():
        segment_id = str(row["segment_id"])
        segment_geometry = segment_geometry_by_id.get(segment_id)
        if segment_geometry is None:
            continue
        point, effective_distance = _interpolate_approach_point(
            segment_geometry,
            str(row["endpoint_role"]),
            approach_distance_m,
        )
        signal_id = str(row["node_object_id"])
        segment_token = segment_id.replace(":", "_")
        features.append(
            {
                "node_object_id": f"{signal_id}::approach::{segment_token}",
                "junction_id": signal_id,
                "source_system": "bari_signal_network_approach_builder",
                "object_type": "junction_approach",
                "node_role": "junction_approach",
                "name": _normalize_tag_text(row.get("segment_name")) or _clean_text(row.get("name")),
                "signal_type": _clean_text(row.get("signal_type")),
                "segment_id": segment_id,
                "segment_highway": _normalize_tag_text(row.get("segment_highway")),
                "segment_name": _normalize_tag_text(row.get("segment_name")),
                "segment_ref": _normalize_tag_text(row.get("segment_ref")),
                "segment_junction": _normalize_tag_text(row.get("segment_junction")),
                "signal_distance_m": float(row.get("signal_distance_m") or 0.0),
                "approach_distance_m": float(effective_distance),
                "approach_endpoint_role": _clean_text(row.get("endpoint_role")),
                "geometry": point,
            }
        )
    return projected_signals.__class__(features, geometry="geometry", crs=projected_signals.crs)


def _build_network_junction_objects(
    *,
    projected_segments: Any,
    projected_signals: Any,
    junction_buffer_m: float,
    unsignalized_min_degree: int,
    unsignalized_major_edge_min: int,
) -> tuple[Any, Any]:
    gpd, pd, Point = _load_geo_stack()

    endpoint_points, _segment_geometry_by_id = _build_segment_endpoint_points(projected_segments, Point)
    if endpoint_points.empty:
        empty = _empty_geodataframe(gpd, projected_segments.crs)
        return empty, empty

    working = endpoint_points.copy()
    working["is_major_edge"] = working["segment_highway"].apply(
        lambda value: any(highway in MAJOR_HIGHWAY_CLASSES for highway in _highway_classes(value))
    )
    working["is_roundabout_edge"] = (
        working["segment_junction"].fillna("").astype(str).str.contains("roundabout", case=False)
    )

    grouped_rows: list[dict[str, Any]] = []
    for node_ref, group in working.groupby("endpoint_node_ref", dropna=False):
        if group.empty:
            continue
        representative = group.sort_values(
            by=["is_major_edge", "is_roundabout_edge", "segment_length_m"],
            ascending=[False, False, True],
            kind="stable",
        ).iloc[0]
        geometry = representative.geometry
        names = [
            value
            for value in group["segment_name"].dropna().astype(str).unique().tolist()
            if value and value.lower() != "nan"
        ]
        refs = [
            value
            for value in group["segment_ref"].dropna().astype(str).unique().tolist()
            if value and value.lower() != "nan"
        ]
        highways = [
            value
            for value in group["segment_highway"].dropna().astype(str).unique().tolist()
            if value and value.lower() != "nan"
        ]
        grouped_rows.append(
            {
                "network_node_ref": str(node_ref) if node_ref is not None else None,
                "incident_edge_count": int(len(group)),
                "major_edge_count": int(group["is_major_edge"].sum()),
                "roundabout_edge_count": int(group["is_roundabout_edge"].sum()),
                "segment_id": _clean_text(representative.get("segment_id")),
                "segment_highway": _normalize_tag_text(representative.get("segment_highway")),
                "segment_name": _normalize_tag_text(representative.get("segment_name")),
                "segment_ref": _normalize_tag_text(representative.get("segment_ref")),
                "segment_junction": _normalize_tag_text(representative.get("segment_junction")),
                "candidate_name": " | ".join(names[:3]) or None,
                "candidate_ref": " | ".join(refs[:3]) or None,
                "candidate_highway": " | ".join(highways[:3]) or None,
                "geometry": geometry,
            }
        )

    candidate_points = gpd.GeoDataFrame(grouped_rows, geometry="geometry", crs=projected_segments.crs)
    if candidate_points.empty:
        empty = _empty_geodataframe(gpd, projected_segments.crs)
        return empty, empty

    signal_lookup = projected_signals[["node_object_id", "geometry"]].rename(columns={"node_object_id": "linked_signal_id"})
    signal_join = candidate_points.sjoin_nearest(
        signal_lookup,
        how="left",
        distance_col="signal_distance_m",
        max_distance=float(junction_buffer_m),
    )
    signal_join = signal_join.drop(columns=["index_right"], errors="ignore")

    unsignalized_mask = (
        (signal_join["roundabout_edge_count"] == 0)
        & (signal_join["incident_edge_count"] >= int(unsignalized_min_degree))
        & (signal_join["major_edge_count"] >= int(unsignalized_major_edge_min))
        & (signal_join["linked_signal_id"].isna())
    )
    roundabout_mask = signal_join["roundabout_edge_count"] > 0

    unsignalized_rows = signal_join.loc[unsignalized_mask].copy()
    roundabout_rows = signal_join.loc[roundabout_mask].copy()

    unsignalized_features: list[dict[str, Any]] = []
    for _, row in unsignalized_rows.iterrows():
        node_ref = _clean_text(row.get("network_node_ref")) or f"junction-{len(unsignalized_features) + 1}"
        unsignalized_features.append(
            {
                "node_object_id": f"it-bari-junction-{node_ref}",
                "junction_id": f"it-bari-junction-{node_ref}",
                "source_system": "bari_network_junction_builder",
                "object_type": "unsignalized_junction",
                "node_role": "unsignalized_junction",
                "name": row.get("candidate_name")
                or row.get("segment_name")
                or row.get("candidate_ref")
                or f"Unsignalized junction {node_ref}",
                "network_node_ref": node_ref,
                "segment_id": row.get("segment_id"),
                "segment_highway": row.get("segment_highway"),
                "segment_name": row.get("segment_name"),
                "segment_ref": row.get("segment_ref"),
                "segment_junction": row.get("segment_junction"),
                "incident_edge_count": int(row.get("incident_edge_count") or 0),
                "major_edge_count": int(row.get("major_edge_count") or 0),
                "roundabout_edge_count": int(row.get("roundabout_edge_count") or 0),
                "signal_distance_m": float(row.get("signal_distance_m"))
                if row.get("signal_distance_m") is not None
                else None,
                "geometry": row.geometry,
            }
        )

    roundabout_features: list[dict[str, Any]] = []
    for _, row in roundabout_rows.iterrows():
        node_ref = _clean_text(row.get("network_node_ref")) or f"roundabout-{len(roundabout_features) + 1}"
        roundabout_features.append(
            {
                "node_object_id": f"it-bari-roundabout-{node_ref}",
                "junction_id": f"it-bari-roundabout-{node_ref}",
                "source_system": "bari_network_roundabout_builder",
                "object_type": "roundabout",
                "node_role": "roundabout_junction",
                "name": row.get("candidate_name")
                or row.get("segment_name")
                or row.get("candidate_ref")
                or f"Roundabout {node_ref}",
                "network_node_ref": node_ref,
                "segment_id": row.get("segment_id"),
                "segment_highway": row.get("segment_highway"),
                "segment_name": row.get("segment_name"),
                "segment_ref": row.get("segment_ref"),
                "segment_junction": row.get("segment_junction"),
                "incident_edge_count": int(row.get("incident_edge_count") or 0),
                "major_edge_count": int(row.get("major_edge_count") or 0),
                "roundabout_edge_count": int(row.get("roundabout_edge_count") or 0),
                "signal_distance_m": float(row.get("signal_distance_m"))
                if row.get("signal_distance_m") is not None
                else None,
                "geometry": row.geometry,
            }
        )

    unsignalized_gdf = (
        gpd.GeoDataFrame(unsignalized_features, geometry="geometry", crs=projected_segments.crs)
        if unsignalized_features
        else _empty_geodataframe(gpd, projected_segments.crs)
    )
    roundabout_gdf = (
        gpd.GeoDataFrame(roundabout_features, geometry="geometry", crs=projected_segments.crs)
        if roundabout_features
        else _empty_geodataframe(gpd, projected_segments.crs)
    )
    return unsignalized_gdf, roundabout_gdf


def _fetch_crossing_features(boundary_path: str | Path) -> Any:
    ox = _load_osm_stack()
    gpd, _pd, _Point = _load_geo_stack()

    boundary = gpd.read_file(boundary_path)
    if boundary.empty:
        raise RuntimeError(f"Boundary input is empty: {boundary_path}")
    if boundary.crs is None:
        boundary = boundary.set_crs(epsg=4326)
    boundary = boundary.to_crs(epsg=4326)
    if hasattr(boundary.geometry, "union_all"):
        polygon = boundary.geometry.union_all()
    else:
        polygon = boundary.geometry.unary_union
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        raise RuntimeError(f"Boundary geometry is empty for crossing extraction: {boundary_path}")
    return ox.features_from_polygon(polygon, {"highway": "crossing", "footway": "crossing"})


def _prepare_crossing_points(
    *,
    boundary_path: str | Path,
    crossings_path: str | Path | None,
    raw_dir: str | Path | None,
    local_crs: Any,
) -> tuple[Any, dict[str, Any]]:
    gpd, pd, _Point = _load_geo_stack()
    raw_root = Path(raw_dir) if raw_dir is not None else None
    raw_path = None

    if crossings_path is not None:
        source_label = "local_crossings"
        source_kind = "local_file"
        source_value = Path(crossings_path)
        raw_crossings = gpd.read_file(source_value)
        resolved_source = str(source_value)
    else:
        source_label = "osm_crossings"
        source_kind = "osm_features"
        resolved_source = str(boundary_path)
        raw_crossings = _fetch_crossing_features(boundary_path)
        if raw_root is not None:
            raw_root.mkdir(parents=True, exist_ok=True)
            raw_path = raw_root / "bari_osm_crossings_raw.geojson"
            raw_crossings.reset_index().to_file(raw_path, driver="GeoJSON")

    if raw_crossings.empty:
        empty = gpd.GeoDataFrame([], geometry=[], crs="EPSG:4326").to_crs(local_crs)
        return (
            empty,
            {
                "crossing_source_kind": source_kind,
                "crossing_source_label": source_label,
                "crossing_source_resolved": resolved_source,
                "crossing_raw_path": str(raw_path) if raw_path else None,
                "crossing_raw_sha256": _sha256(raw_path) if raw_path else None,
                "raw_crossing_feature_count": 0,
            },
        )

    frame = raw_crossings.reset_index()
    if frame.crs is None:
        frame = frame.set_crs(epsg=4326)
    frame = frame.to_crs(epsg=4326)
    if "element" not in frame.columns and "element_type" in frame.columns:
        frame["element"] = frame["element_type"]
    if "osmid" not in frame.columns:
        frame["osmid"] = frame.index.astype(str)
    frame["source_record_id"] = frame.apply(
        lambda row: f"{_clean_text(row.get('element')) or 'feature'}-{_clean_text(row.get('osmid')) or row.name}",
        axis=1,
    )
    frame["geometry"] = frame.geometry.apply(
        lambda geometry: geometry if geometry.geom_type == "Point" else geometry.representative_point()
    )
    frame = frame.drop_duplicates(subset=["source_record_id"]).copy()
    crossing_points = gpd.GeoDataFrame(frame, geometry="geometry", crs=frame.crs).to_crs(local_crs)

    return (
        crossing_points,
        {
            "crossing_source_kind": source_kind,
            "crossing_source_label": source_label,
            "crossing_source_resolved": resolved_source,
            "crossing_raw_path": str(raw_path) if raw_path else str(crossings_path) if crossings_path else None,
            "crossing_raw_sha256": _sha256(raw_path)
            if raw_path
            else _sha256(Path(crossings_path))
            if crossings_path is not None
            else None,
            "raw_crossing_feature_count": int(len(crossing_points)),
        },
    )


def _build_crossing_objects(
    *,
    projected_crossings: Any,
    projected_signals: Any,
    projected_segments: Any,
    signal_link_m: float,
) -> Any:
    gpd, _pd, _Point = _load_geo_stack()
    if projected_crossings.empty:
        return _empty_geodataframe(gpd, projected_signals.crs)

    signal_lookup = projected_signals[["node_object_id", "name", "signal_type", "geometry"]].rename(
        columns={
            "node_object_id": "linked_signal_id",
            "name": "linked_signal_name",
            "signal_type": "linked_signal_type",
        }
    )
    signal_join = projected_crossings.sjoin_nearest(
        signal_lookup,
        how="left",
        max_distance=float(signal_link_m),
        distance_col="signal_distance_m",
    )
    signal_join = signal_join.drop(columns=["index_right"], errors="ignore")
    segment_lookup = projected_segments[["segment_id", "highway", "name", "ref", "junction", "geometry"]].rename(
        columns={
            "segment_id": "linked_segment_id",
            "highway": "linked_segment_highway",
            "name": "linked_segment_name",
            "ref": "linked_segment_ref",
            "junction": "linked_segment_junction",
        }
    )
    segment_join = signal_join.sjoin_nearest(
        segment_lookup,
        how="left",
        distance_col="nearest_segment_distance_m",
    )
    segment_join = segment_join.drop(columns=["index_right"], errors="ignore")
    segment_join = segment_join.sort_values(
        by=["source_record_id", "signal_distance_m", "nearest_segment_distance_m"],
        kind="stable",
    ).drop_duplicates(subset=["source_record_id"], keep="first")

    features: list[dict[str, Any]] = []
    for _, row in segment_join.iterrows():
        source_record_id = _clean_text(row.get("source_record_id")) or f"crossing-{len(features) + 1}"
        junction_id = _clean_text(row.get("linked_signal_id")) or f"it-bari-crossing-{source_record_id}"
        signal_name = _normalize_tag_text(row.get("linked_signal_name"))
        crossing_name = _normalize_tag_text(row.get("name"))
        segment_name = _normalize_tag_text(row.get("linked_segment_name"))
        features.append(
            {
                "node_object_id": f"it-bari-crossing-{source_record_id}",
                "junction_id": junction_id,
                "source_system": "osm_crossing_features",
                "object_type": "crossing",
                "node_role": "pedestrian_crossing",
                "name": signal_name or segment_name or _normalize_tag_text(row.get("linked_segment_ref")) or crossing_name or f"Crossing {source_record_id}",
                "crossing_type": _clean_text(row.get("crossing")) or _clean_text(row.get("highway")),
                "crossing_markings": _clean_text(row.get("crossing:markings")),
                "crossing_signals": _clean_text(row.get("crossing:signals")),
                "signal_type": _clean_text(row.get("linked_signal_type")),
                "segment_id": _clean_text(row.get("linked_segment_id")),
                "segment_highway": _normalize_tag_text(row.get("linked_segment_highway")),
                "segment_name": segment_name,
                "segment_ref": _normalize_tag_text(row.get("linked_segment_ref")),
                "segment_junction": _normalize_tag_text(row.get("linked_segment_junction")),
                "nearest_segment_distance_m": float(row.get("nearest_segment_distance_m") or 0.0),
                "signal_distance_m": float(row.get("signal_distance_m") or 0.0)
                if row.get("signal_distance_m") is not None
                else None,
                "source_record_id": source_record_id,
                "geometry": row.geometry,
            }
        )

    return gpd.GeoDataFrame(features, geometry="geometry", crs=projected_crossings.crs)


def build_bari_crossing_and_approach_objects(
    output_dir: str | Path,
    *,
    signal_nodes_path: str | Path = "data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson",
    segments_path: str | Path = "data/processed/segments/bari/road_segments.geojson",
    boundary_path: str | Path = "data/processed/segments/bari/boundary.geojson",
    crossings_path: str | Path | None = None,
    raw_dir: str | Path | None = "data/raw/bari_crossing_objects",
    approach_distance_m: float = 25.0,
    junction_buffer_m: float = 35.0,
    signal_link_m: float = 50.0,
    unsignalized_min_degree: int = 4,
    unsignalized_major_edge_min: int = 2,
) -> dict[str, Any]:
    gpd, pd, _Point = _load_geo_stack()

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    signal_nodes_input = Path(signal_nodes_path)
    segments_input = Path(segments_path)
    boundary_input = Path(boundary_path)

    signals = gpd.read_file(signal_nodes_input)
    segments = gpd.read_file(segments_input)
    if signals.empty:
        raise RuntimeError(f"Signal node input is empty: {signal_nodes_input}")
    if segments.empty:
        raise RuntimeError(f"Segment input is empty: {segments_input}")
    if "segment_id" not in segments.columns:
        raise RuntimeError(f"Segment input does not contain required 'segment_id' column: {segments_input}")
    if "node_object_id" not in signals.columns:
        raise RuntimeError(f"Signal input does not contain required 'node_object_id' column: {signal_nodes_input}")

    local_crs = segments.estimate_utm_crs() or signals.estimate_utm_crs() or "EPSG:3857"
    projected_signals = signals.to_crs(local_crs)
    projected_segments = segments.to_crs(local_crs)

    approach_objects = _build_signal_anchored_approach_objects(
        projected_signals=projected_signals,
        projected_segments=projected_segments,
        approach_distance_m=approach_distance_m,
        junction_buffer_m=junction_buffer_m,
    )
    projected_crossings, crossing_source_meta = _prepare_crossing_points(
        boundary_path=boundary_input,
        crossings_path=crossings_path,
        raw_dir=raw_dir,
        local_crs=local_crs,
    )
    crossing_objects = _build_crossing_objects(
        projected_crossings=projected_crossings,
        projected_signals=projected_signals,
        projected_segments=projected_segments,
        signal_link_m=signal_link_m,
    )
    unsignalized_junction_objects, roundabout_objects = _build_network_junction_objects(
        projected_segments=projected_segments,
        projected_signals=projected_signals,
        junction_buffer_m=junction_buffer_m,
        unsignalized_min_degree=unsignalized_min_degree,
        unsignalized_major_edge_min=unsignalized_major_edge_min,
    )

    combined = pd.concat(
        [approach_objects, crossing_objects, unsignalized_junction_objects, roundabout_objects],
        ignore_index=True,
        sort=False,
    )
    combined_gdf = gpd.GeoDataFrame(combined, geometry="geometry", crs=local_crs).to_crs(epsg=4326)

    geojson_path = output_root / "road_node_objects.geojson"
    manifest_path = output_root / "road_node_objects.manifest.json"
    combined_gdf.to_file(geojson_path, driver="GeoJSON")

    crossing_linked_to_signal_count = 0
    if not crossing_objects.empty and "signal_distance_m" in crossing_objects.columns:
        crossing_linked_to_signal_count = int(crossing_objects["signal_distance_m"].notna().sum())

    return _format_output_manifest(
        manifest_path=manifest_path,
        source={
            "adapter": "bari_mixed_node_object_builder",
            "signal_source_path": str(signal_nodes_input),
            "signal_source_sha256": _sha256(signal_nodes_input),
            **crossing_source_meta,
        },
        inputs={
            "signal_nodes_path": str(signal_nodes_input),
            "signal_nodes_sha256": _sha256(signal_nodes_input),
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "boundary_path": str(boundary_input),
            "boundary_sha256": _sha256(boundary_input),
            "crossings_path": str(crossings_path) if crossings_path is not None else None,
            "approach_distance_m": float(approach_distance_m),
            "junction_buffer_m": float(junction_buffer_m),
            "signal_link_m": float(signal_link_m),
            "unsignalized_min_degree": int(unsignalized_min_degree),
            "unsignalized_major_edge_min": int(unsignalized_major_edge_min),
        },
        outputs={
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "manifest_path": str(manifest_path),
        },
        stats={
            "signal_anchor_count": int(projected_signals["node_object_id"].nunique()),
            "junction_approach_count": int(len(approach_objects)),
            "crossing_object_count": int(len(crossing_objects)),
            "unsignalized_junction_count": int(len(unsignalized_junction_objects)),
            "roundabout_object_count": int(len(roundabout_objects)),
            "total_node_object_count": int(len(combined_gdf)),
            "crossings_linked_to_signal_count": crossing_linked_to_signal_count,
            "crossings_linked_to_segment_count": int(crossing_objects["segment_id"].notna().sum())
            if not crossing_objects.empty and "segment_id" in crossing_objects.columns
            else 0,
        },
    )


def build_bari_conflict_zones(
    output_dir: str | Path,
    *,
    node_objects_path: str | Path = "data/processed/node_objects/bari_crossing_approaches/road_node_objects.geojson",
    segments_path: str | Path = "data/processed/segments/bari/road_segments.geojson",
    crossing_radius_m: float = 12.0,
    unsignalized_radius_m: float = 20.0,
    roundabout_fallback_radius_m: float = 16.0,
    junction_approach_length_m: float = 20.0,
    roundabout_entry_length_m: float = 18.0,
    default_zone_half_width_m: float = 6.0,
) -> dict[str, Any]:
    gpd, _pd, Point = _load_geo_stack()

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    node_objects_input = Path(node_objects_path)
    segments_input = Path(segments_path)

    node_objects = gpd.read_file(node_objects_input)
    segments = gpd.read_file(segments_input)
    if node_objects.empty:
        raise RuntimeError(f"Node-object input is empty: {node_objects_input}")
    if segments.empty:
        raise RuntimeError(f"Segment input is empty: {segments_input}")
    if "node_object_id" not in node_objects.columns:
        raise RuntimeError(f"Node-object input does not contain required 'node_object_id' column: {node_objects_input}")
    if "segment_id" not in segments.columns:
        raise RuntimeError(f"Segment input does not contain required 'segment_id' column: {segments_input}")

    local_crs = segments.estimate_utm_crs() or node_objects.estimate_utm_crs() or "EPSG:3857"
    projected_nodes = node_objects.to_crs(local_crs)
    projected_segments = segments.to_crs(local_crs)

    endpoint_points, segment_geometry_by_id = _build_segment_endpoint_points(projected_segments, Point)
    endpoint_groups = {
        node_ref: group.copy()
        for node_ref, group in endpoint_points.groupby("endpoint_node_ref", dropna=False)
    }
    endpoint_lookup = {
        _clean_text(record.get("endpoint_id")): record
        for record in endpoint_points.to_dict(orient="records")
        if _clean_text(record.get("endpoint_id"))
    }

    features: list[dict[str, Any]] = []
    zone_counts = {
        "crossing_conflict_zone_count": 0,
        "junction_approach_conflict_zone_count": 0,
        "unsignalized_junction_conflict_zone_count": 0,
        "roundabout_entry_conflict_zone_count": 0,
        "roundabout_fallback_conflict_zone_count": 0,
    }

    def append_feature(feature: dict[str, Any], counter_key: str) -> None:
        features.append(feature)
        zone_counts[counter_key] += 1

    for _, row in projected_nodes.iterrows():
        parent_object_id = str(row.get("node_object_id"))
        parent_object_type = _clean_text(row.get("object_type")) or "unknown"
        base_name = (
            _normalize_tag_text(row.get("name"))
            or _normalize_tag_text(row.get("segment_name"))
            or _normalize_tag_text(row.get("segment_ref"))
            or parent_object_id
        )

        if parent_object_type == "crossing":
            turn_context = _derive_turn_context(
                endpoint_groups=endpoint_groups,
                endpoint_lookup=endpoint_lookup,
                segment_id=_clean_text(row.get("segment_id")),
            )
            crossing_protection_state = _classify_crossing_protection_state(
                signal_type=row.get("signal_type"),
                crossing_type=row.get("crossing_type"),
                crossing_signals=row.get("crossing_signals"),
                crossing_markings=row.get("crossing_markings"),
            )
            control_detail = (
                _normalize_signal_type(row.get("signal_type"))
                or _normalize_tag_text(row.get("crossing_signals"))
                or _normalize_tag_text(row.get("crossing_markings"))
                or "unlabeled_crossing_control"
            )
            append_feature(
                {
                    "node_object_id": f"{parent_object_id}::zone::crossing",
                    "junction_id": row.get("junction_id"),
                    "source_system": "bari_conflict_zone_builder",
                    "object_type": "conflict_zone",
                    "node_role": "conflict_zone",
                    "zone_type": "crossing_conflict_zone",
                    "parent_object_id": parent_object_id,
                    "parent_object_type": parent_object_type,
                    "name": base_name,
                    "signal_type": row.get("signal_type"),
                    "crossing_type": row.get("crossing_type"),
                    "crossing_markings": row.get("crossing_markings"),
                    "crossing_signals": row.get("crossing_signals"),
                    "movement_family": "crossing",
                    "control_state": crossing_protection_state,
                    "crossing_protection_state": crossing_protection_state,
                    "turn_path_class": "pedestrian_crossing",
                    "movement_arm_count": 2,
                    "priority_rule": _crossing_priority_rule(crossing_protection_state),
                    "control_detail": control_detail,
                    "approach_node_ref": turn_context["approach_node_ref"],
                    "approach_arm_id": None,
                    "approach_bearing_deg": None,
                    "approach_compass": None,
                    "connected_arm_count": turn_context["connected_arm_count"],
                    "arm_compass_catalog": turn_context["arm_compass_catalog"],
                    "turn_option_catalog": "pedestrian_crossing",
                    "turn_option_count": 1,
                    "maneuver_complexity": "crossing_only",
                    "roundabout_component_role": None,
                    "segment_id": row.get("segment_id"),
                    "segment_highway": row.get("segment_highway"),
                    "segment_name": row.get("segment_name"),
                    "segment_ref": row.get("segment_ref"),
                    "segment_junction": row.get("segment_junction"),
                    "nearest_segment_distance_m": row.get("nearest_segment_distance_m"),
                    "signal_distance_m": row.get("signal_distance_m"),
                    "source_record_id": row.get("source_record_id"),
                    "zone_radius_m": float(crossing_radius_m),
                    "zone_length_m": None,
                    "zone_width_m": float(crossing_radius_m * 2.0),
                    "geometry": row.geometry.buffer(float(crossing_radius_m)),
                },
                "crossing_conflict_zone_count",
            )
            continue

        if parent_object_type == "junction_approach":
            segment_id = _clean_text(row.get("segment_id"))
            segment_geometry = segment_geometry_by_id.get(segment_id) if segment_id else None
            endpoint_role = _clean_text(row.get("approach_endpoint_role")) or "end"
            turn_context = _derive_turn_context(
                endpoint_groups=endpoint_groups,
                endpoint_lookup=endpoint_lookup,
                segment_id=segment_id,
                endpoint_role=endpoint_role,
            )
            zone_line, effective_length = _build_endpoint_conflict_line(
                segment_geometry,
                endpoint_role,
                junction_approach_length_m,
            )
            half_width = _zone_half_width_for_highway(row.get("segment_highway"), default_zone_half_width_m)
            geometry = zone_line.buffer(half_width, cap_style=2) if zone_line is not None else row.geometry.buffer(half_width)
            append_feature(
                {
                    "node_object_id": f"{parent_object_id}::zone::approach",
                    "junction_id": row.get("junction_id"),
                    "source_system": "bari_conflict_zone_builder",
                    "object_type": "conflict_zone",
                    "node_role": "conflict_zone",
                    "zone_type": "junction_approach_conflict_zone",
                    "parent_object_id": parent_object_id,
                    "parent_object_type": parent_object_type,
                    "name": base_name,
                    "signal_type": row.get("signal_type"),
                    "movement_family": "approach",
                    "control_state": "signalized",
                    "crossing_protection_state": None,
                    "turn_path_class": "approach_to_signal",
                    "movement_arm_count": None,
                    "priority_rule": "signal_controlled",
                    "control_detail": _normalize_signal_type(row.get("signal_type")) or "signalized_approach",
                    "approach_node_ref": turn_context["approach_node_ref"],
                    "approach_arm_id": turn_context["approach_arm_id"],
                    "approach_bearing_deg": turn_context["approach_bearing_deg"],
                    "approach_compass": turn_context["approach_compass"],
                    "connected_arm_count": turn_context["connected_arm_count"],
                    "arm_compass_catalog": turn_context["arm_compass_catalog"],
                    "turn_option_catalog": turn_context["turn_option_catalog"],
                    "turn_option_count": turn_context["turn_option_count"],
                    "maneuver_complexity": turn_context["maneuver_complexity"],
                    "roundabout_component_role": None,
                    "segment_id": row.get("segment_id"),
                    "segment_highway": row.get("segment_highway"),
                    "segment_name": row.get("segment_name"),
                    "segment_ref": row.get("segment_ref"),
                    "segment_junction": row.get("segment_junction"),
                    "signal_distance_m": row.get("signal_distance_m"),
                    "approach_distance_m": row.get("approach_distance_m"),
                    "approach_endpoint_role": endpoint_role,
                    "zone_radius_m": None,
                    "zone_length_m": float(effective_length),
                    "zone_width_m": float(half_width * 2.0),
                    "geometry": geometry,
                },
                "junction_approach_conflict_zone_count",
            )
            continue

        if parent_object_type == "unsignalized_junction":
            turn_context = _derive_turn_context(
                endpoint_groups=endpoint_groups,
                endpoint_lookup=endpoint_lookup,
                network_node_ref=_clean_text(row.get("network_node_ref")),
            )
            append_feature(
                {
                    "node_object_id": f"{parent_object_id}::zone::junction",
                    "junction_id": row.get("junction_id"),
                    "source_system": "bari_conflict_zone_builder",
                    "object_type": "conflict_zone",
                    "node_role": "conflict_zone",
                    "zone_type": "unsignalized_junction_conflict_zone",
                    "parent_object_id": parent_object_id,
                    "parent_object_type": parent_object_type,
                    "name": base_name,
                    "movement_family": "junction_area",
                    "control_state": (
                        "unsignalized_multi_arm"
                        if (_parse_int(row.get("incident_edge_count")) or 0) >= 4
                        else "unsignalized_minor"
                    ),
                    "crossing_protection_state": None,
                    "turn_path_class": (
                        "multi_arm_intersection"
                        if (_parse_int(row.get("incident_edge_count")) or 0) >= 4
                        else "simple_intersection"
                    ),
                    "movement_arm_count": _parse_int(row.get("incident_edge_count")),
                    "priority_rule": (
                        "major_minor_priority"
                        if (_parse_int(row.get("major_edge_count")) or 0) >= 2
                        else "local_priority"
                    ),
                    "control_detail": (
                        f"incident_edges={_parse_int(row.get('incident_edge_count')) or 0};"
                        f"major_edges={_parse_int(row.get('major_edge_count')) or 0}"
                    ),
                    "approach_node_ref": turn_context["approach_node_ref"],
                    "approach_arm_id": None,
                    "approach_bearing_deg": None,
                    "approach_compass": None,
                    "connected_arm_count": turn_context["connected_arm_count"],
                    "arm_compass_catalog": turn_context["arm_compass_catalog"],
                    "turn_option_catalog": turn_context["turn_option_catalog"],
                    "turn_option_count": turn_context["turn_option_count"],
                    "maneuver_complexity": turn_context["maneuver_complexity"],
                    "roundabout_component_role": None,
                    "segment_id": row.get("segment_id"),
                    "segment_highway": row.get("segment_highway"),
                    "segment_name": row.get("segment_name"),
                    "segment_ref": row.get("segment_ref"),
                    "segment_junction": row.get("segment_junction"),
                    "network_node_ref": row.get("network_node_ref"),
                    "incident_edge_count": row.get("incident_edge_count"),
                    "major_edge_count": row.get("major_edge_count"),
                    "roundabout_edge_count": row.get("roundabout_edge_count"),
                    "signal_distance_m": row.get("signal_distance_m"),
                    "zone_radius_m": float(unsignalized_radius_m),
                    "zone_length_m": None,
                    "zone_width_m": float(unsignalized_radius_m * 2.0),
                    "geometry": row.geometry.buffer(float(unsignalized_radius_m)),
                },
                "unsignalized_junction_conflict_zone_count",
            )
            continue

        if parent_object_type != "roundabout":
            continue

        node_ref = _clean_text(row.get("network_node_ref"))
        connected_segments = endpoint_groups.get(node_ref)
        roundabout_entry_count = 0
        if connected_segments is not None and not connected_segments.empty:
            candidate_entries = connected_segments.loc[
                ~connected_segments["segment_junction"].fillna("").astype(str).str.contains("roundabout", case=False)
            ].copy()
            candidate_entries = candidate_entries.sort_values(
                by=["segment_highway", "segment_length_m", "segment_id"],
                kind="stable",
            ).drop_duplicates(subset="segment_id", keep="first")

            for _, entry in candidate_entries.iterrows():
                segment_id = _clean_text(entry.get("segment_id"))
                segment_geometry = segment_geometry_by_id.get(segment_id) if segment_id else None
                endpoint_role = _clean_text(entry.get("endpoint_role")) or "end"
                turn_context = _derive_turn_context(
                    endpoint_groups=endpoint_groups,
                    endpoint_lookup=endpoint_lookup,
                    segment_id=segment_id,
                    endpoint_role=endpoint_role,
                    network_node_ref=node_ref,
                )
                zone_line, effective_length = _build_endpoint_conflict_line(
                    segment_geometry,
                    endpoint_role,
                    roundabout_entry_length_m,
                )
                half_width = _zone_half_width_for_highway(entry.get("segment_highway"), default_zone_half_width_m)
                geometry = (
                    zone_line.buffer(half_width, cap_style=2)
                    if zone_line is not None
                    else row.geometry.buffer(half_width)
                )
                entry_segment_id = segment_id or f"entry-{roundabout_entry_count + 1}"
                append_feature(
                    {
                        "node_object_id": f"{parent_object_id}::zone::roundabout_entry::{entry_segment_id.replace(':', '_')}",
                        "junction_id": row.get("junction_id"),
                        "source_system": "bari_conflict_zone_builder",
                        "object_type": "conflict_zone",
                        "node_role": "conflict_zone",
                        "zone_type": "roundabout_entry_conflict_zone",
                        "parent_object_id": parent_object_id,
                        "parent_object_type": parent_object_type,
                        "name": _normalize_tag_text(entry.get("segment_name")) or base_name,
                        "movement_family": "roundabout_entry",
                        "control_state": "yield_controlled",
                        "crossing_protection_state": None,
                        "turn_path_class": "roundabout_entry_merge",
                        "movement_arm_count": _parse_int(row.get("incident_edge_count")),
                        "priority_rule": "yield_to_circulating",
                        "control_detail": _normalize_tag_text(entry.get("segment_highway")) or "roundabout_entry",
                        "approach_node_ref": turn_context["approach_node_ref"],
                        "approach_arm_id": turn_context["approach_arm_id"],
                        "approach_bearing_deg": turn_context["approach_bearing_deg"],
                        "approach_compass": turn_context["approach_compass"],
                        "connected_arm_count": turn_context["connected_arm_count"],
                        "arm_compass_catalog": turn_context["arm_compass_catalog"],
                        "turn_option_catalog": turn_context["turn_option_catalog"],
                        "turn_option_count": turn_context["turn_option_count"],
                        "maneuver_complexity": turn_context["maneuver_complexity"],
                        "roundabout_component_role": "entry",
                        "segment_id": segment_id,
                        "segment_highway": entry.get("segment_highway"),
                        "segment_name": entry.get("segment_name"),
                        "segment_ref": entry.get("segment_ref"),
                        "segment_junction": entry.get("segment_junction"),
                        "network_node_ref": node_ref,
                        "incident_edge_count": row.get("incident_edge_count"),
                        "major_edge_count": row.get("major_edge_count"),
                        "roundabout_edge_count": row.get("roundabout_edge_count"),
                        "approach_endpoint_role": endpoint_role,
                        "zone_radius_m": None,
                        "zone_length_m": float(effective_length),
                        "zone_width_m": float(half_width * 2.0),
                        "geometry": geometry,
                    },
                    "roundabout_entry_conflict_zone_count",
                )
                roundabout_entry_count += 1

        if roundabout_entry_count == 0:
            turn_context = _derive_turn_context(
                endpoint_groups=endpoint_groups,
                endpoint_lookup=endpoint_lookup,
                network_node_ref=node_ref,
            )
            append_feature(
                {
                    "node_object_id": f"{parent_object_id}::zone::roundabout",
                    "junction_id": row.get("junction_id"),
                    "source_system": "bari_conflict_zone_builder",
                    "object_type": "conflict_zone",
                    "node_role": "conflict_zone",
                    "zone_type": "roundabout_conflict_zone",
                    "parent_object_id": parent_object_id,
                    "parent_object_type": parent_object_type,
                    "name": base_name,
                    "movement_family": "roundabout_core",
                    "control_state": "roundabout_core",
                    "crossing_protection_state": None,
                    "turn_path_class": "roundabout_internal",
                    "movement_arm_count": _parse_int(row.get("incident_edge_count")),
                    "priority_rule": "circulating_priority",
                    "control_detail": _normalize_tag_text(row.get("segment_highway")) or "roundabout_core",
                    "approach_node_ref": turn_context["approach_node_ref"],
                    "approach_arm_id": None,
                    "approach_bearing_deg": None,
                    "approach_compass": None,
                    "connected_arm_count": turn_context["connected_arm_count"],
                    "arm_compass_catalog": turn_context["arm_compass_catalog"],
                    "turn_option_catalog": turn_context["turn_option_catalog"] or "circulatory_only",
                    "turn_option_count": turn_context["turn_option_count"],
                    "maneuver_complexity": turn_context["maneuver_complexity"],
                    "roundabout_component_role": "core",
                    "segment_id": row.get("segment_id"),
                    "segment_highway": row.get("segment_highway"),
                    "segment_name": row.get("segment_name"),
                    "segment_ref": row.get("segment_ref"),
                    "segment_junction": row.get("segment_junction"),
                    "network_node_ref": node_ref,
                    "incident_edge_count": row.get("incident_edge_count"),
                    "major_edge_count": row.get("major_edge_count"),
                    "roundabout_edge_count": row.get("roundabout_edge_count"),
                    "zone_radius_m": float(roundabout_fallback_radius_m),
                    "zone_length_m": None,
                    "zone_width_m": float(roundabout_fallback_radius_m * 2.0),
                    "geometry": row.geometry.buffer(float(roundabout_fallback_radius_m)),
                },
                "roundabout_fallback_conflict_zone_count",
            )

    conflict_gdf = (
        gpd.GeoDataFrame(features, geometry="geometry", crs=local_crs)
        if features
        else _empty_geodataframe(gpd, local_crs)
    ).to_crs(epsg=4326)
    movement_family_counts = {}
    control_state_counts = {}
    turn_option_catalog_counts = {}
    maneuver_complexity_counts = {}
    if not conflict_gdf.empty:
        if "movement_family" in conflict_gdf.columns:
            movement_family_counts = {
                str(key): int(value)
                for key, value in conflict_gdf["movement_family"].fillna("unknown").value_counts().items()
            }
        if "control_state" in conflict_gdf.columns:
            control_state_counts = {
                str(key): int(value)
                for key, value in conflict_gdf["control_state"].fillna("unknown").value_counts().items()
            }
        if "turn_option_catalog" in conflict_gdf.columns:
            turn_option_catalog_counts = {
                str(key): int(value)
                for key, value in conflict_gdf["turn_option_catalog"].fillna("unknown").value_counts().items()
            }
        if "maneuver_complexity" in conflict_gdf.columns:
            maneuver_complexity_counts = {
                str(key): int(value)
                for key, value in conflict_gdf["maneuver_complexity"].fillna("unknown").value_counts().items()
            }
    geojson_path = output_root / "road_conflict_zones.geojson"
    manifest_path = output_root / "road_conflict_zones.manifest.json"
    conflict_gdf.to_file(geojson_path, driver="GeoJSON")

    return _format_output_manifest(
        manifest_path=manifest_path,
        source={
            "adapter": "bari_conflict_zone_builder",
            "node_objects_source_path": str(node_objects_input),
            "node_objects_source_sha256": _sha256(node_objects_input),
            "segments_source_path": str(segments_input),
            "segments_source_sha256": _sha256(segments_input),
        },
        inputs={
            "node_objects_path": str(node_objects_input),
            "node_objects_sha256": _sha256(node_objects_input),
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "crossing_radius_m": float(crossing_radius_m),
            "unsignalized_radius_m": float(unsignalized_radius_m),
            "roundabout_fallback_radius_m": float(roundabout_fallback_radius_m),
            "junction_approach_length_m": float(junction_approach_length_m),
            "roundabout_entry_length_m": float(roundabout_entry_length_m),
            "default_zone_half_width_m": float(default_zone_half_width_m),
        },
        outputs={
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "manifest_path": str(manifest_path),
        },
        stats={
            **zone_counts,
            "total_conflict_zone_count": int(len(conflict_gdf)),
            "source_node_object_count": int(len(projected_nodes)),
            "movement_family_counts": movement_family_counts,
            "control_state_counts": control_state_counts,
            "turn_option_catalog_counts": turn_option_catalog_counts,
            "maneuver_complexity_counts": maneuver_complexity_counts,
        },
    )


def build_bari_movement_objects(
    output_dir: str | Path,
    *,
    conflict_zones_path: str | Path = "data/processed/conflict_zones/bari/road_conflict_zones.geojson",
    segments_path: str | Path = "data/processed/segments/bari/road_segments.geojson",
    movement_offset_m: float = 8.0,
    target_resolution_max_heading_delta_deg: float = 35.0,
    target_resolution_min_score_gap: float = 25.0,
) -> dict[str, Any]:
    gpd, _pd, Point = _load_geo_stack()

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    conflict_zones_input = Path(conflict_zones_path)
    segments_input = Path(segments_path)

    zones = gpd.read_file(conflict_zones_input)
    segments = gpd.read_file(segments_input)
    if zones.empty:
        raise RuntimeError(f"Conflict-zone input is empty: {conflict_zones_input}")
    if segments.empty:
        raise RuntimeError(f"Segment input is empty: {segments_input}")
    if "node_object_id" not in zones.columns:
        raise RuntimeError(f"Conflict-zone input does not contain required 'node_object_id' column: {conflict_zones_input}")
    if "segment_id" not in segments.columns:
        raise RuntimeError(f"Segment input does not contain required 'segment_id' column: {segments_input}")

    local_crs = segments.estimate_utm_crs() or zones.estimate_utm_crs() or "EPSG:3857"
    projected_zones = zones.to_crs(local_crs)
    projected_segments = segments.to_crs(local_crs)
    endpoint_points, _segment_geometry_by_id = _build_segment_endpoint_points(projected_segments, Point)
    endpoint_groups = {
        node_ref: group.copy()
        for node_ref, group in endpoint_points.groupby("endpoint_node_ref", dropna=False)
    }
    endpoint_lookup = {
        _clean_text(record.get("endpoint_id")): record
        for record in endpoint_points.to_dict(orient="records")
        if _clean_text(record.get("endpoint_id"))
    }

    features: list[dict[str, Any]] = []
    movement_role_counts: dict[str, int] = {}
    movement_turn_counts: dict[str, int] = {}
    movement_resolution_state_counts: dict[str, int] = {}
    movement_resolution_method_counts: dict[str, int] = {}
    signal_priority_variant_counts: dict[str, int] = {}
    phase_priority_group_counts: dict[str, int] = {}

    def register_feature(feature: dict[str, Any]) -> None:
        features.append(feature)
        role = _clean_text(feature.get("movement_role")) or "unknown"
        turn = _clean_text(feature.get("movement_turn")) or "unknown"
        resolution_state = _clean_text(feature.get("movement_resolution_state")) or "unknown"
        resolution_method = _clean_text(feature.get("movement_resolution_method")) or "unknown"
        signal_priority = _clean_text(feature.get("signal_priority_variant")) or "unknown"
        phase_priority_group = _clean_text(feature.get("phase_priority_group")) or "unknown"
        movement_role_counts[role] = movement_role_counts.get(role, 0) + 1
        movement_turn_counts[turn] = movement_turn_counts.get(turn, 0) + 1
        movement_resolution_state_counts[resolution_state] = (
            movement_resolution_state_counts.get(resolution_state, 0) + 1
        )
        movement_resolution_method_counts[resolution_method] = (
            movement_resolution_method_counts.get(resolution_method, 0) + 1
        )
        signal_priority_variant_counts[signal_priority] = (
            signal_priority_variant_counts.get(signal_priority, 0) + 1
        )
        phase_priority_group_counts[phase_priority_group] = (
            phase_priority_group_counts.get(phase_priority_group, 0) + 1
        )

    for _, row in projected_zones.iterrows():
        zone_id = str(row.get("node_object_id"))
        zone_type = _clean_text(row.get("zone_type")) or "unknown_zone"
        base_name = (
            _normalize_tag_text(row.get("name"))
            or _normalize_tag_text(row.get("segment_name"))
            or _normalize_tag_text(row.get("segment_ref"))
            or zone_id
        )
        center = row.geometry.representative_point()

        if zone_type == "crossing_conflict_zone":
            register_feature(
                {
                    "node_object_id": f"{zone_id}::movement::crossing",
                    "junction_id": row.get("junction_id"),
                    "source_system": "bari_movement_object_builder",
                    "object_type": "movement_object",
                    "node_role": "crossing_movement",
                    "movement_role": "pedestrian_crossing",
                    "movement_turn": "cross",
                    "name": base_name,
                    "parent_object_id": zone_id,
                    "parent_object_type": "conflict_zone",
                    "movement_source_zone_id": zone_id,
                    "movement_source_zone_type": zone_type,
                    "movement_source_parent_object_id": row.get("parent_object_id"),
                    "movement_family": row.get("movement_family"),
                    "control_state": row.get("control_state"),
                    "crossing_protection_state": row.get("crossing_protection_state"),
                    "turn_path_class": row.get("turn_path_class"),
                    "movement_arm_count": row.get("movement_arm_count"),
                    "priority_rule": row.get("priority_rule"),
                    "control_detail": row.get("control_detail"),
                    "approach_node_ref": row.get("approach_node_ref"),
                    "incoming_arm_id": None,
                    "incoming_bearing_deg": None,
                    "incoming_compass": None,
                    "outgoing_arm_id": None,
                    "outgoing_bearing_deg": None,
                    "outgoing_compass": None,
                    "candidate_target_arm_count": 0,
                    "candidate_target_arm_catalog": None,
                    "movement_resolution_state": "crossing_zone_equivalent",
                    "movement_resolution_method": "crossing_zone_center",
                    "movement_target_rank": None,
                    "movement_target_score": None,
                    "movement_target_heading_delta_deg": None,
                    "movement_target_continuity_flags": None,
                    "signal_priority_variant": _signal_priority_variant(
                        movement_role="pedestrian_crossing",
                        crossing_protection_state=row.get("crossing_protection_state"),
                    ),
                    "phase_priority_group": _phase_priority_group(
                        movement_role="pedestrian_crossing",
                        movement_turn="cross",
                        crossing_protection_state=row.get("crossing_protection_state"),
                    ),
                    "maneuver_complexity": row.get("maneuver_complexity"),
                    "roundabout_component_role": row.get("roundabout_component_role"),
                    "segment_id": row.get("segment_id"),
                    "segment_highway": row.get("segment_highway"),
                    "segment_name": row.get("segment_name"),
                    "segment_ref": row.get("segment_ref"),
                    "segment_junction": row.get("segment_junction"),
                    "geometry": center,
                }
            )
            continue

        if zone_type in {"junction_approach_conflict_zone", "roundabout_entry_conflict_zone"}:
            source_endpoint_id = _clean_text(row.get("approach_arm_id"))
            source_bearing = row.get("approach_bearing_deg")
            connected_group = endpoint_groups.get(_clean_text(row.get("approach_node_ref")))
            for turn_label in _split_turn_option_catalog(row.get("turn_option_catalog")):
                raw_target_candidates = _candidate_targets_for_turn(
                    connected_group=connected_group,
                    source_endpoint_id=source_endpoint_id or "",
                    source_bearing_deg=float(source_bearing) if source_bearing is not None else None,
                    turn_label=turn_label,
                )
                ranked_candidates = _rank_target_candidates_for_turn(
                    target_candidates=raw_target_candidates,
                    source_segment_highway=row.get("segment_highway"),
                    source_segment_name=row.get("segment_name"),
                    source_segment_ref=row.get("segment_ref"),
                    source_bearing_deg=float(source_bearing) if source_bearing is not None else None,
                    turn_label=turn_label,
                )
                target_catalog = " | ".join(_target_arm_label(candidate) for candidate in ranked_candidates) or None
                resolved_candidates, resolution_state, resolution_method = _resolve_ranked_target_candidates(
                    ranked_candidates,
                    max_heading_delta_deg=target_resolution_max_heading_delta_deg,
                    min_score_gap=target_resolution_min_score_gap,
                )
                target_records = resolved_candidates or [None]
                for target_index, target_candidate in enumerate(target_records, start=1):
                    if target_candidate is not None:
                        outgoing_arm_id = _clean_text(target_candidate.get("endpoint_id"))
                        outgoing_bearing_deg = target_candidate.get("endpoint_bearing_deg")
                        outgoing_compass = _clean_text(target_candidate.get("endpoint_compass"))
                        movement_heading = float(outgoing_bearing_deg) if outgoing_bearing_deg is not None else None
                        movement_target_rank = target_candidate.get("movement_target_rank")
                        movement_target_score = target_candidate.get("movement_target_score")
                        movement_target_heading_delta_deg = target_candidate.get("movement_target_heading_delta_deg")
                        movement_target_continuity_flags = target_candidate.get("movement_target_continuity_flags")
                    else:
                        outgoing_arm_id = None
                        outgoing_bearing_deg = None
                        outgoing_compass = None
                        movement_heading = _movement_heading_from_turn(
                            float(source_bearing) if source_bearing is not None else None,
                            turn_label,
                        )
                        movement_target_rank = None
                        movement_target_score = None
                        movement_target_heading_delta_deg = None
                        movement_target_continuity_flags = None
                    geometry = _offset_point_by_bearing(Point, center, movement_heading, movement_offset_m)
                    movement_role = (
                        "signalized_turn_movement"
                        if zone_type == "junction_approach_conflict_zone"
                        else "roundabout_entry_movement"
                    )
                    register_feature(
                        {
                            "node_object_id": (
                                f"{zone_id}::movement::{_sanitize_token(source_endpoint_id)}::"
                                f"{_sanitize_token(turn_label)}::{_sanitize_token(outgoing_arm_id or f'candidate_{target_index}')}"
                            ),
                            "junction_id": row.get("junction_id"),
                            "source_system": "bari_movement_object_builder",
                            "object_type": "movement_object",
                            "node_role": "turn_movement",
                            "movement_role": movement_role,
                            "movement_turn": turn_label,
                            "name": f"{base_name} [{turn_label}]",
                            "parent_object_id": zone_id,
                            "parent_object_type": "conflict_zone",
                            "movement_source_zone_id": zone_id,
                            "movement_source_zone_type": zone_type,
                            "movement_source_parent_object_id": row.get("parent_object_id"),
                            "movement_family": row.get("movement_family"),
                            "control_state": row.get("control_state"),
                            "crossing_protection_state": row.get("crossing_protection_state"),
                            "turn_path_class": row.get("turn_path_class"),
                            "movement_arm_count": row.get("movement_arm_count"),
                            "priority_rule": row.get("priority_rule"),
                            "control_detail": row.get("control_detail"),
                            "approach_node_ref": row.get("approach_node_ref"),
                            "incoming_arm_id": source_endpoint_id,
                            "incoming_bearing_deg": source_bearing,
                            "incoming_compass": row.get("approach_compass"),
                            "outgoing_arm_id": outgoing_arm_id,
                            "outgoing_bearing_deg": outgoing_bearing_deg,
                            "outgoing_compass": outgoing_compass,
                            "candidate_target_arm_count": int(len(ranked_candidates)),
                            "candidate_target_arm_catalog": target_catalog,
                            "movement_resolution_state": resolution_state,
                            "movement_resolution_method": resolution_method,
                            "movement_target_rank": movement_target_rank,
                            "movement_target_score": movement_target_score,
                            "movement_target_heading_delta_deg": movement_target_heading_delta_deg,
                            "movement_target_continuity_flags": movement_target_continuity_flags,
                            "signal_priority_variant": _signal_priority_variant(
                                movement_role=movement_role,
                                priority_rule=row.get("priority_rule"),
                            ),
                            "phase_priority_group": _phase_priority_group(
                                movement_role=movement_role,
                                movement_turn=turn_label,
                                priority_rule=row.get("priority_rule"),
                            ),
                            "maneuver_complexity": row.get("maneuver_complexity"),
                            "roundabout_component_role": row.get("roundabout_component_role"),
                            "segment_id": row.get("segment_id"),
                            "segment_highway": row.get("segment_highway"),
                            "segment_name": row.get("segment_name"),
                            "segment_ref": row.get("segment_ref"),
                            "segment_junction": row.get("segment_junction"),
                            "geometry": geometry,
                        }
                    )
            continue

        if zone_type == "unsignalized_junction_conflict_zone":
            node_ref = _clean_text(row.get("approach_node_ref") or row.get("network_node_ref"))
            connected_group = endpoint_groups.get(node_ref)
            if connected_group is None or connected_group.empty:
                continue
            for _, source_arm in connected_group.iterrows():
                source_endpoint_id = _clean_text(source_arm.get("endpoint_id"))
                source_bearing = source_arm.get("endpoint_bearing_deg")
                source_compass = _clean_text(source_arm.get("endpoint_compass"))
                if not source_endpoint_id or source_bearing is None:
                    continue
                turn_options = _split_turn_option_catalog(
                    _format_turn_catalog(
                        {
                            _classify_turn_direction(
                                (float(source_bearing) + 180.0) % 360.0,
                                float(candidate.get("endpoint_bearing_deg")),
                            )
                            for _, candidate in connected_group.iterrows()
                            if _clean_text(candidate.get("endpoint_id")) != source_endpoint_id
                            and candidate.get("endpoint_bearing_deg") is not None
                        }
                    )
                )
                for turn_label in turn_options:
                    raw_target_candidates = _candidate_targets_for_turn(
                        connected_group=connected_group,
                        source_endpoint_id=source_endpoint_id,
                        source_bearing_deg=float(source_bearing),
                        turn_label=turn_label,
                    )
                    ranked_candidates = _rank_target_candidates_for_turn(
                        target_candidates=raw_target_candidates,
                        source_segment_highway=source_arm.get("segment_highway"),
                        source_segment_name=source_arm.get("segment_name"),
                        source_segment_ref=source_arm.get("segment_ref"),
                        source_bearing_deg=float(source_bearing),
                        turn_label=turn_label,
                    )
                    target_catalog = " | ".join(_target_arm_label(candidate) for candidate in ranked_candidates) or None
                    resolved_candidates, resolution_state, resolution_method = _resolve_ranked_target_candidates(
                        ranked_candidates,
                        max_heading_delta_deg=target_resolution_max_heading_delta_deg,
                        min_score_gap=target_resolution_min_score_gap,
                    )
                    target_records = resolved_candidates or [None]
                    for target_index, target_candidate in enumerate(target_records, start=1):
                        if target_candidate is not None:
                            outgoing_arm_id = _clean_text(target_candidate.get("endpoint_id"))
                            outgoing_bearing_deg = target_candidate.get("endpoint_bearing_deg")
                            outgoing_compass = _clean_text(target_candidate.get("endpoint_compass"))
                            movement_heading = float(outgoing_bearing_deg) if outgoing_bearing_deg is not None else None
                            movement_target_rank = target_candidate.get("movement_target_rank")
                            movement_target_score = target_candidate.get("movement_target_score")
                            movement_target_heading_delta_deg = target_candidate.get("movement_target_heading_delta_deg")
                            movement_target_continuity_flags = target_candidate.get("movement_target_continuity_flags")
                        else:
                            outgoing_arm_id = None
                            outgoing_bearing_deg = None
                            outgoing_compass = None
                            movement_heading = _movement_heading_from_turn(float(source_bearing), turn_label)
                            movement_target_rank = None
                            movement_target_score = None
                            movement_target_heading_delta_deg = None
                            movement_target_continuity_flags = None
                        geometry = _offset_point_by_bearing(Point, center, movement_heading, movement_offset_m)
                        register_feature(
                            {
                                "node_object_id": (
                                    f"{zone_id}::movement::{_sanitize_token(source_endpoint_id)}::"
                                    f"{_sanitize_token(turn_label)}::{_sanitize_token(outgoing_arm_id or f'candidate_{target_index}')}"
                                ),
                                "junction_id": row.get("junction_id"),
                                "source_system": "bari_movement_object_builder",
                                "object_type": "movement_object",
                                "node_role": "turn_movement",
                                "movement_role": "unsignalized_turn_movement",
                                "movement_turn": turn_label,
                                "name": f"{base_name} [{source_compass or source_endpoint_id} {turn_label}]",
                                "parent_object_id": zone_id,
                                "parent_object_type": "conflict_zone",
                                "movement_source_zone_id": zone_id,
                                "movement_source_zone_type": zone_type,
                                "movement_source_parent_object_id": row.get("parent_object_id"),
                                "movement_family": row.get("movement_family"),
                                "control_state": row.get("control_state"),
                                "crossing_protection_state": row.get("crossing_protection_state"),
                                "turn_path_class": row.get("turn_path_class"),
                                "movement_arm_count": row.get("movement_arm_count"),
                                "priority_rule": row.get("priority_rule"),
                                "control_detail": row.get("control_detail"),
                                "approach_node_ref": node_ref,
                                "incoming_arm_id": source_endpoint_id,
                                "incoming_bearing_deg": float(source_bearing),
                                "incoming_compass": source_compass,
                                "outgoing_arm_id": outgoing_arm_id,
                                "outgoing_bearing_deg": outgoing_bearing_deg,
                                "outgoing_compass": outgoing_compass,
                                "candidate_target_arm_count": int(len(ranked_candidates)),
                                "candidate_target_arm_catalog": target_catalog,
                                "movement_resolution_state": resolution_state,
                                "movement_resolution_method": resolution_method,
                                "movement_target_rank": movement_target_rank,
                                "movement_target_score": movement_target_score,
                                "movement_target_heading_delta_deg": movement_target_heading_delta_deg,
                                "movement_target_continuity_flags": movement_target_continuity_flags,
                                "signal_priority_variant": _signal_priority_variant(
                                    movement_role="unsignalized_turn_movement",
                                    priority_rule=row.get("priority_rule"),
                                ),
                                "phase_priority_group": _phase_priority_group(
                                    movement_role="unsignalized_turn_movement",
                                    movement_turn=turn_label,
                                    priority_rule=row.get("priority_rule"),
                                ),
                                "maneuver_complexity": row.get("maneuver_complexity"),
                                "roundabout_component_role": row.get("roundabout_component_role"),
                                "segment_id": row.get("segment_id"),
                                "segment_highway": row.get("segment_highway"),
                                "segment_name": row.get("segment_name"),
                                "segment_ref": row.get("segment_ref"),
                                "segment_junction": row.get("segment_junction"),
                                "geometry": geometry,
                            }
                        )
            continue

        if zone_type == "roundabout_conflict_zone":
            register_feature(
                {
                    "node_object_id": f"{zone_id}::movement::circulate",
                    "junction_id": row.get("junction_id"),
                    "source_system": "bari_movement_object_builder",
                    "object_type": "movement_object",
                    "node_role": "roundabout_circulatory_movement",
                    "movement_role": "roundabout_circulatory_movement",
                    "movement_turn": "circulate",
                    "name": f"{base_name} [circulate]",
                    "parent_object_id": zone_id,
                    "parent_object_type": "conflict_zone",
                    "movement_source_zone_id": zone_id,
                    "movement_source_zone_type": zone_type,
                    "movement_source_parent_object_id": row.get("parent_object_id"),
                    "movement_family": row.get("movement_family"),
                    "control_state": row.get("control_state"),
                    "crossing_protection_state": row.get("crossing_protection_state"),
                    "turn_path_class": row.get("turn_path_class"),
                    "movement_arm_count": row.get("movement_arm_count"),
                    "priority_rule": row.get("priority_rule"),
                    "control_detail": row.get("control_detail"),
                    "approach_node_ref": row.get("approach_node_ref"),
                    "incoming_arm_id": None,
                    "incoming_bearing_deg": None,
                    "incoming_compass": None,
                    "outgoing_arm_id": None,
                    "outgoing_bearing_deg": None,
                    "outgoing_compass": None,
                    "candidate_target_arm_count": 0,
                    "candidate_target_arm_catalog": None,
                    "movement_resolution_state": "circulatory_fallback",
                    "movement_resolution_method": "roundabout_core_placeholder",
                    "movement_target_rank": None,
                    "movement_target_score": None,
                    "movement_target_heading_delta_deg": None,
                    "movement_target_continuity_flags": None,
                    "signal_priority_variant": _signal_priority_variant(
                        movement_role="roundabout_circulatory_movement",
                        priority_rule=row.get("priority_rule"),
                    ),
                    "phase_priority_group": _phase_priority_group(
                        movement_role="roundabout_circulatory_movement",
                        movement_turn="circulate",
                        priority_rule=row.get("priority_rule"),
                    ),
                    "maneuver_complexity": row.get("maneuver_complexity"),
                    "roundabout_component_role": "core",
                    "segment_id": row.get("segment_id"),
                    "segment_highway": row.get("segment_highway"),
                    "segment_name": row.get("segment_name"),
                    "segment_ref": row.get("segment_ref"),
                    "segment_junction": row.get("segment_junction"),
                    "geometry": center,
                }
            )

    movement_gdf = (
        gpd.GeoDataFrame(features, geometry="geometry", crs=local_crs)
        if features
        else _empty_geodataframe(gpd, local_crs)
    ).to_crs(epsg=4326)
    geojson_path = output_root / "road_movement_objects.geojson"
    manifest_path = output_root / "road_movement_objects.manifest.json"
    movement_gdf.to_file(geojson_path, driver="GeoJSON")

    return _format_output_manifest(
        manifest_path=manifest_path,
        source={
            "adapter": "bari_movement_object_builder",
            "conflict_zones_source_path": str(conflict_zones_input),
            "conflict_zones_source_sha256": _sha256(conflict_zones_input),
            "segments_source_path": str(segments_input),
            "segments_source_sha256": _sha256(segments_input),
        },
        inputs={
            "conflict_zones_path": str(conflict_zones_input),
            "conflict_zones_sha256": _sha256(conflict_zones_input),
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "movement_offset_m": float(movement_offset_m),
            "target_resolution_max_heading_delta_deg": float(target_resolution_max_heading_delta_deg),
            "target_resolution_min_score_gap": float(target_resolution_min_score_gap),
        },
        outputs={
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "manifest_path": str(manifest_path),
        },
        stats={
            "source_conflict_zone_count": int(len(projected_zones)),
            "movement_object_count": int(len(movement_gdf)),
            "movement_role_counts": dict(sorted(movement_role_counts.items())),
            "movement_turn_counts": dict(sorted(movement_turn_counts.items())),
            "movement_resolution_state_counts": dict(sorted(movement_resolution_state_counts.items())),
            "movement_resolution_method_counts": dict(sorted(movement_resolution_method_counts.items())),
            "signal_priority_variant_counts": dict(sorted(signal_priority_variant_counts.items())),
            "phase_priority_group_counts": dict(sorted(phase_priority_group_counts.items())),
        },
    )
