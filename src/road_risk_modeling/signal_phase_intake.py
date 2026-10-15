"""Build Bari signal-phase intake artifacts from movement review priorities."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .governance_interoperability import (
    DEFAULT_GOVERNANCE_BUNDLE_PATH,
    SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
    SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY,
    SIGNAL_PHASE_SUPPORT_ARTIFACT_FAMILY,
    artifact_role_policy_ids,
    governance_contract_reference,
    signal_phase_source_family_id,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_INTAKE_VERSION = "signal_phase_intake_v1"
SIGNAL_PHASE_INTAKE_CONTRACT_VERSION = "signal_phase_intake_public_v1"

TURN_ORDER = {
    "cross": 0,
    "left": 1,
    "straight": 2,
    "right": 3,
    "u_turn": 4,
    "circulate": 5,
}

INTAKE_PROFILES = [
    {
        "profile_id": "signal_stage_plan_export",
        "profile_type": "provider_feed",
        "label": "Signal stage plan export",
        "description": "Fixed-time or adaptive plan tables keyed by junction, phase, and stage, including active windows and stage durations.",
        "publication_tier": "restricted_operational_control",
        "retention_policy": "retain approved plan extracts for 24 months, publish only derived score products",
        "datex_exchange_fit": "medium",
        "template_filename": "signal_stage_plan_export_template.csv",
        "required_fields": [
            "junction_id",
            "plan_id",
            "stage_id",
            "phase_id",
            "active_from_local",
            "active_to_local",
            "cycle_length_s",
            "green_s",
            "amber_s",
            "all_red_s",
            "control_mode",
        ],
        "optional_fields": [
            "pedestrian_walk_s",
            "pedestrian_clearance_s",
            "day_type",
            "notes",
        ],
        "field_types": {
            "junction_id": "string",
            "plan_id": "string",
            "stage_id": "string",
            "phase_id": "string",
            "active_from_local": "string",
            "active_to_local": "string",
            "cycle_length_s": "integer",
            "green_s": "integer",
            "amber_s": "integer",
            "all_red_s": "integer",
            "control_mode": "string",
            "pedestrian_walk_s": "integer",
            "pedestrian_clearance_s": "integer",
            "day_type": "string",
            "notes": "string",
        },
    },
    {
        "profile_id": "controller_event_log_export",
        "profile_type": "provider_feed",
        "label": "Controller event log export",
        "description": "Timestamped controller-state or stage-event aggregates for the highest-priority signalized junctions.",
        "publication_tier": "restricted_operational_control",
        "retention_policy": "retain aggregated controller events for 12 months, avoid raw device traces where not required",
        "datex_exchange_fit": "high",
        "template_filename": "controller_event_log_export_template.csv",
        "required_fields": [
            "junction_id",
            "device_id",
            "event_start_utc",
            "event_end_utc",
            "phase_id",
            "stage_id",
            "event_type",
            "control_mode",
        ],
        "optional_fields": [
            "plan_id",
            "detector_call",
            "priority_request",
            "notes",
        ],
        "field_types": {
            "junction_id": "string",
            "device_id": "string",
            "event_start_utc": "datetime",
            "event_end_utc": "datetime",
            "phase_id": "string",
            "stage_id": "string",
            "event_type": "string",
            "control_mode": "string",
            "plan_id": "string",
            "detector_call": "boolean",
            "priority_request": "boolean",
            "notes": "string",
        },
    },
    {
        "profile_id": "arm_phase_mapping_sheet",
        "profile_type": "analyst_mapping",
        "label": "Arm-to-phase mapping sheet",
        "description": "Analyst-maintained mapping between Bari movement objects and signal phases or stages for each priority junction.",
        "publication_tier": "restricted_internal_mapping",
        "retention_policy": "retain as long as the phase mapping remains current for the modeled junction",
        "datex_exchange_fit": "low",
        "template_filename": "arm_phase_mapping_sheet_template.csv",
        "required_fields": [
            "junction_id",
            "incoming_arm_id",
            "movement_turn",
            "phase_id",
            "stage_id",
            "protection_state",
        ],
        "optional_fields": [
            "outgoing_arm_id",
            "pedestrian_stage_flag",
            "notes",
        ],
        "field_types": {
            "junction_id": "string",
            "incoming_arm_id": "string",
            "movement_turn": "string",
            "phase_id": "string",
            "stage_id": "string",
            "protection_state": "string",
            "outgoing_arm_id": "string",
            "pedestrian_stage_flag": "boolean",
            "notes": "string",
        },
    },
    {
        "profile_id": "junction_phase_diagram_support",
        "profile_type": "support_artifact",
        "label": "Junction phase diagram support",
        "description": "Diagram, sketch, or CAD-derived phasing support used to resolve stages, pedestrian phases, and controlled approaches at a junction.",
        "publication_tier": "restricted_operational_support",
        "retention_policy": "retain the latest validated support diagram while the modeled junction layout and control logic remain current",
        "datex_exchange_fit": "low",
        "template_filename": "junction_phase_diagram_support_template.pdf",
        "required_fields": [],
        "optional_fields": [],
        "field_types": {},
        "allowed_extensions": [
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".tif",
            ".tiff",
            ".svg",
            ".dwg",
            ".dxf",
        ],
    },
]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
    return rows


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sort_catalog(values: set[str]) -> str:
    return " | ".join(sorted(values, key=lambda item: (TURN_ORDER.get(item, 99), item)))


def _load_signal_lookup(signal_nodes_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(signal_nodes_path)
    features = payload.get("features", [])
    if not isinstance(features, list):
        raise RuntimeError("Signal node GeoJSON must contain a top-level 'features' list.")

    lookup: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        coordinates = geometry.get("coordinates", []) or []
        junction_id = _clean_text(properties.get("node_object_id"))
        if not junction_id:
            continue
        lookup[junction_id] = {
            "signal_name": _clean_text(properties.get("name")),
            "signal_type": _clean_text(properties.get("signal_type")),
            "asset_code": _clean_text(properties.get("asset_code")),
            "source_record_id": _clean_text(properties.get("source_record_id")),
            "latitude": coordinates[1] if len(coordinates) >= 2 else None,
            "longitude": coordinates[0] if len(coordinates) >= 2 else None,
        }
    return lookup


def _load_movement_scope_lookup(movement_objects_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(movement_objects_path)
    features = payload.get("features", [])
    if not isinstance(features, list):
        raise RuntimeError("Movement object GeoJSON must contain a top-level 'features' list.")

    lookup: dict[str, dict[str, Any]] = {}
    for feature in features:
        properties = feature.get("properties", {}) or {}
        junction_id = _clean_text(properties.get("junction_id"))
        if not junction_id:
            continue
        movement_role = _clean_text(properties.get("movement_role")) or ""
        phase_group = _clean_text(properties.get("phase_priority_group")) or ""
        if movement_role != "signalized_turn_movement" and phase_group != "signalized_pedestrian_stage":
            continue
        entry = lookup.setdefault(
            junction_id,
            {
                "movement_turns": set(),
                "phase_groups": set(),
                "incoming_arms": set(),
                "explicit_target_count": 0,
                "heuristic_target_count": 0,
                "ambiguous_target_count": 0,
                "sample_movements": [],
            },
        )
        movement_turn = _clean_text(properties.get("movement_turn"))
        if movement_turn:
            entry["movement_turns"].add(movement_turn)
        if phase_group:
            entry["phase_groups"].add(phase_group)
        incoming_arm_id = _clean_text(properties.get("incoming_arm_id")) or _clean_text(properties.get("approach_arm_id"))
        if incoming_arm_id:
            entry["incoming_arms"].add(incoming_arm_id)
        resolution_state = _clean_text(properties.get("movement_resolution_state")) or ""
        if resolution_state == "explicit_target":
            entry["explicit_target_count"] += 1
        elif resolution_state == "heuristic_target_resolution":
            entry["heuristic_target_count"] += 1
        elif resolution_state == "ambiguous_target_variant":
            entry["ambiguous_target_count"] += 1
        entry["sample_movements"].append(
            {
                "movement_role": movement_role,
                "movement_turn": movement_turn,
                "incoming_arm_id": incoming_arm_id,
                "outgoing_arm_id": _clean_text(properties.get("outgoing_arm_id")),
                "phase_priority_group": phase_group,
                "movement_resolution_state": resolution_state,
            }
        )

    formatted: dict[str, dict[str, Any]] = {}
    for junction_id, entry in lookup.items():
        ranked_samples = sorted(
            entry["sample_movements"],
            key=lambda item: (
                0 if item.get("movement_role") == "signalized_turn_movement" else 1,
                TURN_ORDER.get(item.get("movement_turn") or "", 99),
                0 if item.get("movement_resolution_state") == "explicit_target" else 1,
                str(item.get("incoming_arm_id") or ""),
                str(item.get("outgoing_arm_id") or ""),
            ),
        )
        formatted[junction_id] = {
            "movement_turn_catalog": _sort_catalog(entry["movement_turns"]),
            "phase_priority_groups_present": " | ".join(sorted(entry["phase_groups"])),
            "approach_arm_count": len(entry["incoming_arms"]),
            "explicit_target_count": entry["explicit_target_count"],
            "heuristic_target_count": entry["heuristic_target_count"],
            "ambiguous_target_count": entry["ambiguous_target_count"],
            "sample_movement": ranked_samples[0] if ranked_samples else None,
        }
    return formatted


def _priority_band(row: dict[str, Any]) -> str:
    review_priority_score = _safe_int(row.get("review_priority_score"))
    signalized_crashes = _safe_int(row.get("signalized_crash_total"))
    ambiguous_crashes = _safe_int(row.get("ambiguous_crash_total"))
    ambiguous_movements = _safe_int(row.get("ambiguous_movement_count"))
    if review_priority_score >= 5000 or signalized_crashes >= 35 or ambiguous_crashes >= 20:
        return "tier_1_immediate"
    if review_priority_score >= 1500 or signalized_crashes >= 15 or ambiguous_movements >= 12:
        return "tier_2_next_wave"
    return "tier_3_monitor"


def _recommended_provider_profile(row: dict[str, Any]) -> str:
    if _safe_int(row.get("ambiguous_movement_count")) >= 20 or _safe_int(row.get("signalized_crash_total")) >= 35:
        return "controller_event_log_export"
    return "signal_stage_plan_export"


def _required_inputs(row: dict[str, Any]) -> list[str]:
    phase_groups = {
        part.strip()
        for part in (_clean_text(row.get("phase_priority_groups_present")) or "").split("|")
        if part.strip()
    }
    inputs = ["arm-to-phase mapping sheet"]
    provider_profile = _recommended_provider_profile(row)
    if provider_profile == "controller_event_log_export":
        inputs.append("controller event log export")
    else:
        inputs.append("signal stage plan export")
    if _safe_int(row.get("ambiguous_movement_count")) > 0:
        inputs.append("junction phase diagram or phasing sketch")
    if "signalized_pedestrian_stage" in phase_groups:
        inputs.append("pedestrian stage definition")
    return inputs


def _mapping_level(row: dict[str, Any]) -> str:
    if _safe_int(row.get("ambiguous_movement_count")) > 0:
        return "junction_arm_and_turn_to_phase"
    return "phase_to_movement_family"


def _sample_values(profile: dict[str, Any], sample_row: dict[str, Any]) -> dict[str, str]:
    junction_id = _clean_text(sample_row.get("junction_id")) or "it-bari-signal-000"
    signal_name = _clean_text(sample_row.get("signal_name")) or "Sample Bari Signal"
    sample_movement = sample_row.get("sample_movement") if isinstance(sample_row.get("sample_movement"), dict) else {}
    movement_turn = _clean_text(sample_movement.get("movement_turn")) or "straight"
    incoming_arm_id = _clean_text(sample_movement.get("incoming_arm_id")) or "incoming_arm_01"
    outgoing_arm_id = _clean_text(sample_movement.get("outgoing_arm_id")) or "outgoing_arm_02"
    if profile["profile_id"] == "signal_stage_plan_export":
        return {
            "junction_id": junction_id,
            "plan_id": "weekday_am_peak",
            "stage_id": "stage_01",
            "phase_id": "phase_01",
            "active_from_local": "07:00",
            "active_to_local": "09:30",
            "cycle_length_s": "90",
            "green_s": "32",
            "amber_s": "4",
            "all_red_s": "2",
            "control_mode": "fixed_time",
            "pedestrian_walk_s": "10",
            "pedestrian_clearance_s": "12",
            "day_type": "weekday",
            "notes": signal_name,
        }
    if profile["profile_id"] == "controller_event_log_export":
        return {
            "junction_id": junction_id,
            "device_id": "bari_ctrl_001",
            "event_start_utc": "2025-05-06T07:00:00Z",
            "event_end_utc": "2025-05-06T07:01:30Z",
            "phase_id": "phase_01",
            "stage_id": "stage_01",
            "event_type": "stage_active",
            "control_mode": "controller_runtime",
            "plan_id": "weekday_am_peak",
            "detector_call": "false",
            "priority_request": "false",
            "notes": signal_name,
        }
    if profile["profile_id"] == "junction_phase_diagram_support":
        return {
            "junction_id": junction_id,
            "signal_name": signal_name,
            "movement_turn": movement_turn,
            "incoming_arm_id": incoming_arm_id,
            "outgoing_arm_id": outgoing_arm_id,
        }
    return {
        "junction_id": junction_id,
        "incoming_arm_id": incoming_arm_id,
        "movement_turn": movement_turn,
        "phase_id": "phase_01",
        "stage_id": "stage_01",
        "protection_state": "protected",
        "outgoing_arm_id": outgoing_arm_id,
        "pedestrian_stage_flag": "false",
        "notes": signal_name,
    }


def _write_csv_template(path: Path, fieldnames: list[str], sample_values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({field: sample_values.get(field, "") for field in fieldnames})


def _write_support_template(path: Path, sample_values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "%PDF-1.4",
            "% Bari signal-phase support placeholder",
            f"Junction: {sample_values.get('junction_id', 'it-bari-signal-000')}",
            f"Signal: {sample_values.get('signal_name', 'Sample Bari Signal')}",
            "Purpose: illustrate stage sequencing, pedestrian phases, and controlled approaches.",
            f"Sample movement: {sample_values.get('movement_turn', 'straight')}",
            f"Incoming arm: {sample_values.get('incoming_arm_id', 'incoming_arm_01')}",
            f"Outgoing arm: {sample_values.get('outgoing_arm_id', 'outgoing_arm_02')}",
        ]
    )
    path.write_text(content + "\n", encoding="utf-8")


def _mapping_stub(
    profile: dict[str, Any],
    template_path: Path,
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    if profile["profile_type"] == "support_artifact":
        artifact_family_id = SIGNAL_PHASE_SUPPORT_ARTIFACT_FAMILY
        return {
            "mapping_stub_version": "signal_phase_mapping_stub_v1",
            "profile_id": profile["profile_id"],
            "profile_type": profile["profile_type"],
            "profile_label": profile["label"],
            "source_template_path": str(template_path),
            "target_join_strategy": {
                "junction_key": "junction_id",
                "movement_mapping_level": "supporting_context_only",
                "note": "Validate and catalog the support artifact, but do not auto-join it into the movement phase layer.",
            },
            "field_mappings": [],
            "quality_gates": [
                "support file exists and is non-empty",
                "support file extension matches the accepted delivery policy",
                "diagram or sketch can be linked to the requested junction and current operational layout",
            ],
            "publication_policy": {
                "publication_tier": profile["publication_tier"],
                "public_release_policy": "Publish only derived risk products and summary indicators, never raw support diagrams.",
                "restricted_use_policy": "Use support diagrams only for internal movement interpretation, QA, and manual phase resolution.",
                "retention_policy": profile["retention_policy"],
            },
            "governance": governance_contract_reference(
                governance_bundle_path=governance_bundle_path,
                artifact_family_ids=[artifact_family_id],
                source_family_ids=[signal_phase_source_family_id(profile["profile_id"])],
                role_policy_ids=artifact_role_policy_ids(artifact_family_id),
            ),
            "support_validation": {
                "validation_mode": "file_presence_and_extension",
                "allowed_extensions": profile.get("allowed_extensions", []),
                "minimum_file_size_bytes": 16,
            },
        }

    artifact_family_id = SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY
    field_mappings = []
    for field_name in profile["required_fields"]:
        field_mappings.append(
            {
                "target_field": field_name,
                "source_field": f"TODO_{profile['profile_id']}__{field_name}",
                "required": True,
                "type": profile.get("field_types", {}).get(field_name, "string"),
            }
        )
    for field_name in profile["optional_fields"]:
        field_mappings.append(
            {
                "target_field": field_name,
                "source_field": f"TODO_{profile['profile_id']}__{field_name}",
                "required": False,
                "type": profile.get("field_types", {}).get(field_name, "string"),
            }
        )
    return {
        "mapping_stub_version": "signal_phase_mapping_stub_v1",
        "profile_id": profile["profile_id"],
        "profile_type": profile["profile_type"],
        "profile_label": profile["label"],
        "source_template_path": str(template_path),
        "target_join_strategy": {
            "junction_key": "junction_id",
            "movement_mapping_level": "junction_incoming_arm_and_turn_to_phase",
            "note": "Map source phase or stage records onto Bari movement objects via junction_id, incoming_arm_id, movement_turn, and optional outgoing_arm_id.",
        },
        "field_mappings": field_mappings,
        "quality_gates": [
            "junction_id present and matches Bari signal node ids",
            "phase_id and stage_id consistent within each junction",
            "active windows or event timestamps present for the delivered control data",
        ],
        "publication_policy": {
            "publication_tier": profile["publication_tier"],
            "public_release_policy": "Publish only derived risk products and summary indicators, never raw control exports.",
            "restricted_use_policy": "Use raw control extracts only for internal movement mapping and control-aware model features.",
            "retention_policy": profile["retention_policy"],
        },
        "governance": governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[artifact_family_id],
            source_family_ids=[signal_phase_source_family_id(profile["profile_id"])],
            role_policy_ids=artifact_role_policy_ids(artifact_family_id),
        ),
    }


def _rights_matrix_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for profile in INTAKE_PROFILES:
        rows.append(
            {
                "profile_id": profile["profile_id"],
                "profile_type": profile["profile_type"],
                "label": profile["label"],
                "publication_tier": profile["publication_tier"],
                "public_release_policy": "publish derived movement-risk outputs only",
                "restricted_use_policy": "restricted control-data processing for phase mapping and model features",
                "retention_policy": profile["retention_policy"],
                "datex_exchange_fit": profile["datex_exchange_fit"],
                "personal_data_allowed": "no",
            }
        )
    return rows


def _write_rights_matrix(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "profile_id",
        "profile_type",
        "label",
        "publication_tier",
        "public_release_policy",
        "restricted_use_policy",
        "retention_policy",
        "datex_exchange_fit",
        "personal_data_allowed",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _priority_rows(
    signal_phase_readiness: list[dict[str, Any]],
    *,
    signal_lookup: dict[str, dict[str, Any]],
    movement_scope_lookup: dict[str, dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    ordered = sorted(
        signal_phase_readiness,
        key=lambda row: (-_safe_int(row.get("review_priority_score")), -_safe_int(row.get("signalized_crash_total")), str(row.get("junction_id") or "")),
    )
    rows: list[dict[str, Any]] = []
    for row in ordered[:top_n]:
        junction_id = _clean_text(row.get("junction_id")) or ""
        signal_meta = signal_lookup.get(junction_id, {})
        movement_scope = movement_scope_lookup.get(junction_id, {})
        rows.append(
            {
                "junction_id": junction_id,
                "signal_name": _clean_text(row.get("signal_name")) or signal_meta.get("signal_name"),
                "signal_type": _clean_text(row.get("signal_type")) or signal_meta.get("signal_type"),
                "asset_code": signal_meta.get("asset_code"),
                "source_record_id": signal_meta.get("source_record_id"),
                "latitude": signal_meta.get("latitude"),
                "longitude": signal_meta.get("longitude"),
                "signalized_movement_count": _safe_int(row.get("signalized_movement_count")),
                "ambiguous_movement_count": _safe_int(row.get("ambiguous_movement_count")),
                "heuristic_resolved_movement_count": _safe_int(row.get("heuristic_resolved_movement_count")),
                "signalized_crash_total": _safe_int(row.get("signalized_crash_total")),
                "ambiguous_crash_total": _safe_int(row.get("ambiguous_crash_total")),
                "heuristic_resolved_crash_total": _safe_int(row.get("heuristic_resolved_crash_total")),
                "matched_crashes_at_junction_total": _safe_int(row.get("matched_crashes_at_junction_total")),
                "review_priority_score": _safe_int(row.get("review_priority_score")),
                "priority_band": _priority_band(row),
                "recommended_provider_profile": _recommended_provider_profile(row),
                "movement_turn_catalog": movement_scope.get("movement_turn_catalog"),
                "movement_turn_count": len(
                    [part for part in (movement_scope.get("movement_turn_catalog") or "").split(" | ") if part]
                ),
                "approach_arm_count": _safe_int(movement_scope.get("approach_arm_count")),
                "explicit_target_count": _safe_int(movement_scope.get("explicit_target_count")),
                "heuristic_target_count": _safe_int(movement_scope.get("heuristic_target_count")),
                "movement_phase_groups_present": movement_scope.get("phase_priority_groups_present")
                or _clean_text(row.get("phase_priority_groups_present")),
                "sample_movement": movement_scope.get("sample_movement"),
                "required_inputs": " | ".join(_required_inputs(row)),
                "target_mapping_level": _mapping_level(row),
                "recommended_next_input": _clean_text(row.get("recommended_next_input")),
                "timing_data_status": _clean_text(row.get("timing_data_status")),
            }
        )
    return rows


def _write_priority_signals_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "junction_id",
        "signal_name",
        "signal_type",
        "asset_code",
        "source_record_id",
        "latitude",
        "longitude",
        "signalized_movement_count",
        "ambiguous_movement_count",
        "heuristic_resolved_movement_count",
        "signalized_crash_total",
        "ambiguous_crash_total",
        "heuristic_resolved_crash_total",
        "matched_crashes_at_junction_total",
        "review_priority_score",
        "priority_band",
        "recommended_provider_profile",
        "movement_turn_catalog",
        "movement_turn_count",
        "approach_arm_count",
        "explicit_target_count",
        "heuristic_target_count",
        "movement_phase_groups_present",
        "required_inputs",
        "target_mapping_level",
        "recommended_next_input",
        "timing_data_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _markdown_report(summary: dict[str, Any], priority_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Bari Signal-Phase Intake Pack",
        "",
        "This pack converts the Bari movement review queue into a concrete intake package for real signal-phase data onboarding.",
        "",
        "## Summary",
        "",
        f"- signalized junction review rows: `{summary['signal_phase_review_row_count']}`",
        f"- exported priority signals: `{summary['priority_signal_export_count']}`",
        f"- tier 1 immediate signals in export: `{summary['priority_band_counts'].get('tier_1_immediate', 0)}`",
        f"- provider profiles: `{summary['provider_profile_count']}`",
        f"- sample templates: `{summary['template_count']}`",
        f"- mapping stubs: `{summary['mapping_stub_count']}`",
        "",
        "## Priority Signals",
        "",
    ]
    for row in priority_rows[:5]:
        lines.append(
            f"- `{row['junction_id']}` {row.get('signal_name') or 'Unnamed signal'}: "
            f"`{row['signalized_crash_total']}` signalized crashes, "
            f"`{row['ambiguous_movement_count']}` ambiguous movements, "
            f"profile `{row['recommended_provider_profile']}`"
        )
    lines.extend(
        [
            "",
            "## Intake Guidance",
            "",
            "- Start with the tier-1 signals because they combine the highest matched-crash totals with the largest unresolved movement burden.",
            "- Use `controller_event_log_export` where ambiguous movements are large or crash totals are highest; use `signal_stage_plan_export` for lower-priority fixed-time follow-up.",
            "- Treat the `arm_phase_mapping_sheet` as mandatory for movement-object alignment even when a provider can already deliver phase tables.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_bari_signal_phase_intake_pack(
    *,
    output_dir: str | Path = "data/planning/signal_phase_intake/bari",
    movement_review_path: str | Path = "data/reporting/movement_review/bari/movement_review_pack.json",
    phase_readiness_csv_path: str | Path | None = None,
    signal_nodes_path: str | Path = "data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson",
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    top_n: int = 20,
    governance_bundle_path: str | Path = DEFAULT_GOVERNANCE_BUNDLE_PATH,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    movement_review_file = Path(movement_review_path)
    phase_readiness_file = Path(phase_readiness_csv_path) if phase_readiness_csv_path else movement_review_file.with_name("signal_phase_readiness.csv")
    signal_nodes_file = Path(signal_nodes_path)
    movement_objects_file = Path(movement_objects_path)

    review_payload = _load_json(movement_review_file)
    if phase_readiness_file.exists():
        signal_phase_readiness = _load_csv_rows(phase_readiness_file)
    else:
        signal_phase_readiness = review_payload.get("signal_phase_readiness", [])
        if not isinstance(signal_phase_readiness, list):
            raise RuntimeError("Movement review JSON must include a top-level 'signal_phase_readiness' list.")

    signal_lookup = _load_signal_lookup(signal_nodes_file)
    movement_scope_lookup = _load_movement_scope_lookup(movement_objects_file)
    priority_rows = _priority_rows(
        signal_phase_readiness,
        signal_lookup=signal_lookup,
        movement_scope_lookup=movement_scope_lookup,
        top_n=top_n,
    )
    sample_row = priority_rows[0] if priority_rows else {"junction_id": "it-bari-signal-000", "signal_name": "Sample Bari Signal"}

    templates_dir = output_root / "sample_templates"
    mapping_dir = output_root / "mapping_stubs"
    priority_csv_path = output_root / "priority_signals.csv"
    rights_matrix_path = output_root / "source_rights_matrix.csv"
    report_json_path = output_root / "signal_phase_intake_pack.json"
    report_md_path = output_root / "signal_phase_intake_pack.md"
    manifest_path = output_root / "signal_phase_intake_pack.manifest.json"

    template_paths: list[Path] = []
    mapping_paths: list[Path] = []
    provider_profiles_payload: list[dict[str, Any]] = []
    for profile in INTAKE_PROFILES:
        template_path = templates_dir / profile["template_filename"]
        sample_values = _sample_values(profile, sample_row)
        if profile["profile_type"] == "support_artifact":
            _write_support_template(template_path, sample_values)
        else:
            fieldnames = [*profile["required_fields"], *profile["optional_fields"]]
            _write_csv_template(template_path, fieldnames, sample_values)
        mapping_path = mapping_dir / f"{profile['profile_id']}_mapping_stub.json"
        mapping_stub = _mapping_stub(profile, template_path, governance_bundle_path)
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_path.write_text(json.dumps(mapping_stub, indent=2, sort_keys=True), encoding="utf-8")
        template_paths.append(template_path)
        mapping_paths.append(mapping_path)
        provider_profiles_payload.append(
            {
                "profile_id": profile["profile_id"],
                "profile_type": profile["profile_type"],
                "label": profile["label"],
                "description": profile["description"],
                "publication_tier": profile["publication_tier"],
                "retention_policy": profile["retention_policy"],
                "datex_exchange_fit": profile["datex_exchange_fit"],
                "template_path": str(template_path),
                "mapping_stub_path": str(mapping_path),
            }
        )

    _write_priority_signals_csv(priority_csv_path, priority_rows)
    _write_rights_matrix(rights_matrix_path, _rights_matrix_rows())

    priority_band_counts: dict[str, int] = {}
    for row in priority_rows:
        priority_band_counts[row["priority_band"]] = priority_band_counts.get(row["priority_band"], 0) + 1

    summary = {
        "signal_phase_review_row_count": len(signal_phase_readiness),
        "priority_signal_export_count": len(priority_rows),
        "priority_band_counts": priority_band_counts,
        "provider_profile_count": len([profile for profile in INTAKE_PROFILES if profile["profile_type"] == "provider_feed"]),
        "template_count": len(template_paths),
        "mapping_stub_count": len(mapping_paths),
    }
    input_references = {
        "movement_review_path": _artifact_reference("movement_review_report", movement_review_file, _sha256(movement_review_file)),
        "signal_nodes_path": _artifact_reference("signal_nodes", signal_nodes_file, _sha256(signal_nodes_file)),
        "movement_objects_path": _artifact_reference("movement_objects", movement_objects_file, _sha256(movement_objects_file)),
        "top_n": top_n,
    }
    if phase_readiness_file.exists():
        input_references["phase_readiness_csv_path"] = _artifact_reference(
            "phase_readiness_csv",
            phase_readiness_file,
            _sha256(phase_readiness_file),
        )
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_intake_version": SIGNAL_PHASE_INTAKE_VERSION,
        "signal_phase_intake_contract_version": SIGNAL_PHASE_INTAKE_CONTRACT_VERSION,
        "governance": governance_contract_reference(
            governance_bundle_path=governance_bundle_path,
            artifact_family_ids=[
                SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
                SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY,
                SIGNAL_PHASE_SUPPORT_ARTIFACT_FAMILY,
            ],
            source_family_ids=sorted(
                {signal_phase_source_family_id(profile["profile_id"]) for profile in INTAKE_PROFILES}
            ),
            role_policy_ids=artifact_role_policy_ids(
                SIGNAL_PHASE_INTAKE_ARTIFACT_FAMILY,
                SIGNAL_PHASE_MAPPING_STUB_ARTIFACT_FAMILY,
                SIGNAL_PHASE_SUPPORT_ARTIFACT_FAMILY,
            ),
        ),
        "summary": summary,
        "provider_profiles": provider_profiles_payload,
        "top_priority_signals": priority_rows,
        "horizon_alignment": ["PHOEBE", "iDriving", "AI4CCAM", "CONDUCTOR"],
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_markdown_report(summary, priority_rows), encoding="utf-8")

    manifest = {
        "source": {
            "adapter": "bari_signal_phase_intake_builder",
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_intake_version": SIGNAL_PHASE_INTAKE_VERSION,
        "contract_version": SIGNAL_PHASE_INTAKE_CONTRACT_VERSION,
        "inputs": input_references,
        "governance": payload["governance"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "priority_signals_csv_path": str(priority_csv_path),
            "priority_signals_csv_sha256": _sha256(priority_csv_path),
            "source_rights_matrix_path": str(rights_matrix_path),
            "source_rights_matrix_sha256": _sha256(rights_matrix_path),
            "template_paths": [str(path) for path in template_paths],
            "mapping_stub_paths": [str(path) for path in mapping_paths],
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("movement_review_report", movement_review_file, _sha256(movement_review_file)),
            *(
                [_artifact_reference("phase_readiness_csv", phase_readiness_file, _sha256(phase_readiness_file))]
                if phase_readiness_file.exists()
                else []
            ),
            _artifact_reference("signal_nodes", signal_nodes_file, _sha256(signal_nodes_file)),
            _artifact_reference("movement_objects", movement_objects_file, _sha256(movement_objects_file)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_intake_report", report_json_path, _sha256(report_json_path)),
            _artifact_reference("signal_phase_intake_markdown", report_md_path, _sha256(report_md_path)),
            _artifact_reference("priority_signals_csv", priority_csv_path, _sha256(priority_csv_path)),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
