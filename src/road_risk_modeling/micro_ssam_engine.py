"""Microscopic Trajectory Surrogate Safety Assessment (SSAM) & Multi-Agent VRU Conflict Engine.

Implements high-frequency multi-modal trajectory analysis, computing pairwise Time-to-Collision (TTC),
Post-Encroachment Time (PET), Deceleration Rate to Avoid a Crash (DRAC), and Conflict Severity Index (CSI)
with Vulnerable Road User (VRU) biomechanical weighting (aligned with US FHWA SSAM & EU Horizon Europe PHOEBE/IVORY).
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


SSAM_ENGINE_VERSION = "micro_ssam_v1"
SSAM_CONTRACT_VERSION = "micro_ssam_public_v1"

VRU_AGENT_TYPES = {"pedestrian", "bicycle", "bicyclist", "cyclist", "e_scooter", "micromobility"}
MOTOR_VEHICLE_TYPES = {"car", "automobile", "truck", "bus", "van", "motorcycle", "heavy_vehicle"}


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
class TrajectoryPoint:
    """A single spatial-temporal coordinate observation for a moving agent."""

    time_sec: float
    x_coord: float
    y_coord: float
    speed_mps: float
    heading_deg: float = 0.0
    accel_mps2: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_sec": round(self.time_sec, 2),
            "x_coord": round(self.x_coord, 2),
            "y_coord": round(self.y_coord, 2),
            "speed_mps": round(self.speed_mps, 2),
            "heading_deg": round(self.heading_deg, 1),
            "accel_mps2": round(self.accel_mps2, 2),
        }


@dataclass(frozen=True, slots=True)
class AgentTrajectory:
    """A moving agent (vehicle or VRU) and its sequence of trajectory waypoints."""

    agent_id: str
    agent_type: str  # car, truck, bus, motorcycle, bicycle, pedestrian, e_scooter
    length_m: float = 4.5
    width_m: float = 1.8
    junction_id: str | None = None
    segment_id: str | None = None
    points: tuple[TrajectoryPoint, ...] = field(default_factory=tuple)

    @property
    def is_vru(self) -> bool:
        return self.agent_type.lower() in VRU_AGENT_TYPES

    @property
    def bounding_radius(self) -> float:
        return math.hypot(self.length_m / 2.0, self.width_m / 2.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "is_vru": self.is_vru,
            "length_m": round(self.length_m, 2),
            "width_m": round(self.width_m, 2),
            "junction_id": self.junction_id,
            "segment_id": self.segment_id,
            "points_count": len(self.points),
        }


@dataclass(frozen=True, slots=True)
class MicroscopicConflictEvent:
    """A detected microscopic near-miss conflict event between two road agents."""

    conflict_id: str
    time_sec: float
    agent_1_id: str
    agent_1_type: str
    agent_2_id: str
    agent_2_type: str
    conflict_type: str  # rear_end, crossing, head_on, vru_crossing
    ttc_seconds: float
    pet_seconds: float
    drac_mps2: float
    delta_v_kmh: float
    is_vru_involved: bool
    conflict_severity_index: float  # [0.0, 1.0]
    severity_tier: str             # critical, severe, moderate
    conflict_x: float
    conflict_y: float
    junction_id: str | None = None
    segment_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "time_sec": round(self.time_sec, 2),
            "agent_1_id": self.agent_1_id,
            "agent_1_type": self.agent_1_type,
            "agent_2_id": self.agent_2_id,
            "agent_2_type": self.agent_2_type,
            "conflict_type": self.conflict_type,
            "ttc_seconds": round(self.ttc_seconds, 2),
            "pet_seconds": round(self.pet_seconds, 2),
            "drac_mps2": round(self.drac_mps2, 2),
            "delta_v_kmh": round(self.delta_v_kmh, 1),
            "is_vru_involved": self.is_vru_involved,
            "conflict_severity_index": round(self.conflict_severity_index, 3),
            "severity_tier": self.severity_tier,
            "conflict_x": round(self.conflict_x, 2),
            "conflict_y": round(self.conflict_y, 2),
            "junction_id": self.junction_id,
            "segment_id": self.segment_id,
        }


@dataclass(frozen=True, slots=True)
class JunctionConflictSummary:
    """Aggregated conflict statistics for an intersection or roadway node."""

    junction_id: str
    total_conflicts: int
    critical_conflicts: int
    vru_conflicts: int
    vru_critical_conflicts: int
    crossing_conflicts: int
    rear_end_conflicts: int
    mean_ttc_seconds: float
    min_ttc_seconds: float
    mean_pet_seconds: float
    max_drac_mps2: float
    mean_csi: float
    max_csi: float
    danger_tier: str  # low, medium, high, critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "junction_id": self.junction_id,
            "total_conflicts": self.total_conflicts,
            "critical_conflicts": self.critical_conflicts,
            "vru_conflicts": self.vru_conflicts,
            "vru_critical_conflicts": self.vru_critical_conflicts,
            "crossing_conflicts": self.crossing_conflicts,
            "rear_end_conflicts": self.rear_end_conflicts,
            "mean_ttc_seconds": round(self.mean_ttc_seconds, 2),
            "min_ttc_seconds": round(self.min_ttc_seconds, 2),
            "mean_pet_seconds": round(self.mean_pet_seconds, 2),
            "max_drac_mps2": round(self.max_drac_mps2, 2),
            "mean_csi": round(self.mean_csi, 3),
            "max_csi": round(self.max_csi, 3),
            "danger_tier": self.danger_tier,
        }


def parse_agent_trajectories(raw_records: Sequence[Mapping[str, Any]]) -> list[AgentTrajectory]:
    """Parse raw agent records and trajectory waypoints from JSON/dict data."""
    trajectories: list[AgentTrajectory] = []

    for idx, rec in enumerate(raw_records, start=1):
        aid = str(rec.get("agent_id") or rec.get("id") or f"agent-{idx:04d}")
        atype = str(rec.get("agent_type") or rec.get("type") or "car").lower()
        jid = str(rec.get("junction_id") or rec.get("intersection_id") or "") or None
        sid = str(rec.get("segment_id") or "") or None

        # Default bounding box dimensions based on agent type
        if atype in {"pedestrian"}:
            default_len, default_width = 0.5, 0.5
        elif atype in {"bicycle", "bicyclist", "cyclist", "e_scooter"}:
            default_len, default_width = 1.8, 0.7
        elif atype in {"motorcycle"}:
            default_len, default_width = 2.2, 0.9
        elif atype in {"bus", "truck", "heavy_vehicle"}:
            default_len, default_width = 12.0, 2.6
        else:
            default_len, default_width = 4.6, 1.9

        length_m = _safe_float(rec.get("length_m") or rec.get("length"), default_len)
        width_m = _safe_float(rec.get("width_m") or rec.get("width"), default_width)

        raw_pts = rec.get("points") or rec.get("waypoints") or []
        pts: list[TrajectoryPoint] = []
        for p in raw_pts:
            t_sec = _safe_float(p.get("time_sec") or p.get("time") or p.get("t"), 0.0)
            x_val = _safe_float(p.get("x_coord") or p.get("x") or p.get("lon"), 0.0)
            y_val = _safe_float(p.get("y_coord") or p.get("y") or p.get("lat"), 0.0)
            spd = _safe_float(p.get("speed_mps") or p.get("speed"), 0.0)
            hdg = _safe_float(p.get("heading_deg") or p.get("heading"), 0.0)
            acc = _safe_float(p.get("accel_mps2") or p.get("accel"), 0.0)

            pts.append(
                TrajectoryPoint(
                    time_sec=t_sec,
                    x_coord=x_val,
                    y_coord=y_val,
                    speed_mps=spd,
                    heading_deg=hdg,
                    accel_mps2=acc,
                )
            )

        # Sort chronologically
        pts.sort(key=lambda pt: pt.time_sec)

        trajectories.append(
            AgentTrajectory(
                agent_id=aid,
                agent_type=atype,
                length_m=length_m,
                width_m=width_m,
                junction_id=jid,
                segment_id=sid,
                points=tuple(pts),
            )
        )

    return trajectories


def _interpolate_point(t: float, points: Sequence[TrajectoryPoint]) -> TrajectoryPoint | None:
    """Linearly interpolate an agent's position and speed at exact timestamp t."""
    if not points:
        return None
    if t < points[0].time_sec or t > points[-1].time_sec:
        return None

    # Binary search or scan
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i + 1]
        if p1.time_sec <= t <= p2.time_sec:
            dt = p2.time_sec - p1.time_sec
            if dt <= 1e-6:
                return p1
            alpha = (t - p1.time_sec) / dt
            interp_x = p1.x_coord + alpha * (p2.x_coord - p1.x_coord)
            interp_y = p1.y_coord + alpha * (p2.y_coord - p1.y_coord)
            interp_speed = p1.speed_mps + alpha * (p2.speed_mps - p1.speed_mps)
            interp_accel = p1.accel_mps2 + alpha * (p2.accel_mps2 - p1.accel_mps2)
            # Angular interpolation
            diff_h = (p2.heading_deg - p1.heading_deg + 180.0) % 360.0 - 180.0
            interp_heading = (p1.heading_deg + alpha * diff_h) % 360.0
            return TrajectoryPoint(
                time_sec=t,
                x_coord=interp_x,
                y_coord=interp_y,
                speed_mps=interp_speed,
                heading_deg=interp_heading,
                accel_mps2=interp_accel,
            )
    return points[-1] if abs(t - points[-1].time_sec) < 1e-6 else None


def _classify_conflict_type(
    agent_1: AgentTrajectory,
    agent_2: AgentTrajectory,
    heading_1: float,
    heading_2: float,
) -> str:
    """Classify conflict geometry based on agent categories and relative heading angle."""
    is_vru = agent_1.is_vru or agent_2.is_vru
    delta_heading = abs((heading_1 - heading_2 + 180.0) % 360.0 - 180.0)

    if is_vru:
        return "vru_crossing" if delta_heading > 35.0 else "vru_longitudinal"

    if delta_heading <= 35.0:
        return "rear_end"
    elif delta_heading >= 145.0:
        return "head_on"
    else:
        return "crossing"


def detect_trajectory_conflicts(
    trajectories: Sequence[AgentTrajectory],
    max_ttc_threshold: float = 4.0,
    max_pet_threshold: float = 3.5,
    spatial_proximity_threshold_m: float = 40.0,
    time_step_sec: float = 0.1,
) -> list[MicroscopicConflictEvent]:
    """Evaluate pairwise agent interactions and detect microscopic conflicts."""
    conflicts: list[MicroscopicConflictEvent] = []
    conflict_count = 0

    n_agents = len(trajectories)
    for i in range(n_agents):
        for j in range(i + 1, n_agents):
            a1 = trajectories[i]
            a2 = trajectories[j]

            if not a1.points or not a2.points:
                continue

            # Determine temporal overlap window
            t_start = max(a1.points[0].time_sec, a2.points[0].time_sec)
            t_end = min(a1.points[-1].time_sec, a2.points[-1].time_sec)

            if (t_end - t_start) < time_step_sec:
                continue

            # Check bounding radius combined clearance
            radius_sum = a1.bounding_radius + a2.bounding_radius

            # Track minimum TTC and closest approach
            min_ttc = float("inf")
            min_ttc_time = t_start
            min_dist = float("inf")
            best_conflict_x = 0.0
            best_conflict_y = 0.0
            best_p1: TrajectoryPoint | None = None
            best_p2: TrajectoryPoint | None = None

            # Sample temporal overlap
            curr_t = t_start
            while curr_t <= t_end + 1e-6:
                p1 = _interpolate_point(curr_t, a1.points)
                p2 = _interpolate_point(curr_t, a2.points)

                if p1 and p2:
                    dx = p2.x_coord - p1.x_coord
                    dy = p2.y_coord - p1.y_coord
                    dist = math.hypot(dx, dy)

                    if dist < min_dist:
                        min_dist = dist
                        best_conflict_x = (p1.x_coord + p2.x_coord) / 2.0
                        best_conflict_y = (p1.y_coord + p2.y_coord) / 2.0
                        best_p1 = p1
                        best_p2 = p2

                    # Compute relative velocity
                    v1x = p1.speed_mps * math.cos(math.radians(p1.heading_deg))
                    v1y = p1.speed_mps * math.sin(math.radians(p1.heading_deg))
                    v2x = p2.speed_mps * math.cos(math.radians(p2.heading_deg))
                    v2y = p2.speed_mps * math.sin(math.radians(p2.heading_deg))

                    rel_vx = v2x - v1x
                    rel_vy = v2y - v1y
                    rel_speed_sq = rel_vx * rel_vx + rel_vy * rel_vy

                    # Converging check (dot product of position difference and relative velocity < 0)
                    dot_prod = dx * rel_vx + dy * rel_vy
                    if dot_prod < -1e-3 and rel_speed_sq > 0.01:
                        # Projected TTC along line of sight
                        ttc_candidate = -dot_prod / rel_speed_sq
                        # Check if within collision lateral tolerance
                        if ttc_candidate > 0 and ttc_candidate < min_ttc:
                            min_ttc = ttc_candidate
                            min_ttc_time = curr_t

                curr_t += time_step_sec

            # Spatial proximity check
            if min_dist > spatial_proximity_threshold_m:
                continue

            # Estimate Post-Encroachment Time (PET)
            # Find times when a1 and a2 passed closest to the conflict point (best_conflict_x, best_conflict_y)
            t1_cross = min(a1.points, key=lambda p: math.hypot(p.x_coord - best_conflict_x, p.y_coord - best_conflict_y)).time_sec
            t2_cross = min(a2.points, key=lambda p: math.hypot(p.x_coord - best_conflict_x, p.y_coord - best_conflict_y)).time_sec
            pet = abs(t2_cross - t1_cross)

            # DRAC (Deceleration Rate to Avoid Crash)
            clearance_dist = max(0.5, min_dist - radius_sum)
            speed_diff_mps = abs((best_p1.speed_mps if best_p1 else 0.0) - (best_p2.speed_mps if best_p2 else 0.0))
            drac = (speed_diff_mps ** 2) / (2.0 * clearance_dist)

            # Check if threshold criteria met
            has_valid_ttc = min_ttc <= max_ttc_threshold
            has_valid_pet = pet <= max_pet_threshold and min_dist <= 15.0

            if not (has_valid_ttc or has_valid_pet):
                continue

            conflict_count += 1
            cid = f"conf-{conflict_count:05d}"
            effective_ttc = min(min_ttc, 10.0)
            delta_v_kmh = speed_diff_mps * 3.6
            is_vru = a1.is_vru or a2.is_vru

            # Conflict classification
            h1 = best_p1.heading_deg if best_p1 else 0.0
            h2 = best_p2.heading_deg if best_p2 else 0.0
            ctype = _classify_conflict_type(a1, a2, h1, h2)

            # Conflict Severity Index (CSI)
            score_ttc = max(0.0, 1.0 - (effective_ttc / max_ttc_threshold))
            score_pet = max(0.0, 1.0 - (pet / max_pet_threshold))
            score_speed = min(1.0, delta_v_kmh / 50.0)
            vru_weight = 1.5 if is_vru else 1.0

            raw_csi = (0.45 * score_ttc + 0.35 * score_pet + 0.20 * score_speed) * vru_weight
            csi = min(1.0, max(0.0, raw_csi))

            # Severity tier
            if csi >= 0.70 or effective_ttc <= 1.5 or (is_vru and pet <= 1.0):
                severity_tier = "critical"
            elif csi >= 0.40 or effective_ttc <= 2.5:
                severity_tier = "severe"
            else:
                severity_tier = "moderate"

            jid = a1.junction_id or a2.junction_id or "junction_unspecified"
            sid = a1.segment_id or a2.segment_id

            conflicts.append(
                MicroscopicConflictEvent(
                    conflict_id=cid,
                    time_sec=min_ttc_time,
                    agent_1_id=a1.agent_id,
                    agent_1_type=a1.agent_type,
                    agent_2_id=a2.agent_id,
                    agent_2_type=a2.agent_type,
                    conflict_type=ctype,
                    ttc_seconds=effective_ttc,
                    pet_seconds=pet,
                    drac_mps2=drac,
                    delta_v_kmh=delta_v_kmh,
                    is_vru_involved=is_vru,
                    conflict_severity_index=csi,
                    severity_tier=severity_tier,
                    conflict_x=best_conflict_x,
                    conflict_y=best_conflict_y,
                    junction_id=jid,
                    segment_id=sid,
                )
            )

    # Sort descending by severity index
    conflicts.sort(key=lambda c: c.conflict_severity_index, reverse=True)
    return conflicts


def aggregate_conflicts_to_junctions(
    conflicts: Sequence[MicroscopicConflictEvent],
) -> list[JunctionConflictSummary]:
    """Aggregate conflict events to junctions/intersections and rank danger indices."""
    junction_map: dict[str, list[MicroscopicConflictEvent]] = {}
    for c in conflicts:
        jid = c.junction_id or "junction_unspecified"
        junction_map.setdefault(jid, []).append(c)

    summaries: list[JunctionConflictSummary] = []
    for jid, evts in junction_map.items():
        total = len(evts)
        critical = sum(1 for e in evts if e.severity_tier == "critical")
        vru_all = sum(1 for e in evts if e.is_vru_involved)
        vru_crit = sum(1 for e in evts if e.is_vru_involved and e.severity_tier == "critical")
        crossings = sum(1 for e in evts if e.conflict_type in {"crossing", "vru_crossing"})
        rears = sum(1 for e in evts if e.conflict_type == "rear_end")

        mean_ttc = sum(e.ttc_seconds for e in evts) / total
        min_ttc = min(e.ttc_seconds for e in evts)
        mean_pet = sum(e.pet_seconds for e in evts) / total
        max_drac = max(e.drac_mps2 for e in evts)
        mean_csi = sum(e.conflict_severity_index for e in evts) / total
        max_csi = max(e.conflict_severity_index for e in evts)

        if max_csi >= 0.75 or critical >= 3:
            tier = "critical"
        elif max_csi >= 0.50 or critical >= 1:
            tier = "high"
        elif max_csi >= 0.30:
            tier = "medium"
        else:
            tier = "low"

        summaries.append(
            JunctionConflictSummary(
                junction_id=jid,
                total_conflicts=total,
                critical_conflicts=critical,
                vru_conflicts=vru_all,
                vru_critical_conflicts=vru_crit,
                crossing_conflicts=crossings,
                rear_end_conflicts=rears,
                mean_ttc_seconds=mean_ttc,
                min_ttc_seconds=min_ttc,
                mean_pet_seconds=mean_pet,
                max_drac_mps2=max_drac,
                mean_csi=mean_csi,
                max_csi=max_csi,
                danger_tier=tier,
            )
        )

    # Sort descending by max CSI and total conflicts
    summaries.sort(key=lambda s: (s.max_csi, s.total_conflicts), reverse=True)
    return summaries


def export_micro_ssam_artifacts(
    conflicts: Sequence[MicroscopicConflictEvent],
    junction_summaries: Sequence[JunctionConflictSummary],
    output_dir: Path | str,
    network_label: str = "national_network",
) -> dict[str, str]:
    """Export microscopic SSAM conflict artifacts (CSVs, JSON bundle, Markdown report, Manifest)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Export Microscopic Conflicts CSV
    conflicts_csv = out_dir / f"{network_label}_micro_conflicts.csv"
    c_fields = [
        "conflict_id", "time_sec", "junction_id", "segment_id",
        "agent_1_id", "agent_1_type", "agent_2_id", "agent_2_type",
        "conflict_type", "ttc_seconds", "pet_seconds", "drac_mps2",
        "delta_v_kmh", "is_vru_involved", "conflict_severity_index",
        "severity_tier", "conflict_x", "conflict_y"
    ]
    with conflicts_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=c_fields)
        writer.writeheader()
        for c in conflicts:
            writer.writerow({
                "conflict_id": c.conflict_id,
                "time_sec": round(c.time_sec, 2),
                "junction_id": c.junction_id or "",
                "segment_id": c.segment_id or "",
                "agent_1_id": c.agent_1_id,
                "agent_1_type": c.agent_1_type,
                "agent_2_id": c.agent_2_id,
                "agent_2_type": c.agent_2_type,
                "conflict_type": c.conflict_type,
                "ttc_seconds": round(c.ttc_seconds, 2),
                "pet_seconds": round(c.pet_seconds, 2),
                "drac_mps2": round(c.drac_mps2, 2),
                "delta_v_kmh": round(c.delta_v_kmh, 1),
                "is_vru_involved": c.is_vru_involved,
                "conflict_severity_index": round(c.conflict_severity_index, 3),
                "severity_tier": c.severity_tier,
                "conflict_x": round(c.conflict_x, 2),
                "conflict_y": round(c.conflict_y, 2),
            })

    # 2. Export Junction Conflict Summary CSV
    junctions_csv = out_dir / f"{network_label}_junction_conflict_summary.csv"
    j_fields = [
        "junction_id", "total_conflicts", "critical_conflicts", "vru_conflicts",
        "vru_critical_conflicts", "crossing_conflicts", "rear_end_conflicts",
        "mean_ttc_seconds", "min_ttc_seconds", "mean_pet_seconds", "max_drac_mps2",
        "mean_csi", "max_csi", "danger_tier"
    ]
    with junctions_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=j_fields)
        writer.writeheader()
        for j in junction_summaries:
            writer.writerow({
                "junction_id": j.junction_id,
                "total_conflicts": j.total_conflicts,
                "critical_conflicts": j.critical_conflicts,
                "vru_conflicts": j.vru_conflicts,
                "vru_critical_conflicts": j.vru_critical_conflicts,
                "crossing_conflicts": j.crossing_conflicts,
                "rear_end_conflicts": j.rear_end_conflicts,
                "mean_ttc_seconds": round(j.mean_ttc_seconds, 2),
                "min_ttc_seconds": round(j.min_ttc_seconds, 2),
                "mean_pet_seconds": round(j.mean_pet_seconds, 2),
                "max_drac_mps2": round(j.max_drac_mps2, 2),
                "mean_csi": round(j.mean_csi, 3),
                "max_csi": round(j.max_csi, 3),
                "danger_tier": j.danger_tier,
            })

    # 3. Export Comprehensive JSON Bundle
    json_path = out_dir / f"{network_label}_ssam_bundle.json"
    total_conf = len(conflicts)
    crit_conf = sum(1 for c in conflicts if c.severity_tier == "critical")
    vru_conf = sum(1 for c in conflicts if c.is_vru_involved)
    payload = {
        "ssam_engine_version": SSAM_ENGINE_VERSION,
        "contract_version": SSAM_CONTRACT_VERSION,
        "network_label": network_label,
        "generated_at_utc": timestamp,
        "summary": {
            "total_conflicts_detected": total_conf,
            "critical_conflicts_count": crit_conf,
            "vru_conflicts_count": vru_conf,
            "vru_conflict_ratio_pct": round((vru_conf / max(1, total_conf)) * 100.0, 2),
            "conflict_type_breakdown": {
                "rear_end": sum(1 for c in conflicts if c.conflict_type == "rear_end"),
                "crossing": sum(1 for c in conflicts if c.conflict_type == "crossing"),
                "head_on": sum(1 for c in conflicts if c.conflict_type == "head_on"),
                "vru_crossing": sum(1 for c in conflicts if c.conflict_type == "vru_crossing"),
                "vru_longitudinal": sum(1 for c in conflicts if c.conflict_type == "vru_longitudinal"),
            },
            "total_junctions_analyzed": len(junction_summaries),
            "critical_junctions_count": sum(1 for j in junction_summaries if j.danger_tier == "critical"),
        },
        "junction_summaries": [j.to_dict() for j in junction_summaries],
        "top_critical_conflicts": [c.to_dict() for c in conflicts[:30]],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 4. Export Markdown Safety Briefing Report
    md_path = out_dir / f"{network_label}_vru_conflict_report.md"
    lines = [
        f"# Microscopic Trajectory SSAM & VRU Conflict Report: {network_label}",
        "",
        f"- **Generated at:** `{timestamp}`",
        "- **Standard Alignment:** US Federal Highway Administration (FHWA) SSAM & EU Horizon Europe PHOEBE/IVORY",
        f"- **Total Microscopic Conflicts Detected:** **{total_conf:,}**",
        f"- **Critical Conflicts (TTC ≤ 1.5s / CSI ≥ 0.70):** **{crit_conf:,}**",
        f"- **Vulnerable Road User (VRU) Conflicts:** **{vru_conf:,}** ({payload['summary']['vru_conflict_ratio_pct']:.1f}% of all conflicts)",
        f"- **Intersections / Junctions Evaluated:** {len(junction_summaries)}",
        "",
        "## Conflict Type Distribution",
        "",
        "| Conflict Geometry | Count | Share (%) | Primary Contributing Factors |",
        "| :--- | ---: | ---: | :--- |",
        f"| 🚶/🚲 VRU Crossing | {payload['summary']['conflict_type_breakdown']['vru_crossing']:,} | {payload['summary']['conflict_type_breakdown']['vru_crossing'] / max(1, total_conf) * 100.0:.1f}% | Missing pedestrian signals, unprotected bike crossings |",
        f"| 🚗/🚗 Angle / Crossing | {payload['summary']['conflict_type_breakdown']['crossing']:,} | {payload['summary']['conflict_type_breakdown']['crossing'] / max(1, total_conf) * 100.0:.1f}% | Unsignalized left-turns, sight distance restrictions |",
        f"| 🚙 Rear-End | {payload['summary']['conflict_type_breakdown']['rear_end']:,} | {payload['summary']['conflict_type_breakdown']['rear_end'] / max(1, total_conf) * 100.0:.1f}% | Stop-and-go congestion, sudden speed drops |",
        f"| 💥 Head-On | {payload['summary']['conflict_type_breakdown']['head_on']:,} | {payload['summary']['conflict_type_breakdown']['head_on'] / max(1, total_conf) * 100.0:.1f}% | Undivided carriageways, overtaking maneuvers |",
        "",
        "## High-Danger Junction Hotspots (Ranked by Conflict Severity Index)",
        "",
        "| Junction ID | Danger Tier | Conflicts | Critical | VRU Conflicts | Min TTC | Max DRAC | Max CSI |",
        "| :--- | :---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for j in junction_summaries[:15]:
        tier_icon = "🚨 Critical" if j.danger_tier == "critical" else ("⚠️ High" if j.danger_tier == "high" else "🟡 Medium")
        lines.append(
            f"| `{j.junction_id}` | {tier_icon} | {j.total_conflicts} | {j.critical_conflicts} | {j.vru_conflicts} | {j.min_ttc_seconds:.2f}s | {j.max_drac_mps2:.2f} m/s² | {j.max_csi:.3f} |"
        )
    lines.extend([
        "",
        "## Recommended Microscopic Engineering Countermeasures",
        "",
        "1. **Leading Pedestrian Interval (LPI)**: Give pedestrians a 3–5 second advance green phase before turning motor vehicles receive a green light.",
        "2. **Protected Left-Turn Phasing**: Eliminate permissive left turns where vehicle-pedestrian conflict severity exceeds CSI 0.65.",
        "3. **Intersection Daylighting & Curb Extensions**: Ban parking within 10 meters of crosswalks to maintain clear sight triangles.",
        "4. **Raised Crosswalks & Speed Tables**: Physically enforce 30 km/h design speed across conflict conflict zones.",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # 5. Export Manifest
    manifest_path = out_dir / f"{network_label}_ssam.manifest.json"
    manifest = {
        "artifact_family": "microscopic_ssam_conflict_analysis",
        "network_label": network_label,
        "ssam_engine_version": SSAM_ENGINE_VERSION,
        "generated_at_utc": timestamp,
        "files": {
            "conflicts_csv": {"path": str(conflicts_csv.name), "sha256": _sha256(conflicts_csv)},
            "junctions_csv": {"path": str(junctions_csv.name), "sha256": _sha256(junctions_csv)},
            "bundle_json": {"path": str(json_path.name), "sha256": _sha256(json_path)},
            "report_md": {"path": str(md_path.name), "sha256": _sha256(md_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "conflicts_csv": str(conflicts_csv),
        "junctions_csv": str(junctions_csv),
        "bundle_json": str(json_path),
        "report_md": str(md_path),
        "manifest": str(manifest_path),
    }
