"""Versioned exposure-policy utilities for segment layers."""

from __future__ import annotations

import math
from typing import Any


EXPOSURE_POLICY_VERSION = "segment_exposure_v2_static_context_built_env"

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

POI_COUNT_COLUMNS = [
    "poi_any_count",
    "poi_education_count",
    "poi_healthcare_count",
    "poi_transit_count",
    "poi_retail_count",
    "poi_hospitality_count",
    "poi_leisure_count",
]

BUILT_ENV_COUNT_COLUMNS = [
    "building_any_count",
    "building_residential_count",
    "building_commercial_count",
    "landuse_residential_count",
    "landuse_commercial_count",
    "landuse_industrial_count",
]

EXPOSURE_NUMERIC_COLUMNS = [
    "exposure_policy_index",
    "exposure_movement_index",
    "exposure_activity_index",
    "exposure_network_index",
    "exposure_built_environment_index",
    "exposure_population_proxy_index",
    "exposure_data_completeness",
    "exposure_weighted_poi_score",
]

EXPOSURE_MODEL_NUMERIC_COLUMNS = [
    "exposure_movement_index",
    "exposure_activity_index",
    "exposure_network_index",
    "exposure_built_environment_index",
    "exposure_population_proxy_index",
    "exposure_data_completeness",
    "exposure_weighted_poi_score",
]


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


def _coerce_numeric_series(frame: Any, pd: Any, preferred: str, fallback: str | None = None) -> Any:
    if preferred in frame.columns:
        return pd.to_numeric(frame[preferred], errors="coerce")
    if fallback is not None and fallback in frame.columns:
        return frame[fallback].map(_extract_numeric)
    return pd.Series([None] * len(frame), index=frame.index, dtype="float64")


def _coerce_indicator_series(frame: Any, pd: Any, column: str, default: float = 0.0) -> Any:
    if column not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _road_class_rank(frame: Any, pd: Any) -> Any:
    if "road_class_rank" in frame.columns:
        return pd.to_numeric(frame["road_class_rank"], errors="coerce")
    if "highway" not in frame.columns:
        return pd.Series([None] * len(frame), index=frame.index, dtype="float64")
    normalized = frame["highway"].map(_normalize_list_like).fillna("")
    return normalized.map(lambda value: ROAD_CLASS_RANK.get(value.split("|")[0], 0) if value else None)


def apply_exposure_policy(frame: Any, pd: Any) -> Any:
    working = frame.copy()

    segment_length_m = _coerce_numeric_series(working, pd, "segment_length_m").fillna(0.0).clip(lower=1.0)
    lanes_numeric = _coerce_numeric_series(working, pd, "lanes_numeric", "lanes")
    maxspeed_numeric = _coerce_numeric_series(working, pd, "maxspeed_numeric", "maxspeed")
    width_numeric = _coerce_numeric_series(working, pd, "width_numeric", "width")
    road_class_rank = _road_class_rank(working, pd)
    node_degree_max = _coerce_indicator_series(working, pd, "node_degree_max", default=0.0)
    is_dead_end = _coerce_indicator_series(working, pd, "is_dead_end", default=0.0).clip(lower=0.0, upper=1.0)
    is_intersection_connector = _coerce_indicator_series(
        working,
        pd,
        "is_intersection_connector",
        default=0.0,
    ).clip(lower=0.0, upper=1.0)
    segment_name_present = _coerce_indicator_series(working, pd, "segment_name_present", default=0.0).clip(
        lower=0.0,
        upper=1.0,
    )

    lanes_for_policy = lanes_numeric.fillna(1.0).clip(lower=1.0, upper=6.0)
    maxspeed_for_policy = maxspeed_numeric.fillna(30.0).clip(lower=10.0, upper=130.0)
    width_for_policy = width_numeric.fillna(7.0).clip(lower=3.0, upper=20.0)
    road_class_for_policy = road_class_rank.fillna(2.0).clip(lower=0.0, upper=8.0)

    poi_any_count = _coerce_indicator_series(working, pd, "poi_any_count", default=0.0)
    poi_education_count = _coerce_indicator_series(working, pd, "poi_education_count", default=0.0)
    poi_healthcare_count = _coerce_indicator_series(working, pd, "poi_healthcare_count", default=0.0)
    poi_transit_count = _coerce_indicator_series(working, pd, "poi_transit_count", default=0.0)
    poi_retail_count = _coerce_indicator_series(working, pd, "poi_retail_count", default=0.0)
    poi_hospitality_count = _coerce_indicator_series(working, pd, "poi_hospitality_count", default=0.0)
    poi_leisure_count = _coerce_indicator_series(working, pd, "poi_leisure_count", default=0.0)
    building_any_count = _coerce_indicator_series(working, pd, "building_any_count", default=0.0)
    building_residential_count = _coerce_indicator_series(working, pd, "building_residential_count", default=0.0)
    building_commercial_count = _coerce_indicator_series(working, pd, "building_commercial_count", default=0.0)
    landuse_residential_count = _coerce_indicator_series(working, pd, "landuse_residential_count", default=0.0)
    landuse_commercial_count = _coerce_indicator_series(working, pd, "landuse_commercial_count", default=0.0)
    landuse_industrial_count = _coerce_indicator_series(working, pd, "landuse_industrial_count", default=0.0)

    length_km = (segment_length_m / 1000.0).clip(lower=0.01)
    lane_factor = (0.75 + (lanes_for_policy / 4.0)).clip(lower=0.8, upper=2.25)
    speed_factor = (0.5 + (maxspeed_for_policy / 60.0)).clip(lower=0.6, upper=2.7)
    width_factor = (0.6 + (width_for_policy / 10.0)).clip(lower=0.8, upper=2.6)
    class_factor = 1.0 + (road_class_for_policy / 8.0)

    weighted_poi_score = (
        poi_any_count
        + (1.2 * poi_education_count)
        + (1.4 * poi_healthcare_count)
        + (1.2 * poi_transit_count)
        + (1.0 * poi_retail_count)
        + (0.8 * poi_hospitality_count)
        + (0.6 * poi_leisure_count)
    )
    built_environment_score = (
        (0.8 * building_any_count)
        + (1.4 * building_residential_count)
        + (1.2 * building_commercial_count)
        + (1.8 * landuse_residential_count)
        + (1.4 * landuse_commercial_count)
        + (1.0 * landuse_industrial_count)
    )
    population_proxy_score = (
        (1.5 * building_residential_count)
        + (2.0 * landuse_residential_count)
        + (0.4 * building_any_count)
    )
    built_environment_index = 1.0 + built_environment_score.map(lambda value: math.log1p(float(value)) / 4.0)
    population_proxy_index = 1.0 + population_proxy_score.map(lambda value: math.log1p(float(value)) / 4.0)
    activity_signal = weighted_poi_score + (0.5 * landuse_commercial_count) + (0.35 * building_commercial_count)
    activity_index = 1.0 + activity_signal.map(lambda value: math.log1p(float(value)) / 3.0)
    network_index = (
        1.0
        + (node_degree_max.clip(lower=0.0, upper=8.0) / 10.0)
        + (0.2 * is_intersection_connector)
        + (0.05 * segment_name_present)
        - (0.1 * is_dead_end)
    ).clip(lower=0.5)
    movement_index = length_km * lane_factor * speed_factor * width_factor * class_factor

    poi_context_available = 1.0 if set(POI_COUNT_COLUMNS).issubset(set(working.columns)) else 0.0
    built_env_available = 1.0 if set(BUILT_ENV_COUNT_COLUMNS).issubset(set(working.columns)) else 0.0
    node_degree_available = 1.0 if "node_degree_max" in working.columns else 0.0
    completeness_components = [
        pd.Series([1.0] * len(working), index=working.index),
        lanes_numeric.notna().astype(float),
        maxspeed_numeric.notna().astype(float),
        width_numeric.notna().astype(float),
        road_class_rank.notna().astype(float),
        pd.Series([node_degree_available] * len(working), index=working.index),
        pd.Series([poi_context_available] * len(working), index=working.index),
        pd.Series([built_env_available] * len(working), index=working.index),
    ]
    exposure_data_completeness = sum(completeness_components) / float(len(completeness_components))
    confidence_factor = 0.8 + (0.2 * exposure_data_completeness)

    working["exposure_movement_index"] = movement_index
    working["exposure_activity_index"] = activity_index
    working["exposure_network_index"] = network_index
    working["exposure_built_environment_index"] = built_environment_index
    working["exposure_population_proxy_index"] = population_proxy_index
    working["exposure_weighted_poi_score"] = weighted_poi_score
    working["exposure_data_completeness"] = exposure_data_completeness
    working["exposure_policy_index"] = (
        movement_index
        * activity_index
        * network_index
        * built_environment_index
        * confidence_factor
    )
    working["exposure_proxy_index"] = working["exposure_policy_index"]
    working["exposure_policy_version"] = EXPOSURE_POLICY_VERSION
    return working
