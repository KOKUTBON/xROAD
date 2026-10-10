"""Road-network extraction and segment generation."""

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


def load_geospatial_stack() -> Any:
    try:
        import osmnx as ox  # type: ignore
        import geopandas as gpd  # type: ignore
        from shapely.geometry import box  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "OSMnx is not installed. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return ox, gpd, box


def _geometry_union(geometries: Any) -> Any:
    if hasattr(geometries, "union_all"):
        return geometries.union_all()
    return geometries.unary_union


def _write_segment_outputs(
    segments: Any,
    boundary: Any,
    output_root: Path,
    manifest_inputs: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Any]:
    geojson_path = output_root / "road_segments.geojson"
    boundary_path = output_root / "boundary.geojson"
    manifest_path = output_root / "road_segments.manifest.json"
    segments.to_file(geojson_path, driver="GeoJSON")
    boundary.to_file(boundary_path, driver="GeoJSON")

    manifest = {
        "inputs": manifest_inputs,
        "outputs": {
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "boundary_path": str(boundary_path),
            "boundary_sha256": _sha256(boundary_path),
            "manifest_path": str(manifest_path),
        },
        "stats": stats,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _write_boundary_outputs(
    boundary: Any,
    output_root: Path,
    manifest_inputs: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Any]:
    boundary_path = output_root / "boundary.geojson"
    manifest_path = output_root / "boundary.manifest.json"
    boundary.to_file(boundary_path, driver="GeoJSON")

    manifest = {
        "inputs": manifest_inputs,
        "outputs": {
            "boundary_path": str(boundary_path),
            "boundary_sha256": _sha256(boundary_path),
            "manifest_path": str(manifest_path),
        },
        "stats": stats,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def extract_boundary_from_place(
    place_query: str,
    output_dir: str | Path,
) -> dict[str, Any]:
    ox, _gpd, _box = load_geospatial_stack()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    boundary = ox.geocode_to_gdf(place_query)
    local_crs = boundary.estimate_utm_crs() or "EPSG:3857"
    projected_boundary = boundary.to_crs(local_crs)
    min_x, min_y, max_x, max_y = projected_boundary.total_bounds
    area_m2 = float(projected_boundary.geometry.area.sum())

    return _write_boundary_outputs(
        boundary=boundary,
        output_root=output_root,
        manifest_inputs={
            "place_query": place_query,
            "boundary_source": "place_query",
        },
        stats={
            "feature_count": int(len(boundary)),
            "area_m2": area_m2,
            "area_km2": float(area_m2 / 1_000_000.0),
            "bbox_min_x": float(min_x),
            "bbox_min_y": float(min_y),
            "bbox_max_x": float(max_x),
            "bbox_max_y": float(max_y),
        },
    )


def extract_segments_from_place(
    place_query: str,
    output_dir: str | Path,
    network_type: str = "drive",
) -> dict[str, Any]:
    ox, _gpd, _box = load_geospatial_stack()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    boundary = ox.geocode_to_gdf(place_query)
    graph = ox.graph_from_place(place_query, network_type=network_type)
    edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()
    local_crs = edges.estimate_utm_crs() or "EPSG:3857"
    projected_edges = edges.to_crs(local_crs)
    projected_edges["segment_id"] = projected_edges.apply(
        lambda row: f"{network_type}:{row['u']}:{row['v']}:{row['key']}",
        axis=1,
    )
    projected_edges["segment_length_m"] = projected_edges.geometry.length
    segments = projected_edges.to_crs(epsg=4326)
    return _write_segment_outputs(
        segments=segments,
        boundary=boundary,
        output_root=output_root,
        manifest_inputs={
            "place_query": place_query,
            "network_type": network_type,
            "boundary_source": "place_query",
        },
        stats={
            "segment_count": int(len(segments)),
            "total_length_m": float(segments["segment_length_m"].sum()),
            "mean_length_m": float(segments["segment_length_m"].mean()),
        },
    )


def extract_segments_from_boundary(
    boundary_path: str | Path,
    output_dir: str | Path,
    network_type: str = "drive",
) -> dict[str, Any]:
    ox, gpd, _box = load_geospatial_stack()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    boundary_input = Path(boundary_path)
    boundary = gpd.read_file(boundary_input)
    if boundary.empty:
        raise RuntimeError(f"Boundary input is empty: {boundary_input}")
    if boundary.crs is None:
        boundary = boundary.set_crs(epsg=4326)

    boundary_wgs84 = boundary.to_crs(epsg=4326)
    boundary_geometry = _geometry_union(boundary_wgs84.geometry)
    if boundary_geometry.is_empty:
        raise RuntimeError(f"Boundary input has empty geometry: {boundary_input}")
    if not boundary_geometry.is_valid:
        boundary_geometry = boundary_geometry.buffer(0)
    if boundary_geometry.is_empty:
        raise RuntimeError(f"Boundary input could not be repaired into a valid geometry: {boundary_input}")

    graph = ox.graph_from_polygon(boundary_geometry, network_type=network_type)
    edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()
    local_crs = edges.estimate_utm_crs() or boundary.estimate_utm_crs() or "EPSG:3857"
    projected_edges = edges.to_crs(local_crs)
    projected_edges["segment_id"] = projected_edges.apply(
        lambda row: f"{network_type}:{row['u']}:{row['v']}:{row['key']}",
        axis=1,
    )
    projected_edges["segment_length_m"] = projected_edges.geometry.length
    segments = projected_edges.to_crs(epsg=4326)
    projected_boundary = boundary_wgs84.to_crs(local_crs)
    area_m2 = float(projected_boundary.geometry.area.sum())

    return _write_segment_outputs(
        segments=segments,
        boundary=boundary_wgs84,
        output_root=output_root,
        manifest_inputs={
            "boundary_path": str(boundary_input),
            "boundary_sha256": _sha256(boundary_input),
            "network_type": network_type,
            "boundary_source": "boundary_geojson",
        },
        stats={
            "segment_count": int(len(segments)),
            "total_length_m": float(segments["segment_length_m"].sum()),
            "mean_length_m": float(segments["segment_length_m"].mean()),
            "boundary_area_m2": area_m2,
            "boundary_area_km2": float(area_m2 / 1_000_000.0),
        },
    )


def compare_boundaries(
    reference_boundary_path: str | Path,
    candidate_boundary_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    _ox, gpd, _box = load_geospatial_stack()
    reference_input = Path(reference_boundary_path)
    candidate_input = Path(candidate_boundary_path)

    reference = gpd.read_file(reference_input)
    candidate = gpd.read_file(candidate_input)
    if reference.empty or candidate.empty:
        raise RuntimeError("Boundary comparison requires non-empty GeoJSON inputs.")

    if reference.crs is None:
        reference = reference.set_crs(epsg=4326)
    if candidate.crs is None:
        candidate = candidate.set_crs(epsg=4326)

    local_crs = reference.estimate_utm_crs() or candidate.estimate_utm_crs() or "EPSG:3857"
    projected_reference = reference.to_crs(local_crs)
    projected_candidate = candidate.to_crs(local_crs)

    reference_geom = _geometry_union(projected_reference.geometry)
    candidate_geom = _geometry_union(projected_candidate.geometry)
    intersection = reference_geom.intersection(candidate_geom)
    union = reference_geom.union(candidate_geom)

    reference_area_m2 = float(reference_geom.area)
    candidate_area_m2 = float(candidate_geom.area)
    intersection_area_m2 = float(intersection.area)
    union_area_m2 = float(union.area)

    report = {
        "inputs": {
            "reference_boundary_path": str(reference_input),
            "reference_boundary_sha256": _sha256(reference_input),
            "candidate_boundary_path": str(candidate_input),
            "candidate_boundary_sha256": _sha256(candidate_input),
        },
        "stats": {
            "reference_area_m2": reference_area_m2,
            "reference_area_km2": float(reference_area_m2 / 1_000_000.0),
            "candidate_area_m2": candidate_area_m2,
            "candidate_area_km2": float(candidate_area_m2 / 1_000_000.0),
            "intersection_area_m2": intersection_area_m2,
            "intersection_area_km2": float(intersection_area_m2 / 1_000_000.0),
            "union_area_m2": union_area_m2,
            "union_area_km2": float(union_area_m2 / 1_000_000.0),
            "intersection_over_union": float(intersection_area_m2 / union_area_m2) if union_area_m2 else 0.0,
            "reference_coverage_ratio": (
                float(intersection_area_m2 / reference_area_m2) if reference_area_m2 else 0.0
            ),
            "candidate_within_reference_ratio": (
                float(intersection_area_m2 / candidate_area_m2) if candidate_area_m2 else 0.0
            ),
        },
    }

    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        report["outputs"] = {
            "report_path": str(output_file),
            "report_sha256": _sha256(output_file),
        }

    return report


def extract_segments_from_records_bbox(
    records_path: str | Path,
    output_dir: str | Path,
    network_type: str = "drive",
    pad_m: float = 1500.0,
    trim_quantile: float = 0.0,
) -> dict[str, Any]:
    ox, gpd, box = load_geospatial_stack()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    records_input = Path(records_path)
    records: list[dict[str, Any]] = []
    with records_input.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("latitude") is None or record.get("longitude") is None:
                continue
            records.append(record)

    if not records:
        raise RuntimeError(f"No coordinate-complete records available for bbox extraction: {records_input}")

    points = gpd.GeoDataFrame(
        records,
        geometry=gpd.points_from_xy(
            [float(record["longitude"]) for record in records],
            [float(record["latitude"]) for record in records],
        ),
        crs="EPSG:4326",
    )
    local_crs = points.estimate_utm_crs() or "EPSG:3857"
    projected_points = points.to_crs(local_crs)
    filtered_points = projected_points
    if not (0.0 <= trim_quantile < 0.5):
        raise RuntimeError("trim_quantile must be >= 0.0 and < 0.5.")
    if trim_quantile > 0.0:
        lower_x = float(projected_points.geometry.x.quantile(trim_quantile))
        upper_x = float(projected_points.geometry.x.quantile(1.0 - trim_quantile))
        lower_y = float(projected_points.geometry.y.quantile(trim_quantile))
        upper_y = float(projected_points.geometry.y.quantile(1.0 - trim_quantile))
        filtered_points = projected_points.loc[
            projected_points.geometry.x.between(lower_x, upper_x)
            & projected_points.geometry.y.between(lower_y, upper_y)
        ].copy()
        if filtered_points.empty:
            raise RuntimeError("Spatial trim removed all points from the records bbox extraction input.")

    min_x, min_y, max_x, max_y = filtered_points.total_bounds
    min_x -= pad_m
    min_y -= pad_m
    max_x += pad_m
    max_y += pad_m

    projected_boundary = gpd.GeoDataFrame(
        [{"boundary_type": "records_bbox", "pad_m": float(pad_m)}],
        geometry=[box(min_x, min_y, max_x, max_y)],
        crs=local_crs,
    )
    boundary = projected_boundary.to_crs(epsg=4326)
    north = float(boundary.total_bounds[3])
    south = float(boundary.total_bounds[1])
    east = float(boundary.total_bounds[2])
    west = float(boundary.total_bounds[0])

    graph = ox.graph_from_bbox((west, south, east, north), network_type=network_type)
    edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()
    projected_edges = edges.to_crs(local_crs)
    projected_edges["segment_id"] = projected_edges.apply(
        lambda row: f"{network_type}:{row['u']}:{row['v']}:{row['key']}",
        axis=1,
    )
    projected_edges["segment_length_m"] = projected_edges.geometry.length
    segments = projected_edges.to_crs(epsg=4326)

    return _write_segment_outputs(
        segments=segments,
        boundary=boundary,
        output_root=output_root,
        manifest_inputs={
            "records_path": str(records_input),
            "records_sha256": _sha256(records_input),
            "network_type": network_type,
            "pad_m": pad_m,
            "trim_quantile": trim_quantile,
            "boundary_source": "records_bbox",
        },
        stats={
            "input_records_with_coordinates": int(len(records)),
            "retained_records_for_bbox": int(len(filtered_points)),
            "segment_count": int(len(segments)),
            "total_length_m": float(segments["segment_length_m"].sum()),
            "mean_length_m": float(segments["segment_length_m"].mean()),
            "bbox_north": north,
            "bbox_south": south,
            "bbox_east": east,
            "bbox_west": west,
        },
    )
