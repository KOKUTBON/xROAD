"""Build a Bari signal-phase next-action queue from the operations cycle."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_ACTION_QUEUE_VERSION = "signal_phase_action_queue_v1"
SIGNAL_PHASE_ACTION_QUEUE_CONTRACT_VERSION = "signal_phase_action_queue_public_v1"
_PENDING_DISPATCH_STATUSES = {"pending_dispatch", "draft_ready", "queued_for_send"}
_PENDING_RESPONSE_STATUSES = {"awaiting_send"}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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


def _is_true(value: Any) -> bool:
    text = (_clean_text(value) or "").lower()
    return text in {"1", "true", "yes", "y"}


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _derive_default_path(operations_cycle_path: Path, relative_path: str) -> Path:
    return operations_cycle_path.parent / relative_path


def _action_queue_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Action Queue",
        "",
        f"As of {payload['generated_at_utc']}, the Bari signal-phase operations cycle has been condensed into a request-level next-action queue.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{payload['summary']['request_count']}`",
        f"- immediate actions: `{payload['summary']['immediate_action_count']}`",
        f"- scheduled actions: `{payload['summary']['scheduled_action_count']}`",
        f"- completed requests: `{payload['summary']['completed_action_count']}`",
        f"- dispatch actions: `{payload['summary']['dispatch_action_count']}`",
        f"- dispatch-log fix actions: `{payload['summary']['dispatch_log_fix_action_count']}`",
        f"- follow-up actions: `{payload['summary']['follow_up_action_count']}`",
        f"- manual-review actions: `{payload['summary']['manual_review_action_count']}`",
        f"- provider-fix actions: `{payload['summary']['provider_fix_action_count']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["action_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['action_category']}` due `{row['due_date'] or 'n/a'}` "
            f"(immediate=`{row['due_now']}`) -> `{row['action_summary']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_action_queue(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_action_queue/bari",
    signal_phase_operations_cycle_path: str | Path = "data/processed/signal_phase_operations_cycles/bari/signal_phase_operations_cycle.json",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    signal_phase_dispatch_bundle_path: str | Path = "data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    lifecycle_items_path: str | Path | None = None,
    follow_up_execution_queue_path: str | Path | None = None,
    dispatch_log_repair_queue_path: str | Path | None = None,
    dispatch_repair_status_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    operations_cycle_input = Path(signal_phase_operations_cycle_path)
    dispatch_queue_input = Path(dispatch_execution_queue_path)
    dispatch_bundle_input = Path(signal_phase_dispatch_bundle_path)
    dispatch_packet_dir = dispatch_bundle_input.parent / "dispatch_packets"
    lifecycle_items_input = (
        Path(lifecycle_items_path)
        if lifecycle_items_path is not None
        else _derive_default_path(operations_cycle_input, "lifecycle/lifecycle_items.csv")
    )
    follow_up_execution_input = (
        Path(follow_up_execution_queue_path)
        if follow_up_execution_queue_path is not None
        else _derive_default_path(
            operations_cycle_input,
            "follow_up_cycle/runtime_follow_up_execution/follow_up_execution_queue.csv",
        )
    )
    dispatch_log_repair_input = (
        Path(dispatch_log_repair_queue_path)
        if dispatch_log_repair_queue_path is not None
        else None
    )
    dispatch_repair_status_input = (
        Path(dispatch_repair_status_path)
        if dispatch_repair_status_path is not None
        else None
    )

    operations_cycle = _load_json(operations_cycle_input)
    dispatch_rows = _read_csv_rows(dispatch_queue_input)
    lifecycle_rows = _read_csv_rows(lifecycle_items_input)
    follow_up_execution_rows = _read_csv_rows(follow_up_execution_input)
    repair_rows = (
        _read_csv_rows(dispatch_log_repair_input)
        if dispatch_log_repair_input is not None and dispatch_log_repair_input.exists()
        else []
    )
    repair_status_rows = (
        _read_csv_rows(dispatch_repair_status_input)
        if dispatch_repair_status_input is not None and dispatch_repair_status_input.exists()
        else []
    )

    lifecycle_by_request: dict[str, list[dict[str, str]]] = {}
    for row in lifecycle_rows:
        request_id = str(row.get("request_id") or "")
        if request_id:
            lifecycle_by_request.setdefault(request_id, []).append(row)

    follow_up_by_request = {
        str(row.get("request_id") or ""): row
        for row in follow_up_execution_rows
        if row.get("request_id")
    }
    repair_by_request = {
        str(row.get("request_id") or ""): row for row in repair_rows if row.get("request_id")
    }
    repair_status_by_request = {
        str(row.get("request_id") or ""): row
        for row in repair_status_rows
        if row.get("request_id")
    }

    today = date.today()
    action_rows: list[dict[str, Any]] = []

    for dispatch_row in sorted(
        dispatch_rows,
        key=lambda row: (_priority_value(row.get("priority_rank")), str(row.get("request_id") or "")),
    ):
        request_id = str(dispatch_row.get("request_id") or "")
        lifecycle_request_rows = lifecycle_by_request.get(request_id, [])
        follow_up_row = follow_up_by_request.get(request_id)
        repair_row = repair_by_request.get(request_id)
        repair_status_row = repair_status_by_request.get(request_id)

        dispatch_status = _clean_text(dispatch_row.get("dispatch_status")) or ""
        response_status = _clean_text(dispatch_row.get("response_status")) or ""
        lifecycle_statuses = sorted(
            {
                str(status)
                for status in (_clean_text(row.get("lifecycle_status")) for row in lifecycle_request_rows)
                if status
            }
        )
        delivery_item_ids = sorted(
            {
                str(item_id)
                for item_id in (_clean_text(row.get("delivery_item_id")) for row in lifecycle_request_rows)
                if item_id
            }
        )
        next_due_date = (
            _parse_date(follow_up_row.get("due_date")) if follow_up_row else _parse_date(dispatch_row.get("first_follow_up_date"))
        )
        follow_up_packet_md_path = _clean_text(follow_up_row.get("execution_packet_md_path")) if follow_up_row else None
        dispatch_packet_md_path = str(dispatch_packet_dir / f"{_slugify(request_id)}.md")
        repair_outcome = _clean_text(repair_row.get("dispatch_validation_outcome")) if repair_row else None
        repair_issue_codes = _clean_text(repair_row.get("dispatch_validation_issue_codes")) if repair_row else None
        repair_packet_md_path = _clean_text(repair_row.get("repair_packet_md_path")) if repair_row else None
        repair_status_category = (
            _clean_text(repair_status_row.get("repair_status_category")) if repair_status_row else None
        )
        repair_status_value = _clean_text(repair_status_row.get("repair_status")) if repair_status_row else None
        repair_status_packet_md_path = (
            _clean_text(repair_status_row.get("repair_packet_md_path")) if repair_status_row else None
        )
        repair_status_issue_codes = (
            _clean_text(repair_status_row.get("validation_issue_codes")) if repair_status_row else None
        )
        repair_status_outcome = (
            _clean_text(repair_status_row.get("validation_outcome")) if repair_status_row else None
        )
        repair_status_summary = (
            _clean_text(repair_status_row.get("action_summary")) if repair_status_row else None
        )
        repair_status_next_action = (
            _clean_text(repair_status_row.get("next_action")) if repair_status_row else None
        )
        repair_status_due_now = _is_true(repair_status_row.get("due_now")) if repair_status_row else False
        repair_writeback_eligible = (
            _clean_text(repair_status_row.get("writeback_eligible")) if repair_status_row else None
        )

        if repair_status_row and repair_status_category == "pending_repair":
            action_category = _clean_text(repair_row.get("action_category")) or "repair_dispatch_log_now"
            due_now = repair_status_due_now or True
            due_date = _clean_text(dispatch_row.get("planned_dispatch_date"))
            source_stage = "dispatch_repair_status"
            packet_md_path = repair_status_packet_md_path or repair_packet_md_path or ""
            recommended_action = (
                _clean_text(repair_row.get("repair_summary"))
                or "Repair the dispatch log entry and rerun validation."
            )
            action_summary = (
                repair_status_summary
                or f"Resolve dispatch-log validation blockers `{repair_status_issue_codes or repair_issue_codes or 'none'}` before writeback is allowed to update runtime state."
            )
        elif repair_status_row and repair_status_category == "ready_for_validation":
            action_category = "rerun_dispatch_validation"
            due_now = repair_status_due_now or True
            due_date = _clean_text(dispatch_row.get("planned_dispatch_date"))
            source_stage = "dispatch_repair_status"
            packet_md_path = repair_status_packet_md_path or repair_packet_md_path or ""
            recommended_action = "Rerun dispatch validation or the Bari runtime cycle so the repaired row can clear."
            action_summary = (
                repair_status_summary
                or "The repaired dispatch row is staged and waiting for validation."
            )
        elif repair_status_row and repair_status_category == "repair_still_blocked":
            action_category = "repair_dispatch_log_again"
            due_now = repair_status_due_now or True
            due_date = _clean_text(dispatch_row.get("planned_dispatch_date"))
            source_stage = "dispatch_repair_status"
            packet_md_path = repair_status_packet_md_path or repair_packet_md_path or ""
            recommended_action = (
                "Update the repair log again and rerun dispatch validation before writeback."
            )
            action_summary = (
                repair_status_summary
                or f"The repaired row is still blocked by `{repair_status_issue_codes or repair_issue_codes or 'none'}`."
            )
        elif repair_status_row and repair_status_category == "repair_cleared_for_writeback":
            action_category = "await_dispatch_writeback"
            due_now = False
            due_date = None
            source_stage = "dispatch_repair_status"
            packet_md_path = repair_status_packet_md_path or repair_packet_md_path or ""
            recommended_action = (
                "Wait for dispatch writeback or rerun the Bari runtime cycle to propagate the cleared row."
            )
            action_summary = (
                repair_status_summary
                or "The repaired dispatch row has already cleared validation and should no longer be re-dispatched."
            )
        elif repair_row:
            action_category = _clean_text(repair_row.get("action_category")) or "repair_dispatch_log_now"
            due_now = True
            due_date = _clean_text(dispatch_row.get("planned_dispatch_date"))
            source_stage = "dispatch_validation"
            packet_md_path = repair_packet_md_path or ""
            recommended_action = _clean_text(repair_row.get("repair_summary")) or "Repair the dispatch log entry and rerun validation."
            action_summary = (
                f"Resolve dispatch-log validation blockers `{repair_issue_codes or 'none'}` "
                f"before writeback is allowed to update runtime state."
            )
        elif dispatch_status in _PENDING_DISPATCH_STATUSES or response_status in _PENDING_RESPONSE_STATUSES:
            action_category = "dispatch_request_now"
            due_now = True
            due_date = _clean_text(dispatch_row.get("planned_dispatch_date"))
            source_stage = "dispatch"
            packet_md_path = dispatch_packet_md_path if Path(dispatch_packet_md_path).exists() else ""
            recommended_action = _clean_text(dispatch_row.get("recommended_routing_action")) or ""
            action_summary = (
                f"Send the initial request through `{_clean_text(dispatch_row.get('primary_channel_value')) or 'primary route'}` "
                f"and CC `{_clean_text(dispatch_row.get('secondary_channel_value')) or 'secondary route'}`."
            )
        elif "manual_review_required" in lifecycle_statuses:
            action_category = "manual_delivery_review"
            due_now = True
            due_date = None
            source_stage = "delivery_review"
            recommended_action = "Review the delivery drop zone and select the correct file for validation."
            action_summary = f"Manual review required for `{len(delivery_item_ids)}` delivery items."
        elif "provider_fix_required" in lifecycle_statuses or "partial_review_required" in lifecycle_statuses:
            action_category = "request_provider_fix"
            due_now = True
            due_date = None
            source_stage = "provider_fix"
            recommended_action = "Request a corrected provider extract before the next validation run."
            action_summary = "One or more delivery items require provider correction."
        elif follow_up_row and _is_true(follow_up_row.get("due_now")):
            action_category = "execute_follow_up_now"
            due_now = True
            due_date = _clean_text(follow_up_row.get("due_date"))
            source_stage = "follow_up"
            packet_md_path = follow_up_packet_md_path or ""
            recommended_action = _clean_text(follow_up_row.get("recommended_action")) or ""
            action_summary = (
                f"Execute `{_clean_text(follow_up_row.get('next_follow_up_stage')) or 'follow_up'}` "
                f"for the open request using the prepared packet."
            )
        elif follow_up_row:
            action_category = "scheduled_follow_up"
            due_now = bool(next_due_date and next_due_date <= today)
            due_date = _clean_text(follow_up_row.get("due_date"))
            source_stage = "follow_up"
            packet_md_path = follow_up_packet_md_path or ""
            recommended_action = _clean_text(follow_up_row.get("recommended_action")) or ""
            action_summary = (
                f"Prepare `{_clean_text(follow_up_row.get('next_follow_up_stage')) or 'follow_up'}` "
                f"for `{due_date or 'the scheduled due date'}`."
            )
        elif lifecycle_statuses and all(status == "applied_to_movement_layer" for status in lifecycle_statuses):
            action_category = "completed"
            due_now = False
            due_date = None
            source_stage = "completed"
            packet_md_path = ""
            recommended_action = "No open operational action."
            action_summary = "All delivery items for this request have been applied to the movement layer."
        else:
            action_category = "await_delivery"
            due_now = False
            due_date = next_due_date.isoformat() if next_due_date else None
            source_stage = "delivery_wait"
            packet_md_path = ""
            recommended_action = "Wait for provider delivery and rerun the operations cycle when something lands."
            action_summary = "No immediate operator action is required before the next due date."

        action_rows.append(
            {
                "dispatch_reference": _clean_text(dispatch_row.get("dispatch_reference")),
                "request_id": request_id,
                "junction_id": _clean_text(dispatch_row.get("junction_id")),
                "signal_name": _clean_text(dispatch_row.get("signal_name")),
                "priority_rank": _safe_int(dispatch_row.get("priority_rank")),
                "priority_band": _clean_text(dispatch_row.get("priority_band")),
                "action_category": action_category,
                "source_stage": source_stage,
                "due_date": due_date,
                "due_now": due_now,
                "dispatch_status": dispatch_status,
                "response_status": response_status,
                "lifecycle_statuses": " | ".join(lifecycle_statuses),
                "open_delivery_item_count": len(delivery_item_ids),
                "delivery_item_ids": " | ".join(delivery_item_ids),
                "dispatch_validation_outcome": repair_status_outcome or repair_outcome or "",
                "dispatch_validation_issue_codes": repair_status_issue_codes or repair_issue_codes or "",
                "repair_status_category": repair_status_category or "",
                "repair_status": repair_status_value or "",
                "repair_next_action": repair_status_next_action or "",
                "repair_writeback_eligible": repair_writeback_eligible or "",
                "packet_md_path": packet_md_path,
                "primary_channel_value": _clean_text(dispatch_row.get("primary_channel_value")),
                "secondary_channel_value": _clean_text(dispatch_row.get("secondary_channel_value")),
                "phone_escalation_value": _clean_text(dispatch_row.get("phone_escalation_value")),
                "recommended_action": recommended_action,
                "action_summary": action_summary,
            }
        )

    action_rows.sort(key=lambda row: (_priority_value(row.get("priority_rank")), str(row.get("request_id") or "")))

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(action_rows),
        "immediate_action_count": sum(1 for row in action_rows if row["due_now"]),
        "scheduled_action_count": sum(1 for row in action_rows if not row["due_now"] and row["action_category"] != "completed"),
        "completed_action_count": sum(1 for row in action_rows if row["action_category"] == "completed"),
        "dispatch_action_count": sum(1 for row in action_rows if row["action_category"] == "dispatch_request_now"),
        "dispatch_log_fix_action_count": sum(
            1
            for row in action_rows
            if row["action_category"]
            in {
                "repair_dispatch_log_now",
                "complete_dispatch_log_entry",
                "repair_dispatch_log_again",
                "rerun_dispatch_validation",
            }
        ),
        "follow_up_action_count": sum(
            1
            for row in action_rows
            if row["action_category"] in {"execute_follow_up_now", "scheduled_follow_up"}
        ),
        "manual_review_action_count": sum(
            1 for row in action_rows if row["action_category"] == "manual_delivery_review"
        ),
        "provider_fix_action_count": sum(
            1 for row in action_rows if row["action_category"] == "request_provider_fix"
        ),
        "next_due_date": next((row["due_date"] for row in action_rows if row.get("due_date")), None),
    }

    action_queue_path = output_root / "action_queue.csv"
    bundle_json_path = output_root / "signal_phase_action_queue.json"
    bundle_md_path = output_root / "signal_phase_action_queue.md"
    manifest_path = output_root / "signal_phase_action_queue.manifest.json"

    _write_csv(
        action_queue_path,
        action_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "action_category",
            "source_stage",
            "due_date",
            "due_now",
            "dispatch_status",
            "response_status",
            "lifecycle_statuses",
            "open_delivery_item_count",
            "delivery_item_ids",
            "dispatch_validation_outcome",
            "dispatch_validation_issue_codes",
            "repair_status_category",
            "repair_status",
            "repair_next_action",
            "repair_writeback_eligible",
            "packet_md_path",
            "primary_channel_value",
            "secondary_channel_value",
            "phone_escalation_value",
            "recommended_action",
            "action_summary",
        ],
    )

    payload = {
        "signal_phase_action_queue_version": SIGNAL_PHASE_ACTION_QUEUE_VERSION,
        "signal_phase_action_queue_contract_version": SIGNAL_PHASE_ACTION_QUEUE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "action_queue": action_rows,
        "inputs": {
            "signal_phase_operations_cycle_path": str(operations_cycle_input),
            "dispatch_execution_queue_path": str(dispatch_queue_input),
            "signal_phase_dispatch_bundle_path": str(dispatch_bundle_input),
            "lifecycle_items_path": str(lifecycle_items_input),
            "follow_up_execution_queue_path": str(follow_up_execution_input),
            "dispatch_log_repair_queue_path": str(dispatch_log_repair_input) if dispatch_log_repair_input else "",
            "dispatch_repair_status_path": str(dispatch_repair_status_input) if dispatch_repair_status_input else "",
        },
        "outputs": {
            "action_queue_path": str(action_queue_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_action_queue_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_action_queue_version": SIGNAL_PHASE_ACTION_QUEUE_VERSION,
        "contract": {
            "resource_name": "signal_phase_action_queue",
            "public_contract_version": SIGNAL_PHASE_ACTION_QUEUE_CONTRACT_VERSION,
            "signal_phase_action_queue_version": SIGNAL_PHASE_ACTION_QUEUE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_action_queue_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "action_queue_path": str(action_queue_path),
            "action_queue_sha256": _sha256(action_queue_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_operations_cycle_json",
                    operations_cycle_input,
                    _sha256(operations_cycle_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_queue",
                    dispatch_queue_input,
                    _sha256(dispatch_queue_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_bundle",
                    dispatch_bundle_input,
                    _sha256(dispatch_bundle_input) if dispatch_bundle_input.exists() else "",
                ),
                _artifact_reference(
                    "signal_phase_lifecycle_items",
                    lifecycle_items_input,
                    _sha256(lifecycle_items_input),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_execution_queue",
                    follow_up_execution_input,
                    _sha256(follow_up_execution_input),
                ),
                *(
                    [
                        _artifact_reference(
                            "signal_phase_dispatch_repair_queue",
                            dispatch_log_repair_input,
                            _sha256(dispatch_log_repair_input),
                        )
                    ]
                    if dispatch_log_repair_input is not None and dispatch_log_repair_input.exists()
                    else []
                ),
                *(
                    [
                        _artifact_reference(
                            "signal_phase_dispatch_repair_status_queue",
                            dispatch_repair_status_input,
                            _sha256(dispatch_repair_status_input),
                        )
                    ]
                    if dispatch_repair_status_input is not None and dispatch_repair_status_input.exists()
                    else []
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_action_queue_json", bundle_json_path, _sha256(bundle_json_path)),
                _artifact_reference(
                    "signal_phase_action_queue_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_action_queue_csv", action_queue_path, _sha256(action_queue_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_action_queue_version": SIGNAL_PHASE_ACTION_QUEUE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
