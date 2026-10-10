"""Commercial Floating Car Data (FCD) & High-Frequency Near-Miss Telematics Engine.

Implements kinematic anomaly detection, Surrogate Safety Measures (SSMs),
exposure normalization (Million Vehicle-Kilometers Traveled - MVKT),
and multi-source proactive safety score fusion with AASHTO HSM and iRAP.
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


TELEMATICS_ENGINE_VERSION = "telematics_fcd_v1"
TELEMATICS_CONTRACT_VERSION = "telematics_fcd_public_v1"

# Standard Earth gravity (m/s^2)
GRAVITY_G = 9.80665

# Kinematic Thresholds (in g-force where 1g ≈ 9.81 m/s^2)
# Ref: FHWA Surrogate Safety Assessment Model (SSAM) & International Telematics Protocols
HARSH_BRAKING_THRESHOLDS = {
    "moderate": -0.35,  # -3.43 m/s^2 (abrupt stop)
    "severe": -0.45,    # -4.41 m/s^2 (emergency braking)
    "critical": -0.60,  # -5.88 m/s^2 (collision-avoidance lockup)
}

HARSH_CORNERING_THRESHOLDS = {
    "moderate": 0.30,   # 2.94 m/s^2 (fast turn)
    "severe": 0.40,     # 3.92 m/s^2 (abrupt swerve)
    "critical": 0.55,   # 5.39 m/s^2 (loss-of-control threshold)
}

HARSH_ACCEL_THRESHOLDS = {
    "moderate": 0.30,   # rapid launch
    "severe": 0.45,     # aggressive acceleration
}


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
    f = _safe_float(val, float(default))
    return int(round(f))


@dataclass(frozen=True, slots=True)
class KinematicNearMissEvent:
    """A detected high-frequency kinematic near-miss anomaly."""

    event_id: str
    segment_id: str
    timestamp: str
    event_type: str  # harsh_braking, harsh_cornering, harsh_acceleration, sudden_speed_drop
    severity: str    # moderate, severe, critical
    peak_accel_g: float
    initial_speed_kmh: float
    final_speed_kmh: float
    delta_v_kmh: float
    duration_s: float
    latitude: float | None = None
    longitude: float | None = None
    vehicle_type: str = "passenger_car"  # passenger_car, heavy_truck, bus, motorcycle, light_commercial
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "segment_id": self.segment_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "severity": self.severity,
            "peak_accel_g": round(self.peak_accel_g, 3),
            "initial_speed_kmh": round(self.initial_speed_kmh, 1),
            "final_speed_kmh": round(self.final_speed_kmh, 1),
            "delta_v_kmh": round(self.delta_v_kmh, 1),
            "duration_s": round(self.duration_s, 2),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "vehicle_type": self.vehicle_type,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class SegmentTelematicsMetrics:
    """Aggregated telematics and proactive near-miss risk evaluation for a roadway segment."""

    segment_id: str
    length_km: float
    aadt: float
    mvkt_annual: float  # Million Vehicle-Kilometers Traveled annually
    harsh_braking_count: int
    harsh_cornering_count: int
    harsh_accel_count: int
    sudden_speed_drop_count: int
    total_near_miss_events: int
    critical_events_count: int
    near_miss_rate_per_mvkt: float
    predictive_risk_score: float  # 0 to 100 proactive risk index
    risk_tier: str                # critical_proactive_hotspot, high_risk_corridor, monitored_baseline, low_anomaly_network
    priority_rank: int
    hsm_psi_crashes: float = 0.0
    irap_star_rating: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "length_km": round(self.length_km, 3),
            "aadt": round(self.aadt, 1),
            "mvkt_annual": round(self.mvkt_annual, 4),
            "event_counts": {
                "harsh_braking": self.harsh_braking_count,
                "harsh_cornering": self.harsh_cornering_count,
                "harsh_acceleration": self.harsh_accel_count,
                "sudden_speed_drop": self.sudden_speed_drop_count,
                "total_near_misses": self.total_near_miss_events,
                "critical_events": self.critical_events_count,
            },
            "near_miss_rate_per_mvkt": round(self.near_miss_rate_per_mvkt, 2),
            "predictive_risk_score": round(self.predictive_risk_score, 1),
            "risk_tier": self.risk_tier,
            "priority_rank": self.priority_rank,
            "hsm_psi_crashes": round(self.hsm_psi_crashes, 2),
            "irap_star_rating": self.irap_star_rating,
        }


def classify_braking_severity(accel_x_g: float) -> str | None:
    """Classify deceleration into moderate, severe, critical, or None."""
    if accel_x_g <= HARSH_BRAKING_THRESHOLDS["critical"]:
        return "critical"
    if accel_x_g <= HARSH_BRAKING_THRESHOLDS["severe"]:
        return "severe"
    if accel_x_g <= HARSH_BRAKING_THRESHOLDS["moderate"]:
        return "moderate"
    return None


def classify_cornering_severity(accel_y_g: float) -> str | None:
    """Classify lateral acceleration magnitude into moderate, severe, critical, or None."""
    abs_y = abs(accel_y_g)
    if abs_y >= HARSH_CORNERING_THRESHOLDS["critical"]:
        return "critical"
    if abs_y >= HARSH_CORNERING_THRESHOLDS["severe"]:
        return "severe"
    if abs_y >= HARSH_CORNERING_THRESHOLDS["moderate"]:
        return "moderate"
    return None


def classify_acceleration_severity(accel_x_g: float) -> str | None:
    """Classify longitudinal launch acceleration into moderate, severe, or None."""
    if accel_x_g >= HARSH_ACCEL_THRESHOLDS["severe"]:
        return "severe"
    if accel_x_g >= HARSH_ACCEL_THRESHOLDS["moderate"]:
        return "moderate"
    return None


def detect_events_from_waypoints(
    waypoints: Sequence[Mapping[str, Any]],
    segment_id: str = "seg-unknown",
) -> list[KinematicNearMissEvent]:
    """Analyze time-series vehicle waypoints (e.g. 1Hz - 10Hz) to detect kinematic near-miss events."""
    if len(waypoints) < 2:
        return []

    events: list[KinematicNearMissEvent] = []

    for i in range(1, len(waypoints)):
        prev = waypoints[i - 1]
        curr = waypoints[i]

        t_prev = _safe_float(prev.get("timestamp_s") or prev.get("time") or (i - 1))
        t_curr = _safe_float(curr.get("timestamp_s") or curr.get("time") or i)
        dt = max(0.1, t_curr - t_prev)

        v_prev = _safe_float(prev.get("speed_kmh") or prev.get("speed") or 0.0)
        v_curr = _safe_float(curr.get("speed_kmh") or curr.get("speed") or 0.0)
        delta_v = v_curr - v_prev

        # Longitudinal acceleration in g: a = (dv / dt) in m/s^2 / 9.81
        if "accel_x_g" in curr:
            ax = _safe_float(curr["accel_x_g"])
        elif "accel_x" in curr:
            ax = _safe_float(curr["accel_x"]) / GRAVITY_G
        else:
            dv_ms = (delta_v * 1000.0 / 3600.0)
            ax = (dv_ms / dt) / GRAVITY_G

        # Lateral acceleration in g
        if "accel_y_g" in curr:
            ay = _safe_float(curr["accel_y_g"])
        elif "accel_y" in curr:
            ay = _safe_float(curr["accel_y"]) / GRAVITY_G
        else:
            # Estimate from yaw rate if available
            yaw_rate_dps = _safe_float(curr.get("yaw_rate_dps") or 0.0)
            if yaw_rate_dps != 0.0:
                v_ms = (v_curr * 1000.0 / 3600.0)
                omega_rad = math.radians(yaw_rate_dps)
                ay = (v_ms * omega_rad) / GRAVITY_G
            else:
                ay = 0.0

        ts_str = str(curr.get("timestamp") or datetime.now(UTC).isoformat())
        lat = _safe_float(curr.get("latitude") or curr.get("lat")) or None
        lon = _safe_float(curr.get("longitude") or curr.get("lon")) or None
        vtype = str(curr.get("vehicle_type") or "passenger_car")

        # 1. Check Harsh Braking
        b_sev = classify_braking_severity(ax)
        if b_sev:
            events.append(
                KinematicNearMissEvent(
                    event_id=f"evt-brake-{segment_id}-{i}",
                    segment_id=segment_id,
                    timestamp=ts_str,
                    event_type="harsh_braking",
                    severity=b_sev,
                    peak_accel_g=ax,
                    initial_speed_kmh=v_prev,
                    final_speed_kmh=v_curr,
                    delta_v_kmh=abs(delta_v),
                    duration_s=dt,
                    latitude=lat,
                    longitude=lon,
                    vehicle_type=vtype,
                )
            )

        # 2. Check Harsh Cornering (Swerving)
        c_sev = classify_cornering_severity(ay)
        if c_sev:
            events.append(
                KinematicNearMissEvent(
                    event_id=f"evt-corner-{segment_id}-{i}",
                    segment_id=segment_id,
                    timestamp=ts_str,
                    event_type="harsh_cornering",
                    severity=c_sev,
                    peak_accel_g=abs(ay),
                    initial_speed_kmh=v_prev,
                    final_speed_kmh=v_curr,
                    delta_v_kmh=abs(delta_v),
                    duration_s=dt,
                    latitude=lat,
                    longitude=lon,
                    vehicle_type=vtype,
                )
            )

        # 3. Check Sudden Speed Drop (Δv ≥ 25 km/h over ≤ 3s without extreme g)
        if delta_v <= -25.0 and dt <= 3.0 and not b_sev:
            events.append(
                KinematicNearMissEvent(
                    event_id=f"evt-drop-{segment_id}-{i}",
                    segment_id=segment_id,
                    timestamp=ts_str,
                    event_type="sudden_speed_drop",
                    severity="severe" if delta_v <= -40.0 else "moderate",
                    peak_accel_g=ax,
                    initial_speed_kmh=v_prev,
                    final_speed_kmh=v_curr,
                    delta_v_kmh=abs(delta_v),
                    duration_s=dt,
                    latitude=lat,
                    longitude=lon,
                    vehicle_type=vtype,
                )
            )

    return events


def parse_telematics_events(records: Sequence[Mapping[str, Any]]) -> list[KinematicNearMissEvent]:
    """Parse pre-detected or provider-reported telematics near-miss events."""
    parsed: list[KinematicNearMissEvent] = []
    for idx, rec in enumerate(records, start=1):
        seg_id = str(rec.get("segment_id") or rec.get("id") or "seg-unknown")
        evt_type = str(rec.get("event_type") or "harsh_braking").lower()
        peak_g = _safe_float(rec.get("peak_accel_g") or rec.get("acceleration_g") or -0.45)
        
        # Determine severity
        sev = str(rec.get("severity") or "").lower()
        if not sev or sev not in {"moderate", "severe", "critical"}:
            if evt_type == "harsh_braking":
                sev = classify_braking_severity(peak_g) or "moderate"
            elif evt_type == "harsh_cornering":
                sev = classify_cornering_severity(peak_g) or "moderate"
            else:
                sev = "moderate"

        init_v = _safe_float(rec.get("initial_speed_kmh") or 50.0)
        final_v = _safe_float(rec.get("final_speed_kmh") or max(0.0, init_v - 20.0))
        delta_v = _safe_float(rec.get("delta_v_kmh") or abs(final_v - init_v))
        dur = _safe_float(rec.get("duration_s") or 1.5)
        ts = str(rec.get("timestamp") or datetime.now(UTC).isoformat())
        lat = _safe_float(rec.get("latitude") or rec.get("lat")) or None
        lon = _safe_float(rec.get("longitude") or rec.get("lon")) or None
        vtype = str(rec.get("vehicle_type") or "passenger_car")

        parsed.append(
            KinematicNearMissEvent(
                event_id=str(rec.get("event_id") or f"fcd-evt-{idx}"),
                segment_id=seg_id,
                timestamp=ts,
                event_type=evt_type,
                severity=sev,
                peak_accel_g=peak_g,
                initial_speed_kmh=init_v,
                final_speed_kmh=final_v,
                delta_v_kmh=delta_v,
                duration_s=dur,
                latitude=lat,
                longitude=lon,
                vehicle_type=vtype,
                metadata=dict(rec.get("metadata") or {}),
            )
        )
    return parsed


def calculate_segment_telematics_metrics(
    segments: Sequence[Mapping[str, Any]],
    telematics_events: Sequence[KinematicNearMissEvent],
    days_analyzed: int = 365,
    fleet_penetration_rate: float = 0.05,  # typically 3% to 10% of total traffic
) -> list[SegmentTelematicsMetrics]:
    """Aggregate telematics anomalies onto roadway segments and compute proactive risk scores."""
    # Index events by segment_id
    events_by_segment: dict[str, list[KinematicNearMissEvent]] = {}
    for evt in telematics_events:
        events_by_segment.setdefault(evt.segment_id, []).append(evt)

    results: list[SegmentTelematicsMetrics] = []

    for seg in segments:
        seg_id = str(seg.get("segment_id") or seg.get("id") or "seg-unknown")
        
        # Length in km
        if "length_km" in seg:
            length_km = _safe_float(seg["length_km"], 0.2)
        elif "segment_length_m" in seg:
            length_km = _safe_float(seg["segment_length_m"], 200.0) / 1000.0
        elif "length_m" in seg:
            length_km = _safe_float(seg["length_m"], 200.0) / 1000.0
        else:
            length_km = 0.2
        length_km = max(0.02, length_km)

        # AADT
        aadt = _safe_float(seg.get("aadt") or seg.get("flow_daily_estimate") or 2500.0)
        aadt = max(100.0, aadt)

        # Exposure: Million Vehicle-Kilometers Traveled (MVKT)
        # MVKT = (AADT * Length_km * Days) / 1,000,000
        mvkt = (aadt * length_km * max(1, days_analyzed)) / 1_000_000.0
        sample_mvkt = max(0.0001, mvkt * max(0.001, fleet_penetration_rate))

        # Event counts
        seg_evts = events_by_segment.get(seg_id, [])
        hbe = sum(1 for e in seg_evts if e.event_type == "harsh_braking")
        hce = sum(1 for e in seg_evts if e.event_type == "harsh_cornering")
        hae = sum(1 for e in seg_evts if e.event_type == "harsh_acceleration")
        drop = sum(1 for e in seg_evts if e.event_type == "sudden_speed_drop")
        crit = sum(1 for e in seg_evts if e.severity == "critical")
        total = len(seg_evts)

        # Weighted near-miss count: critical events count 2.5x, severe 1.5x, moderate 1.0x
        weighted_events = sum(
            2.5 if e.severity == "critical" else (1.5 if e.severity == "severe" else 1.0)
            for e in seg_evts
        )

        # Near-Miss Rate per MVKT of sampled fleet
        nm_rate = weighted_events / sample_mvkt

        # Fusion inputs: HSM Empirical Bayes PSI and iRAP Star Rating if provided
        hsm_psi = _safe_float(seg.get("psi_excess_crashes_annual") or seg.get("hsm_psi") or 0.0)
        irap_stars = _safe_int(seg.get("minimum_stars_overall") or seg.get("irap_stars") or 3)
        irap_deficit = max(0, 5 - irap_stars)  # 0 (5-star) to 4 (1-star)

        # Composite Predictive Risk Score (0 to 100):
        # Component 1: Telematics Near-Miss Rate (40% weight, saturated at 100 events/MVKT)
        s_telematics = min(100.0, (nm_rate / 80.0) * 100.0)
        # Component 2: HSM PSI excess crashes (35% weight, saturated at 5 excess crashes/yr)
        s_hsm = min(100.0, (max(0.0, hsm_psi) / 3.0) * 100.0)
        # Component 3: iRAP Star Deficit (25% weight, deficit 0 to 4 mapped to 0 to 100)
        s_irap = (irap_deficit / 4.0) * 100.0

        composite_score = (0.40 * s_telematics) + (0.35 * s_hsm) + (0.25 * s_irap)

        # Risk Tier Classification
        if composite_score >= 65.0 or crit >= 3:
            tier = "critical_proactive_hotspot"
        elif composite_score >= 40.0:
            tier = "high_risk_corridor"
        elif composite_score >= 20.0:
            tier = "monitored_baseline"
        else:
            tier = "low_anomaly_network"

        results.append(
            SegmentTelematicsMetrics(
                segment_id=seg_id,
                length_km=length_km,
                aadt=aadt,
                mvkt_annual=mvkt,
                harsh_braking_count=hbe,
                harsh_cornering_count=hce,
                harsh_accel_count=hae,
                sudden_speed_drop_count=drop,
                total_near_miss_events=total,
                critical_events_count=crit,
                near_miss_rate_per_mvkt=nm_rate,
                predictive_risk_score=composite_score,
                risk_tier=tier,
                priority_rank=1,
                hsm_psi_crashes=hsm_psi,
                irap_star_rating=irap_stars,
            )
        )

    # Rank by predictive_risk_score descending
    results.sort(key=lambda item: item.predictive_risk_score, reverse=True)

    ranked_results: list[SegmentTelematicsMetrics] = []
    for rank, item in enumerate(results, start=1):
        ranked_results.append(
            SegmentTelematicsMetrics(
                segment_id=item.segment_id,
                length_km=item.length_km,
                aadt=item.aadt,
                mvkt_annual=item.mvkt_annual,
                harsh_braking_count=item.harsh_braking_count,
                harsh_cornering_count=item.harsh_cornering_count,
                harsh_accel_count=item.harsh_accel_count,
                sudden_speed_drop_count=item.sudden_speed_drop_count,
                total_near_miss_events=item.total_near_miss_events,
                critical_events_count=item.critical_events_count,
                near_miss_rate_per_mvkt=item.near_miss_rate_per_mvkt,
                predictive_risk_score=item.predictive_risk_score,
                risk_tier=item.risk_tier,
                priority_rank=rank,
                hsm_psi_crashes=item.hsm_psi_crashes,
                irap_star_rating=item.irap_star_rating,
            )
        )

    return ranked_results


def export_telematics_screening_artifacts(
    metrics: Sequence[SegmentTelematicsMetrics],
    events: Sequence[KinematicNearMissEvent],
    output_dir: Path | str,
    network_label: str = "national_network",
) -> dict[str, str]:
    """Export telematics near-miss screening artifacts (CSV, JSON, Markdown report, Manifest)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Export Segment Rates CSV
    csv_path = out_dir / f"{network_label}_telematics_near_miss_rates.csv"
    fieldnames = [
        "priority_rank", "segment_id", "length_km", "aadt", "mvkt_annual",
        "total_near_miss_events", "harsh_braking_count", "harsh_cornering_count",
        "harsh_accel_count", "sudden_speed_drop_count", "critical_events_count",
        "near_miss_rate_per_mvkt", "predictive_risk_score", "risk_tier",
        "hsm_psi_crashes", "irap_star_rating"
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics:
            writer.writerow({
                "priority_rank": m.priority_rank,
                "segment_id": m.segment_id,
                "length_km": round(m.length_km, 3),
                "aadt": round(m.aadt, 1),
                "mvkt_annual": round(m.mvkt_annual, 4),
                "total_near_miss_events": m.total_near_miss_events,
                "harsh_braking_count": m.harsh_braking_count,
                "harsh_cornering_count": m.harsh_cornering_count,
                "harsh_accel_count": m.harsh_accel_count,
                "sudden_speed_drop_count": m.sudden_speed_drop_count,
                "critical_events_count": m.critical_events_count,
                "near_miss_rate_per_mvkt": round(m.near_miss_rate_per_mvkt, 2),
                "predictive_risk_score": round(m.predictive_risk_score, 1),
                "risk_tier": m.risk_tier,
                "hsm_psi_crashes": round(m.hsm_psi_crashes, 2),
                "irap_star_rating": m.irap_star_rating,
            })

    # 2. Export JSON Bundle
    json_path = out_dir / f"{network_label}_telematics_bundle.json"
    tier_counts = {
        "critical_proactive_hotspot": sum(1 for m in metrics if m.risk_tier == "critical_proactive_hotspot"),
        "high_risk_corridor": sum(1 for m in metrics if m.risk_tier == "high_risk_corridor"),
        "monitored_baseline": sum(1 for m in metrics if m.risk_tier == "monitored_baseline"),
        "low_anomaly_network": sum(1 for m in metrics if m.risk_tier == "low_anomaly_network"),
    }
    payload = {
        "telematics_engine_version": TELEMATICS_ENGINE_VERSION,
        "contract_version": TELEMATICS_CONTRACT_VERSION,
        "generated_at_utc": timestamp,
        "network_label": network_label,
        "summary": {
            "total_segments_screened": len(metrics),
            "total_telematics_events": len(events),
            "tier_distribution": tier_counts,
            "total_mvkt_annual": round(sum(m.mvkt_annual for m in metrics), 2),
            "average_near_miss_rate_per_mvkt": round(
                sum(m.near_miss_rate_per_mvkt for m in metrics) / max(1, len(metrics)), 2
            ),
        },
        "top_segments": [m.to_dict() for m in metrics[:50]],
        "events_sample": [e.to_dict() for e in events[:100]],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 3. Export Markdown Executive Report
    md_path = out_dir / f"{network_label}_telematics_near_miss_report.md"
    lines = [
        f"# Telematics & Floating Car Data (FCD) Near-Miss Screening: {network_label}",
        "",
        f"- **Generated at:** `{timestamp}`",
        "- **Standard Alignment:** FHWA Surrogate Safety Assessment (SSAM) & Kinematic Telematics Protocols",
        f"- **Total Network Segments Evaluated:** {len(metrics):,}",
        f"- **Total Kinematic Near-Miss Anomalies Ingested:** {len(events):,}",
        f"- **Critical Proactive Hotspots Identified:** **{tier_counts['critical_proactive_hotspot']:,}** corridors",
        f"- **High-Risk Corridors:** **{tier_counts['high_risk_corridor']:,}** corridors",
        "",
        "## Risk Tier Distribution",
        "",
        "| Risk Tier | Segment Count | Description | Action Required |",
        "| :--- | ---: | :--- | :--- |",
        f"| 🚨 **Critical Proactive Hotspot** | {tier_counts['critical_proactive_hotspot']:,} | Severe harsh braking/swerving density | Immediate safety engineering audit |",
        f"| ⚠️ **High-Risk Corridor** | {tier_counts['high_risk_corridor']:,} | Elevated kinematic anomaly frequency | Targeted speed management & signal retiming |",
        f"| 🔍 **Monitored Baseline** | {tier_counts['monitored_baseline']:,} | Moderate near-miss activity | Continuous telematics surveillance |",
        f"| ✅ **Low-Anomaly Network** | {tier_counts['low_anomaly_network']:,} | Minimal unexpected driver maneuvers | Standard maintenance cycle |",
        "",
        "## Top Prioritized Proactive Hotspots",
        "",
        "| Rank | Segment ID | Risk Score | Risk Tier | Near-Miss Rate (/MVKT) | Total Events | Critical Events | iRAP | HSM PSI |",
        "| ---: | :--- | ---: | :--- | ---: | ---: | ---: | :---: | ---: |",
    ]
    for m in metrics[:25]:
        lines.append(
            f"| #{m.priority_rank} | `{m.segment_id}` | **{m.predictive_risk_score:.1f}** | `{m.risk_tier}` | {m.near_miss_rate_per_mvkt:.1f} | {m.total_near_miss_events} | {m.critical_events_count} | {m.irap_star_rating}★ | +{m.hsm_psi_crashes:.2f} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # 4. Export Manifest
    manifest_path = out_dir / f"{network_label}_telematics.manifest.json"
    manifest = {
        "artifact_family": "telematics_near_miss",
        "network_label": network_label,
        "telematics_engine_version": TELEMATICS_ENGINE_VERSION,
        "generated_at_utc": timestamp,
        "files": {
            "rates_csv": {"path": str(csv_path.name), "sha256": _sha256(csv_path)},
            "bundle_json": {"path": str(json_path.name), "sha256": _sha256(json_path)},
            "report_md": {"path": str(md_path.name), "sha256": _sha256(md_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "rates_csv": str(csv_path),
        "bundle_json": str(json_path),
        "report_md": str(md_path),
        "manifest": str(manifest_path),
    }
