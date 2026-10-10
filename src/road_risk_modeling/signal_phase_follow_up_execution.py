"""Build Bari signal-phase external follow-up execution bundles."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_VERSION = "signal_phase_follow_up_execution_bundle_v1"
SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_CONTRACT_VERSION = "signal_phase_follow_up_execution_bundle_public_v1"

_EXTERNAL_CONTACT_STATUSES = {"awaiting_delivery_follow_up"}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _is_true(value: Any) -> bool:
    text = (_clean_text(value) or "").lower()
    return text in {"1", "true", "yes", "y"}


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _execution_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Signal-Phase Follow-up Execution: {packet['request_id']}",
        "",
        "## Execution Summary",
        "",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Stage: `{packet['next_follow_up_stage']}`",
        f"- Due date: `{packet['due_date']}`",
        f"- Due now: `{packet['due_now']}`",
        f"- Open profiles: `{packet['open_profile_ids']}`",
        "",
        "## Contact Route",
        "",
        f"- Recommended channel: `{packet['recommended_channel']}`",
        f"- Primary channel: `{packet['primary_channel_value']}`",
        f"- Secondary channel: `{packet['secondary_channel_value']}`",
        f"- Phone escalation: `{packet['phone_escalation_value']}`",
        "",
        "## Suggested Message",
        "",
        str(packet["suggested_message"]),
        "",
        "## After Execution",
        "",
        "- record the actual channel used",
        "- record execution timestamp",
        "- save acknowledgement or protocol reference",
        "- update the tracker rows listed in the execution-update CSV",
        "",
    ]
    return "\n".join(lines)


def _execution_message(row: dict[str, Any]) -> str:
    suggested = _clean_text(row.get("suggested_message"))
    if suggested:
        return suggested
    return (
        f"We are following up on Bari signal-phase request `{row['request_id']}` for `{row['signal_name']}` "
        f"(`{row['junction_id']}`). As of `{row['due_date']}`, the requested items remain open for "
        f"`{row['open_profile_ids'] or 'requested signal-phase items'}`. Please confirm receipt and routing of the "
        f"original request, or provide the available extract for the scoped window "
        f"`{row['preferred_focus_hour_ranges']}`. If a full export is not immediately available, the fallback pilot "
        f"scope is `{row['fallback_pilot_scope']}`."
    )


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Follow-up Execution Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari request-level follow-up queue has been filtered into external-contact actions and internal holds.",
        "",
        "## Summary",
        "",
        f"- request packets reviewed: `{payload['summary']['request_count']}`",
        f"- execution-ready packets: `{payload['summary']['execution_ready_count']}`",
        f"- internal-hold packets: `{payload['summary']['internal_hold_count']}`",
        f"- due now: `{payload['summary']['due_now_count']}`",
        f"- first follow-ups: `{payload['summary']['first_follow_up_count']}`",
        f"- escalations: `{payload['summary']['escalation_count']}`",
        f"- tracker updates staged: `{payload['summary']['tracker_update_count']}`",
        "",
        "## Execution Queue",
        "",
    ]
    for row in payload["execution_ready_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: `{row['next_follow_up_stage']}` due `{row['due_date']}` via `{row['recommended_channel']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_follow_up_execution_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_follow_up_execution/bari",
    follow_up_ready_queue_path: str | Path = "data/reporting/signal_phase_follow_up/bari/follow_up_ready_queue.csv",
    follow_up_tracker_path: str | Path = "data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "execution_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    follow_up_queue_input = Path(follow_up_ready_queue_path)
    follow_up_tracker_input = Path(follow_up_tracker_path)

    follow_up_queue = _read_csv_rows(follow_up_queue_input)
    follow_up_tracker = _read_csv_rows(follow_up_tracker_input)

    tracker_by_request_stage: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in follow_up_tracker:
        request_id = str(row.get("request_id") or "")
        stage = str(row.get("follow_up_stage") or "")
        if request_id and stage:
            tracker_by_request_stage.setdefault((request_id, stage), []).append(row)

    execution_ready_queue: list[dict[str, Any]] = []
    internal_hold_queue: list[dict[str, Any]] = []
    tracker_update_rows: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for row in sorted(
        [item for item in follow_up_queue if isinstance(item, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("request_id") or "")),
    ):
        request_status = _clean_text(row.get("request_follow_up_status")) or ""
        next_stage = _clean_text(row.get("next_follow_up_stage")) or ""
        tracker_rows = tracker_by_request_stage.get((str(row.get("request_id") or ""), next_stage), [])

        if request_status in _EXTERNAL_CONTACT_STATUSES:
            execution_row = dict(row)
            execution_row["execution_status"] = "pending_execution"
            execution_row["execution_completed_at"] = ""
            execution_row["execution_channel_used"] = ""
            execution_row["execution_outcome"] = ""
            execution_row["response_received"] = "no"
            execution_row["response_summary"] = ""
            execution_row["protocol_reference"] = ""
            execution_row["evidence_path"] = ""
            execution_row["execution_notes"] = ""
            execution_row["suggested_message"] = _execution_message(row)
            packet_base = f"{_slugify(str(row['request_id']))}__{_slugify(next_stage)}"
            packet_md_path = packet_dir / f"{packet_base}.md"
            packet_json_path = packet_dir / f"{packet_base}.json"
            packet_md_path.write_text(_execution_packet_markdown(execution_row), encoding="utf-8")
            packet_json_path.write_text(json.dumps(execution_row, indent=2, sort_keys=True), encoding="utf-8")
            execution_row["execution_packet_md_path"] = str(packet_md_path)
            execution_row["execution_packet_json_path"] = str(packet_json_path)
            packet_paths.extend([str(packet_md_path), str(packet_json_path)])
            execution_ready_queue.append(execution_row)

            for tracker_row in tracker_rows:
                tracker_update_rows.append(
                    {
                        "dispatch_reference": _clean_text(tracker_row.get("dispatch_reference")),
                        "request_id": _clean_text(tracker_row.get("request_id")),
                        "junction_id": _clean_text(tracker_row.get("junction_id")),
                        "signal_name": _clean_text(tracker_row.get("signal_name")),
                        "follow_up_stage": _clean_text(tracker_row.get("follow_up_stage")),
                        "due_date": _clean_text(tracker_row.get("due_date")),
                        "current_completion_status": _clean_text(tracker_row.get("completion_status")) or "pending",
                        "target_completion_status": "completed_after_execution",
                        "completion_date": "",
                        "completion_notes": "",
                        "linked_execution_status": "pending_execution",
                        "linked_execution_packet_md_path": str(packet_md_path),
                    }
                )
        else:
            internal_hold_queue.append(
                {
                    "request_id": _clean_text(row.get("request_id")),
                    "junction_id": _clean_text(row.get("junction_id")),
                    "signal_name": _clean_text(row.get("signal_name")),
                    "next_follow_up_stage": next_stage,
                    "request_follow_up_status": request_status,
                    "open_profile_ids": _clean_text(row.get("open_profile_ids")),
                    "hold_reason": (
                        "This request is not external-contact ready; complete the internal action implied by the request status before sending a follow-up."
                    ),
                }
            )

    execution_queue_path = output_root / "follow_up_execution_queue.csv"
    internal_hold_path = output_root / "internal_hold_queue.csv"
    tracker_updates_path = output_root / "follow_up_tracker_updates.csv"
    bundle_json_path = output_root / "signal_phase_follow_up_execution_bundle.json"
    bundle_md_path = output_root / "signal_phase_follow_up_execution_bundle.md"
    manifest_path = output_root / "signal_phase_follow_up_execution_bundle.manifest.json"

    _write_csv(
        execution_queue_path,
        execution_ready_queue,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "request_follow_up_status",
            "next_follow_up_stage",
            "due_date",
            "due_now",
            "open_delivery_item_count",
            "open_profile_ids",
            "recommended_channel",
            "recommended_action",
            "primary_channel_value",
            "secondary_channel_value",
            "phone_escalation_value",
            "email_subject",
            "recommended_time_window",
            "preferred_focus_hour_ranges",
            "fallback_pilot_scope",
            "execution_status",
            "execution_completed_at",
            "execution_channel_used",
            "execution_outcome",
            "response_received",
            "response_summary",
            "protocol_reference",
            "evidence_path",
            "execution_notes",
            "execution_packet_md_path",
            "execution_packet_json_path",
        ],
    )
    _write_csv(
        internal_hold_path,
        internal_hold_queue,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "next_follow_up_stage",
            "request_follow_up_status",
            "open_profile_ids",
            "hold_reason",
        ],
    )
    _write_csv(
        tracker_updates_path,
        tracker_update_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "follow_up_stage",
            "due_date",
            "current_completion_status",
            "target_completion_status",
            "completion_date",
            "completion_notes",
            "linked_execution_status",
            "linked_execution_packet_md_path",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(follow_up_queue),
        "execution_ready_count": len(execution_ready_queue),
        "internal_hold_count": len(internal_hold_queue),
        "due_now_count": sum(1 for row in execution_ready_queue if _is_true(row.get("due_now"))),
        "first_follow_up_count": sum(
            1 for row in execution_ready_queue if _clean_text(row.get("next_follow_up_stage")) == "first_follow_up"
        ),
        "escalation_count": sum(
            1 for row in execution_ready_queue if _clean_text(row.get("next_follow_up_stage")) == "escalation"
        ),
        "tracker_update_count": len(tracker_update_rows),
    }
    payload = {
        "signal_phase_follow_up_execution_bundle_version": SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_VERSION,
        "signal_phase_follow_up_execution_bundle_contract_version": SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "execution_ready_queue": execution_ready_queue,
        "internal_hold_queue": internal_hold_queue,
        "outputs": {
            "follow_up_execution_queue_path": str(execution_queue_path),
            "internal_hold_queue_path": str(internal_hold_path),
            "tracker_updates_path": str(tracker_updates_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_follow_up_execution_bundle_version": SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_follow_up_execution_bundle",
            "public_contract_version": SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_CONTRACT_VERSION,
            "signal_phase_follow_up_execution_bundle_version": SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_follow_up_execution_builder",
        },
        "inputs": {
            "follow_up_ready_queue_path": str(follow_up_queue_input),
            "follow_up_tracker_path": str(follow_up_tracker_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "follow_up_execution_queue_path": str(execution_queue_path),
            "follow_up_execution_queue_sha256": _sha256(execution_queue_path),
            "internal_hold_queue_path": str(internal_hold_path),
            "internal_hold_queue_sha256": _sha256(internal_hold_path),
            "tracker_updates_path": str(tracker_updates_path),
            "tracker_updates_sha256": _sha256(tracker_updates_path),
            "packet_paths": packet_paths,
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_follow_up_queue", follow_up_queue_input, _sha256(follow_up_queue_input)),
                _artifact_reference("signal_phase_follow_up_tracker", follow_up_tracker_input, _sha256(follow_up_tracker_input)),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_follow_up_execution_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_execution_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_follow_up_execution_queue",
                    execution_queue_path,
                    _sha256(execution_queue_path),
                ),
                _artifact_reference("signal_phase_follow_up_internal_hold_queue", internal_hold_path, _sha256(internal_hold_path)),
                _artifact_reference("signal_phase_follow_up_tracker_updates", tracker_updates_path, _sha256(tracker_updates_path)),
                *[
                    _artifact_reference("signal_phase_follow_up_execution_packet", Path(path), _sha256(Path(path)))
                    for path in packet_paths
                ],
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_follow_up_execution_bundle_version": SIGNAL_PHASE_FOLLOW_UP_EXECUTION_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
