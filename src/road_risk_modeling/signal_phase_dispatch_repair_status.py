"""Build Bari dispatch-repair status bundles from repair, validation, and execution state."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_VERSION = (
    "signal_phase_dispatch_repair_status_bundle_v1"
)
SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_dispatch_repair_status_bundle_public_v1"
)
_READY_REPAIR_STATUSES = {"ready_for_validation", "completed_after_repair", "completed"}
_PENDING_REPAIR_STATUSES = {"", "pending_repair"}


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


def _status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Repair Status Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari dispatch-repair path has been consolidated into request-level status rows across repair logging, repair execution, and validation.",
        "",
        "## Summary",
        "",
        f"- repair-related requests: `{payload['summary']['request_count']}`",
        f"- pending repair: `{payload['summary']['pending_repair_count']}`",
        f"- ready for validation: `{payload['summary']['ready_for_validation_count']}`",
        f"- still blocked after repair: `{payload['summary']['still_blocked_count']}`",
        f"- cleared for writeback: `{payload['summary']['cleared_for_writeback_count']}`",
        f"- history only: `{payload['summary']['history_only_count']}`",
        f"- due now: `{payload['summary']['due_now_count']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["status_rows"]:
        lines.append(
            f"- `{row['request_id']}` `{row['repair_status_category']}` "
            f"(due_now=`{row['due_now']}`) -> `{row['action_summary']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_repair_status_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_dispatch_repair_status/bari",
    dispatch_log_repair_queue_path: str | Path = "data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
    dispatch_log_repair_log_path: str | Path = "data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
    dispatch_repair_execution_ready_queue_path: str | Path = "data/reporting/signal_phase_dispatch_repair_execution/bari/dispatch_repair_execution_ready_queue.csv",
    dispatch_repair_internal_hold_queue_path: str | Path = "data/reporting/signal_phase_dispatch_repair_execution/bari/dispatch_repair_internal_hold_queue.csv",
    dispatch_validation_queue_path: str | Path = "data/quality/signal_phase_dispatch_validation/bari/dispatch_execution_queue_validated.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    repair_queue_input = Path(dispatch_log_repair_queue_path)
    repair_log_input = Path(dispatch_log_repair_log_path)
    execution_ready_input = Path(dispatch_repair_execution_ready_queue_path)
    internal_hold_input = Path(dispatch_repair_internal_hold_queue_path)
    validation_input = Path(dispatch_validation_queue_path)

    repair_queue_rows = _read_csv_rows(repair_queue_input) if repair_queue_input.exists() else []
    repair_log_rows = _read_csv_rows(repair_log_input) if repair_log_input.exists() else []
    execution_ready_rows = (
        _read_csv_rows(execution_ready_input) if execution_ready_input.exists() else []
    )
    internal_hold_rows = _read_csv_rows(internal_hold_input) if internal_hold_input.exists() else []
    validation_rows = _read_csv_rows(validation_input) if validation_input.exists() else []

    repair_queue_by_request = {
        str(row.get("request_id") or ""): row for row in repair_queue_rows if row.get("request_id")
    }
    repair_log_by_request = {
        str(row.get("request_id") or ""): row for row in repair_log_rows if row.get("request_id")
    }
    execution_ready_by_request = {
        str(row.get("request_id") or ""): row
        for row in execution_ready_rows
        if row.get("request_id")
    }
    internal_hold_by_request = {
        str(row.get("request_id") or ""): row for row in internal_hold_rows if row.get("request_id")
    }
    validation_by_request = {
        str(row.get("request_id") or ""): row for row in validation_rows if row.get("request_id")
    }

    request_ids = sorted(
        {
            *repair_queue_by_request.keys(),
            *repair_log_by_request.keys(),
            *execution_ready_by_request.keys(),
            *internal_hold_by_request.keys(),
        },
        key=lambda request_id: (
            _priority_value(
                repair_queue_by_request.get(request_id, {}).get("dispatch_validation_issue_count")
            ),
            request_id,
        ),
    )

    status_rows: list[dict[str, Any]] = []
    due_now_rows: list[dict[str, Any]] = []
    pending_repair_count = 0
    ready_for_validation_count = 0
    still_blocked_count = 0
    cleared_for_writeback_count = 0
    history_only_count = 0
    due_now_count = 0

    for request_id in request_ids:
        repair_queue_row = repair_queue_by_request.get(request_id, {})
        repair_log_row = repair_log_by_request.get(request_id, {})
        execution_ready_row = execution_ready_by_request.get(request_id, {})
        internal_hold_row = internal_hold_by_request.get(request_id, {})
        validation_row = validation_by_request.get(request_id, {})

        dispatch_reference = (
            _clean_text(repair_queue_row.get("dispatch_reference"))
            or _clean_text(repair_log_row.get("dispatch_reference"))
            or _clean_text(validation_row.get("dispatch_reference"))
            or ""
        )
        junction_id = (
            _clean_text(repair_queue_row.get("junction_id"))
            or _clean_text(repair_log_row.get("junction_id"))
            or _clean_text(validation_row.get("junction_id"))
            or ""
        )
        signal_name = (
            _clean_text(repair_queue_row.get("signal_name"))
            or _clean_text(repair_log_row.get("signal_name"))
            or _clean_text(validation_row.get("signal_name"))
            or ""
        )
        action_category = _clean_text(repair_queue_row.get("action_category")) or ""
        repair_status = _clean_text(repair_log_row.get("repair_status")) or ""
        validation_outcome = _clean_text(validation_row.get("dispatch_validation_outcome")) or ""
        validation_issue_codes = (
            _clean_text(validation_row.get("dispatch_validation_issue_codes"))
            or _clean_text(repair_queue_row.get("dispatch_validation_issue_codes"))
            or ""
        )
        writeback_eligible = _clean_text(validation_row.get("writeback_eligible")) or "no"
        repair_applied = _clean_text(validation_row.get("repair_applied")) or "no"
        repair_packet_md_path = (
            _clean_text(execution_ready_row.get("repair_packet_md_path"))
            or _clean_text(internal_hold_row.get("repair_packet_md_path"))
            or _clean_text(repair_queue_row.get("repair_packet_md_path"))
            or ""
        )
        repair_packet_json_path = _clean_text(repair_queue_row.get("repair_packet_json_path")) or ""

        if execution_ready_row:
            execution_queue_state = "repair_execution_ready"
        elif internal_hold_row:
            execution_queue_state = "internal_hold"
        else:
            execution_queue_state = "not_queued"

        lowered_repair_status = repair_status.lower()
        if (
            validation_outcome == "accepted_for_writeback"
            and (repair_log_row or repair_applied.lower() == "yes")
        ):
            repair_status_category = "repair_cleared_for_writeback"
            due_now = "no"
            next_action = "wait_for_writeback_refresh"
            action_summary = (
                "The repaired dispatch row has passed validation and is ready for the next writeback or runtime refresh."
            )
            cleared_for_writeback_count += 1
        elif (
            validation_outcome in {"rejected_for_writeback", "incomplete_operator_entry"}
            and lowered_repair_status in _READY_REPAIR_STATUSES
        ):
            repair_status_category = "repair_still_blocked"
            due_now = "yes"
            next_action = "update_repair_log_and_rerun_validation"
            action_summary = (
                f"The repair was staged, but validation is still blocked by `{validation_issue_codes or 'unknown issues'}`."
            )
            still_blocked_count += 1
            due_now_count += 1
        elif lowered_repair_status in _READY_REPAIR_STATUSES:
            repair_status_category = "ready_for_validation"
            due_now = "yes"
            next_action = "rerun_validation_or_runtime_cycle"
            action_summary = (
                "The corrected dispatch row is staged; rerun validation or the Bari runtime cycle to clear it."
            )
            ready_for_validation_count += 1
            due_now_count += 1
        elif repair_queue_row or execution_ready_row:
            repair_status_category = "pending_repair"
            due_now = "yes"
            next_action = "complete_repair_log"
            action_summary = (
                f"Complete the repair for `{validation_issue_codes or 'the current validation blockers'}` and mark the row ready for validation."
            )
            pending_repair_count += 1
            due_now_count += 1
        else:
            repair_status_category = "repair_history_only"
            due_now = "no"
            next_action = "none"
            action_summary = "The request only remains in repair history and has no current open repair action."
            history_only_count += 1

        status_row = {
            "dispatch_reference": dispatch_reference,
            "request_id": request_id,
            "junction_id": junction_id,
            "signal_name": signal_name,
            "action_category": action_category,
            "repair_status_category": repair_status_category,
            "repair_status": repair_status or "not_started",
            "validation_outcome": validation_outcome or "not_revalidated",
            "validation_issue_codes": validation_issue_codes,
            "writeback_eligible": writeback_eligible,
            "repair_applied": repair_applied,
            "execution_queue_state": execution_queue_state,
            "due_now": due_now,
            "next_action": next_action,
            "action_summary": action_summary,
            "repair_packet_md_path": repair_packet_md_path,
            "repair_packet_json_path": repair_packet_json_path,
        }
        status_rows.append(status_row)
        if due_now == "yes":
            due_now_rows.append(status_row)

    status_queue_path = output_root / "dispatch_repair_status.csv"
    due_now_queue_path = output_root / "dispatch_repair_due_now_queue.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_repair_status_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_repair_status_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_repair_status_bundle.manifest.json"

    fieldnames = [
        "dispatch_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "action_category",
        "repair_status_category",
        "repair_status",
        "validation_outcome",
        "validation_issue_codes",
        "writeback_eligible",
        "repair_applied",
        "execution_queue_state",
        "due_now",
        "next_action",
        "action_summary",
        "repair_packet_md_path",
        "repair_packet_json_path",
    ]
    _write_csv(status_queue_path, status_rows, fieldnames)
    _write_csv(due_now_queue_path, due_now_rows, fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(status_rows),
        "pending_repair_count": pending_repair_count,
        "ready_for_validation_count": ready_for_validation_count,
        "still_blocked_count": still_blocked_count,
        "cleared_for_writeback_count": cleared_for_writeback_count,
        "history_only_count": history_only_count,
        "due_now_count": due_now_count,
        "execution_ready_count": len(execution_ready_rows),
        "internal_hold_count": len(internal_hold_rows),
    }
    payload = {
        "signal_phase_dispatch_repair_status_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_VERSION,
        "signal_phase_dispatch_repair_status_bundle_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "inputs": {
            "dispatch_log_repair_queue_path": str(repair_queue_input),
            "dispatch_log_repair_log_path": str(repair_log_input),
            "dispatch_repair_execution_ready_queue_path": str(execution_ready_input),
            "dispatch_repair_internal_hold_queue_path": str(internal_hold_input),
            "dispatch_validation_queue_path": str(validation_input),
        },
        "outputs": {
            "status_queue_path": str(status_queue_path),
            "due_now_queue_path": str(due_now_queue_path),
            "manifest_path": str(manifest_path),
        },
        "status_rows": status_rows,
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_status_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_dispatch_repair_status_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_repair_status_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_repair_status_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_repair_status_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "status_queue_path": str(status_queue_path),
            "status_queue_sha256": _sha256(status_queue_path),
            "due_now_queue_path": str(due_now_queue_path),
            "due_now_queue_sha256": _sha256(due_now_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            *(
                [
                    _artifact_reference(
                        "signal_phase_dispatch_repair_queue",
                        repair_queue_input,
                        _sha256(repair_queue_input),
                    )
                ]
                if repair_queue_input.exists()
                else []
            ),
            *(
                [
                    _artifact_reference(
                        "signal_phase_dispatch_repair_log",
                        repair_log_input,
                        _sha256(repair_log_input),
                    )
                ]
                if repair_log_input.exists()
                else []
            ),
            *(
                [
                    _artifact_reference(
                        "signal_phase_dispatch_repair_execution_ready_queue",
                        execution_ready_input,
                        _sha256(execution_ready_input),
                    )
                ]
                if execution_ready_input.exists()
                else []
            ),
            *(
                [
                    _artifact_reference(
                        "signal_phase_dispatch_repair_internal_hold_queue",
                        internal_hold_input,
                        _sha256(internal_hold_input),
                    )
                ]
                if internal_hold_input.exists()
                else []
            ),
            *(
                [
                    _artifact_reference(
                        "signal_phase_dispatch_execution_validated_queue",
                        validation_input,
                        _sha256(validation_input),
                    )
                ]
                if validation_input.exists()
                else []
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_status_bundle_json",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_repair_status_bundle_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_dispatch_repair_status_queue",
                status_queue_path,
                _sha256(status_queue_path),
            ),
            _artifact_reference(
                "signal_phase_dispatch_repair_due_now_queue",
                due_now_queue_path,
                _sha256(due_now_queue_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_dispatch_repair_status_bundle_version": SIGNAL_PHASE_DISPATCH_REPAIR_STATUS_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
