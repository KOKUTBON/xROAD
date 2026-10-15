"""Build Bari signal-phase acquisition trackers from the request pack."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_ACQUISITION_PLAN_VERSION = "signal_phase_acquisition_plan_v1"
SIGNAL_PHASE_ACQUISITION_PLAN_CONTRACT_VERSION = "signal_phase_acquisition_plan_public_v1"

OUTREACH_TRACKER_FIELDNAMES = [
    "request_id",
    "junction_id",
    "signal_name",
    "priority_rank",
    "priority_band",
    "recommended_provider_profile",
    "acquisition_status",
    "owner_team",
    "contact_name",
    "contact_email",
    "last_contact_date",
    "next_follow_up_date",
    "request_window",
    "required_profiles",
    "delivery_note",
    "signalized_crash_total",
    "ambiguous_movement_count",
    "preferred_primary_channel",
    "preferred_secondary_channel",
    "routing_decision",
    "external_blocker",
]

PROFILE_SPECS = {
    "controller_event_log_export": {
        "owner_team": "Comune di Bari traffic control center / ITS operator",
        "delivery_format": "CSV export or database extract with UTC timestamps",
        "requested_window": "last_12_months_plus_current_control_state",
        "acceptance_gate": (
            "phase_id and stage_id complete, event windows valid, and at least 90 days of records for the requested junction."
        ),
        "priority_note": "Use first for the busiest and most ambiguous signalized junctions.",
    },
    "signal_stage_plan_export": {
        "owner_team": "Comune di Bari mobility department / signal maintenance contractor",
        "delivery_format": "CSV or XLSX stage-plan table with active windows and durations",
        "requested_window": "current_validated_plan_plus_recent_archived_plan_if_available",
        "acceptance_gate": (
            "phase_id and stage_id present for every active plan window and durations sum coherently to the stated cycle length."
        ),
        "priority_note": "Use where full controller logs are not immediately available.",
    },
    "arm_phase_mapping_sheet": {
        "owner_team": "Internal analyst mapping with municipality review",
        "delivery_format": "CSV mapping sheet aligned to Bari movement-object identifiers",
        "requested_window": "current_junction_geometry_revision",
        "acceptance_gate": (
            "incoming_arm_id, movement_turn, phase_id, and stage_id resolved for the requested movement set."
        ),
        "priority_note": "Mandatory for joining provider timing data back to Bari movement objects.",
    },
    "junction_phase_diagram_support": {
        "owner_team": "Comune di Bari mobility department / signal maintenance contractor",
        "delivery_format": "PDF, image, or CAD-derived phasing sketch",
        "requested_window": "current_operational_layout",
        "acceptance_gate": "diagram or sketch clearly identifies stages, pedestrian phases, and controlled approaches.",
        "priority_note": "Use where ambiguous movements or pedestrian stages remain unresolved.",
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _split_profiles(value: Any) -> list[str]:
    text = _clean_text(value) or ""
    return [part.strip() for part in text.split("|") if part.strip()]


def _priority_value(priority_band: str) -> int:
    return {"tier_1_immediate": 1, "tier_2_next_wave": 2, "tier_3_monitor": 3}.get(priority_band, 9)


def _preserve_text(existing_row: dict[str, str], field_name: str, fallback: str) -> str:
    return _clean_text(existing_row.get(field_name)) or fallback


def _outreach_rows(
    request_rows: list[dict[str, Any]],
    existing_rows_by_request: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    existing_rows_by_request = existing_rows_by_request or {}
    rows: list[dict[str, Any]] = []
    for request in request_rows:
        priority_band = _clean_text(request.get("priority_band")) or "tier_3_monitor"
        request_id = str(request["request_id"])
        existing_row = existing_rows_by_request.get(request_id, {})
        default_owner_team = PROFILE_SPECS[request["recommended_provider_profile"]]["owner_team"]
        rows.append(
            {
                "request_id": request_id,
                "junction_id": request["junction_id"],
                "signal_name": request["signal_name"],
                "priority_rank": request["priority_rank"],
                "priority_band": priority_band,
                "recommended_provider_profile": request["recommended_provider_profile"],
                "acquisition_status": _preserve_text(existing_row, "acquisition_status", "pending_outreach"),
                "owner_team": _preserve_text(existing_row, "owner_team", default_owner_team),
                "contact_name": _preserve_text(existing_row, "contact_name", ""),
                "contact_email": _preserve_text(existing_row, "contact_email", ""),
                "last_contact_date": _preserve_text(existing_row, "last_contact_date", ""),
                "next_follow_up_date": _preserve_text(existing_row, "next_follow_up_date", ""),
                "request_window": PROFILE_SPECS[request["recommended_provider_profile"]]["requested_window"],
                "required_profiles": request["required_profiles"],
                "delivery_note": PROFILE_SPECS[request["recommended_provider_profile"]]["priority_note"],
                "signalized_crash_total": request["signalized_crash_total"],
                "ambiguous_movement_count": request["ambiguous_movement_count"],
                "preferred_primary_channel": _preserve_text(existing_row, "preferred_primary_channel", ""),
                "preferred_secondary_channel": _preserve_text(existing_row, "preferred_secondary_channel", ""),
                "routing_decision": _preserve_text(existing_row, "routing_decision", ""),
                "external_blocker": _preserve_text(existing_row, "external_blocker", ""),
            }
        )
    rows.sort(
        key=lambda item: (
            _priority_value(item["priority_band"]),
            int(item["priority_rank"]),
            str(item["junction_id"]),
        )
    )
    return rows


def _delivery_rows(request_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request in request_rows:
        for profile_id in _split_profiles(request.get("required_profiles")):
            spec = PROFILE_SPECS.get(profile_id)
            if spec is None:
                continue
            rows.append(
                {
                    "delivery_item_id": f"{request['request_id']}__{profile_id}",
                    "request_id": request["request_id"],
                    "junction_id": request["junction_id"],
                    "signal_name": request["signal_name"],
                    "priority_band": request["priority_band"],
                    "profile_id": profile_id,
                    "owner_team": spec["owner_team"],
                    "delivery_format": spec["delivery_format"],
                    "requested_window": spec["requested_window"],
                    "acceptance_gate": spec["acceptance_gate"],
                    "delivery_status": "awaiting_request",
                    "received_date": "",
                    "validated_date": "",
                    "mapped_to_movements": "no",
                    "notes": spec["priority_note"],
                }
            )
    rows.sort(
        key=lambda item: (
            _priority_value(item["priority_band"]),
            str(item["request_id"]),
            str(item["profile_id"]),
        )
    )
    return rows


def _tier1_rows(request_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in request_rows
        if _clean_text(row.get("priority_band")) == "tier_1_immediate"
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _plan_markdown(payload: dict[str, Any]) -> str:
    tracker_status_counts = payload["stats"]["outreach_status_counts"]
    lines = [
        "# Bari Signal-Phase Acquisition Plan",
        "",
        f"As of {payload['generated_at_utc']}, the request pack has been converted into an execution tracker.",
        "",
        "## Summary",
        "",
        f"- Total request rows: `{payload['stats']['request_row_count']}`",
        f"- Tier-1 immediate signals: `{payload['stats']['tier_1_signal_count']}`",
        f"- Tier-2 next-wave signals: `{payload['stats']['tier_2_signal_count']}`",
        f"- Delivery checklist rows: `{payload['stats']['delivery_item_count']}`",
        f"- Recommended next wave profiles: `{payload['stats']['recommended_profile_counts']}`",
        f"- Outreach status counts: `{tracker_status_counts}`",
        f"- Rows with contact details: `{payload['stats']['contact_ready_row_count']}`",
        f"- Rows with a recorded last-contact date: `{payload['stats']['contacted_row_count']}`",
        "",
        "## Tier-1 Signal Queue",
        "",
    ]
    for row in payload["tier_1_requests"]:
        lines.append(
            f"- `{row['junction_id']}` `{row['signal_name']}`: profile `{row['recommended_provider_profile']}`, "
            f"signalized crashes `{row['signalized_crash_total']}`, ambiguous movements `{row['ambiguous_movement_count']}`"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Outreach tracker: `{payload['outputs']['outreach_tracker_csv_path']}`",
            f"- Delivery checklist: `{payload['outputs']['delivery_checklist_csv_path']}`",
            "",
            "## Immediate Action",
            "",
            (
                "Preserve the live outreach tracker as the source of truth, continue dispatching the ready tier-1 rows, "
                "and validate each received file against the delivery checklist before running the existing phase ingestion path."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def build_bari_signal_phase_acquisition_plan(
    *,
    output_dir: str | Path = "data/planning/signal_phase_acquisition/bari",
    signal_phase_request_pack_path: str | Path = "data/planning/signal_phase_requests/bari/signal_phase_request_pack.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    request_pack_path = Path(signal_phase_request_pack_path)
    request_payload = _load_json(request_pack_path)
    request_rows = request_payload.get("priority_request_rows", [])
    if not isinstance(request_rows, list):
        raise RuntimeError("Signal phase request pack must include a top-level 'priority_request_rows' list.")

    outreach_tracker_csv_path = output_root / "outreach_tracker.csv"
    delivery_checklist_csv_path = output_root / "delivery_checklist.csv"
    plan_json_path = output_root / "signal_phase_acquisition_plan.json"
    plan_md_path = output_root / "signal_phase_acquisition_plan.md"
    manifest_path = output_root / "signal_phase_acquisition_plan.manifest.json"

    existing_outreach_rows: list[dict[str, str]] = []
    if outreach_tracker_csv_path.exists():
        existing_outreach_rows = _read_csv_rows(outreach_tracker_csv_path)
    existing_outreach_by_request = {
        str(row.get("request_id") or ""): row
        for row in existing_outreach_rows
        if _clean_text(row.get("request_id"))
    }

    outreach_rows = _outreach_rows(request_rows, existing_outreach_by_request)
    delivery_rows = _delivery_rows(request_rows)
    tier_1_requests = _tier1_rows(request_rows)

    _write_csv(
        outreach_tracker_csv_path,
        outreach_rows,
        OUTREACH_TRACKER_FIELDNAMES,
    )
    _write_csv(
        delivery_checklist_csv_path,
        delivery_rows,
        [
            "delivery_item_id",
            "request_id",
            "junction_id",
            "signal_name",
            "priority_band",
            "profile_id",
            "owner_team",
            "delivery_format",
            "requested_window",
            "acceptance_gate",
            "delivery_status",
            "received_date",
            "validated_date",
            "mapped_to_movements",
            "notes",
        ],
    )

    generated_at_utc = datetime.now(UTC).isoformat()
    outreach_status_counts: dict[str, int] = {}
    for row in outreach_rows:
        status = _clean_text(row.get("acquisition_status")) or "pending_outreach"
        outreach_status_counts[status] = outreach_status_counts.get(status, 0) + 1

    stats = {
        "request_row_count": len(request_rows),
        "tier_1_signal_count": len(tier_1_requests),
        "tier_2_signal_count": sum(
            1
            for row in request_rows
            if _clean_text(row.get("priority_band")) == "tier_2_next_wave"
        ),
        "delivery_item_count": len(delivery_rows),
        "recommended_profile_counts": request_payload.get("stats", {}).get("recommended_profile_counts", {}),
        "outreach_status_counts": outreach_status_counts,
        "contact_ready_row_count": sum(
            1
            for row in outreach_rows
            if _clean_text(row.get("contact_name")) and _clean_text(row.get("contact_email"))
        ),
        "contacted_row_count": sum(1 for row in outreach_rows if _clean_text(row.get("last_contact_date"))),
    }

    payload = {
        "signal_phase_acquisition_plan_version": SIGNAL_PHASE_ACQUISITION_PLAN_VERSION,
        "signal_phase_acquisition_plan_contract_version": SIGNAL_PHASE_ACQUISITION_PLAN_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "source": {
            "adapter": "bari_signal_phase_acquisition_plan_builder",
        },
        "stats": stats,
        "tier_1_requests": tier_1_requests,
        "inputs": {
            "signal_phase_request_pack_path": {
                "path": str(request_pack_path),
                "role": "signal_phase_request_pack",
                "sha256": _sha256(request_pack_path),
            }
        },
        "outputs": {
            "outreach_tracker_csv_path": str(outreach_tracker_csv_path),
            "delivery_checklist_csv_path": str(delivery_checklist_csv_path),
            "plan_json_path": str(plan_json_path),
            "plan_md_path": str(plan_md_path),
            "manifest_path": str(manifest_path),
        },
    }
    plan_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    plan_md_path.write_text(_plan_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_acquisition_plan_version": SIGNAL_PHASE_ACQUISITION_PLAN_VERSION,
        "contract": {
            "resource_name": "signal_phase_acquisition_plan",
            "public_contract_version": SIGNAL_PHASE_ACQUISITION_PLAN_CONTRACT_VERSION,
            "signal_phase_acquisition_plan_version": SIGNAL_PHASE_ACQUISITION_PLAN_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_acquisition_plan_builder",
        },
        "stats": stats,
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "outreach_tracker_csv_path": str(outreach_tracker_csv_path),
            "outreach_tracker_csv_sha256": _sha256(outreach_tracker_csv_path),
            "delivery_checklist_csv_path": str(delivery_checklist_csv_path),
            "delivery_checklist_csv_sha256": _sha256(delivery_checklist_csv_path),
            "plan_json_path": str(plan_json_path),
            "plan_json_sha256": _sha256(plan_json_path),
            "plan_md_path": str(plan_md_path),
            "plan_md_sha256": _sha256(plan_md_path),
        },
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_request_pack", request_pack_path, _sha256(request_pack_path)),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_acquisition_plan_json", plan_json_path, _sha256(plan_json_path)),
                _artifact_reference("signal_phase_acquisition_plan_markdown", plan_md_path, _sha256(plan_md_path)),
                _artifact_reference("signal_phase_outreach_tracker_csv", outreach_tracker_csv_path, _sha256(outreach_tracker_csv_path)),
                _artifact_reference("signal_phase_delivery_checklist_csv", delivery_checklist_csv_path, _sha256(delivery_checklist_csv_path)),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
