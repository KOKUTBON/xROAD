"""Exposure-Normalized Segment-Time Panel Engine for Road Accident Occurrence Risk.

Implements the core recommendations of the Research Audit:
1. Target separation: models crash occurrence risk P(crash occurs | X) per road-segment x week,
   incorporating traffic exposure explicitly: E_{s,t} = AADT_s * L_s * 7.
2. Exposure offset: log(E_{s,t}) offset for Poisson / Negative-Binomial count models.
3. CRS-safe metric spatial snapping with threshold (30-50m) retaining road_distance_m.
4. Strictly causal temporal join: merge_asof backward join for weather (no future leakage).
5. Leakage blacklist: strips post-crash attributes (fatalities, injuries, citations, damages).
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _sha256

SEGMENT_PANEL_ENGINE_VERSION = "segment_panel_v1"
PANEL_CONTRACT_VERSION = "segment_panel_public_v1"
PRIMARY_UNIT = "segment_week"
EXPOSURE_UNIT = "vehicle_km"

LEAKAGE_BLACKLIST = frozenset({
    "fatality_count",
    "injury_count",
    "fatalities",
    "serious_injuries",
    "ambulance_called",
    "ambulance_response_min",
    "police_citation",
    "citation_issued",
    "investigation_result",
    "post_crash_investigation",
    "vehicle_damage",
    "vehicle_damage_cost",
    "crash_severity",
    "severity_class",
    "future_crash_count",
})


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return default if math.isnan(val) else float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "null", ""}:
        return default
    try:
        f = float(s)
        return default if math.isnan(f) else f
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    return int(round(_safe_float(val, float(default))))


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in meters between two coordinates."""
    r = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


@dataclass(frozen=True, slots=True)
class RoadSegmentRecord:
    """Roadway network segment with physical geometry and baseline exposure."""

    segment_id: str
    name: str
    latitude: float
    longitude: float
    length_km: float
    aadt: float
    road_class: str
    speed_limit_kmh: float = 50.0
    lanes: int = 2
    spatial_group: str = "group_default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "name": self.name,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "length_km": round(self.length_km, 3),
            "aadt": round(self.aadt, 1),
            "road_class": self.road_class,
            "speed_limit_kmh": round(self.speed_limit_kmh, 1),
            "lanes": self.lanes,
            "spatial_group": self.spatial_group,
        }


@dataclass(frozen=True, slots=True)
class CrashPointRecord:
    """A discrete historical accident record."""

    crash_id: str
    timestamp_utc: str
    latitude: float
    longitude: float
    severity: str = "slight"
    post_crash_attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "crash_id": self.crash_id,
            "timestamp_utc": self.timestamp_utc,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "severity": self.severity,
            "post_crash_attributes": self.post_crash_attributes,
        }


@dataclass(frozen=True, slots=True)
class WeatherRecord:
    """Historical meteorological observation from a weather station."""

    station_id: str
    timestamp_utc: str
    precipitation_mm: float
    temperature_c: float
    visibility_km: float = 10.0
    wind_speed_mps: float = 3.0
    is_severe: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "timestamp_utc": self.timestamp_utc,
            "precipitation_mm": round(self.precipitation_mm, 2),
            "temperature_c": round(self.temperature_c, 1),
            "visibility_km": round(self.visibility_km, 1),
            "wind_speed_mps": round(self.wind_speed_mps, 1),
            "is_severe": self.is_severe,
        }


@dataclass(frozen=True, slots=True)
class SegmentTimeObservation:
    """An analytical panel observation: one road segment during one calendar week."""

    segment_id: str
    spatial_group: str
    period_start: str
    period_end: str
    crash_count: int               # Primary occurrence target Y_{s,t}
    any_crash: int                 # Binary occurrence indicator (1 if crash_count >= 1 else 0)
    fatal_crash_count: int         # Fatal crash subset
    exposure_vehicle_km: float     # Traffic exposure E_{s,t} = AADT * length_km * 7
    log_exposure: float            # Offset term log(E_{s,t})
    length_km: float
    aadt: float
    speed_limit_kmh: float
    lanes: int
    precipitation_mm: float
    temperature_c: float
    is_wet: bool
    hour_sin: float = 0.0
    hour_cos: float = 1.0
    dow_sin: float = 0.0
    dow_cos: float = 1.0
    poi_density_250m: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "spatial_group": self.spatial_group,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "crash_count": self.crash_count,
            "any_crash": self.any_crash,
            "fatal_crash_count": self.fatal_crash_count,
            "exposure_vehicle_km": round(self.exposure_vehicle_km, 2),
            "log_exposure": round(self.log_exposure, 4),
            "length_km": round(self.length_km, 3),
            "aadt": round(self.aadt, 1),
            "speed_limit_kmh": round(self.speed_limit_kmh, 1),
            "lanes": self.lanes,
            "precipitation_mm": round(self.precipitation_mm, 2),
            "temperature_c": round(self.temperature_c, 1),
            "is_wet": self.is_wet,
            "hour_sin": round(self.hour_sin, 3),
            "hour_cos": round(self.hour_cos, 3),
            "dow_sin": round(self.dow_sin, 3),
            "dow_cos": round(self.dow_cos, 3),
            "poi_density_250m": self.poi_density_250m,
        }


@dataclass(frozen=True, slots=True)
class SegmentPanelDataset:
    """Assembled panel dataset ready for baseline & boosted tree modeling."""

    network_label: str
    total_segments: int
    total_periods: int
    total_observations: int
    total_crashes: int
    mean_exposure_vehicle_km: float
    observations: list[SegmentTimeObservation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel_engine_version": SEGMENT_PANEL_ENGINE_VERSION,
            "contract_version": PANEL_CONTRACT_VERSION,
            "unit": PRIMARY_UNIT,
            "exposure_unit": EXPOSURE_UNIT,
            "network_label": self.network_label,
            "total_segments": self.total_segments,
            "total_periods": self.total_periods,
            "total_observations": self.total_observations,
            "total_crashes": self.total_crashes,
            "mean_exposure_vehicle_km": round(self.mean_exposure_vehicle_km, 2),
            "observations": [o.to_dict() for o in self.observations],
        }


def snap_crashes_to_segments(
    crashes: Sequence[CrashPointRecord | Mapping[str, Any]],
    segments: Sequence[RoadSegmentRecord | Mapping[str, Any]],
    max_distance_m: float = 50.0,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Snap crashes to nearest road segment within metric distance threshold.

    Returns:
      (matched_by_segment, unmatched_crashes)
    """
    seg_records = [
        s if isinstance(s, RoadSegmentRecord) else RoadSegmentRecord(
            segment_id=str(s["segment_id"]),
            name=str(s.get("name") or s["segment_id"]),
            latitude=_safe_float(s.get("latitude")),
            longitude=_safe_float(s.get("longitude")),
            length_km=max(0.01, _safe_float(s.get("length_km"), 0.5)),
            aadt=max(10.0, _safe_float(s.get("aadt"), 5000.0)),
            road_class=str(s.get("road_class") or "urban_arterial"),
            speed_limit_kmh=_safe_float(s.get("speed_limit_kmh"), 50.0),
            lanes=_safe_int(s.get("lanes"), 2),
            spatial_group=str(s.get("spatial_group") or "group_default"),
        )
        for s in segments
    ]

    matched_by_seg: dict[str, list[dict[str, Any]]] = {s.segment_id: [] for s in seg_records}
    unmatched: list[dict[str, Any]] = []

    for raw_c in crashes:
        c_dict = raw_c.to_dict() if isinstance(raw_c, CrashPointRecord) else dict(raw_c)
        c_lat = _safe_float(c_dict.get("latitude"))
        c_lon = _safe_float(c_dict.get("longitude"))

        # Find nearest segment
        best_seg = None
        min_dist = float("inf")
        for s in seg_records:
            dist = haversine_distance_m(c_lat, c_lon, s.latitude, s.longitude)
            if dist < min_dist:
                min_dist = dist
                best_seg = s

        if best_seg is not None and min_dist <= max_distance_m:
            entry = dict(c_dict)
            entry["matched_segment_id"] = best_seg.segment_id
            entry["road_distance_m"] = round(min_dist, 2)
            matched_by_seg[best_seg.segment_id].append(entry)
        else:
            c_dict["road_distance_m"] = round(min_dist, 2) if min_dist != float("inf") else None
            unmatched.append(c_dict)

    return matched_by_seg, unmatched


def backward_join_weather(
    target_dt: datetime,
    weather_records: Sequence[WeatherRecord | Mapping[str, Any]],
    tolerance_hours: float = 2.0,
) -> dict[str, Any]:
    """Causal weather join: selects latest weather at or strictly before target_dt.

    Guarantees zero future data leakage (weather_timestamp <= target_dt).
    """
    valid_candidates: list[tuple[datetime, Mapping[str, Any]]] = []
    max_delta = timedelta(hours=tolerance_hours)

    for w in weather_records:
        w_dict = w.to_dict() if isinstance(w, WeatherRecord) else dict(w)
        ts_str = str(w_dict.get("timestamp_utc", ""))
        try:
            w_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        # Strictly causal check: weather must be observed before or at prediction time
        if w_dt <= target_dt and (target_dt - w_dt) <= max_delta:
            valid_candidates.append((w_dt, w_dict))

    if not valid_candidates:
        # Fallback default when station has a short gap
        return {
            "precipitation_mm": 0.0,
            "temperature_c": 18.0,
            "is_wet": False,
            "weather_joined_lag_minutes": None,
        }

    # Pick the most recent observation prior to target_dt
    valid_candidates.sort(key=lambda x: x[0], reverse=True)
    best_dt, best_w = valid_candidates[0]
    lag_min = (target_dt - best_dt).total_seconds() / 60.0
    precip = _safe_float(best_w.get("precipitation_mm"), 0.0)

    return {
        "precipitation_mm": precip,
        "temperature_c": _safe_float(best_w.get("temperature_c"), 18.0),
        "is_wet": precip > 0.2,
        "weather_joined_lag_minutes": round(lag_min, 1),
    }


def filter_leakage_features(raw_features: Mapping[str, Any]) -> dict[str, Any]:
    """Strip any feature present in the post-crash leakage blacklist."""
    cleaned = {}
    for k, v in raw_features.items():
        if k.lower() not in LEAKAGE_BLACKLIST:
            cleaned[k] = v
    return cleaned


def build_segment_week_panel(
    segments: Sequence[RoadSegmentRecord | Mapping[str, Any]],
    crashes: Sequence[CrashPointRecord | Mapping[str, Any]],
    weather: Sequence[WeatherRecord | Mapping[str, Any]] | None = None,
    weeks_count: int = 8,
    base_start_iso: str = "2026-01-05T00:00:00Z",
    network_label: str = "benchmark_network",
) -> SegmentPanelDataset:
    """Build a deterministic road-segment x week analytical panel with exposure terms."""
    seg_records = [
        s if isinstance(s, RoadSegmentRecord) else RoadSegmentRecord(
            segment_id=str(s["segment_id"]),
            name=str(s.get("name") or s["segment_id"]),
            latitude=_safe_float(s.get("latitude")),
            longitude=_safe_float(s.get("longitude")),
            length_km=max(0.01, _safe_float(s.get("length_km"), 0.5)),
            aadt=max(10.0, _safe_float(s.get("aadt"), 5000.0)),
            road_class=str(s.get("road_class") or "urban_arterial"),
            speed_limit_kmh=_safe_float(s.get("speed_limit_kmh"), 50.0),
            lanes=_safe_int(s.get("lanes"), 2),
            spatial_group=str(s.get("spatial_group") or "group_default"),
        )
        for s in segments
    ]

    matched_by_seg, _ = snap_crashes_to_segments(crashes, seg_records)
    weather_list = list(weather or [])

    start_dt = datetime.fromisoformat(base_start_iso.replace("Z", "+00:00"))
    observations: list[SegmentTimeObservation] = []
    total_crashes_count = 0

    for w_idx in range(weeks_count):
        p_start = start_dt + timedelta(weeks=w_idx)
        p_end = p_start + timedelta(days=7)
        p_start_str = p_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        p_end_str = p_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Temporal cyclic features based on week of year
        week_num = p_start.isocalendar()[1]
        dow_sin = math.sin(2.0 * math.pi * (w_idx % 52) / 52.0)
        dow_cos = math.cos(2.0 * math.pi * (w_idx % 52) / 52.0)

        # Causal weather joined at cutoff (period_start)
        weather_info = backward_join_weather(p_start, weather_list)

        for s in seg_records:
            # Calculate exposure: AADT * length_km * 7 days
            exposure_vkm = s.aadt * s.length_km * 7.0
            log_exp = math.log(max(1.0, exposure_vkm))

            # Count crashes occurring within [p_start, p_end)
            seg_crashes = matched_by_seg.get(s.segment_id, [])
            period_crashes = []
            fatal_count = 0

            for c in seg_crashes:
                try:
                    c_dt = datetime.fromisoformat(str(c["timestamp_utc"]).replace("Z", "+00:00"))
                    if p_start <= c_dt < p_end:
                        period_crashes.append(c)
                        if str(c.get("severity", "")).lower() in {"fatal", "fatal_crash", "3"}:
                            fatal_count += 1
                except (ValueError, KeyError):
                    continue

            n_crashes = len(period_crashes)
            total_crashes_count += n_crashes

            obs = SegmentTimeObservation(
                segment_id=s.segment_id,
                spatial_group=s.spatial_group,
                period_start=p_start_str,
                period_end=p_end_str,
                crash_count=n_crashes,
                any_crash=1 if n_crashes >= 1 else 0,
                fatal_crash_count=fatal_count,
                exposure_vehicle_km=exposure_vkm,
                log_exposure=log_exp,
                length_km=s.length_km,
                aadt=s.aadt,
                speed_limit_kmh=s.speed_limit_kmh,
                lanes=s.lanes,
                precipitation_mm=weather_info["precipitation_mm"],
                temperature_c=weather_info["temperature_c"],
                is_wet=weather_info["is_wet"],
                hour_sin=0.0,
                hour_cos=1.0,
                dow_sin=dow_sin,
                dow_cos=dow_cos,
                poi_density_250m=max(0, int(round(s.aadt / 2000.0))),
            )
            observations.append(obs)

    mean_exp = sum(o.exposure_vehicle_km for o in observations) / max(1, len(observations))

    return SegmentPanelDataset(
        network_label=network_label,
        total_segments=len(seg_records),
        total_periods=weeks_count,
        total_observations=len(observations),
        total_crashes=total_crashes_count,
        mean_exposure_vehicle_km=mean_exp,
        observations=observations,
    )


def export_panel_artifacts(
    dataset: SegmentPanelDataset,
    output_dir: Path | str,
    network_label: str = "panel_export",
) -> dict[str, str]:
    """Export segment-week panel as CSV, JSON bundle, and cryptographic SHA-256 manifest."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Export panel observations CSV
    csv_path = out_dir / f"{network_label}_segment_week_panel.csv"
    fields = [
        "segment_id", "spatial_group", "period_start", "period_end", "crash_count",
        "any_crash", "fatal_crash_count", "exposure_vehicle_km", "log_exposure",
        "length_km", "aadt", "speed_limit_kmh", "lanes", "precipitation_mm",
        "temperature_c", "is_wet", "hour_sin", "hour_cos", "dow_sin", "dow_cos", "poi_density_250m"
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=fields)
        writer.writeheader()
        for obs in dataset.observations:
            writer.writerow(obs.to_dict())

    # 2. Export panel bundle JSON
    json_path = out_dir / f"{network_label}_segment_week_panel.json"
    json_path.write_text(json.dumps(dataset.to_dict(), indent=2), encoding="utf-8")

    # 3. Export sovereign manifest
    manifest_path = out_dir / f"{network_label}.manifest.json"
    manifest = {
        "artifact_family": "segment_time_panel_dataset",
        "network_label": network_label,
        "engine_version": SEGMENT_PANEL_ENGINE_VERSION,
        "contract_version": PANEL_CONTRACT_VERSION,
        "unit": PRIMARY_UNIT,
        "exposure_unit": EXPOSURE_UNIT,
        "generated_at_utc": timestamp,
        "total_observations": dataset.total_observations,
        "total_crashes": dataset.total_crashes,
        "files": {
            "panel_csv": {"path": str(csv_path.name), "sha256": _sha256(csv_path)},
            "panel_json": {"path": str(json_path.name), "sha256": _sha256(json_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "panel_csv": str(csv_path),
        "panel_json": str(json_path),
        "manifest": str(manifest_path),
    }
