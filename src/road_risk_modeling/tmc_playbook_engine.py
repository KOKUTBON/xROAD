"""Autonomous Incident Response & Traffic Management Center (TMC) Playbook Automation Engine.

Translates real-time risk alerts (ST-GNN forecasting, telematics near-miss clusters,
C-ITS warnings, adverse weather) into coordinated multi-tier field actuation plans:
1. Dynamic VSL Step-Down (shockwave dissipation)
2. Multi-Lingual VMS Layout (Vienna Convention pictograms A,17, A,24, A,32, C,14)
3. C-ITS Direct V2X Envelopes (ETSI EN 302 637-3 DENM messages)
4. Shared Micromobility MDS Geofence Enforcement (10 km/h slow zone / no-go zone)
5. Highway Patrol & Emergency Dispatch Recommendations
with EU AI Act (Regulation 2024/1689 Article 14) Human-in-the-Loop (HITL) governance.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Mapping, Sequence


TMC_ENGINE_VERSION = "tmc_playbook_engine_v1"
TMC_CONTRACT_VERSION = "tmc_playbook_public_v1"

# EU AI Act (Regulation 2024/1689) Article 14 Human-in-the-Loop Governance Modes
HITL_OVERSIGHT_LEVELS = {
    "ADVISORY": "Operator manual confirmation required for each action tier",
    "ONE_CLICK": "Pre-computed multi-tier bundle authorized via single operator confirmation",
    "AUTONOMOUS_WITH_OVERRIDE": "Immediate field actuation with a 15-second human veto grace window",
}

# Standard Vienna Convention Pictograms for VMS
VIENNA_PICTOGRAMS = {
    "CONGESTION_AHEAD": "A,17",
    "SLIPPERY_ROAD": "A,24",
    "DANGER_GENERAL": "A,32",
    "PEDESTRIAN_CROSSING": "A,11",
    "SPEED_LIMIT": "C,14",
    "NO_ENTRY": "C,1",
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
    return int(round(_safe_float(val, float(default))))


@dataclass(frozen=True, slots=True)
class PlaybookTriggerRule:
    """Threshold criteria to trigger an incident response playbook."""

    threat_type: str                  # shockwave_congestion, adverse_weather, vru_crosswalk_surge, near_miss_cluster, queue_tail
    min_severity_tier: str            # critical, severe, elevated, moderate
    min_crash_probability: float = 0.50
    min_speed_drop_kmh: float = 15.0
    min_precipitation_mm_h: float = 0.0
    min_near_miss_count: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "threat_type": self.threat_type,
            "min_severity_tier": self.min_severity_tier,
            "min_crash_probability": round(self.min_crash_probability, 3),
            "min_speed_drop_kmh": round(self.min_speed_drop_kmh, 1),
            "min_precipitation_mm_h": round(self.min_precipitation_mm_h, 1),
            "min_near_miss_count": self.min_near_miss_count,
        }


@dataclass(frozen=True, slots=True)
class PlaybookActuationAction:
    """An operational actuation action across one of the 5 field tiers."""

    action_id: str
    action_tier: str                  # vsl_control, vms_signage, cits_denm, micromobility_geofence, patrol_dispatch
    target_entity_id: str             # gantry_id, vms_id, rsu_id, operator_fleet, dispatch_unit
    headline: str
    parameters: dict[str, Any]
    status: str = "staged"            # staged, active, overridden, completed, failed

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_tier": self.action_tier,
            "target_entity_id": self.target_entity_id,
            "headline": self.headline,
            "parameters": self.parameters,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class TmcPlaybookTemplate:
    """Standard Operating Playbook definition for traffic control center."""

    playbook_id: str
    title: str
    description: str
    threat_type: str
    default_oversight_level: str      # ONE_CLICK, ADVISORY, AUTONOMOUS_WITH_OVERRIDE
    trigger_rule: PlaybookTriggerRule
    expected_crash_reduction_pct: float
    target_response_time_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "title": self.title,
            "description": self.description,
            "threat_type": self.threat_type,
            "default_oversight_level": self.default_oversight_level,
            "trigger_rule": self.trigger_rule.to_dict(),
            "expected_crash_reduction_pct": round(self.expected_crash_reduction_pct, 1),
            "target_response_time_seconds": self.target_response_time_seconds,
        }


@dataclass(frozen=True, slots=True)
class TmcIncidentRecord:
    """An active or historical operational incident with synthesized playbook actions."""

    incident_id: str
    corridor_id: str
    location_name: str
    latitude: float
    longitude: float
    threat_type: str
    severity_tier: str                # critical, severe, elevated, moderate
    detected_at_utc: str
    playbook_id: str
    playbook_title: str
    oversight_level: str              # ONE_CLICK, ADVISORY, AUTONOMOUS_WITH_OVERRIDE
    authorization_state: str          # pending_approval, authorized, active, overridden, resolved
    operator_id: str | None
    authorized_at_utc: str | None
    actions: list[PlaybookActuationAction]
    sha256_audit_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "corridor_id": self.corridor_id,
            "location_name": self.location_name,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "threat_type": self.threat_type,
            "severity_tier": self.severity_tier,
            "detected_at_utc": self.detected_at_utc,
            "playbook_id": self.playbook_id,
            "playbook_title": self.playbook_title,
            "oversight_level": self.oversight_level,
            "authorization_state": self.authorization_state,
            "operator_id": self.operator_id,
            "authorized_at_utc": self.authorized_at_utc,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
            "sha256_audit_hash": self.sha256_audit_hash,
            "contract_version": TMC_CONTRACT_VERSION,
        }


@dataclass(frozen=True, slots=True)
class PlaybookActuationReceipt:
    """Audit receipt proving cryptographic authorization of playbook actions."""

    incident_id: str
    playbook_id: str
    operator_id: str
    authorization_state: str
    executed_at_utc: str
    active_actions_count: int
    sha256_receipt_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "playbook_id": self.playbook_id,
            "operator_id": self.operator_id,
            "authorization_state": self.authorization_state,
            "executed_at_utc": self.executed_at_utc,
            "active_actions_count": self.active_actions_count,
            "sha256_receipt_hash": self.sha256_receipt_hash,
            "status": "authorized_and_broadcasting",
        }


# ---------------------------------------------------------------------------
# Standard Operating Playbooks Catalog
# ---------------------------------------------------------------------------

STANDARD_PLAYBOOKS: dict[str, TmcPlaybookTemplate] = {
    "PB_SHOCKWAVE_CONGESTION": TmcPlaybookTemplate(
        playbook_id="PB_SHOCKWAVE_CONGESTION",
        title="Motorway Congestion Shockwave Damping",
        description="Steps down upstream Variable Speed Limits (VSL) and activates queue warning signs to prevent rear-end chain collisions.",
        threat_type="shockwave_congestion",
        default_oversight_level="ONE_CLICK",
        trigger_rule=PlaybookTriggerRule(
            threat_type="shockwave_congestion",
            min_severity_tier="severe",
            min_crash_probability=0.60,
            min_speed_drop_kmh=25.0,
        ),
        expected_crash_reduction_pct=42.5,
        target_response_time_seconds=30,
    ),
    "PB_ADVERSE_WEATHER_FOG_RAIN": TmcPlaybookTemplate(
        playbook_id="PB_ADVERSE_WEATHER_FOG_RAIN",
        title="Adverse Weather & Reduced Friction Protocol",
        description="Enforces reduced wet speed limits, displays Vienna A,24 slippery road warning, and broadcasts C-ITS adverse weather advisory.",
        threat_type="adverse_weather",
        default_oversight_level="ONE_CLICK",
        trigger_rule=PlaybookTriggerRule(
            threat_type="adverse_weather",
            min_severity_tier="elevated",
            min_crash_probability=0.45,
            min_precipitation_mm_h=10.0,
        ),
        expected_crash_reduction_pct=34.0,
        target_response_time_seconds=60,
    ),
    "PB_VRU_CROSSWALK_SURGE": TmcPlaybookTemplate(
        playbook_id="PB_VRU_CROSSWALK_SURGE",
        title="Urban VRU Conflict Surge & Pedestrian Protection",
        description="Enforces 30 km/h arterial approach limits, increases pedestrian crossing signal green time, and restricts shared micromobility to 10 km/h.",
        threat_type="vru_crosswalk_surge",
        default_oversight_level="ONE_CLICK",
        trigger_rule=PlaybookTriggerRule(
            threat_type="vru_crosswalk_surge",
            min_severity_tier="severe",
            min_crash_probability=0.55,
            min_near_miss_count=3,
        ),
        expected_crash_reduction_pct=58.2,
        target_response_time_seconds=20,
    ),
    "PB_CRITICAL_CORRIDOR_NEAR_MISS": TmcPlaybookTemplate(
        playbook_id="PB_CRITICAL_CORRIDOR_NEAR_MISS",
        title="Critical Telematics Near-Miss Cluster Intervention",
        description="Rapid response for corridors experiencing severe harsh-braking surges (>= 3 events in 5 min) indicating imminent crash likelihood.",
        threat_type="near_miss_cluster",
        default_oversight_level="AUTONOMOUS_WITH_OVERRIDE",
        trigger_rule=PlaybookTriggerRule(
            threat_type="near_miss_cluster",
            min_severity_tier="critical",
            min_crash_probability=0.75,
            min_near_miss_count=3,
        ),
        expected_crash_reduction_pct=64.8,
        target_response_time_seconds=15,
    ),
    "PB_SECONDARY_INCIDENT_PROTECTION": TmcPlaybookTemplate(
        playbook_id="PB_SECONDARY_INCIDENT_PROTECTION",
        title="Secondary Crash Prevention & Queue Tail Shield",
        description="Immediate multi-lane speed tapering, red lane closure X indicators, and emergency responder dispatch to protect stranded incident vehicles.",
        threat_type="queue_tail",
        default_oversight_level="ONE_CLICK",
        trigger_rule=PlaybookTriggerRule(
            threat_type="queue_tail",
            min_severity_tier="critical",
            min_crash_probability=0.70,
            min_speed_drop_kmh=40.0,
        ),
        expected_crash_reduction_pct=52.0,
        target_response_time_seconds=20,
    ),
}


def get_standard_tmc_playbooks() -> list[dict[str, Any]]:
    """Returns catalog of all registered standard operating playbooks."""
    return [p.to_dict() for p in STANDARD_PLAYBOOKS.values()]


# ---------------------------------------------------------------------------
# Multi-Tier Actuation Action Compiler
# ---------------------------------------------------------------------------

def compile_playbook_actuation_plan(
    playbook: TmcPlaybookTemplate,
    corridor_id: str,
    location_name: str,
    latitude: float,
    longitude: float,
    current_speed_kmh: float = 90.0,
    speed_limit_kmh: float = 90.0,
) -> list[PlaybookActuationAction]:
    """Synthesizes coordinated field actions across all 5 operational tiers."""
    actions: list[PlaybookActuationAction] = []
    p_id = playbook.playbook_id

    # -----------------------------------------------------------------------
    # Tier 1: Dynamic Variable Speed Limit (VSL)
    # -----------------------------------------------------------------------
    if p_id in {"PB_SHOCKWAVE_CONGESTION", "PB_SECONDARY_INCIDENT_PROTECTION"}:
        vsl_mandatory = max(40, int(round((current_speed_kmh - 30.0) / 10.0) * 10))
        actions.append(PlaybookActuationAction(
            action_id=f"ACT-VSL-{corridor_id[:8]}-01",
            action_tier="vsl_control",
            target_entity_id=f"GANTRY-{corridor_id[:8]}-UPSTREAM-500M",
            headline=f"Step-down upstream VSL to {vsl_mandatory} km/h (Drop: -{int(speed_limit_kmh - vsl_mandatory)} km/h)",
            parameters={
                "nominal_speed_limit_kmh": int(speed_limit_kmh),
                "mandatory_vsl_kmh": vsl_mandatory,
                "step_down_gantries": [
                    {"distance_m": 1200, "speed_kmh": min(int(speed_limit_kmh), vsl_mandatory + 20)},
                    {"distance_m": 600, "speed_kmh": vsl_mandatory},
                ],
                "dwell_time_minutes": 20,
            },
        ))
    elif p_id == "PB_VRU_CROSSWALK_SURGE":
        actions.append(PlaybookActuationAction(
            action_id=f"ACT-VSL-{corridor_id[:8]}-01",
            action_tier="vsl_control",
            target_entity_id=f"SPEED-SIGN-{corridor_id[:8]}",
            headline="Mandate 30 km/h Urban Calm Zone on corridor approach",
            parameters={
                "nominal_speed_limit_kmh": int(speed_limit_kmh),
                "mandatory_vsl_kmh": 30,
                "dwell_time_minutes": 30,
            },
        ))
    else:  # Adverse weather / default
        actions.append(PlaybookActuationAction(
            action_id=f"ACT-VSL-{corridor_id[:8]}-01",
            action_tier="vsl_control",
            target_entity_id=f"GANTRY-{corridor_id[:8]}",
            headline=f"Enforce wet weather advisory VSL: {max(50, int(speed_limit_kmh - 20))} km/h",
            parameters={
                "nominal_speed_limit_kmh": int(speed_limit_kmh),
                "mandatory_vsl_kmh": max(50, int(speed_limit_kmh - 20)),
                "dwell_time_minutes": 45,
            },
        ))

    # -----------------------------------------------------------------------
    # Tier 2: Multi-Lingual Variable Message Sign (VMS)
    # -----------------------------------------------------------------------
    if p_id == "PB_SHOCKWAVE_CONGESTION":
        pictogram = VIENNA_PICTOGRAMS["CONGESTION_AHEAD"]
        text_it = "CODE A 500M - RALLENTARE"
        text_en = "QUEUES AHEAD - SLOW DOWN"
    elif p_id == "PB_ADVERSE_WEATHER_FOG_RAIN":
        pictogram = VIENNA_PICTOGRAMS["SLIPPERY_ROAD"]
        text_it = "ASFALTO RESO VISCIDO DA PIOGGIA"
        text_en = "SLIPPERY ROAD - REDUCE SPEED"
    elif p_id == "PB_VRU_CROSSWALK_SURGE":
        pictogram = VIENNA_PICTOGRAMS["PEDESTRIAN_CROSSING"]
        text_it = "ATTENZIONE PEDONI IN TRANSITO"
        text_en = "PEDESTRIANS CROSSING AHEAD"
    else:
        pictogram = VIENNA_PICTOGRAMS["DANGER_GENERAL"]
        text_it = "PERICOLO INCIDENTE SUL TRACCIATO"
        text_en = "ACCIDENT HAZARD AHEAD"

    actions.append(PlaybookActuationAction(
        action_id=f"ACT-VMS-{corridor_id[:8]}-02",
        action_tier="vms_signage",
        target_entity_id=f"VMS-{corridor_id[:8]}-PORTAL",
        headline=f"VMS Layout: [{pictogram}] {text_it} / {text_en}",
        parameters={
            "vienna_pictogram": pictogram,
            "text_line_1_it": text_it,
            "text_line_2_en": text_en,
            "flashing_beacons": True,
        },
    ))

    # -----------------------------------------------------------------------
    # Tier 3: C-ITS Direct V2X Envelopes (ETSI EN 302 637-3 DENM)
    # -----------------------------------------------------------------------
    actions.append(PlaybookActuationAction(
        action_id=f"ACT-CITS-{corridor_id[:8]}-03",
        action_tier="cits_denm",
        target_entity_id=f"RSU-{corridor_id[:8]}-BROADCAST",
        headline=f"Broadcast ETSI DENM v2: {playbook.threat_type.upper()} within 1200m radius",
        parameters={
            "etsi_cause_code": 1 if "shockwave" in p_id.lower() else (17 if "weather" in p_id.lower() else 99),
            "sub_cause_code": 2,
            "dissemination_radius_m": 1200,
            "transmission_interval_ms": 200,
            "security_profile": "ETSI_TS_103_097_SIGNED",
        },
    ))

    # -----------------------------------------------------------------------
    # Tier 4: Shared Micromobility MDS Geofence Enforcement
    # -----------------------------------------------------------------------
    if p_id in {"PB_VRU_CROSSWALK_SURGE", "PB_CRITICAL_CORRIDOR_NEAR_MISS"}:
        actions.append(PlaybookActuationAction(
            action_id=f"ACT-MDS-{corridor_id[:8]}-04",
            action_tier="micromobility_geofence",
            target_entity_id="MDS-FLEET-API-DISPATCH",
            headline="Enforce 10 km/h Slow-Zone on shared e-scooter fleets within 250m buffer",
            parameters={
                "geofence_type": "slow_zone",
                "max_speed_kph": 10.0,
                "radius_meters": 250,
                "target_operators": ["LIME", "BIT", "TIER", "DOTT", "VOI"],
                "policy_duration_minutes": 60,
            },
        ))
    else:
        actions.append(PlaybookActuationAction(
            action_id=f"ACT-MDS-{corridor_id[:8]}-04",
            action_tier="micromobility_geofence",
            target_entity_id="MDS-FLEET-API-DISPATCH",
            headline="Corridor routing advisory: Suggest alternate route for micromobility",
            parameters={
                "geofence_type": "advisory_reroute",
                "radius_meters": 400,
            },
        ))

    # -----------------------------------------------------------------------
    # Tier 5: Highway Patrol & Emergency Dispatch
    # -----------------------------------------------------------------------
    actions.append(PlaybookActuationAction(
        action_id=f"ACT-PATROL-{corridor_id[:8]}-05",
        action_tier="patrol_dispatch",
        target_entity_id="POLIZIA-STRADALE-SALA-OPERATIVA",
        headline="Priority 1 Patrol Dispatch alert transmitted to local operations board",
        parameters={
            "priority": "P1" if "critical" in playbook.trigger_rule.min_severity_tier else "P2",
            "target_eta_minutes": 8,
            "assigned_sector": "BARI_NORD_SUD_TANGENZIALE",
        },
    ))

    return actions


def evaluate_incident_triggers(
    threat_type: str,
    severity_tier: str,
    crash_probability: float,
    speed_drop_kmh: float = 0.0,
    precipitation_mm_h: float = 0.0,
    near_miss_count: int = 0,
) -> TmcPlaybookTemplate:
    """Matches operational alert parameters to the optimal response playbook."""
    # Find exact or best matching playbook
    for pb in STANDARD_PLAYBOOKS.values():
        rule = pb.trigger_rule
        if rule.threat_type == threat_type:
            return pb

    # Severity-based fallback
    if severity_tier == "critical" or speed_drop_kmh >= 25.0:
        return STANDARD_PLAYBOOKS["PB_SHOCKWAVE_CONGESTION"]
    if precipitation_mm_h >= 5.0:
        return STANDARD_PLAYBOOKS["PB_ADVERSE_WEATHER_FOG_RAIN"]
    if near_miss_count >= 2:
        return STANDARD_PLAYBOOKS["PB_VRU_CROSSWALK_SURGE"]

    return STANDARD_PLAYBOOKS["PB_SHOCKWAVE_CONGESTION"]


def open_tmc_incident(
    *,
    incident_id: str,
    threat_type: str,
    severity_tier: str,
    corridor_id: str,
    location_name: str,
    latitude: float,
    longitude: float,
    crash_probability: float = 0.0,
    speed_drop_kmh: float = 0.0,
    precipitation_mm_h: float = 0.0,
    near_miss_count: int = 0,
    current_speed_kmh: float = 90.0,
    speed_limit_kmh: float = 90.0,
    detected_at_utc: str | None = None,
) -> TmcIncidentRecord:
    """Open an incident from observed alert parameters, pending operator approval.

    The matching playbook is compiled into a five-tier action plan, but nothing
    is actuated: every action stays staged until an operator authorizes it.
    """
    playbook = evaluate_incident_triggers(
        threat_type=threat_type,
        severity_tier=severity_tier,
        crash_probability=crash_probability,
        speed_drop_kmh=speed_drop_kmh,
        precipitation_mm_h=precipitation_mm_h,
        near_miss_count=near_miss_count,
    )
    actions = compile_playbook_actuation_plan(
        playbook,
        corridor_id=corridor_id,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        current_speed_kmh=current_speed_kmh,
        speed_limit_kmh=speed_limit_kmh,
    )
    detected = detected_at_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    audit_hash = hashlib.sha256(
        f"{incident_id}|{playbook.playbook_id}|{detected}".encode("utf-8")
    ).hexdigest()
    return TmcIncidentRecord(
        incident_id=incident_id,
        corridor_id=corridor_id,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        threat_type=threat_type,
        severity_tier=severity_tier,
        detected_at_utc=detected,
        playbook_id=playbook.playbook_id,
        playbook_title=playbook.title,
        oversight_level="ONE_CLICK",
        authorization_state="pending_approval",
        operator_id=None,
        authorized_at_utc=None,
        actions=actions,
        sha256_audit_hash=audit_hash,
    )


def authorize_and_execute_playbook(
    incident: TmcIncidentRecord,
    operator_id: str,
    authorization_mode: str = "ONE_CLICK",
) -> tuple[TmcIncidentRecord, PlaybookActuationReceipt]:
    """Authorize every staged action tier of an existing incident.

    Returns the updated incident and its receipt. Callers must resolve the
    incident first: there is no path that produces a receipt for an incident
    that does not exist.
    """
    if not operator_id or not operator_id.strip():
        raise ValueError("operator_id is required to authorize a playbook.")
    if incident.authorization_state not in {"pending_approval", "overridden"}:
        raise ValueError(
            f"Incident {incident.incident_id} is {incident.authorization_state}; "
            "only pending incidents can be authorized."
        )

    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated_actions = [
        PlaybookActuationAction(
            action_id=a.action_id,
            action_tier=a.action_tier,
            target_entity_id=a.target_entity_id,
            headline=a.headline,
            parameters=a.parameters,
            status="active",
        )
        for a in incident.actions
    ]
    receipt_hash = hashlib.sha256(
        f"{incident.incident_id}|{operator_id}|{now_iso}|{len(updated_actions)}".encode("utf-8")
    ).hexdigest()
    updated = TmcIncidentRecord(
        incident_id=incident.incident_id,
        corridor_id=incident.corridor_id,
        location_name=incident.location_name,
        latitude=incident.latitude,
        longitude=incident.longitude,
        threat_type=incident.threat_type,
        severity_tier=incident.severity_tier,
        detected_at_utc=incident.detected_at_utc,
        playbook_id=incident.playbook_id,
        playbook_title=incident.playbook_title,
        oversight_level=authorization_mode,
        authorization_state="active",
        operator_id=operator_id,
        authorized_at_utc=now_iso,
        actions=updated_actions,
        sha256_audit_hash=receipt_hash,
    )
    receipt = PlaybookActuationReceipt(
        incident_id=incident.incident_id,
        playbook_id=incident.playbook_id,
        operator_id=operator_id,
        authorization_state="active",
        executed_at_utc=now_iso,
        active_actions_count=len(updated_actions),
        sha256_receipt_hash=receipt_hash,
    )
    return updated, receipt
