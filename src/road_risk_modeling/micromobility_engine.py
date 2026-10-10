"""VRU Micromobility Sensor Fusion Engine for E-Scooters, Cargo-Bikes, and Shared Fleets.

Implements high-frequency inertial measurement unit (IMU) telemetry processing,
sidewalk-riding incursion detection, curb-strike and pavement defect profiling,
evasive near-miss swerve identification, tram-track slip anomaly detection,
and direct calibration of the iRAP Bicyclist/Pedestrian Star Rating pipeline.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _sha256


MICROMOBILITY_ENGINE_VERSION = "micromobility_vru_v1"
MICROMOBILITY_CONTRACT_VERSION = "micromobility_sensor_fusion_public_v1"
FLEET_SPEC_STANDARDS = "GBFS v2.3 / MDS v2.0 / High-Frequency 6-Axis IMU"

# Anomaly Detection Kinematic Thresholds
CURB_STRIKE_THRESHOLD_G = 1.80          # Delta vertical acceleration spike (g)
EVASIVE_SWERVE_LATERAL_G = 0.35         # Lateral acceleration threshold (g)
EVASIVE_SWERVE_YAW_DEG_S = 45.0         # Yaw rate threshold (deg/s)
SIDEWALK_SPEED_LIMIT_MPS = 1.67         # Maximum allowable sidewalk speed (6.0 km/h)
SIDEWALK_ROUGHNESS_G = 0.40             # Surface vibration roughness index (g)
TRAM_SLIP_RATIO_THRESHOLD = 0.30        # Wheel-to-ground slip differential ratio


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


@dataclass(frozen=True, slots=True)
class MicromobilityWaypoint:
    """A discrete high-frequency telemetry sample from a micromobility vehicle."""

    device_id: str
    vehicle_type: str             # e_scooter, e_bike, cargo_bike
    timestamp: str
    latitude: float
    longitude: float
    speed_mps: float
    accel_x: float = 0.0          # Longitudinal acceleration (g)
    accel_y: float = 0.0          # Lateral acceleration (g)
    accel_z: float = 1.0          # Vertical acceleration (g, default gravity 1.0)
    yaw_rate_deg_s: float = 0.0   # Angular rate (deg/s)
    is_sidewalk: bool = False     # Geometric incursion flag
    wheel_speed_mps: float | None = None
    segment_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "vehicle_type": self.vehicle_type,
            "timestamp": self.timestamp,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "speed_mps": round(self.speed_mps, 2),
            "accel_x": round(self.accel_x, 3),
            "accel_y": round(self.accel_y, 3),
            "accel_z": round(self.accel_z, 3),
            "yaw_rate_deg_s": round(self.yaw_rate_deg_s, 2),
            "is_sidewalk": self.is_sidewalk,
            "segment_id": self.segment_id,
        }


@dataclass(frozen=True, slots=True)
class MicromobilityEvent:
    """An isolated micro-safety conflict or infrastructure anomaly event."""

    event_id: str
    device_id: str
    vehicle_type: str
    segment_id: str
    event_type: str               # sidewalk_riding, curb_strike, evasive_swerve, tram_track_slip
    severity_tier: str            # critical, high, moderate
    latitude: float
    longitude: float
    timestamp: str
    peak_g: float
    metric_value: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "device_id": self.device_id,
            "vehicle_type": self.vehicle_type,
            "segment_id": self.segment_id,
            "event_type": self.event_type,
            "severity_tier": self.severity_tier,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "timestamp": self.timestamp,
            "peak_g": round(self.peak_g, 3),
            "metric_value": round(self.metric_value, 3),
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class SegmentMicromobilityProfile:
    """Aggregated micromobility conflict metrics and iRAP calibration for a corridor."""

    segment_id: str
    total_trips: int
    total_distance_km: float
    sidewalk_riding_events: int
    curb_strikes: int
    evasive_swerves: int
    tram_slips: int
    micromobility_conflict_index: float # MCI per thousand fleet-km
    vru_exposure_tier: str              # extreme, high, moderate, low
    nominal_bicycle_srs: float
    calibrated_bicycle_srs: float       # Adjusted for micromobility conflicts
    recommended_countermeasure: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "total_trips": self.total_trips,
            "total_distance_km": round(self.total_distance_km, 2),
            "sidewalk_riding_events": self.sidewalk_riding_events,
            "curb_strikes": self.curb_strikes,
            "evasive_swerves": self.evasive_swerves,
            "tram_slips": self.tram_slips,
            "micromobility_conflict_index": round(self.micromobility_conflict_index, 2),
            "vru_exposure_tier": self.vru_exposure_tier,
            "nominal_bicycle_srs": round(self.nominal_bicycle_srs, 2),
            "calibrated_bicycle_srs": round(self.calibrated_bicycle_srs, 2),
            "recommended_countermeasure": self.recommended_countermeasure,
        }


@dataclass(frozen=True, slots=True)
class MicromobilityFleetAuditReport:
    """Comprehensive citywide micromobility sensor fusion audit dossier."""

    network_label: str
    total_devices: int
    total_distance_km: float
    total_events_detected: int
    mean_mci: float
    critical_events_count: int
    segment_profiles: list[SegmentMicromobilityProfile]
    evaluation_timestamp_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "micromobility_engine_version": MICROMOBILITY_ENGINE_VERSION,
            "contract_version": MICROMOBILITY_CONTRACT_VERSION,
            "fleet_spec_standards": FLEET_SPEC_STANDARDS,
            "network_label": self.network_label,
            "total_devices": self.total_devices,
            "total_distance_km": round(self.total_distance_km, 2),
            "total_events_detected": self.total_events_detected,
            "mean_mci": round(self.mean_mci, 2),
            "critical_events_count": self.critical_events_count,
            "segment_profiles": [p.to_dict() for p in self.segment_profiles],
            "evaluation_timestamp_utc": self.evaluation_timestamp_utc,
        }


def detect_micromobility_events(
    waypoints: Sequence[MicromobilityWaypoint | Mapping[str, Any]],
) -> list[MicromobilityEvent]:
    """Detect micro-safety anomalies from high-frequency micromobility telemetry.

    Detects:
      1. Sidewalk Riding: speed > 6 km/h (1.67 m/s) on sidewalk or high pavement roughness.
      2. Curb Strike / Pavement Defect: |delta a_z| >= 1.8g.
      3. Evasive Near-Miss Swerve: |a_y| >= 0.35g and |yaw_rate| >= 45 deg/s.
      4. Tram Track / Wet Rail Slip: wheel slip ratio >= 0.30.
    """
    events: list[MicromobilityEvent] = []
    prev_wp: MicromobilityWaypoint | None = None

    for idx, raw in enumerate(waypoints):
        if isinstance(raw, MicromobilityWaypoint):
            wp = raw
        else:
            wp = MicromobilityWaypoint(
                device_id=str(raw.get("device_id") or "dev-01"),
                vehicle_type=str(raw.get("vehicle_type") or "e_scooter"),
                timestamp=str(raw.get("timestamp") or datetime.now(UTC).isoformat()),
                latitude=_safe_float(raw.get("latitude")),
                longitude=_safe_float(raw.get("longitude")),
                speed_mps=_safe_float(raw.get("speed_mps")),
                accel_x=_safe_float(raw.get("accel_x")),
                accel_y=_safe_float(raw.get("accel_y")),
                accel_z=_safe_float(raw.get("accel_z"), 1.0),
                yaw_rate_deg_s=_safe_float(raw.get("yaw_rate_deg_s")),
                is_sidewalk=bool(raw.get("is_sidewalk", False)),
                wheel_speed_mps=_safe_float(raw.get("wheel_speed_mps")) if raw.get("wheel_speed_mps") is not None else None,
                segment_id=str(raw.get("segment_id")) if raw.get("segment_id") else None,
            )

        seg_id = wp.segment_id or "seg-unknown"

        # 1. Sidewalk Riding Detection
        if (wp.is_sidewalk or abs(wp.accel_z - 1.0) >= SIDEWALK_ROUGHNESS_G) and wp.speed_mps > SIDEWALK_SPEED_LIMIT_MPS:
            severity = "critical" if wp.speed_mps > 4.16 else ("high" if wp.speed_mps > 2.78 else "moderate") # 15 km/h, 10 km/h
            events.append(
                MicromobilityEvent(
                    event_id=f"MM-SW-{wp.device_id}-{idx}",
                    device_id=wp.device_id,
                    vehicle_type=wp.vehicle_type,
                    segment_id=seg_id,
                    event_type="sidewalk_riding",
                    severity_tier=severity,
                    latitude=wp.latitude,
                    longitude=wp.longitude,
                    timestamp=wp.timestamp,
                    peak_g=abs(wp.accel_y),
                    metric_value=round(wp.speed_mps * 3.6, 1), # Speed in km/h
                    description=f"Illegal sidewalk riding at {wp.speed_mps*3.6:.1f} km/h (speed limit 6 km/h)",
                )
            )

        # 2. Curb Strike & Pavement Shock Detection
        if prev_wp and prev_wp.device_id == wp.device_id:
            delta_az = abs(wp.accel_z - prev_wp.accel_z)
            if delta_az >= CURB_STRIKE_THRESHOLD_G:
                severity = "critical" if delta_az >= 2.5 else "high"
                events.append(
                    MicromobilityEvent(
                        event_id=f"MM-CS-{wp.device_id}-{idx}",
                        device_id=wp.device_id,
                        vehicle_type=wp.vehicle_type,
                        segment_id=seg_id,
                        event_type="curb_strike",
                        severity_tier=severity,
                        latitude=wp.latitude,
                        longitude=wp.longitude,
                        timestamp=wp.timestamp,
                        peak_g=delta_az,
                        metric_value=round(delta_az, 2),
                        description=f"Severe vertical impact ({delta_az:.2f}g) indicating sharp curb or pavement defect",
                    )
                )

        # 3. Evasive Near-Miss Swerve Detection
        if abs(wp.accel_y) >= EVASIVE_SWERVE_LATERAL_G and abs(wp.yaw_rate_deg_s) >= EVASIVE_SWERVE_YAW_DEG_S:
            severity = "critical" if abs(wp.accel_y) >= 0.50 else "high"
            events.append(
                MicromobilityEvent(
                    event_id=f"MM-ES-{wp.device_id}-{idx}",
                    device_id=wp.device_id,
                    vehicle_type=wp.vehicle_type,
                    segment_id=seg_id,
                    event_type="evasive_swerve",
                    severity_tier=severity,
                    latitude=wp.latitude,
                    longitude=wp.longitude,
                    timestamp=wp.timestamp,
                    peak_g=abs(wp.accel_y),
                    metric_value=round(abs(wp.yaw_rate_deg_s), 1),
                    description=f"Evasive swerve ({abs(wp.accel_y):.2f}g, {abs(wp.yaw_rate_deg_s):.1f}°/s) around pedestrian or door",
                )
            )

        # 4. Tram Track / Rail Slip Anomaly Detection
        if wp.wheel_speed_mps is not None and wp.speed_mps > 2.0:
            slip_ratio = abs(wp.wheel_speed_mps - wp.speed_mps) / max(1.0, wp.speed_mps)
            if slip_ratio >= TRAM_SLIP_RATIO_THRESHOLD:
                severity = "critical" if slip_ratio >= 0.50 else "high"
                events.append(
                    MicromobilityEvent(
                        event_id=f"MM-TS-{wp.device_id}-{idx}",
                        device_id=wp.device_id,
                        vehicle_type=wp.vehicle_type,
                        segment_id=seg_id,
                        event_type="tram_track_slip",
                        severity_tier=severity,
                        latitude=wp.latitude,
                        longitude=wp.longitude,
                        timestamp=wp.timestamp,
                        peak_g=slip_ratio,
                        metric_value=round(slip_ratio * 100.0, 1),
                        description=f"Wheel slip anomaly ({slip_ratio*100.0:.1f}%) on rail/tram track crossing",
                    )
                )

        prev_wp = wp

    return events


def aggregate_micromobility_profiles(
    events: Sequence[MicromobilityEvent],
    segments_data: Sequence[Mapping[str, Any]] | None = None,
) -> list[SegmentMicromobilityProfile]:
    """Aggregate micro-safety events to corridor profiles, computing MCI and iRAP adjustments."""
    events_by_seg: dict[str, list[MicromobilityEvent]] = {}
    for ev in events:
        events_by_seg.setdefault(ev.segment_id, []).append(ev)

    # Compile segment profiles
    seg_metadata: dict[str, Mapping[str, Any]] = {}
    if segments_data:
        for s in segments_data:
            sid = str(s.get("segment_id") or "seg-unknown")
            seg_metadata[sid] = s

    all_segment_ids = set(events_by_seg.keys()) | set(seg_metadata.keys())
    profiles: list[SegmentMicromobilityProfile] = []

    for sid in sorted(all_segment_ids):
        seg_evs = events_by_seg.get(sid, [])
        meta = seg_metadata.get(sid, {})

        n_sw = sum(1 for e in seg_evs if e.event_type == "sidewalk_riding")
        n_cs = sum(1 for e in seg_evs if e.event_type == "curb_strike")
        n_es = sum(1 for e in seg_evs if e.event_type == "evasive_swerve")
        n_ts = sum(1 for e in seg_evs if e.event_type == "tram_track_slip")

        trips = _safe_int(meta.get("total_trips"), max(10, len(seg_evs) * 4))
        dist_km = _safe_float(meta.get("total_distance_km"), max(2.5, trips * 1.2))

        # Compute Micromobility Conflict Index (MCI) per 1,000 fleet-km
        # MCI = (1.5 * swerves + 2.0 * curb_strikes + 1.2 * sidewalk + 1.8 * tram_slips) / (dist_km / 1000)
        weighted_conflicts = 1.5 * n_es + 2.0 * n_cs + 1.2 * n_sw + 1.8 * n_ts
        exposure_k_km = max(0.005, dist_km / 1000.0)
        mci = weighted_conflicts / exposure_k_km

        # Assign VRU exposure tier
        if mci >= 80.0:
            tier = "extreme"
            recommendation = "Physical cycle track barrier separation & sidewalk pedestrian fence"
        elif mci >= 40.0:
            tier = "high"
            recommendation = "Segregated painted cycle track & dropped curb ramp smoothing"
        elif mci >= 15.0:
            tier = "moderate"
            recommendation = "Shared micromobility 20 km/h geofenced speed zone & surface rehabilitation"
        else:
            tier = "low"
            recommendation = "Standard mixed traffic operational maintenance"

        # iRAP Bicycle Star Rating Score Calibration
        nominal_srs = _safe_float(meta.get("bicycle_srs") or meta.get("nominal_bicycle_srs"), 15.0)
        # Empirical amplification factor based on micromobility conflict friction
        amplification = min(2.0, 1.0 + (mci / 100.0) * 0.50)
        calibrated_srs = nominal_srs * amplification

        profiles.append(
            SegmentMicromobilityProfile(
                segment_id=sid,
                total_trips=trips,
                total_distance_km=dist_km,
                sidewalk_riding_events=n_sw,
                curb_strikes=n_cs,
                evasive_swerves=n_es,
                tram_slips=n_ts,
                micromobility_conflict_index=mci,
                vru_exposure_tier=tier,
                nominal_bicycle_srs=nominal_srs,
                calibrated_bicycle_srs=calibrated_srs,
                recommended_countermeasure=recommendation,
            )
        )

    return profiles


def run_micromobility_fleet_audit(
    waypoints_data: Sequence[Mapping[str, Any]],
    segments_data: Sequence[Mapping[str, Any]] | None = None,
    network_label: str = "national_network",
) -> tuple[MicromobilityFleetAuditReport, list[MicromobilityEvent]]:
    """Execute citywide micromobility sensor fusion audit and return report and events."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Detect micro-safety events
    events = detect_micromobility_events(waypoints_data)

    # 2. Aggregate to corridor profiles
    profiles = aggregate_micromobility_profiles(events, segments_data)

    unique_devices = len(set(str(w.get("device_id")) for w in waypoints_data))
    total_dist = sum(p.total_distance_km for p in profiles)
    mean_mci = sum(p.micromobility_conflict_index for p in profiles) / max(1, len(profiles))
    crit_count = sum(1 for e in events if e.severity_tier == "critical")

    report = MicromobilityFleetAuditReport(
        network_label=network_label,
        total_devices=max(1, unique_devices),
        total_distance_km=total_dist,
        total_events_detected=len(events),
        mean_mci=mean_mci,
        critical_events_count=crit_count,
        segment_profiles=profiles,
        evaluation_timestamp_utc=timestamp,
    )

    return report, events


def export_micromobility_artifacts(
    report: MicromobilityFleetAuditReport,
    events: Sequence[MicromobilityEvent],
    output_dir: Path | str,
    network_label: str = "national_network",
) -> dict[str, str]:
    """Export micromobility sensor fusion artifacts (CSVs, JSON bundle, Markdown report, Manifest)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Export Events CSV
    events_csv = out_dir / f"{network_label}_events.csv"
    ev_fields = [
        "event_id", "device_id", "vehicle_type", "segment_id", "event_type",
        "severity_tier", "latitude", "longitude", "timestamp", "peak_g", "metric_value", "description"
    ]
    with events_csv.open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=ev_fields)
        writer.writeheader()
        for e in events:
            writer.writerow(e.to_dict())

    # 2. Export Segment Profiles CSV
    profiles_csv = out_dir / f"{network_label}_segment_profiles.csv"
    prof_fields = [
        "segment_id", "total_trips", "total_distance_km", "sidewalk_riding_events",
        "curb_strikes", "evasive_swerves", "tram_slips", "micromobility_conflict_index",
        "vru_exposure_tier", "nominal_bicycle_srs", "calibrated_bicycle_srs", "recommended_countermeasure"
    ]
    with profiles_csv.open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=prof_fields)
        writer.writeheader()
        for p in report.segment_profiles:
            writer.writerow(p.to_dict())

    # 3. Export Comprehensive Machine-Readable Bundle JSON
    bundle_json = out_dir / f"{network_label}_bundle.json"
    bundle_payload = {
        "micromobility_engine_version": MICROMOBILITY_ENGINE_VERSION,
        "contract_version": MICROMOBILITY_CONTRACT_VERSION,
        "fleet_spec_standards": FLEET_SPEC_STANDARDS,
        "network_label": network_label,
        "summary": report.to_dict(),
        "events_count": len(events),
    }
    bundle_json.write_text(json.dumps(bundle_payload, indent=2), encoding="utf-8")

    # 4. Export Executive Markdown Report
    report_md = out_dir / f"{network_label}_report.md"
    lines = [
        f"# VRU Micromobility Sensor Fusion Report: {network_label}",
        "",
        f"- **Fleet Ingestion Standard:** `{FLEET_SPEC_STANDARDS}`",
        f"- **Evaluation Timestamp:** `{report.evaluation_timestamp_utc}`",
        f"- **Connected Devices Monitored:** `{report.total_devices:,}` vehicles (E-Scooters, E-Bikes, Cargo-Bikes)",
        f"- **Fleet Exposure Monitored:** `{report.total_distance_km:,.1f}` km",
        f"- **Total Micro-Anomalies Isolated:** **`{report.total_events_detected:,}` events** (`{report.critical_events_count:,}` critical)",
        f"- **Mean Micromobility Conflict Index (MCI):** **`{report.mean_mci:.2f}`** / 1,000 km",
        "",
        "## 1. Corridor Micro-Safety Friction & iRAP Star Rating Calibration",
        "",
        "| Corridor ID | Trips | Sidewalk Events | Curb Strikes | Swerves | Tram Slips | MCI (per 1k km) | VRU Exposure Tier | Recommended Countermeasure |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]

    for p in report.segment_profiles:
        tier_badge = "🔴 EXTREME" if p.vru_exposure_tier == "extreme" else (
            "🟠 HIGH" if p.vru_exposure_tier == "high" else ("🟡 MODERATE" if p.vru_exposure_tier == "moderate" else "🟢 LOW")
        )
        lines.append(
            f"| `{p.segment_id}` | {p.total_trips} | {p.sidewalk_riding_events} | {p.curb_strikes} | {p.evasive_swerves} | {p.tram_slips} | **{p.micromobility_conflict_index:.1f}** | {tier_badge} | {p.recommended_countermeasure} |"
        )

    lines.extend([
        "",
        "## 2. Infrastructure Intervention Recommendations",
        "",
        "1. **Segregated Physical Protection**: Corridors with high evasive swerves and sidewalk riding require physical curb separation to remove e-scooters from pedestrian walkways.",
        "2. **Curb Ramp Smoothing & Pothole Repair**: High vertical jerk zones ($|\\Delta a_z| \\ge 1.8g$) indicate sharp impact hazards requiring immediate civil leveling.",
        "3. **Tram Track Crossing Safety**: Segments with rail wheel-slip anomalies require non-slip track coatings and angled bike crossing deflection markings.",
        "",
    ])

    report_md.write_text("\n".join(lines), encoding="utf-8")

    # 5. Export Sovereign Manifest
    manifest_path = out_dir / f"{network_label}.manifest.json"
    manifest = {
        "artifact_family": "micromobility_vru_sensor_fusion",
        "network_label": network_label,
        "micromobility_engine_version": MICROMOBILITY_ENGINE_VERSION,
        "fleet_spec_standards": FLEET_SPEC_STANDARDS,
        "generated_at_utc": timestamp,
        "files": {
            "events_csv": {"path": str(events_csv.name), "sha256": _sha256(events_csv)},
            "profiles_csv": {"path": str(profiles_csv.name), "sha256": _sha256(profiles_csv)},
            "bundle_json": {"path": str(bundle_json.name), "sha256": _sha256(bundle_json)},
            "report_md": {"path": str(report_md.name), "sha256": _sha256(report_md)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "events_csv": str(events_csv),
        "profiles_csv": str(profiles_csv),
        "bundle_json": str(bundle_json),
        "report_md": str(report_md),
        "manifest": str(manifest_path),
    }
