"""Build Bari signal-phase dispatch writeback bundles from execution logs."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_VERSION = "signal_phase_dispatch_writeback_bundle_v1"
SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_CONTRACT_VERSION = "signal_phase_dispatch_writeback_bundle_public_v1"
_PENDING_EXECUTION_STATUSES = {"pending_execution"}


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


def _is_true(value: Any) -> bool:
    text = (_clean_text(value) or "").lower()
    return text in {"1", "true", "yes", "y"}


def _is_executed_status(value: Any) -> bool:
    status = _clean_text(value)
    if not status:
        return False
    return status not in _PENDING_EXECUTION_STATUSES


def _is_writeback_eligible(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    explicit_flag = _clean_text(row.get("writeback_eligible"))
    if explicit_flag is not None:
        return explicit_flag.lower() in {"1", "true", "yes", "y"}
    validation_outcome = _clean_text(row.get("dispatch_validation_outcome"))
    if validation_outcome is not None:
        return validation_outcome == "accepted_for_writeback"
    return _is_executed_status(row.get("execution_status"))


def _parse_date(value: Any) -> date | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _date_portion(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    candidate = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate).date().isoformat()
    except ValueError:
        if "T" in text:
            return text.split("T", 1)[0]
        return text


def _append_note(existing: Any, note: str | None) -> str:
    current = _clean_text(existing)
    addition = _clean_text(note)
    if not current and not addition:
        return ""
    if not current:
        return str(addition)
    if not addition:
        return str(current)
    return f"{current} | {addition}"


def _execution_note(row: dict[str, Any]) -> str:
    parts = [
        f"dispatch status={row.get('execution_status') or 'unknown'}",
    ]
    if _clean_text(row.get("execution_completed_at")):
        parts.append(f"at={row['execution_completed_at']}")
    if _clean_text(row.get("execution_channel_used")):
        parts.append(f"channel={row['execution_channel_used']}")
    if _clean_text(row.get("execution_outcome")):
        parts.append(f"outcome={row['execution_outcome']}")
    if _is_true(row.get("response_received")):
        parts.append("response_received=yes")
    if _clean_text(row.get("protocol_reference")):
        parts.append(f"protocol={row['protocol_reference']}")
    return " ".join(parts)


def _response_status(row: dict[str, Any], fallback: str | None) -> str:
    if not _is_executed_status(row.get("execution_status")):
        return fallback or ""
    if _is_true(row.get("response_received")):
        return "response_received_after_dispatch"
    return fallback or "awaiting_delivery"


def _shift_days(
    planned_dispatch_date_value: Any,
    actual_dispatch_date_value: Any,
) -> int:
    planned_dispatch_date = _parse_date(planned_dispatch_date_value)
    actual_dispatch_date = _parse_date(actual_dispatch_date_value)
    if not planned_dispatch_date or not actual_dispatch_date:
        return 0
    return (actual_dispatch_date - planned_dispatch_date).days


def _shift_due_date(
    due_date_value: Any,
    planned_dispatch_date_value: Any,
    actual_dispatch_date_value: Any,
) -> tuple[str | None, int]:
    due_date = _parse_date(due_date_value)
    planned_dispatch_date = _parse_date(planned_dispatch_date_value)
    actual_dispatch_date = _parse_date(actual_dispatch_date_value)
    if not due_date or not planned_dispatch_date or not actual_dispatch_date:
        return _clean_text(due_date_value), 0
    delta = due_date - planned_dispatch_date
    shifted = actual_dispatch_date + timedelta(days=delta.days)
    return shifted.isoformat(), (actual_dispatch_date - planned_dispatch_date).days


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Dispatch Writeback Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari initial-dispatch execution queue has been transformed into synced runtime dispatch and follow-up exports.",
        "",
        "## Summary",
        "",
        f"- dispatch rows: `{payload['summary']['dispatch_row_count']}`",
        f"- follow-up tracker rows: `{payload['summary']['tracker_row_count']}`",
        f"- execution queue rows: `{payload['summary']['execution_queue_row_count']}`",
        f"- writeback-ready rows: `{payload['summary']['writeback_ready_count']}`",
        f"- dispatch rows updated: `{payload['summary']['dispatch_rows_updated_count']}`",
        f"- tracker rows retimed: `{payload['summary']['tracker_rows_retimed_count']}`",
        f"- response-received rows: `{payload['summary']['response_received_count']}`",
        f"- targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- unresolved signalized movements across execution rows: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across execution rows: `{payload['summary']['unresolved_signalized_crash_total']}`",
        f"- writeback-ready unresolved signalized movements: `{payload['summary']['writeback_ready_unresolved_signalized_movement_total']}`",
        f"- writeback-ready unresolved signalized crashes: `{payload['summary']['writeback_ready_unresolved_signalized_crash_total']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_dispatch_writeback_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_dispatch_writeback/bari",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    follow_up_tracker_path: str | Path = "data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    dispatch_execution_ready_queue_path: str | Path = "data/quality/signal_phase_dispatch_validation/bari/dispatch_execution_queue_validated.csv",
    dispatch_tracker_updates_path: str | Path = "data/reporting/signal_phase_dispatch_execution/bari/dispatch_tracker_updates.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    dispatch_input = Path(dispatch_execution_queue_path)
    tracker_input = Path(follow_up_tracker_path)
    execution_input = Path(dispatch_execution_ready_queue_path)
    tracker_updates_input = Path(dispatch_tracker_updates_path)

    dispatch_rows = _read_csv_rows(dispatch_input)
    tracker_rows = _read_csv_rows(tracker_input)
    execution_rows = _read_csv_rows(execution_input)
    tracker_update_rows = _read_csv_rows(tracker_updates_input)

    execution_by_request = {
        str(row.get("request_id") or ""): row
        for row in execution_rows
        if row.get("request_id")
    }
    tracker_update_by_request = {
        str(row.get("request_id") or ""): row
        for row in tracker_update_rows
        if row.get("request_id")
    }
    dispatch_by_request = {
        str(row.get("request_id") or ""): row
        for row in dispatch_rows
        if row.get("request_id")
    }

    synced_dispatch_rows: list[dict[str, Any]] = []
    synced_tracker_rows: list[dict[str, Any]] = []
    writeback_ready_rows: list[dict[str, Any]] = []
    tracker_rows_retimed_count = 0

    for row in dispatch_rows:
        request_id = str(row.get("request_id") or "")
        execution_row = execution_by_request.get(request_id)
        tracker_update_row = tracker_update_by_request.get(request_id)
        synced = dict(row)
        synced["synced_execution_status"] = ""
        synced["synced_execution_completed_at"] = ""
        synced["synced_execution_channel_used"] = ""
        synced["synced_execution_outcome"] = ""
        synced["synced_response_received"] = "no"
        synced["synced_response_summary"] = ""
        synced["synced_protocol_reference"] = ""
        synced["synced_evidence_path"] = ""
        if _is_writeback_eligible(execution_row):
            synced["synced_execution_status"] = _clean_text(execution_row.get("execution_status")) or ""
            synced["synced_execution_completed_at"] = _clean_text(execution_row.get("execution_completed_at")) or ""
            synced["synced_execution_channel_used"] = _clean_text(execution_row.get("execution_channel_used")) or ""
            synced["synced_execution_outcome"] = _clean_text(execution_row.get("execution_outcome")) or ""
            synced["synced_response_received"] = "yes" if _is_true(execution_row.get("response_received")) else "no"
            synced["synced_response_summary"] = _clean_text(execution_row.get("response_summary")) or ""
            synced["synced_protocol_reference"] = _clean_text(execution_row.get("protocol_reference")) or ""
            synced["synced_evidence_path"] = _clean_text(execution_row.get("evidence_path")) or ""
            synced["dispatch_status"] = _clean_text(tracker_update_row.get("target_dispatch_status")) or _clean_text(
                row.get("dispatch_status")
            )
            synced["response_status"] = _response_status(
                execution_row,
                _clean_text(tracker_update_row.get("target_response_status")) or _clean_text(row.get("response_status")),
            )
            if _is_true(execution_row.get("response_received")):
                synced["response_received_date"] = _date_portion(execution_row.get("execution_completed_at"))
            if _clean_text(execution_row.get("evidence_path")):
                synced["delivery_evidence_path"] = _clean_text(execution_row.get("evidence_path"))
            synced["notes"] = _append_note(row.get("notes"), _execution_note(execution_row))
            ready_row = dict(execution_row)
            ready_row["linked_target_dispatch_status"] = synced["dispatch_status"]
            ready_row["linked_target_response_status"] = synced["response_status"]
            writeback_ready_rows.append(ready_row)
        synced_dispatch_rows.append(synced)

    for row in tracker_rows:
        request_id = str(row.get("request_id") or "")
        execution_row = execution_by_request.get(request_id)
        dispatch_row = dispatch_by_request.get(request_id)
        synced = dict(row)
        synced["original_due_date"] = _clean_text(row.get("due_date")) or ""
        synced["synced_dispatch_status"] = ""
        synced["synced_dispatch_completed_at"] = ""
        synced["synced_execution_channel_used"] = ""
        synced["synced_protocol_reference"] = ""
        synced["synced_evidence_path"] = ""
        synced["due_date_shift_days"] = 0
        if _is_writeback_eligible(execution_row) and dispatch_row:
            tracker_update_row = tracker_update_by_request.get(request_id)
            synced["synced_dispatch_status"] = _clean_text(tracker_update_row.get("target_dispatch_status")) or _clean_text(
                dispatch_row.get("dispatch_status")
            ) or ""
            synced["synced_dispatch_completed_at"] = _clean_text(execution_row.get("execution_completed_at")) or ""
            synced["synced_execution_channel_used"] = _clean_text(execution_row.get("execution_channel_used")) or ""
            synced["synced_protocol_reference"] = _clean_text(execution_row.get("protocol_reference")) or ""
            synced["synced_evidence_path"] = _clean_text(execution_row.get("evidence_path")) or ""
            shifted_due_date, shift_value = _shift_due_date(
                row.get("due_date"),
                dispatch_row.get("planned_dispatch_date"),
                _date_portion(execution_row.get("execution_completed_at")),
            )
            if shifted_due_date and shifted_due_date != _clean_text(row.get("due_date")):
                synced["due_date"] = shifted_due_date
                synced["due_date_shift_days"] = _shift_days(
                    dispatch_row.get("planned_dispatch_date"),
                    _date_portion(execution_row.get("execution_completed_at")),
                )
                tracker_rows_retimed_count += 1
            synced["notes"] = _append_note(row.get("notes"), _execution_note(execution_row))
        synced_tracker_rows.append(synced)

    synced_dispatch_path = output_root / "dispatch_execution_queue_synced.csv"
    synced_tracker_path = output_root / "follow_up_tracker_synced.csv"
    writeback_ready_path = output_root / "writeback_ready_queue.csv"
    bundle_json_path = output_root / "signal_phase_dispatch_writeback_bundle.json"
    bundle_md_path = output_root / "signal_phase_dispatch_writeback_bundle.md"
    manifest_path = output_root / "signal_phase_dispatch_writeback_bundle.manifest.json"

    dispatch_fieldnames = list(dispatch_rows[0].keys()) if dispatch_rows else []
    for field in [
        "synced_execution_status",
        "synced_execution_completed_at",
        "synced_execution_channel_used",
        "synced_execution_outcome",
        "synced_response_received",
        "synced_response_summary",
        "synced_protocol_reference",
        "synced_evidence_path",
    ]:
        if field not in dispatch_fieldnames:
            dispatch_fieldnames.append(field)

    tracker_fieldnames = list(tracker_rows[0].keys()) if tracker_rows else []
    for field in [
        "original_due_date",
        "synced_dispatch_status",
        "synced_dispatch_completed_at",
        "synced_execution_channel_used",
        "synced_protocol_reference",
        "synced_evidence_path",
        "due_date_shift_days",
    ]:
        if field not in tracker_fieldnames:
            tracker_fieldnames.append(field)

    writeback_fieldnames = list(writeback_ready_rows[0].keys()) if writeback_ready_rows else [
        "request_id",
        "execution_status",
        "execution_completed_at",
        "linked_target_dispatch_status",
        "linked_target_response_status",
    ]

    _write_csv(synced_dispatch_path, synced_dispatch_rows, dispatch_fieldnames)
    _write_csv(synced_tracker_path, synced_tracker_rows, tracker_fieldnames)
    _write_csv(writeback_ready_path, writeback_ready_rows, writeback_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dispatch_row_count": len(dispatch_rows),
        "tracker_row_count": len(tracker_rows),
        "execution_queue_row_count": len(execution_rows),
        "writeback_ready_count": len(writeback_ready_rows),
        "dispatch_rows_updated_count": sum(
            1 for row in execution_rows if _is_writeback_eligible(row)
        ),
        "tracker_rows_retimed_count": tracker_rows_retimed_count,
        "response_received_count": sum(
            1 for row in execution_rows if _is_writeback_eligible(row) and _is_true(row.get("response_received"))
        ),
        "targets_with_unresolved_movements": sum(
            1 for row in execution_rows if _safe_int(row.get("unresolved_signalized_movement_count")) > 0
        ),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row.get("unresolved_signalized_movement_count")) for row in execution_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row.get("unresolved_signalized_crash_count")) for row in execution_rows
        ),
        "writeback_ready_unresolved_signalized_movement_total": sum(
            _safe_int(row.get("unresolved_signalized_movement_count")) for row in writeback_ready_rows
        ),
        "writeback_ready_unresolved_signalized_crash_total": sum(
            _safe_int(row.get("unresolved_signalized_crash_count")) for row in writeback_ready_rows
        ),
    }

    payload = {
        "signal_phase_dispatch_writeback_bundle_version": SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_VERSION,
        "signal_phase_dispatch_writeback_bundle_contract_version": SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "inputs": {
            "dispatch_execution_queue_path": str(dispatch_input),
            "follow_up_tracker_path": str(tracker_input),
            "dispatch_execution_ready_queue_path": str(execution_input),
            "dispatch_tracker_updates_path": str(tracker_updates_input),
        },
        "outputs": {
            "synced_dispatch_execution_queue_path": str(synced_dispatch_path),
            "synced_follow_up_tracker_path": str(synced_tracker_path),
            "writeback_ready_queue_path": str(writeback_ready_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_dispatch_writeback_bundle_version": SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_dispatch_writeback_bundle",
            "public_contract_version": SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_CONTRACT_VERSION,
            "signal_phase_dispatch_writeback_bundle_version": SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_dispatch_writeback_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "synced_dispatch_execution_queue_path": str(synced_dispatch_path),
            "synced_dispatch_execution_queue_sha256": _sha256(synced_dispatch_path),
            "synced_follow_up_tracker_path": str(synced_tracker_path),
            "synced_follow_up_tracker_sha256": _sha256(synced_tracker_path),
            "writeback_ready_queue_path": str(writeback_ready_path),
            "writeback_ready_queue_sha256": _sha256(writeback_ready_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_dispatch_execution_queue",
                    dispatch_input,
                    _sha256(dispatch_input),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_tracker",
                    tracker_input,
                    _sha256(tracker_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_execution_ready_queue",
                    execution_input,
                    _sha256(execution_input),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_tracker_updates",
                    tracker_updates_input,
                    _sha256(tracker_updates_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_dispatch_writeback_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_writeback_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_dispatch_execution_queue_synced",
                    synced_dispatch_path,
                    _sha256(synced_dispatch_path),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_tracker_synced_after_dispatch",
                    synced_tracker_path,
                    _sha256(synced_tracker_path),
                ),
                _artifact_reference(
                    "signal_phase_dispatch_writeback_ready_queue",
                    writeback_ready_path,
                    _sha256(writeback_ready_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_dispatch_writeback_bundle_version": SIGNAL_PHASE_DISPATCH_WRITEBACK_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
