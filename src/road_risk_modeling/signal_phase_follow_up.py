"""Build Bari signal-phase follow-up packets from synced operational state."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_FOLLOW_UP_BUNDLE_VERSION = "signal_phase_follow_up_bundle_v1"
SIGNAL_PHASE_FOLLOW_UP_BUNDLE_CONTRACT_VERSION = "signal_phase_follow_up_bundle_public_v1"

_NON_VALIDATED_STATUSES = {"not_started"}
_ACCEPTED_VALIDATION_STATUSES = {"accepted_for_ingestion", "accepted_with_rejections"}
_PROVIDER_FIX_STATUSES = {"provider_fix_required", "schema_not_ready", "empty_delivery"}
_DETECTED_RECEIPT_STATUSES = {"delivery_detected", "multiple_files_manual_review"}


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


def _parse_date(value: Any) -> date | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _is_true(value: Any) -> bool:
    text = (_clean_text(value) or "").lower()
    return text in {"1", "true", "yes", "y"}


def _is_validated_status(value: Any) -> bool:
    status = _clean_text(value)
    if not status:
        return False
    return status not in _NON_VALIDATED_STATUSES


def _request_follow_up_status(receipt_rows: list[dict[str, str]]) -> str:
    if not receipt_rows:
        return "awaiting_delivery_follow_up"
    if all((_clean_text(row.get("synced_applied_to_movement_layer")) or "no") == "yes" for row in receipt_rows):
        return "completed"
    if any(_clean_text(row.get("receipt_status")) == "multiple_files_manual_review" for row in receipt_rows):
        return "manual_review_required"
    if any(_clean_text(row.get("validation_status")) in _PROVIDER_FIX_STATUSES for row in receipt_rows):
        return "provider_fix_required"
    if any(_clean_text(row.get("validation_status")) in _ACCEPTED_VALIDATION_STATUSES for row in receipt_rows):
        return "validated_pending_application"
    if any(_clean_text(row.get("receipt_status")) in _DETECTED_RECEIPT_STATUSES for row in receipt_rows):
        return "delivery_detected_pending_validation"
    return "awaiting_delivery_follow_up"


def _follow_up_message(row: dict[str, Any]) -> str:
    stage_label = "follow-up" if row["next_follow_up_stage"] == "first_follow_up" else "escalation"
    open_profiles = row["open_profile_ids"] or "requested signal-phase items"
    return (
        f"We are following up on Bari signal-phase request `{row['request_id']}` for `{row['signal_name']}` "
        f"(`{row['junction_id']}`). As of `{row['due_date']}`, the requested items remain open for `{open_profiles}`. "
        f"Please confirm receipt and routing of the original request, or provide the available extract for the scoped window "
        f"`{row['preferred_focus_hour_ranges']}`. If a full export is not immediately available, the fallback pilot scope "
        f"is `{row['fallback_pilot_scope']}`. This `{stage_label}` remains tied to the current open delivery items only."
    )


def _packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Signal-Phase Follow-up Packet: {packet['request_id']}",
        "",
        "## Status",
        "",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Next stage: `{packet['next_follow_up_stage']}`",
        f"- Due date: `{packet['due_date']}`",
        f"- Due now: `{packet['due_now']}`",
        f"- Request follow-up status: `{packet['request_follow_up_status']}`",
        f"- Open delivery items: `{packet['open_delivery_item_count']}`",
        f"- Detected deliveries: `{packet['detected_delivery_item_count']}`",
        f"- Validated deliveries: `{packet['validated_delivery_item_count']}`",
        f"- Mapped deliveries: `{packet['mapped_delivery_item_count']}`",
        "",
        "## Channels",
        "",
        f"- Recommended channel: `{packet['recommended_channel']}`",
        f"- Primary channel: `{packet['primary_channel_value']}`",
        f"- Secondary channel: `{packet['secondary_channel_value']}`",
        f"- Phone escalation: `{packet['phone_escalation_value']}`",
        "",
        "## Open Profiles",
        "",
        f"- `{packet['open_profile_ids']}`",
        "",
        "## Suggested Message",
        "",
        packet["suggested_message"],
        "",
    ]
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Follow-up Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari follow-up queue has been consolidated into request-level packets using the current dispatch, lifecycle, and synced receipt state.",
        "",
        "## Summary",
        "",
        f"- request packets: `{payload['summary']['request_count']}`",
        f"- due now: `{payload['summary']['due_now_count']}`",
        f"- first follow-up packets: `{payload['summary']['first_follow_up_count']}`",
        f"- escalation packets: `{payload['summary']['escalation_count']}`",
        f"- awaiting-delivery requests: `{payload['summary']['awaiting_delivery_request_count']}`",
        f"- manual-review requests: `{payload['summary']['manual_review_request_count']}`",
        f"- validated-pending-application requests: `{payload['summary']['validated_pending_application_count']}`",
        f"- open delivery items: `{payload['summary']['open_delivery_item_count']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["follow_up_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: `{row['next_follow_up_stage']}` due `{row['due_date']}` "
            f"for `{row['open_profile_ids']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_follow_up_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_follow_up/bari",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    follow_up_agenda_path: str | Path = "data/reporting/signal_phase_lifecycle/bari/follow_up_agenda.csv",
    synced_receipt_register_path: str | Path = "data/reporting/signal_phase_status_sync/bari/delivery_receipt_register_synced.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "follow_up_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    dispatch_input = Path(dispatch_execution_queue_path)
    agenda_input = Path(follow_up_agenda_path)
    synced_receipts_input = Path(synced_receipt_register_path)

    dispatch_rows = _read_csv_rows(dispatch_input)
    agenda_rows = _read_csv_rows(agenda_input)
    synced_receipts = _read_csv_rows(synced_receipts_input)

    dispatch_by_request = {str(row["request_id"]): row for row in dispatch_rows if row.get("request_id")}
    receipts_by_request: dict[str, list[dict[str, str]]] = {}
    for row in synced_receipts:
        request_id = str(row.get("request_id") or "")
        if request_id:
            receipts_by_request.setdefault(request_id, []).append(row)

    agenda_by_request: dict[str, list[dict[str, str]]] = {}
    for row in agenda_rows:
        request_id = str(row.get("request_id") or "")
        if request_id:
            agenda_by_request.setdefault(request_id, []).append(row)

    follow_up_queue: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for request_id, dispatch_row in sorted(
        dispatch_by_request.items(),
        key=lambda item: (_priority_value(item[1].get("priority_rank")), item[0]),
    ):
        request_receipts = receipts_by_request.get(request_id, [])
        pending_agenda = agenda_by_request.get(request_id, [])
        if not request_receipts or not pending_agenda:
            continue

        request_status = _request_follow_up_status(request_receipts)
        if request_status == "completed":
            continue

        pending_agenda.sort(
            key=lambda row: (_parse_date(row.get("due_date")) or date.max, str(row.get("follow_up_stage") or ""))
        )
        next_due_date = _parse_date(pending_agenda[0].get("due_date"))
        next_stage = _clean_text(pending_agenda[0].get("follow_up_stage")) or "first_follow_up"
        stage_rows = [
            row
            for row in pending_agenda
            if _clean_text(row.get("follow_up_stage")) == next_stage
            and _parse_date(row.get("due_date")) == next_due_date
        ]

        open_receipts = [
            row
            for row in request_receipts
            if (_clean_text(row.get("synced_applied_to_movement_layer")) or "no") != "yes"
        ]
        open_profile_ids = sorted(
            {
                str(profile_id)
                for profile_id in (_clean_text(row.get("profile_id")) for row in open_receipts)
                if profile_id
            }
        )
        queue_row = {
            "dispatch_reference": _clean_text(dispatch_row.get("dispatch_reference")),
            "request_id": request_id,
            "junction_id": _clean_text(dispatch_row.get("junction_id")),
            "signal_name": _clean_text(dispatch_row.get("signal_name")),
            "priority_rank": _safe_int(dispatch_row.get("priority_rank")),
            "priority_band": _clean_text(dispatch_row.get("priority_band")),
            "request_follow_up_status": request_status,
            "next_follow_up_stage": next_stage,
            "due_date": next_due_date.isoformat() if next_due_date else None,
            "due_now": any(_is_true(row.get("due_now")) for row in stage_rows),
            "open_delivery_item_count": len(open_receipts),
            "detected_delivery_item_count": sum(
                1 for row in request_receipts if _clean_text(row.get("receipt_status")) in _DETECTED_RECEIPT_STATUSES
            ),
            "manual_review_item_count": sum(
                1 for row in request_receipts if _clean_text(row.get("receipt_status")) == "multiple_files_manual_review"
            ),
            "validated_delivery_item_count": sum(
                1 for row in request_receipts if _is_validated_status(row.get("validation_status"))
            ),
            "mapped_delivery_item_count": sum(
                1
                for row in request_receipts
                if (_clean_text(row.get("synced_applied_to_movement_layer")) or "no") == "yes"
            ),
            "stage_delivery_item_count": len(stage_rows),
            "open_profile_ids": " | ".join(open_profile_ids),
            "recommended_channel": _clean_text(stage_rows[0].get("recommended_channel")) if stage_rows else None,
            "recommended_action": _clean_text(stage_rows[0].get("recommended_action")) if stage_rows else None,
            "primary_channel_value": _clean_text(dispatch_row.get("primary_channel_value")),
            "secondary_channel_value": _clean_text(dispatch_row.get("secondary_channel_value")),
            "phone_escalation_value": _clean_text(dispatch_row.get("phone_escalation_value")),
            "email_subject": _clean_text(dispatch_row.get("email_subject")),
            "recommended_time_window": _clean_text(dispatch_row.get("recommended_time_window")),
            "preferred_focus_hour_ranges": _clean_text(dispatch_row.get("preferred_focus_hour_ranges")),
            "fallback_pilot_scope": _clean_text(dispatch_row.get("fallback_pilot_scope")),
        }
        queue_row["suggested_message"] = _follow_up_message(queue_row)

        packet_base = f"{_slugify(request_id)}__{_slugify(next_stage)}"
        packet_md_path = packet_dir / f"{packet_base}.md"
        packet_json_path = packet_dir / f"{packet_base}.json"
        packet_md_path.write_text(_packet_markdown(queue_row), encoding="utf-8")
        packet_json_path.write_text(json.dumps(queue_row, indent=2, sort_keys=True), encoding="utf-8")
        queue_row["follow_up_packet_md_path"] = str(packet_md_path)
        queue_row["follow_up_packet_json_path"] = str(packet_json_path)
        packet_paths.extend([str(packet_md_path), str(packet_json_path)])
        follow_up_queue.append(queue_row)

    follow_up_queue.sort(key=lambda row: (_priority_value(row.get("priority_rank")), str(row.get("request_id") or "")))

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(follow_up_queue),
        "due_now_count": sum(1 for row in follow_up_queue if row["due_now"]),
        "first_follow_up_count": sum(1 for row in follow_up_queue if row["next_follow_up_stage"] == "first_follow_up"),
        "escalation_count": sum(1 for row in follow_up_queue if row["next_follow_up_stage"] == "escalation"),
        "awaiting_delivery_request_count": sum(
            1 for row in follow_up_queue if row["request_follow_up_status"] == "awaiting_delivery_follow_up"
        ),
        "manual_review_request_count": sum(
            1 for row in follow_up_queue if row["request_follow_up_status"] == "manual_review_required"
        ),
        "validated_pending_application_count": sum(
            1 for row in follow_up_queue if row["request_follow_up_status"] == "validated_pending_application"
        ),
        "open_delivery_item_count": sum(int(row["open_delivery_item_count"]) for row in follow_up_queue),
    }

    queue_csv_path = output_root / "follow_up_ready_queue.csv"
    bundle_json_path = output_root / "signal_phase_follow_up_bundle.json"
    bundle_md_path = output_root / "signal_phase_follow_up_bundle.md"
    manifest_path = output_root / "signal_phase_follow_up_bundle.manifest.json"

    _write_csv(
        queue_csv_path,
        follow_up_queue,
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
            "detected_delivery_item_count",
            "manual_review_item_count",
            "validated_delivery_item_count",
            "mapped_delivery_item_count",
            "stage_delivery_item_count",
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
            "follow_up_packet_md_path",
            "follow_up_packet_json_path",
        ],
    )

    payload = {
        "signal_phase_follow_up_bundle_version": SIGNAL_PHASE_FOLLOW_UP_BUNDLE_VERSION,
        "signal_phase_follow_up_bundle_contract_version": SIGNAL_PHASE_FOLLOW_UP_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "follow_up_queue": follow_up_queue,
        "outputs": {
            "follow_up_ready_queue_path": str(queue_csv_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_follow_up_bundle_version": SIGNAL_PHASE_FOLLOW_UP_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_follow_up_bundle",
            "public_contract_version": SIGNAL_PHASE_FOLLOW_UP_BUNDLE_CONTRACT_VERSION,
            "signal_phase_follow_up_bundle_version": SIGNAL_PHASE_FOLLOW_UP_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_follow_up_builder",
        },
        "inputs": {
            "dispatch_execution_queue_path": str(dispatch_input),
            "follow_up_agenda_path": str(agenda_input),
            "synced_receipt_register_path": str(synced_receipts_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "follow_up_ready_queue_path": str(queue_csv_path),
            "follow_up_ready_queue_sha256": _sha256(queue_csv_path),
            "packet_paths": packet_paths,
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_dispatch_queue", dispatch_input, _sha256(dispatch_input)),
                _artifact_reference("signal_phase_follow_up_agenda", agenda_input, _sha256(agenda_input)),
                _artifact_reference(
                    "signal_phase_delivery_receipt_register_synced",
                    synced_receipts_input,
                    _sha256(synced_receipts_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_follow_up_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
                _artifact_reference("signal_phase_follow_up_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_follow_up_queue", queue_csv_path, _sha256(queue_csv_path)),
                *[
                    _artifact_reference("signal_phase_follow_up_packet", Path(path), _sha256(Path(path)))
                    for path in packet_paths
                ],
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_follow_up_bundle_version": SIGNAL_PHASE_FOLLOW_UP_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
