"""Static segment enrichment for topology and geometry features."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .exposure_policy import (
    BUILT_ENV_COUNT_COLUMNS,
    EXPOSURE_NUMERIC_COLUMNS,
    EXPOSURE_POLICY_VERSION,
    POI_COUNT_COLUMNS,
    apply_exposure_policy,
)


ROAD_CLASS_RANK = {
    "motorway": 8,
    "trunk": 7,
    "primary": 6,
    "secondary": 5,
    "tertiary": 4,
    "unclassified": 3,
    "residential": 2,
    "living_street": 1,
    "service": 1,
}

OSM_CONTEXT_TAGS = {
    "amenity": True,
    "shop": True,
    "office": True,
    "landuse": ["residential", "commercial", "retail", "industrial"],
    "public_transport": True,
    "highway": ["bus_stop"],
    "railway": ["station", "halt", "tram_stop", "subway_entrance"],
}

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
            "GeoPandas and pandas are required for segment enrichment. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, pd


def _load_osmnx() -> Any:
    try:
        import osmnx as ox  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "OSMnx is required for OSM context enrichment. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return ox


def _normalize_list_like(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return None
        first = inner.split(",")[0].strip().strip("'").strip('"')
        return first or None
    return text


def _road_class_rank(highway_value: Any) -> int:
    normalized = _normalize_list_like(highway_value)
    if not normalized:
        return 0
    return ROAD_CLASS_RANK.get(normalized.split("|")[0], 0)


def _extract_numeric(value: Any) -> float | None:
    text = _normalize_list_like(value)
    if text is None:
        return None
    match = ""
    for char in text:
        if char.isdigit() or char == ".":
            match += char
        elif match:
            break
    return float(match) if match else None


def _bearing_bin(bearing_deg: float) -> str:
    bins = [
        (22.5, "N"),
        (67.5, "NE"),
        (112.5, "E"),
        (157.5, "SE"),
        (202.5, "S"),
        (247.5, "SW"),
        (292.5, "W"),
        (337.5, "NW"),
        (360.0, "N"),
    ]
    for limit, label in bins:
        if bearing_deg < limit:
            return label
    return "N"


def _geometry_metrics(geometry: Any) -> tuple[float, float, float]:
    if geometry is None or geometry.is_empty:
        return 0.0, 1.0, 0.0
    try:
        coords = list(geometry.coords)
    except NotImplementedError:
        merged = geometry.geoms[0] if hasattr(geometry, "geoms") and geometry.geoms else None
        coords = list(merged.coords) if merged is not None else []
    if len(coords) < 2:
        return 0.0, 1.0, 0.0

    x1, y1 = coords[0]
    x2, y2 = coords[-1]
    straight_distance_m = math.hypot(x2 - x1, y2 - y1)
    segment_length_m = float(geometry.length)
    if straight_distance_m <= 0:
        sinuosity = 1.0
        bearing_deg = 0.0
    else:
        sinuosity = max(1.0, segment_length_m / straight_distance_m)
        bearing_deg = (math.degrees(math.atan2(x2 - x1, y2 - y1)) + 360.0) % 360.0
    return straight_distance_m, sinuosity, bearing_deg


def _fetch_osm_context_features(boundary_polygon: Any) -> Any:
    ox = _load_osmnx()
    try:
        return ox.features_from_polygon(boundary_polygon, OSM_CONTEXT_TAGS)
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch OSM context features: {exc}") from exc


CONTEXT_COUNT_COLUMNS = POI_COUNT_COLUMNS + BUILT_ENV_COUNT_COLUMNS


def _classify_context_features(features: Any, pd: Any) -> Any:
    working = features.copy()

    def _series(name: str) -> Any:
        if name not in working.columns:
            return pd.Series([None] * len(working), index=working.index)
        return working[name].map(_normalize_list_like)

    amenity = _series("amenity")
    shop = _series("shop")
    public_transport = _series("public_transport")
    highway = _series("highway")
    railway = _series("railway")
    tourism = _series("tourism")
    leisure = _series("leisure")
    landuse = _series("landuse")
    building = _series("building")
    office = _series("office")

    education_amenities = {"school", "university", "college", "kindergarten", "library"}
    healthcare_amenities = {"hospital", "clinic", "doctors", "pharmacy", "dentist", "social_facility"}
    hospitality_amenities = {"restaurant", "cafe", "bar", "pub", "fast_food", "ice_cream"}
    hospitality_tourism = {"hotel", "hostel", "guest_house", "motel", "apartment"}
    transit_railway = {"station", "halt", "tram_stop", "subway_entrance"}
    residential_buildings = {"apartments", "detached", "house", "residential", "semidetached_house", "terrace"}
    commercial_buildings = {"commercial", "office", "retail", "supermarket"}

    working["poi_any_count"] = 1
    working["poi_education_count"] = amenity.isin(education_amenities).astype(int)
    working["poi_healthcare_count"] = amenity.isin(healthcare_amenities).astype(int)
    working["poi_transit_count"] = (
        public_transport.notna()
        | highway.isin({"bus_stop"})
        | railway.isin(transit_railway)
    ).astype(int)
    working["poi_retail_count"] = shop.notna().astype(int)
    working["poi_hospitality_count"] = (
        amenity.isin(hospitality_amenities)
        | tourism.isin(hospitality_tourism)
    ).astype(int)
    working["poi_leisure_count"] = (tourism.notna() | leisure.notna()).astype(int)
    working["building_any_count"] = (building.notna() | office.notna()).astype(int)
    working["building_residential_count"] = (
        building.isin(residential_buildings) | landuse.isin({"residential"})
    ).astype(int)
    working["building_commercial_count"] = (
        building.isin(commercial_buildings)
        | office.notna()
        | shop.notna()
        | landuse.isin({"commercial", "retail"})
    ).astype(int)
    working["landuse_residential_count"] = landuse.isin({"residential"}).astype(int)
    working["landuse_commercial_count"] = landuse.isin({"commercial", "retail"}).astype(int)
    working["landuse_industrial_count"] = landuse.isin({"industrial"}).astype(int)
    return working


def apply_exposure_policy_to_segments(
    segments_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    gpd, pd = _load_geo_stack()

    segments_input = Path(segments_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    exposure_path = output_root / "road_segments_exposure.geojson"
    manifest_path = output_root / "road_segments_exposure.manifest.json"

    segments = gpd.read_file(segments_input)
    if "segment_id" not in segments.columns:
        raise RuntimeError(f"Segments file does not contain required 'segment_id' column: {segments_input}")

    enriched = apply_exposure_policy(segments, pd)
    enriched.to_file(exposure_path, driver="GeoJSON")

    manifest = {
        "inputs": {
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
        },
        "outputs": {
            "exposure_path": str(exposure_path),
            "exposure_sha256": _sha256(exposure_path),
            "manifest_path": str(manifest_path),
        },
        "policy": {
            "exposure_policy_version": EXPOSURE_POLICY_VERSION,
        },
        "stats": {
            "segment_count": int(len(enriched)),
            "mean_exposure_policy_index": float(
                pd.to_numeric(enriched["exposure_policy_index"], errors="coerce").fillna(0.0).mean()
            ),
            "mean_exposure_data_completeness": float(
                pd.to_numeric(enriched["exposure_data_completeness"], errors="coerce").fillna(0.0).mean()
            ),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def enrich_segments(
    segments_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    gpd, pd = _load_geo_stack()

    segments_input = Path(segments_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    enriched_path = output_root / "road_segments_enriched.geojson"
    manifest_path = output_root / "road_segments_enriched.manifest.json"

    segments = gpd.read_file(segments_input)
    required_columns = {"segment_id", "u", "v", "geometry"}
    missing_columns = required_columns.difference(segments.columns)
    if missing_columns:
        raise RuntimeError(f"Segments file is missing required columns: {sorted(missing_columns)}")

    node_neighbors: dict[Any, set[Any]] = defaultdict(set)
    for _, row in segments[["u", "v"]].dropna().iterrows():
        u = row["u"]
        v = row["v"]
        node_neighbors[u].add(v)
        node_neighbors[v].add(u)
    node_degree = {node: len(neighbors) for node, neighbors in node_neighbors.items()}

    local_crs = segments.estimate_utm_crs() or "EPSG:3857"
    projected = segments.to_crs(local_crs).copy()
    projected["node_degree_u"] = projected["u"].map(node_degree).fillna(0).astype(int)
    projected["node_degree_v"] = projected["v"].map(node_degree).fillna(0).astype(int)
    projected["node_degree_min"] = projected[["node_degree_u", "node_degree_v"]].min(axis=1).astype(int)
    projected["node_degree_max"] = projected[["node_degree_u", "node_degree_v"]].max(axis=1).astype(int)
    projected["node_degree_sum"] = (projected["node_degree_u"] + projected["node_degree_v"]).astype(int)
    projected["is_dead_end"] = (projected["node_degree_min"] <= 1).astype(int)
    projected["is_intersection_connector"] = (projected["node_degree_max"] >= 3).astype(int)

    geometry_metrics = projected.geometry.map(_geometry_metrics)
    projected["straight_distance_m"] = geometry_metrics.map(lambda values: values[0])
    projected["sinuosity"] = geometry_metrics.map(lambda values: values[1])
    projected["bearing_deg"] = geometry_metrics.map(lambda values: values[2])
    projected["bearing_bin"] = projected["bearing_deg"].map(_bearing_bin)
    projected["road_class_rank"] = projected["highway"].map(_road_class_rank).astype(int) if "highway" in projected.columns else 0
    projected["segment_name_present"] = (
        projected["name"].map(lambda value: 0 if _normalize_list_like(value) is None else 1).astype(int)
        if "name" in projected.columns
        else 0
    )

    enriched = projected.to_crs(epsg=4326)
    enriched.to_file(enriched_path, driver="GeoJSON")

    manifest = {
        "inputs": {
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
        },
        "outputs": {
            "enriched_path": str(enriched_path),
            "enriched_sha256": _sha256(enriched_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "segment_count": int(len(enriched)),
            "dead_end_segments": int(enriched["is_dead_end"].sum()),
            "intersection_connector_segments": int(enriched["is_intersection_connector"].sum()),
            "mean_sinuosity": float(pd.to_numeric(enriched["sinuosity"], errors="coerce").fillna(1.0).mean()),
            "mean_node_degree_max": float(pd.to_numeric(enriched["node_degree_max"], errors="coerce").fillna(0).mean()),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def enrich_segments_with_context(
    segments_path: str | Path,
    boundary_path: str | Path,
    output_dir: str | Path,
    poi_buffer_m: float = 150.0,
) -> dict[str, Any]:
    gpd, pd = _load_geo_stack()

    segments_input = Path(segments_path)
    boundary_input = Path(boundary_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    context_path = output_root / "road_segments_context.geojson"
    manifest_path = output_root / "road_segments_context.manifest.json"

    segments = gpd.read_file(segments_input)
    boundary = gpd.read_file(boundary_input)
    if "segment_id" not in segments.columns:
        raise RuntimeError(f"Segments file does not contain required 'segment_id' column: {segments_input}")

    boundary_union = boundary.to_crs(epsg=4326).union_all()
    pois = _fetch_osm_context_features(boundary_union)
    pois = pois.reset_index(drop=True)
    pois = pois.loc[pois.geometry.notna() & (~pois.geometry.is_empty)].copy()
    if not pois.empty:
        pois = _classify_context_features(pois, pd)
        pois["geometry"] = pois.geometry.representative_point()

        local_crs = segments.estimate_utm_crs() or "EPSG:3857"
        projected_segments = segments.to_crs(local_crs)
        projected_pois = pois.to_crs(local_crs)
        segment_buffers = projected_segments[["segment_id", "geometry"]].copy()
        segment_buffers["geometry"] = segment_buffers.geometry.buffer(poi_buffer_m)

        joined = gpd.sjoin(
            projected_pois[CONTEXT_COUNT_COLUMNS + ["geometry"]],
            segment_buffers,
            how="inner",
            predicate="within",
        )
        poi_counts = (
            joined.groupby("segment_id", as_index=False)[CONTEXT_COUNT_COLUMNS]
            .sum()
        )
    else:
        poi_counts = pd.DataFrame(columns=["segment_id"] + CONTEXT_COUNT_COLUMNS)

    enriched = segments.merge(poi_counts, on="segment_id", how="left")
    for column in CONTEXT_COUNT_COLUMNS:
        enriched[column] = pd.to_numeric(enriched.get(column, 0), errors="coerce").fillna(0).astype(int)
    enriched = apply_exposure_policy(enriched, pd)
    enriched.to_file(context_path, driver="GeoJSON")

    manifest = {
        "inputs": {
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "boundary_path": str(boundary_input),
            "boundary_sha256": _sha256(boundary_input),
        },
        "outputs": {
            "context_path": str(context_path),
            "context_sha256": _sha256(context_path),
            "manifest_path": str(manifest_path),
        },
        "policy": {
            "poi_buffer_m": poi_buffer_m,
            "exposure_policy_version": EXPOSURE_POLICY_VERSION,
        },
        "stats": {
            "segment_count": int(len(enriched)),
            "poi_features_retrieved": int(len(pois)),
            "segments_with_any_poi": int((enriched["poi_any_count"] > 0).sum()),
            "total_poi_links": int(enriched["poi_any_count"].sum()),
            "segments_with_any_built_environment": int((enriched["building_any_count"] > 0).sum()),
            "total_built_environment_links": int(enriched["building_any_count"].sum()),
            "mean_exposure_proxy_index": float(pd.to_numeric(enriched["exposure_proxy_index"], errors="coerce").fillna(0.0).mean()),
            "mean_exposure_policy_index": float(pd.to_numeric(enriched["exposure_policy_index"], errors="coerce").fillna(0.0).mean()),
            "mean_exposure_built_environment_index": float(
                pd.to_numeric(enriched["exposure_built_environment_index"], errors="coerce").fillna(0.0).mean()
            ),
            "mean_exposure_population_proxy_index": float(
                pd.to_numeric(enriched["exposure_population_proxy_index"], errors="coerce").fillna(0.0).mean()
            ),
            "mean_exposure_data_completeness": float(
                pd.to_numeric(enriched["exposure_data_completeness"], errors="coerce").fillna(0.0).mean()
            ),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
