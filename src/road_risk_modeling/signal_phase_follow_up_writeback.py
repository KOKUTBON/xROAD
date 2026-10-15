"""Build Bari signal-phase follow-up writeback bundles from execution logs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_VERSION = "signal_phase_follow_up_writeback_bundle_v1"
SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_CONTRACT_VERSION = "signal_phase_follow_up_writeback_bundle_public_v1"
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
        f"follow-up {row.get('next_follow_up_stage') or 'unknown'}",
        f"status={row.get('execution_status') or 'unknown'}",
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
        return "response_received_after_follow_up"
    return "follow_up_executed_no_response_yet"


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Follow-up Writeback Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari follow-up execution queue has been transformed into synced tracker exports and writeback-ready rows.",
        "",
        "## Summary",
        "",
        f"- dispatch rows: `{payload['summary']['dispatch_row_count']}`",
        f"- follow-up tracker rows: `{payload['summary']['tracker_row_count']}`",
        f"- execution queue rows: `{payload['summary']['execution_queue_row_count']}`",
        f"- writeback-ready rows: `{payload['summary']['writeback_ready_count']}`",
        f"- dispatch rows updated: `{payload['summary']['dispatch_rows_updated_count']}`",
        f"- tracker rows completed: `{payload['summary']['tracker_rows_completed_count']}`",
        f"- response-received rows: `{payload['summary']['response_received_count']}`",
        "",
    ]
    return "\n".join(lines)


def build_bari_signal_phase_follow_up_writeback_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_follow_up_writeback/bari",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    follow_up_tracker_path: str | Path = "data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    follow_up_execution_queue_path: str | Path = "data/reporting/signal_phase_follow_up_execution/bari/follow_up_execution_queue.csv",
    follow_up_tracker_updates_path: str | Path = "data/reporting/signal_phase_follow_up_execution/bari/follow_up_tracker_updates.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    dispatch_input = Path(dispatch_execution_queue_path)
    tracker_input = Path(follow_up_tracker_path)
    execution_input = Path(follow_up_execution_queue_path)
    tracker_updates_input = Path(follow_up_tracker_updates_path)

    dispatch_rows = _read_csv_rows(dispatch_input)
    tracker_rows = _read_csv_rows(tracker_input)
    execution_rows = _read_csv_rows(execution_input)
    tracker_update_rows = _read_csv_rows(tracker_updates_input)

    execution_by_request_stage = {
        (str(row.get("request_id") or ""), str(row.get("next_follow_up_stage") or "")): row
        for row in execution_rows
        if row.get("request_id") and row.get("next_follow_up_stage")
    }
    tracker_update_by_request_stage = {
        (str(row.get("request_id") or ""), str(row.get("follow_up_stage") or "")): row
        for row in tracker_update_rows
        if row.get("request_id") and row.get("follow_up_stage")
    }

    synced_dispatch_rows: list[dict[str, Any]] = []
    synced_tracker_rows: list[dict[str, Any]] = []
    writeback_ready_rows: list[dict[str, Any]] = []

    for row in dispatch_rows:
        request_id = str(row.get("request_id") or "")
        execution_row = next(
            (
                candidate
                for (candidate_request_id, _candidate_stage), candidate in execution_by_request_stage.items()
                if candidate_request_id == request_id
            ),
            None,
        )
        synced = dict(row)
        synced["synced_follow_up_stage"] = _clean_text(execution_row.get("next_follow_up_stage")) if execution_row else ""
        synced["synced_execution_status"] = _clean_text(execution_row.get("execution_status")) if execution_row else ""
        synced["synced_execution_completed_at"] = _clean_text(execution_row.get("execution_completed_at")) if execution_row else ""
        synced["synced_execution_channel_used"] = _clean_text(execution_row.get("execution_channel_used")) if execution_row else ""
        synced["synced_execution_outcome"] = _clean_text(execution_row.get("execution_outcome")) if execution_row else ""
        synced["synced_response_received"] = "yes" if execution_row and _is_true(execution_row.get("response_received")) else "no"
        synced["synced_response_summary"] = _clean_text(execution_row.get("response_summary")) if execution_row else ""
        synced["synced_protocol_reference"] = _clean_text(execution_row.get("protocol_reference")) if execution_row else ""
        synced["synced_evidence_path"] = _clean_text(execution_row.get("evidence_path")) if execution_row else ""
        if execution_row and _is_executed_status(execution_row.get("execution_status")):
            synced["response_status"] = _response_status(execution_row, _clean_text(row.get("response_status")))
            if _is_true(execution_row.get("response_received")):
                synced["response_received_date"] = _date_portion(execution_row.get("execution_completed_at"))
            if _clean_text(execution_row.get("evidence_path")):
                synced["delivery_evidence_path"] = _clean_text(execution_row.get("evidence_path"))
            synced["notes"] = _append_note(row.get("notes"), _execution_note(execution_row))
            ready_row = dict(execution_row)
            ready_row["linked_dispatch_response_status"] = synced["response_status"]
            writeback_ready_rows.append(ready_row)
        synced_dispatch_rows.append(synced)

    for row in tracker_rows:
        key = (str(row.get("request_id") or ""), str(row.get("follow_up_stage") or ""))
        execution_row = execution_by_request_stage.get(key)
        tracker_update_row = tracker_update_by_request_stage.get(key)
        synced = dict(row)
        synced["synced_execution_status"] = _clean_text(execution_row.get("execution_status")) if execution_row else ""
        synced["synced_execution_completed_at"] = _clean_text(execution_row.get("execution_completed_at")) if execution_row else ""
        synced["synced_response_received"] = "yes" if execution_row and _is_true(execution_row.get("response_received")) else "no"
        synced["synced_response_summary"] = _clean_text(execution_row.get("response_summary")) if execution_row else ""
        synced["synced_protocol_reference"] = _clean_text(execution_row.get("protocol_reference")) if execution_row else ""
        synced["synced_evidence_path"] = _clean_text(execution_row.get("evidence_path")) if execution_row else ""
        synced["synced_execution_packet_md_path"] = (
            _clean_text(tracker_update_row.get("linked_execution_packet_md_path")) if tracker_update_row else ""
        )
        if execution_row and _is_executed_status(execution_row.get("execution_status")):
            synced["completion_status"] = "completed"
            synced["completion_date"] = _date_portion(execution_row.get("execution_completed_at"))
            synced["notes"] = _append_note(row.get("notes"), _execution_note(execution_row))
        synced_tracker_rows.append(synced)

    synced_dispatch_path = output_root / "dispatch_execution_queue_synced.csv"
    synced_tracker_path = output_root / "follow_up_tracker_synced.csv"
    writeback_ready_path = output_root / "writeback_ready_queue.csv"
    bundle_json_path = output_root / "signal_phase_follow_up_writeback_bundle.json"
    bundle_md_path = output_root / "signal_phase_follow_up_writeback_bundle.md"
    manifest_path = output_root / "signal_phase_follow_up_writeback_bundle.manifest.json"

    dispatch_fieldnames = list(dispatch_rows[0].keys()) if dispatch_rows else []
    for field in [
        "synced_follow_up_stage",
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
        "synced_execution_status",
        "synced_execution_completed_at",
        "synced_response_received",
        "synced_response_summary",
        "synced_protocol_reference",
        "synced_evidence_path",
        "synced_execution_packet_md_path",
    ]:
        if field not in tracker_fieldnames:
            tracker_fieldnames.append(field)

    writeback_fieldnames = list(writeback_ready_rows[0].keys()) if writeback_ready_rows else [
        "request_id",
        "next_follow_up_stage",
        "execution_status",
        "execution_completed_at",
        "execution_channel_used",
        "execution_outcome",
        "response_received",
        "response_summary",
        "protocol_reference",
        "evidence_path",
        "linked_dispatch_response_status",
    ]

    _write_csv(synced_dispatch_path, synced_dispatch_rows, dispatch_fieldnames)
    _write_csv(synced_tracker_path, synced_tracker_rows, tracker_fieldnames)
    _write_csv(writeback_ready_path, writeback_ready_rows, writeback_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dispatch_row_count": len(synced_dispatch_rows),
        "tracker_row_count": len(synced_tracker_rows),
        "execution_queue_row_count": len(execution_rows),
        "writeback_ready_count": len(writeback_ready_rows),
        "dispatch_rows_updated_count": sum(
            1 for row in synced_dispatch_rows if _is_executed_status(row.get("synced_execution_status"))
        ),
        "tracker_rows_completed_count": sum(1 for row in synced_tracker_rows if _clean_text(row.get("completion_status")) == "completed"),
        "response_received_count": sum(
            1 for row in synced_dispatch_rows if (_clean_text(row.get("synced_response_received")) or "no") == "yes"
        ),
    }
    payload = {
        "signal_phase_follow_up_writeback_bundle_version": SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_VERSION,
        "signal_phase_follow_up_writeback_bundle_contract_version": SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "outputs": {
            "synced_dispatch_execution_queue_path": str(synced_dispatch_path),
            "synced_follow_up_tracker_path": str(synced_tracker_path),
            "writeback_ready_queue_path": str(writeback_ready_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_follow_up_writeback_bundle_version": SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_follow_up_writeback_bundle",
            "public_contract_version": SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_CONTRACT_VERSION,
            "signal_phase_follow_up_writeback_bundle_version": SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_follow_up_writeback_builder",
        },
        "inputs": {
            "dispatch_execution_queue_path": str(dispatch_input),
            "follow_up_tracker_path": str(tracker_input),
            "follow_up_execution_queue_path": str(execution_input),
            "follow_up_tracker_updates_path": str(tracker_updates_input),
        },
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
                _artifact_reference("signal_phase_dispatch_queue", dispatch_input, _sha256(dispatch_input)),
                _artifact_reference("signal_phase_follow_up_tracker", tracker_input, _sha256(tracker_input)),
                _artifact_reference(
                    "signal_phase_follow_up_execution_queue",
                    execution_input,
                    _sha256(execution_input),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_tracker_updates",
                    tracker_updates_input,
                    _sha256(tracker_updates_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_follow_up_writeback_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_writeback_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_dispatch_queue_synced",
                    synced_dispatch_path,
                    _sha256(synced_dispatch_path),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_tracker_synced",
                    synced_tracker_path,
                    _sha256(synced_tracker_path),
                ),
                _artifact_reference(
                    "signal_phase_follow_up_writeback_ready_queue",
                    writeback_ready_path,
                    _sha256(writeback_ready_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_follow_up_writeback_bundle_version": SIGNAL_PHASE_FOLLOW_UP_WRITEBACK_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
