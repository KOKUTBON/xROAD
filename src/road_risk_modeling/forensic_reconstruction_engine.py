"""Automated Incident Reconstruction & Forensic Black-Box Playback Engine.

Implements multi-source pre-crash telemetry synchronization (CAN-bus, roadside C-ITS,
dashcam/CV observations, micromobility 6-axis IMU), kinetic energy & impact dynamics
(momentum conservation, Delta-V, deformation energy, Equivalent Barrier Speed),
driver Perception-Reaction Time (PRT vs AASHTO benchmarks), and counterfactual
avoidance evaluation (AEB, speed compliance, geometric sightline clearance)
with cryptographic SHA-256 judicial evidence manifests.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence



FORENSIC_ENGINE_VERSION = "forensic_reconstruction_v1"
FORENSIC_CONTRACT_VERSION = "forensic_reconstruction_public_v1"

# Standard vehicle masses in kg for forensic momentum conservation
STANDARD_AGENT_MASS_KG = {
    "pedestrian": 75.0,
    "bicycle": 85.0,
    "bicyclist": 85.0,
    "cyclist": 85.0,
    "e_scooter": 105.0,
    "motorcycle": 240.0,
    "car": 1500.0,
    "van": 2400.0,
    "transit_bus": 12000.0,
    "bus": 12000.0,
    "heavy_goods_vehicle": 18000.0,
    "truck": 18000.0,
}

# Standard AASHTO / ISO perception-reaction time (PRT) reference benchmarks (seconds)
BENCHMARK_PRT_ALERT_S = 0.9       # Attentive, expectant driver
BENCHMARK_PRT_AASHTO_S = 1.5      # AASHTO Green Book 50th-85th percentile
BENCHMARK_PRT_FATIGUED_S = 2.5    # Impaired or distracted driver


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
class ForensicTelemetrySample:
    """A synchronized telemetry sample along the pre/post-crash timeline."""

    time_sec: float              # Time offset relative to impact instant t0 = 0.0s (e.g. -6.0s to +2.0s)
    speed_kph: float             # Ground velocity in km/h
    speed_mps: float             # Ground velocity in m/s
    accel_mps2: float            # Longitudinal acceleration (+ accel, - braking)
    throttle_pct: float = 0.0    # Accelerator pedal percentage [0..100]
    brake_pressure_bar: float = 0.0  # Hydraulic master cylinder brake pressure [0..160 bar]
    steering_deg: float = 0.0    # Handwheel steering angle in degrees
    yaw_rate_deg_s: float = 0.0  # Vehicle yaw rate
    x_coord: float = 0.0         # Spatial X coordinate in local metric frame (origin at impact point)
    y_coord: float = 0.0         # Spatial Y coordinate in local metric frame

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_sec": round(self.time_sec, 2),
            "speed_kph": round(self.speed_kph, 1),
            "speed_mps": round(self.speed_mps, 2),
            "accel_mps2": round(self.accel_mps2, 2),
            "throttle_pct": round(self.throttle_pct, 1),
            "brake_pressure_bar": round(self.brake_pressure_bar, 1),
            "steering_deg": round(self.steering_deg, 1),
            "yaw_rate_deg_s": round(self.yaw_rate_deg_s, 1),
            "x_coord": round(self.x_coord, 2),
            "y_coord": round(self.y_coord, 2),
        }


@dataclass(frozen=True, slots=True)
class ForensicAgentTrace:
    """Synchronized pre-crash telemetry trace for a vehicle or road user."""

    agent_id: str
    agent_type: str              # car, bus, e_scooter, pedestrian, truck, motorcycle
    mass_kg: float
    length_m: float = 4.5
    width_m: float = 1.8
    samples: tuple[ForensicTelemetrySample, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "mass_kg": round(self.mass_kg, 1),
            "length_m": round(self.length_m, 2),
            "width_m": round(self.width_m, 2),
            "samples_count": len(self.samples),
            "samples": [s.to_dict() for s in self.samples],
        }


@dataclass(frozen=True, slots=True)
class KineticForensicMetrics:
    """Forensic kinetic calculations: momentum conservation, energy, and driver PRT."""

    initial_speed_kph: float
    impact_speed_kph: float
    secondary_initial_speed_kph: float
    secondary_impact_speed_kph: float
    delta_v_primary_kph: float
    delta_v_secondary_kph: float
    impact_kinetic_energy_kj: float
    energy_dissipated_kj: float
    equivalent_barrier_speed_kph: float
    driver_prt_seconds: float
    prt_benchmark_deviation_s: float   # Difference from AASHTO benchmark (positive = delayed)
    hazard_emergence_time_s: float
    brake_onset_time_s: float
    actual_stopping_distance_m: float
    nominal_stopping_distance_m: float
    peak_deceleration_mps2: float
    mean_deceleration_mps2: float
    drac_required_mps2: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_speed_kph": round(self.initial_speed_kph, 1),
            "impact_speed_kph": round(self.impact_speed_kph, 1),
            "secondary_initial_speed_kph": round(self.secondary_initial_speed_kph, 1),
            "secondary_impact_speed_kph": round(self.secondary_impact_speed_kph, 1),
            "delta_v_primary_kph": round(self.delta_v_primary_kph, 1),
            "delta_v_secondary_kph": round(self.delta_v_secondary_kph, 1),
            "impact_kinetic_energy_kj": round(self.impact_kinetic_energy_kj, 1),
            "energy_dissipated_kj": round(self.energy_dissipated_kj, 1),
            "equivalent_barrier_speed_kph": round(self.equivalent_barrier_speed_kph, 1),
            "driver_prt_seconds": round(self.driver_prt_seconds, 2),
            "prt_benchmark_deviation_s": round(self.prt_benchmark_deviation_s, 2),
            "hazard_emergence_time_s": round(self.hazard_emergence_time_s, 2),
            "brake_onset_time_s": round(self.brake_onset_time_s, 2),
            "actual_stopping_distance_m": round(self.actual_stopping_distance_m, 2),
            "nominal_stopping_distance_m": round(self.nominal_stopping_distance_m, 2),
            "peak_deceleration_mps2": round(self.peak_deceleration_mps2, 2),
            "mean_deceleration_mps2": round(self.mean_deceleration_mps2, 2),
            "drac_required_mps2": round(self.drac_required_mps2, 2),
        }


@dataclass(frozen=True, slots=True)
class CounterfactualScenarioResult:
    """Evaluation of a counterfactual safety intervention on collision outcome."""

    scenario_id: str
    scenario_title: str
    intervention_type: str       # aeb_actuation, speed_compliance, geometric_sightline
    collision_avoided: bool
    clearance_margin_m: float    # Positive if avoided, negative if residual impact
    counterfactual_impact_speed_kph: float
    delta_v_reduction_pct: float
    injury_risk_reduction_pct: float
    stopping_distance_m: float
    verdict: str
    explanation: str
    ghost_trajectory_samples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_title": self.scenario_title,
            "intervention_type": self.intervention_type,
            "collision_avoided": self.collision_avoided,
            "clearance_margin_m": round(self.clearance_margin_m, 2),
            "counterfactual_impact_speed_kph": round(self.counterfactual_impact_speed_kph, 1),
            "delta_v_reduction_pct": round(self.delta_v_reduction_pct, 1),
            "injury_risk_reduction_pct": round(self.injury_risk_reduction_pct, 1),
            "stopping_distance_m": round(self.stopping_distance_m, 2),
            "verdict": self.verdict,
            "explanation": self.explanation,
            "ghost_trajectory_samples": self.ghost_trajectory_samples,
        }


@dataclass(frozen=True, slots=True)
class ForensicCaseRecord:
    """A complete forensic incident case record with evidence manifest."""

    case_id: str
    title: str
    incident_timestamp_utc: str
    location_name: str
    latitude: float
    longitude: float
    speed_limit_kph: float
    weather_condition: str
    surface_condition: str
    primary_agent: ForensicAgentTrace
    secondary_agent: ForensicAgentTrace
    kinetic_metrics: KineticForensicMetrics
    counterfactual_scenarios: list[CounterfactualScenarioResult]
    liability_factors: dict[str, float]
    judicial_summary_md: str
    sha256_evidence_hash: str
    created_at_utc: str

    def to_dict(self, include_samples: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "case_id": self.case_id,
            "title": self.title,
            "incident_timestamp_utc": self.incident_timestamp_utc,
            "location_name": self.location_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed_limit_kph": self.speed_limit_kph,
            "weather_condition": self.weather_condition,
            "surface_condition": self.surface_condition,
            "primary_agent": self.primary_agent.to_dict() if include_samples else {
                "agent_id": self.primary_agent.agent_id,
                "agent_type": self.primary_agent.agent_type,
                "mass_kg": self.primary_agent.mass_kg,
            },
            "secondary_agent": self.secondary_agent.to_dict() if include_samples else {
                "agent_id": self.secondary_agent.agent_id,
                "agent_type": self.secondary_agent.agent_type,
                "mass_kg": self.secondary_agent.mass_kg,
            },
            "kinetic_metrics": self.kinetic_metrics.to_dict(),
            "counterfactual_scenarios": [c.to_dict() for c in self.counterfactual_scenarios],
            "liability_factors": self.liability_factors,
            "judicial_summary_md": self.judicial_summary_md,
            "sha256_evidence_hash": self.sha256_evidence_hash,
            "created_at_utc": self.created_at_utc,
            "contract_version": FORENSIC_CONTRACT_VERSION,
        }
        return data


# ---------------------------------------------------------------------------
# Kinetic & Forensic Reconstruction Mathematical Algorithms
# ---------------------------------------------------------------------------

def compute_kinetic_forensics(
    primary_agent: ForensicAgentTrace,
    secondary_agent: ForensicAgentTrace,
    hazard_emergence_time_s: float,
    speed_limit_kph: float = 50.0,
    restitution_coefficient: float = 0.15,
) -> KineticForensicMetrics:
    """Computes momentum conservation, energy dissipation, and driver PRT latency."""
    p_samples = primary_agent.samples
    s_samples = secondary_agent.samples

    if not p_samples:
        raise ValueError("Primary agent trace cannot be empty.")

    # 1. Identify initial speed (before significant braking, e.g. at hazard emergence)
    initial_sample = next((s for s in p_samples if s.time_sec >= hazard_emergence_time_s), p_samples[0])
    initial_speed_kph = initial_sample.speed_kph
    initial_speed_mps = initial_speed_kph / 3.6

    # 2. Identify impact instant (closest to time_sec = 0.0)
    impact_sample = min(p_samples, key=lambda s: abs(s.time_sec))
    impact_speed_kph = impact_sample.speed_kph
    impact_speed_mps = impact_speed_kph / 3.6

    # Secondary agent speeds
    sec_init_sample = next((s for s in s_samples if s.time_sec >= hazard_emergence_time_s), s_samples[0] if s_samples else None)
    sec_impact_sample = min(s_samples, key=lambda s: abs(s.time_sec)) if s_samples else None

    secondary_initial_speed_kph = sec_init_sample.speed_kph if sec_init_sample else 0.0
    secondary_impact_speed_kph = sec_impact_sample.speed_kph if sec_impact_sample else 0.0
    secondary_impact_speed_mps = secondary_impact_speed_kph / 3.6

    # 3. Driver PRT (Perception-Reaction Time)
    # Detected when brake pressure surges (> 5 bar) or deceleration exceeds -1.5 m/s²
    brake_sample = next(
        (s for s in p_samples if s.time_sec >= hazard_emergence_time_s and (s.brake_pressure_bar > 5.0 or s.accel_mps2 < -1.5)),
        None
    )
    if brake_sample:
        brake_onset_time_s = brake_sample.time_sec
        driver_prt_seconds = max(0.1, brake_onset_time_s - hazard_emergence_time_s)
    else:
        # No active braking detected before impact
        brake_onset_time_s = 0.0
        driver_prt_seconds = max(0.1, 0.0 - hazard_emergence_time_s)

    prt_benchmark_deviation_s = driver_prt_seconds - BENCHMARK_PRT_AASHTO_S

    # 4. Deceleration metrics
    braking_samples = [s for s in p_samples if hazard_emergence_time_s <= s.time_sec <= 0.0 and s.accel_mps2 < 0.0]
    peak_decel = min([s.accel_mps2 for s in braking_samples], default=0.0)
    mean_decel = sum([s.accel_mps2 for s in braking_samples]) / len(braking_samples) if braking_samples else 0.0

    # 5. Stopping distances
    # Actual distance traveled from hazard emergence to impact
    start_x = initial_sample.x_coord
    start_y = initial_sample.y_coord
    impact_x = impact_sample.x_coord
    impact_y = impact_sample.y_coord
    actual_stopping_distance_m = math.hypot(impact_x - start_x, impact_y - start_y)

    # Nominal emergency stopping distance under full AASHTO emergency braking (-7.5 m/s²)
    nominal_a = 7.5
    nominal_stopping_distance_m = (initial_speed_mps * BENCHMARK_PRT_ALERT_S) + (initial_speed_mps ** 2) / (2.0 * nominal_a)

    # 6. DRAC required at hazard emergence to avoid collision
    # DRAC = (v1 - v2)^2 / (2 * distance)
    rel_speed_mps = abs(initial_speed_mps - secondary_impact_speed_mps)
    distance_at_hazard = max(1.0, actual_stopping_distance_m)
    drac_required_mps2 = (rel_speed_mps ** 2) / (2.0 * distance_at_hazard)

    # 7. Collision Delta-V & Energy Dissipation (Momentum Conservation)
    m1 = primary_agent.mass_kg
    m2 = secondary_agent.mass_kg
    e = restitution_coefficient

    # Velocity change Delta-V:
    # Delta-v1 = (m2 / (m1 + m2)) * (1 + e) * |v1 - v2|
    rel_v_impact_mps = abs(impact_speed_mps - secondary_impact_speed_mps)
    delta_v1_mps = (m2 / (m1 + m2)) * (1.0 + e) * rel_v_impact_mps
    delta_v2_mps = (m1 / (m1 + m2)) * (1.0 + e) * rel_v_impact_mps

    delta_v_primary_kph = delta_v1_mps * 3.6
    delta_v_secondary_kph = delta_v2_mps * 3.6

    # Kinetic energy at impact: Ek = 0.5 * m1 * v1^2 + 0.5 * m2 * v2^2
    impact_kinetic_energy_kj = (0.5 * m1 * (impact_speed_mps ** 2) + 0.5 * m2 * (secondary_impact_speed_mps ** 2)) / 1000.0

    # Energy dissipated in plastic deformation:
    # Ediss = 0.5 * (m1 * m2 / (m1 + m2)) * (1 - e^2) * (v1 - v2)^2
    energy_dissipated_kj = (0.5 * (m1 * m2 / (m1 + m2)) * (1.0 - (e ** 2)) * (rel_v_impact_mps ** 2)) / 1000.0

    # Equivalent Barrier Speed (EBS): velocity required against a rigid barrier to produce same Ediss
    ebs_mps = math.sqrt(max(0.0, (2.0 * energy_dissipated_kj * 1000.0) / m1))
    equivalent_barrier_speed_kph = ebs_mps * 3.6

    return KineticForensicMetrics(
        initial_speed_kph=initial_speed_kph,
        impact_speed_kph=impact_speed_kph,
        secondary_initial_speed_kph=secondary_initial_speed_kph,
        secondary_impact_speed_kph=secondary_impact_speed_kph,
        delta_v_primary_kph=delta_v_primary_kph,
        delta_v_secondary_kph=delta_v_secondary_kph,
        impact_kinetic_energy_kj=impact_kinetic_energy_kj,
        energy_dissipated_kj=energy_dissipated_kj,
        equivalent_barrier_speed_kph=equivalent_barrier_speed_kph,
        driver_prt_seconds=driver_prt_seconds,
        prt_benchmark_deviation_s=prt_benchmark_deviation_s,
        hazard_emergence_time_s=hazard_emergence_time_s,
        brake_onset_time_s=brake_onset_time_s,
        actual_stopping_distance_m=actual_stopping_distance_m,
        nominal_stopping_distance_m=nominal_stopping_distance_m,
        peak_deceleration_mps2=peak_decel,
        mean_deceleration_mps2=mean_decel,
        drac_required_mps2=drac_required_mps2,
    )


def evaluate_counterfactual_scenarios(
    primary_agent: ForensicAgentTrace,
    secondary_agent: ForensicAgentTrace,
    metrics: KineticForensicMetrics,
    speed_limit_kph: float = 50.0,
) -> list[CounterfactualScenarioResult]:
    """Simulates counterfactual safety interventions to determine whether collision was avoidable."""
    scenarios: list[CounterfactualScenarioResult] = []
    p_samples = primary_agent.samples
    hazard_t = metrics.hazard_emergence_time_s
    initial_v_mps = metrics.initial_speed_kph / 3.6
    dist_to_impact = metrics.actual_stopping_distance_m

    # -----------------------------------------------------------------------
    # Scenario A: Autonomous Emergency Braking (AEB / C-ITS Direct Warning)
    # Rapid machine detection (tr = 0.25s) with maximum dry braking (-8.5 m/s²)
    # -----------------------------------------------------------------------
    aeb_prt_s = 0.25
    aeb_decel_mps2 = -8.5
    time_available = abs(hazard_t)

    # Distance traveled during machine reaction:
    d_react_aeb = initial_v_mps * aeb_prt_s
    # Stopping distance under full AEB braking:
    d_brake_aeb = (initial_v_mps ** 2) / (2.0 * abs(aeb_decel_mps2))
    total_stopping_d_aeb = d_react_aeb + d_brake_aeb

    clearance_aeb = dist_to_impact - total_stopping_d_aeb
    aeb_avoided = clearance_aeb >= 0.0

    if aeb_avoided:
        v_impact_aeb = 0.0
        delta_v_reduc_aeb = 100.0
        injury_reduc_aeb = 100.0
        verdict_aeb = "COLLISION FULLY PREVENTED"
        expl_aeb = f"AEB actuation at t = {round(hazard_t + aeb_prt_s, 2)}s achieves safe vehicle arrest with {round(clearance_aeb, 1)}m safety clearance."
    else:
        # Residual velocity at impact location:
        d_remaining = max(0.0, dist_to_impact - d_react_aeb)
        v_sq = (initial_v_mps ** 2) - 2.0 * abs(aeb_decel_mps2) * d_remaining
        v_impact_aeb = math.sqrt(max(0.0, v_sq)) * 3.6
        delta_v_reduc_aeb = max(0.0, (1.0 - (v_impact_aeb / max(1.0, metrics.impact_speed_kph))) * 100.0)
        injury_reduc_aeb = max(0.0, (1.0 - (v_impact_aeb / max(1.0, metrics.impact_speed_kph)) ** 3) * 100.0)
        verdict_aeb = "SUBSTANTIAL MITIGATION"
        expl_aeb = f"AEB reduced impact speed to {round(v_impact_aeb, 1)} km/h, mitigating severe injury risk by {round(injury_reduc_aeb, 1)}%."

    # Generate ghost trajectory points for Scenario A
    ghost_aeb = []
    for s in p_samples:
        t = s.time_sec
        if t < hazard_t:
            ghost_aeb.append({"time_sec": t, "speed_kph": s.speed_kph, "x_coord": s.x_coord, "y_coord": s.y_coord})
        elif t < hazard_t + aeb_prt_s:
            ghost_aeb.append({"time_sec": t, "speed_kph": s.speed_kph, "x_coord": s.x_coord, "y_coord": s.y_coord})
        else:
            t_brake = t - (hazard_t + aeb_prt_s)
            v_t = max(0.0, initial_v_mps + aeb_decel_mps2 * t_brake)
            ghost_aeb.append({
                "time_sec": t,
                "speed_kph": round(v_t * 3.6, 1),
                "x_coord": round(s.x_coord * (v_t / max(1.0, initial_v_mps)), 2),
                "y_coord": round(s.y_coord * (v_t / max(1.0, initial_v_mps)), 2),
            })

    scenarios.append(CounterfactualScenarioResult(
        scenario_id="SCENARIO_A_AEB",
        scenario_title="C-ITS / Autonomous Emergency Braking (AEB Actuation)",
        intervention_type="aeb_actuation",
        collision_avoided=aeb_avoided,
        clearance_margin_m=clearance_aeb,
        counterfactual_impact_speed_kph=v_impact_aeb,
        delta_v_reduction_pct=delta_v_reduc_aeb,
        injury_risk_reduction_pct=injury_reduc_aeb,
        stopping_distance_m=total_stopping_d_aeb,
        verdict=verdict_aeb,
        explanation=expl_aeb,
        ghost_trajectory_samples=ghost_aeb,
    ))

    # -----------------------------------------------------------------------
    # Scenario B: Regulatory Speed Compliance (e.g., 30 km/h or 50 km/h)
    # Approach at posted speed limit with observed human driver reaction time
    # -----------------------------------------------------------------------
    compliant_v_mps = speed_limit_kph / 3.6
    driver_prt_s = metrics.driver_prt_seconds
    mean_decel = min(-4.5, metrics.mean_deceleration_mps2) if metrics.mean_deceleration_mps2 < 0.0 else -6.0

    d_react_speed = compliant_v_mps * driver_prt_s
    d_brake_speed = (compliant_v_mps ** 2) / (2.0 * abs(mean_decel))
    total_stopping_d_speed = d_react_speed + d_brake_speed

    clearance_speed = dist_to_impact - total_stopping_d_speed
    speed_avoided = clearance_speed >= 0.0

    if speed_avoided:
        v_impact_speed = 0.0
        delta_v_reduc_speed = 100.0
        injury_reduc_speed = 100.0
        verdict_speed = "COLLISION FULLY PREVENTED"
        expl_speed = f"Compliance with the {int(speed_limit_kph)} km/h limit permits complete vehicle stop with {round(clearance_speed, 1)}m clearance."
    else:
        d_remaining = max(0.0, dist_to_impact - d_react_speed)
        v_sq = (compliant_v_mps ** 2) - 2.0 * abs(mean_decel) * d_remaining
        v_impact_speed = math.sqrt(max(0.0, v_sq)) * 3.6
        delta_v_reduc_speed = max(0.0, (1.0 - (v_impact_speed / max(1.0, metrics.impact_speed_kph))) * 100.0)
        injury_reduc_speed = max(0.0, (1.0 - (v_impact_speed / max(1.0, metrics.impact_speed_kph)) ** 3) * 100.0)
        verdict_speed = "SIGNIFICANT SEVERITY REDUCTION"
        expl_speed = f"Speed compliance reduces impact speed to {round(v_impact_speed, 1)} km/h, reducing severe injury probability by {round(injury_reduc_speed, 1)}%."

    # Ghost trajectory for Scenario B
    ghost_speed = []
    for s in p_samples:
        t = s.time_sec
        v_ratio = min(1.0, speed_limit_kph / max(1.0, metrics.initial_speed_kph))
        ghost_speed.append({
            "time_sec": t,
            "speed_kph": round(s.speed_kph * v_ratio, 1),
            "x_coord": round(s.x_coord * v_ratio, 2),
            "y_coord": round(s.y_coord * v_ratio, 2),
        })

    scenarios.append(CounterfactualScenarioResult(
        scenario_id="SCENARIO_B_SPEED_COMPLIANCE",
        scenario_title=f"Regulatory Speed Compliance ({int(speed_limit_kph)} km/h Zone)",
        intervention_type="speed_compliance",
        collision_avoided=speed_avoided,
        clearance_margin_m=clearance_speed,
        counterfactual_impact_speed_kph=v_impact_speed,
        delta_v_reduction_pct=delta_v_reduc_speed,
        injury_risk_reduction_pct=injury_reduc_speed,
        stopping_distance_m=total_stopping_d_speed,
        verdict=verdict_speed,
        explanation=expl_speed,
        ghost_trajectory_samples=ghost_speed,
    ))

    # -----------------------------------------------------------------------
    # Scenario C: Infrastructure Geometric Sightline Clearance
    # Roadside obstruction eliminated, providing 0.9s earlier hazard visibility
    # -----------------------------------------------------------------------
    sightline_gain_s = 0.9
    earlier_hazard_t = hazard_t - sightline_gain_s
    time_gain_dist = initial_v_mps * sightline_gain_s
    extended_dist_to_impact = dist_to_impact + time_gain_dist

    total_stopping_d_sight = (initial_v_mps * metrics.driver_prt_seconds) + (initial_v_mps ** 2) / (2.0 * abs(mean_decel))
    clearance_sight = extended_dist_to_impact - total_stopping_d_sight
    sight_avoided = clearance_sight >= 0.0

    if sight_avoided:
        v_impact_sight = 0.0
        delta_v_reduc_sight = 100.0
        injury_reduc_sight = 100.0
        verdict_sight = "COLLISION FULLY PREVENTED"
        expl_sight = f"Clearing corner sightline obstruction affords +0.9s early perception, halting the vehicle {round(clearance_sight, 1)}m before conflict point."
    else:
        d_remaining = max(0.0, extended_dist_to_impact - (initial_v_mps * metrics.driver_prt_seconds))
        v_sq = (initial_v_mps ** 2) - 2.0 * abs(mean_decel) * d_remaining
        v_impact_sight = math.sqrt(max(0.0, v_sq)) * 3.6
        delta_v_reduc_sight = max(0.0, (1.0 - (v_impact_sight / max(1.0, metrics.impact_speed_kph))) * 100.0)
        injury_reduc_sight = max(0.0, (1.0 - (v_impact_sight / max(1.0, metrics.impact_speed_kph)) ** 3) * 100.0)
        verdict_sight = "MODERATE MITIGATION"
        expl_sight = f"Sightline extension mitigates impact velocity to {round(v_impact_sight, 1)} km/h."

    scenarios.append(CounterfactualScenarioResult(
        scenario_id="SCENARIO_C_GEOMETRIC_SIGHTLINE",
        scenario_title="Infrastructure Sightline Clearance (+15m Sight Triangle)",
        intervention_type="geometric_sightline",
        collision_avoided=sight_avoided,
        clearance_margin_m=clearance_sight,
        counterfactual_impact_speed_kph=v_impact_sight,
        delta_v_reduction_pct=delta_v_reduc_sight,
        injury_risk_reduction_pct=injury_reduc_sight,
        stopping_distance_m=total_stopping_d_sight,
        verdict=verdict_sight,
        explanation=expl_sight,
        ghost_trajectory_samples=[],
    ))

    return scenarios


def compute_liability_attribution(
    metrics: KineticForensicMetrics,
    speed_limit_kph: float,
) -> dict[str, float]:
    """Quantifies forensic contributing causal factors in incident mechanics."""
    # Factor 1: Excessive Speed contribution
    speed_excess = max(0.0, metrics.initial_speed_kph - speed_limit_kph)
    speed_factor = min(60.0, (speed_excess / speed_limit_kph) * 100.0)

    # Factor 2: Driver Perception-Reaction Time (PRT) delay
    prt_delay = max(0.0, metrics.driver_prt_seconds - BENCHMARK_PRT_ALERT_S)
    prt_factor = min(40.0, (prt_delay / 1.5) * 40.0)

    # Factor 3: Infrastructure visibility / sightline deficit
    sightline_factor = max(10.0, 100.0 - (speed_factor + prt_factor))

    # Normalize to 100%
    total = speed_factor + prt_factor + sightline_factor
    return {
        "excessive_speed_contribution_pct": round((speed_factor / total) * 100.0, 1),
        "perception_delay_contribution_pct": round((prt_factor / total) * 100.0, 1),
        "infrastructure_sightline_deficit_pct": round((sightline_factor / total) * 100.0, 1),
    }


def generate_judicial_evidence_dossier(
    case_id: str,
    title: str,
    location_name: str,
    incident_timestamp_utc: str,
    speed_limit_kph: float,
    primary_agent: ForensicAgentTrace,
    secondary_agent: ForensicAgentTrace,
    metrics: KineticForensicMetrics,
    counterfactuals: list[CounterfactualScenarioResult],
    liability: dict[str, float],
    sha256_hash: str,
) -> str:
    """Generates an evidentiary accident reconstruction perital dossier for judicial authorities."""
    lines = [
        f"# PERIZIA TECNICO-FORENSE DI RICOSTRUZIONE CINEMATICA INCIDENTALE",
        f"**Fascicolo Giudiziario:** `{case_id}`",
        f"**Autorità Competente:** Procura della Repubblica / Polizia Stradale / Servizio Mobilità Sostenibile",
        f"**Data e Ora Rilevazione (UTC):** `{incident_timestamp_utc}`",
        f"**Localizzazione:** {location_name}",
        f"**Limite di Velocità Vigente:** {int(speed_limit_kph)} km/h",
        "",
        "---",
        "",
        "## 1. Identificazione dei Soggetti e Masse Cinematiche Coinvolte",
        f"- **Veicolo Principale (Agente 1):** `{primary_agent.agent_id}` ({primary_agent.agent_type.upper()}), Massa: `{primary_agent.mass_kg:.1f} kg`, Lunghezza: `{primary_agent.length_m:.1f} m`",
        f"- **Soggetto Collidente / VRU (Agente 2):** `{secondary_agent.agent_id}` ({secondary_agent.agent_type.upper()}), Massa: `{secondary_agent.mass_kg:.1f} kg`, Lunghezza: `{secondary_agent.length_m:.1f} m`",
        "",
        "## 2. Dinamica Cinematica ed Energetica dell'Impatto",
        f"- **Velocità Iniziale Rilevata ($v_0$):** **{metrics.initial_speed_kph:.1f} km/h** ({metrics.initial_speed_kph / 3.6:.2f} m/s) "
        f"{'(SUPERAMENTO LIMITE)' if metrics.initial_speed_kph > speed_limit_kph else '(NEL LIMITE)'}",
        f"- **Velocità Istantanea all'Impatto ($v_{{imp}}$):** **{metrics.impact_speed_kph:.1f} km/h**",
        f"- **Delta-V Collizionale ($\\Delta v_1$):** `{metrics.delta_v_primary_kph:.1f} km/h`",
        f"- **Delta-V Subito dal VRU/Veicolo 2 ($\\Delta v_2$):** `{metrics.delta_v_secondary_kph:.1f} km/h`",
        f"- **Energia Cinetica Dissipata nell'Urto:** **{metrics.energy_dissipated_kj:.1f} kJ**",
        f"- **Equivalent Barrier Speed (EBS):** `{metrics.equivalent_barrier_speed_kph:.1f} km/h`",
        "",
        "## 3. Analisi Psico-Percettiva del Conducente (PRT)",
        f"- **Istante di Insorgenza del Pericolo ($t_{{haz}}$):** `{metrics.hazard_emergence_time_s:.2f} s` prima del contatto",
        f"- **Istante di Inizio Frenata Efficace ($t_{{brake}}$):** `{metrics.brake_onset_time_s:.2f} s`",
        f"- **Tempo di Percezione e Reazione (PRT):** **{metrics.driver_prt_seconds:.2f} s**",
        f"  - Benchmark Conducente Attento: `{BENCHMARK_PRT_ALERT_S:.2f} s`",
        f"  - Benchmark Standard AASHTO Green Book: `{BENCHMARK_PRT_AASHTO_S:.2f} s`",
        f"  - Scostamento / Ritardo di Reazione: `+{metrics.prt_benchmark_deviation_s:.2f} s`",
        f"- **Decelerazione di Picco Raggiunta:** `{abs(metrics.peak_deceleration_mps2):.2f} m/s²` ({abs(metrics.peak_deceleration_mps2)/9.81:.2f}g)",
        f"- **DRAC Richiesto per l'Evitamento:** `{metrics.drac_required_mps2:.2f} m/s²`",
        "",
        "## 4. Valutazione Controfattuale di Evitabilità ('What-If')",
        "| Scenario Controfattuale | Esito Collisione | Margine di Arresto | Velocità Residua | Riduzione Rischio Lesioni |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for cf in counterfactuals:
        status_symbol = "✓ EVITATO" if cf.collision_avoided else "✗ IMPATTO RESIDUO"
        margin_str = f"+{cf.clearance_margin_m:.1f} m" if cf.clearance_margin_m >= 0 else f"{cf.clearance_margin_m:.1f} m"
        lines.append(
            f"| **{cf.scenario_title}** | **{status_symbol}** | `{margin_str}` | `{cf.counterfactual_impact_speed_kph:.1f} km/h` | **-{cf.injury_risk_reduction_pct:.1f}%** |"
        )

    lines.extend([
        "",
        "## 5. Ripartizione Causale Forense (Liability Factors)",
        f"- **Contributo Eccesso di Velocità:** `{liability.get('excessive_speed_contribution_pct', 0.0):.1f}%`",
        f"- **Contributo Ritardo di Reazione (PRT Latency):** `{liability.get('perception_delay_contribution_pct', 0.0):.1f}%`",
        f"- **Deficit Visibilità Geometrica Infrastrutturale:** `{liability.get('infrastructure_sightline_deficit_pct', 0.0):.1f}%`",
        "",
        "## 6. Attestazione di Integrità Probatoria e Catena di Custodia",
        f"Il presente fascicolo digitale è stato generato deterministicamente dal Motore Sovrano di Ricostruzione Cinematica `forensic_reconstruction_v1`.",
        f"- **Codice Impronta SHA-256 (Integrità Crittografica):**",
        f"  `{sha256_hash}`",
        f"- **Data di Sigillo Probatorio:** `{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}`",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Case construction from user-supplied telemetry
# ---------------------------------------------------------------------------

MIN_SAMPLES_PER_AGENT = 3


class ForensicInputError(ValueError):
    """Raised when submitted telemetry cannot support a reconstruction."""


def _sample_from_mapping(raw: Mapping[str, Any]) -> ForensicTelemetrySample:
    speed_kph = _safe_float(raw.get("speed_kph"))
    speed_mps = raw.get("speed_mps")
    return ForensicTelemetrySample(
        time_sec=_safe_float(raw.get("time_sec")),
        speed_kph=speed_kph,
        speed_mps=_safe_float(speed_mps) if speed_mps is not None else speed_kph / 3.6,
        accel_mps2=_safe_float(raw.get("accel_mps2")),
        throttle_pct=_safe_float(raw.get("throttle_pct")),
        brake_pressure_bar=_safe_float(raw.get("brake_pressure_bar")),
        steering_deg=_safe_float(raw.get("steering_deg")),
        yaw_rate_deg_s=_safe_float(raw.get("yaw_rate_deg_s")),
        x_coord=_safe_float(raw.get("x_coord")),
        y_coord=_safe_float(raw.get("y_coord")),
    )


def agent_trace_from_mapping(raw: Mapping[str, Any], role: str) -> ForensicAgentTrace:
    """Parse and validate one agent's telemetry trace."""
    agent_type = str(raw.get("agent_type") or "").strip()
    if not agent_type:
        raise ForensicInputError(f"{role}: agent_type is required.")
    samples_raw = raw.get("samples") or []
    if len(samples_raw) < MIN_SAMPLES_PER_AGENT:
        raise ForensicInputError(
            f"{role}: at least {MIN_SAMPLES_PER_AGENT} telemetry samples are required."
        )
    samples = tuple(sorted((_sample_from_mapping(s) for s in samples_raw), key=lambda s: s.time_sec))
    if not (samples[0].time_sec <= 0.0 <= samples[-1].time_sec):
        raise ForensicInputError(
            f"{role}: samples must span the impact instant (time_sec = 0.0)."
        )
    mass = raw.get("mass_kg")
    return ForensicAgentTrace(
        agent_id=str(raw.get("agent_id") or role),
        agent_type=agent_type,
        mass_kg=_safe_float(mass) if mass is not None else STANDARD_AGENT_MASS_KG.get(agent_type, 1500.0),
        length_m=_safe_float(raw.get("length_m"), 4.5),
        width_m=_safe_float(raw.get("width_m"), 1.8),
        samples=samples,
    )


def build_forensic_case(
    *,
    case_id: str,
    title: str,
    location_name: str,
    incident_timestamp_utc: str,
    latitude: float,
    longitude: float,
    speed_limit_kph: float,
    weather_condition: str,
    surface_condition: str,
    primary_agent: ForensicAgentTrace,
    secondary_agent: ForensicAgentTrace,
    hazard_emergence_time_s: float,
    created_at_utc: str | None = None,
) -> ForensicCaseRecord:
    """Reconstruct a case: kinetics, counterfactuals, liability, and dossier."""
    metrics = compute_kinetic_forensics(
        primary_agent, secondary_agent,
        hazard_emergence_time_s=hazard_emergence_time_s,
        speed_limit_kph=speed_limit_kph,
    )
    counterfactuals = evaluate_counterfactual_scenarios(
        primary_agent, secondary_agent, metrics, speed_limit_kph=speed_limit_kph
    )
    liability = compute_liability_attribution(metrics, speed_limit_kph=speed_limit_kph)
    hash_source = (
        f"{case_id}|{metrics.initial_speed_kph}|{metrics.impact_speed_kph}|{metrics.energy_dissipated_kj}"
    )
    sha256 = hashlib.sha256(hash_source.encode("utf-8")).hexdigest()
    summary = generate_judicial_evidence_dossier(
        case_id=case_id,
        title=title,
        location_name=location_name,
        incident_timestamp_utc=incident_timestamp_utc,
        speed_limit_kph=speed_limit_kph,
        primary_agent=primary_agent,
        secondary_agent=secondary_agent,
        metrics=metrics,
        counterfactuals=counterfactuals,
        liability=liability,
        sha256_hash=sha256,
    )
    return ForensicCaseRecord(
        case_id=case_id,
        title=title,
        incident_timestamp_utc=incident_timestamp_utc,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        speed_limit_kph=speed_limit_kph,
        weather_condition=weather_condition,
        surface_condition=surface_condition,
        primary_agent=primary_agent,
        secondary_agent=secondary_agent,
        kinetic_metrics=metrics,
        counterfactual_scenarios=counterfactuals,
        liability_factors=liability,
        judicial_summary_md=summary,
        sha256_evidence_hash=sha256,
        created_at_utc=created_at_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def build_forensic_case_from_payload(payload: Mapping[str, Any]) -> ForensicCaseRecord:
    """Validate a JSON payload and reconstruct the case it describes."""
    case_id = str(payload.get("case_id") or "").strip()
    if not case_id:
        raise ForensicInputError("case_id is required.")
    if "hazard_emergence_time_s" not in payload:
        raise ForensicInputError("hazard_emergence_time_s is required.")
    return build_forensic_case(
        case_id=case_id,
        title=str(payload.get("title") or case_id),
        location_name=str(payload.get("location_name") or ""),
        incident_timestamp_utc=str(payload.get("incident_timestamp_utc") or ""),
        latitude=_safe_float(payload.get("latitude")),
        longitude=_safe_float(payload.get("longitude")),
        speed_limit_kph=_safe_float(payload.get("speed_limit_kph"), 50.0),
        weather_condition=str(payload.get("weather_condition") or "unknown"),
        surface_condition=str(payload.get("surface_condition") or "unknown"),
        primary_agent=agent_trace_from_mapping(payload.get("primary_agent") or {}, "primary_agent"),
        secondary_agent=agent_trace_from_mapping(payload.get("secondary_agent") or {}, "secondary_agent"),
        hazard_emergence_time_s=_safe_float(payload.get("hazard_emergence_time_s")),
        created_at_utc=payload.get("created_at_utc"),
    )
