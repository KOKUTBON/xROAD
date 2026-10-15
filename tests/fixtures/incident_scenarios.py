"""Synthetic multi-incident scenarios for tests.

The capacities and flows exercise the LWR shockwave, conflict-detection, and
flow-split maths. No real place, road, or event is described.
"""

from __future__ import annotations

from typing import Any

from road_risk_modeling.incident_coordination_engine import ActiveIncidentNode


def multi_incident_scenarios() -> list[dict[str, Any]]:
    """Synthetic multi-incident scenarios. No real place or road is described."""
    return [
        {
            "scenario_id": "scenario_ring_road_bottleneck",
            "title": "Ring-road bottleneck with a concurrent arterial work zone",
            "description": (
                "Dual concurrent incidents: Heavy truck rollover on Ring Corridor South KM 12.4 "
                "with 60% capacity drop, coupled with scheduled emergency resurfacing on "
                "Arterial Link A (Exit 13). Direct detour collision course detected towards primary feeder."
            ),
            "upstream_distance_km": 2.1,
            "incidents": [
                ActiveIncidentNode(
                    incident_id="INC-A1",
                    corridor_id="corridor_ring_south",
                    location_name="Ring road south km 12.4",
                    latitude=0.1072,
                    longitude=0.8924,
                    severity="critical",
                    capacity_reduction_pct=60.0,
                    incoming_flow_vph=2500.0,
                    residual_capacity_vph=1000.0,
                    nominal_capacity_vph=2500.0,
                    candidate_detour_corridors=[
                        "corridor_arterial_a",
                        "corridor_bypass_b",
                        "corridor_coastal_c",
                    ],
                    description="Heavy vehicle rollover blocking two lanes.",
                ),
                ActiveIncidentNode(
                    incident_id="INC-A2",
                    corridor_id="corridor_arterial_a",
                    location_name="Arterial A km 2.1 (exit 13)",
                    latitude=0.1028,
                    longitude=0.8850,
                    severity="severe",
                    capacity_reduction_pct=50.0,
                    incoming_flow_vph=900.0,
                    residual_capacity_vph=700.0,
                    nominal_capacity_vph=1400.0,
                    candidate_detour_corridors=[
                        "corridor_bypass_b",
                        "corridor_link_d",
                    ],
                    description="Emergency resurfacing work zone.",
                ),
            ],
            "alternative_corridors": [
                {
                    "corridor_id": "corridor_arterial_a",
                    "corridor_name": "Arterial A",
                    "capacity_vph": 1400.0,
                    "speed_kmh": 45.0,
                    "length_km": 3.8,
                    "vms_guidance_text": "EXIT 13 CLOSED - CONTINUE",
                },
                {
                    "corridor_id": "corridor_bypass_b",
                    "corridor_name": "Bypass B",
                    "capacity_vph": 1600.0,
                    "speed_kmh": 60.0,
                    "length_km": 5.2,
                    "vms_guidance_text": "RECOMMENDED DETOUR: BYPASS B",
                },
                {
                    "corridor_id": "corridor_coastal_c",
                    "corridor_name": "Coastal route C",
                    "capacity_vph": 1300.0,
                    "speed_kmh": 40.0,
                    "length_km": 6.1,
                    "vms_guidance_text": "ALTERNATIVE ROUTE: COASTAL C",
                },
            ],
        },
        {
            "scenario_id": "scenario_vru_surge_interchange",
            "title": "Pedestrian surge with a concurrent interchange closure",
            "description": (
                "High-density pedestrian egress event at Central Auditorium along Boulevard D "
                "conjoined with utility trench works at Interchange E at the rail station. Detour "
                "conflict detected on central connector due to simultaneous traffic injection."
            ),
            "upstream_distance_km": 1.4,
            "incidents": [
                ActiveIncidentNode(
                    incident_id="INC-B1",
                    corridor_id="corridor_boulevard_d",
                    location_name="Boulevard D at the auditorium",
                    latitude=0.1235,
                    longitude=0.8722,
                    severity="severe",
                    capacity_reduction_pct=70.0,
                    incoming_flow_vph=1200.0,
                    residual_capacity_vph=360.0,
                    nominal_capacity_vph=1200.0,
                    candidate_detour_corridors=[
                        "corridor_avenue_f",
                        "corridor_coastal_g",
                        "corridor_connector_e",
                    ],
                    description="Evening event pedestrian outflow and shuttle staging.",
                ),
                ActiveIncidentNode(
                    incident_id="INC-B2",
                    corridor_id="corridor_interchange_e",
                    location_name="Interchange E at the rail station",
                    latitude=0.1180,
                    longitude=0.8698,
                    severity="severe",
                    capacity_reduction_pct=60.0,
                    incoming_flow_vph=850.0,
                    residual_capacity_vph=400.0,
                    nominal_capacity_vph=1000.0,
                    candidate_detour_corridors=[
                        "corridor_avenue_f",
                        "corridor_ringway_h",
                    ],
                    description="Bus-rail interchange reconstruction.",
                ),
            ],
            "alternative_corridors": [
                {
                    "corridor_id": "corridor_avenue_f",
                    "corridor_name": "Avenue F",
                    "capacity_vph": 900.0,
                    "speed_kmh": 35.0,
                    "length_km": 2.2,
                    "vms_guidance_text": "AVENUE F - HIGH CONGESTION RISK",
                },
                {
                    "corridor_id": "corridor_coastal_g",
                    "corridor_name": "Coastal route G",
                    "capacity_vph": 1400.0,
                    "speed_kmh": 45.0,
                    "length_km": 3.5,
                    "vms_guidance_text": "OLD-TOWN DETOUR VIA COASTAL ROUTE",
                },
                {
                    "corridor_id": "corridor_ringway_h",
                    "corridor_name": "Ringway H",
                    "capacity_vph": 1500.0,
                    "speed_kmh": 40.0,
                    "length_km": 4.1,
                    "vms_guidance_text": "TO STATION: USE RINGWAY H",
                },
            ],
        },
    ]
