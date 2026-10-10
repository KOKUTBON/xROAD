"""Synthetic forensic reconstruction scenarios for tests.

These generate physically plausible pre-crash trajectories so the kinetic,
counterfactual, and liability computations can be exercised deterministically.
They describe no real place, operator, vehicle, or event.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from road_risk_modeling.forensic_reconstruction_engine import (
    ForensicAgentTrace,
    ForensicTelemetrySample,
)


def _payload(primary: ForensicAgentTrace, secondary: ForensicAgentTrace, **context: Any) -> dict[str, Any]:
    def trace(agent: ForensicAgentTrace) -> dict[str, Any]:
        return {
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
            "mass_kg": agent.mass_kg,
            "length_m": agent.length_m,
            "width_m": agent.width_m,
            "samples": [asdict(sample) for sample in agent.samples],
        }

    return {**context, "primary_agent": trace(primary), "secondary_agent": trace(secondary)}


def bus_vs_scooter_angle_collision() -> dict[str, Any]:
    """Synthetic trajectories — no real location, operator, or event."""

    # Bus approaching at 44 km/h in a 30 km/h zone; e-scooter enters from right at t = -3.2s
    p_samples = []
    # From -5.0s to +1.5s
    times = [round(-5.0 + i * 0.2, 1) for i in range(34)]  # -5.0 to +1.6
    for t in times:
        if t < -1.4:  # Pre-braking phase (44 km/h)
            v = 44.0
            acc = 0.0
            p_bar = 0.0
            th = 25.0
            x = -v / 3.6 * abs(t)
            y = 0.0
        elif t < 0.0:  # Emergency braking phase
            t_rel = t - (-1.4)
            v = max(26.0, 44.0 - 12.8 * t_rel)
            acc = -3.6
            p_bar = 65.0
            th = 0.0
            x = -v / 3.6 * abs(t)
            y = 0.2 * t_rel
        else:  # Post-impact standstill
            v = max(0.0, 26.0 - 20.0 * t)
            acc = -5.0
            p_bar = 85.0
            th = 0.0
            x = 0.0
            y = 0.3
        p_samples.append(ForensicTelemetrySample(
            time_sec=t,
            speed_kph=v,
            speed_mps=v / 3.6,
            accel_mps2=acc,
            throttle_pct=th,
            brake_pressure_bar=p_bar,
            steering_deg=4.2 if t >= -1.4 else 0.0,
            yaw_rate_deg_s=2.5 if t >= -1.4 else 0.0,
            x_coord=x,
            y_coord=y,
        ))

    # Scooter trajectory (crossing from y = 14m at 18 km/h)
    s_samples = []
    for t in times:
        if t <= 0.0:
            v_scoot = 18.0
            y_s = max(0.0, 18.0 / 3.6 * abs(t))
            x_s = 0.5 * (t / 3.0)
        else:
            v_scoot = 0.0
            y_s = 0.0
            x_s = 1.2
        s_samples.append(ForensicTelemetrySample(
            time_sec=t,
            speed_kph=v_scoot,
            speed_mps=v_scoot / 3.6,
            accel_mps2=-0.2 if t <= 0.0 else -8.0,
            throttle_pct=60.0 if t <= 0.0 else 0.0,
            brake_pressure_bar=0.0,
            steering_deg=0.0,
            yaw_rate_deg_s=0.0,
            x_coord=x_s,
            y_coord=y_s,
        ))

    primary = ForensicAgentTrace(
        agent_id="bus-1",
        agent_type="bus",
        mass_kg=12000.0,
        length_m=12.0,
        width_m=2.5,
        samples=tuple(p_samples),
    )
    secondary = ForensicAgentTrace(
        agent_id="scooter-1",
        agent_type="e_scooter",
        mass_kg=105.0,
        length_m=1.2,
        width_m=0.6,
        samples=tuple(s_samples),
    )

    return _payload(primary, secondary, **{'case_id': 'CASE-SYN-001', 'title': 'Synthetic scenario: bus vs e-scooter angle collision', 'location_name': 'Synthetic junction A', 'incident_timestamp_utc': '2026-01-01T08:00:00Z', 'latitude': 0.0, 'longitude': 0.0, 'speed_limit_kph': 30.0, 'weather_condition': 'clear', 'surface_condition': 'dry', 'hazard_emergence_time_s': -3.2})


def car_vs_pedestrian_crosswalk() -> dict[str, Any]:
    """Synthetic trajectories — no real location, operator, or event."""

    times = [round(-4.0 + i * 0.2, 1) for i in range(26)]  # -4.0 to +1.0
    p_samples = []
    for t in times:
        if t < -1.2:
            v = 56.0
            acc = 0.0
            p_bar = 0.0
            th = 30.0
            x = -v / 3.6 * abs(t)
            y = 0.0
        elif t < 0.0:
            t_rel = t - (-1.2)
            v = max(32.0, 56.0 - 20.0 * t_rel)
            acc = -5.8
            p_bar = 90.0
            th = 0.0
            x = -v / 3.6 * abs(t)
            y = 0.0
        else:
            v = max(0.0, 32.0 - 32.0 * t)
            acc = -7.0
            p_bar = 110.0
            th = 0.0
            x = 0.0
            y = 0.0
        p_samples.append(ForensicTelemetrySample(
            time_sec=t,
            speed_kph=v,
            speed_mps=v / 3.6,
            accel_mps2=acc,
            throttle_pct=th,
            brake_pressure_bar=p_bar,
            x_coord=x,
            y_coord=y,
        ))

    s_samples = []
    for t in times:
        v_ped = 4.5 if t <= 0.0 else 0.0
        y_ped = max(0.0, 4.5 / 3.6 * abs(t)) if t <= 0.0 else 0.0
        s_samples.append(ForensicTelemetrySample(
            time_sec=t,
            speed_kph=v_ped,
            speed_mps=v_ped / 3.6,
            accel_mps2=0.0,
            x_coord=0.0,
            y_coord=y_ped,
        ))

    primary = ForensicAgentTrace(
        agent_id="car-1",
        agent_type="car",
        mass_kg=1550.0,
        length_m=4.6,
        width_m=1.8,
        samples=tuple(p_samples),
    )
    secondary = ForensicAgentTrace(
        agent_id="pedestrian-1",
        agent_type="pedestrian",
        mass_kg=75.0,
        length_m=0.5,
        width_m=0.5,
        samples=tuple(s_samples),
    )

    return _payload(primary, secondary, **{'case_id': 'CASE-SYN-002', 'title': 'Synthetic scenario: car vs pedestrian on crosswalk', 'location_name': 'Synthetic crossing B', 'incident_timestamp_utc': '2026-01-01T19:00:00Z', 'latitude': 0.0, 'longitude': 0.0, 'speed_limit_kph': 50.0, 'weather_condition': 'night_clear', 'surface_condition': 'dry', 'hazard_emergence_time_s': -2.6})


def truck_vs_queue_rear_end() -> dict[str, Any]:
    """Synthetic trajectories — no real location, operator, or event."""

    times = [round(-5.0 + i * 0.2, 1) for i in range(32)]  # -5.0 to +1.2
    p_samples = []
    for t in times:
        if t < -1.8:
            v = 82.0
            acc = 0.0
            p_bar = 0.0
            th = 40.0
            x = -v / 3.6 * abs(t)
            y = 0.0
        elif t < 0.0:
            t_rel = t - (-1.8)
            v = max(46.0, 82.0 - 20.0 * t_rel)
            acc = -5.5
            p_bar = 120.0
            th = 0.0
            x = -v / 3.6 * abs(t)
            y = 0.0
        else:
            v = max(0.0, 46.0 - 46.0 * t)
            acc = -8.0
            p_bar = 140.0
            th = 0.0
            x = 0.0
            y = 0.0
        p_samples.append(ForensicTelemetrySample(
            time_sec=t,
            speed_kph=v,
            speed_mps=v / 3.6,
            accel_mps2=acc,
            throttle_pct=th,
            brake_pressure_bar=p_bar,
            x_coord=x,
            y_coord=y,
        ))

    s_samples = []
    for t in times:
        s_samples.append(ForensicTelemetrySample(
            time_sec=t,
            speed_kph=0.0,
            speed_mps=0.0,
            accel_mps2=0.0,
            x_coord=0.0,
            y_coord=0.0,
        ))

    primary = ForensicAgentTrace(
        agent_id="truck-1",
        agent_type="truck",
        mass_kg=18000.0,
        length_m=16.5,
        width_m=2.55,
        samples=tuple(p_samples),
    )
    secondary = ForensicAgentTrace(
        agent_id="car-2",
        agent_type="car",
        mass_kg=1200.0,
        length_m=3.6,
        width_m=1.6,
        samples=tuple(s_samples),
    )

    return _payload(primary, secondary, **{'case_id': 'CASE-SYN-003', 'title': 'Synthetic scenario: heavy vehicle vs queued traffic rear-end', 'location_name': 'Synthetic arterial C', 'incident_timestamp_utc': '2026-01-01T14:00:00Z', 'latitude': 0.0, 'longitude': 0.0, 'speed_limit_kph': 70.0, 'weather_condition': 'rain_wet', 'surface_condition': 'wet', 'hazard_emergence_time_s': -3.8})


ALL_SCENARIOS = (
    bus_vs_scooter_angle_collision,
    car_vs_pedestrian_crosswalk,
    truck_vs_queue_rear_end,
)
