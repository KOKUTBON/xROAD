"""Build a Bari signal-phase delivery lifecycle report."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_LIFECYCLE_REPORT_VERSION = "signal_phase_lifecycle_report_v1"
SIGNAL_PHASE_LIFECYCLE_REPORT_CONTRACT_VERSION = "signal_phase_lifecycle_report_public_v1"


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


def _parse_date(value: Any) -> date | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _load_applied_validation_manifest_paths(receive_cycle_path: Path) -> tuple[str | None, set[str]]:
    if not receive_cycle_path.exists():
        return None, set()
    receive_cycle = _load_json(receive_cycle_path)
    session_manifest_value = receive_cycle.get("outputs", {}).get("delivery_session_manifest_path")
    session_manifest_path = _clean_text(session_manifest_value)
    if not session_manifest_path:
        return None, set()
    session_manifest = _load_json(Path(session_manifest_path))
    session_json_value = session_manifest.get("outputs", {}).get("session_json_path")
    session_json_path = _clean_text(session_json_value)
    if not session_json_path:
        return session_manifest_path, set()
    session_payload = _load_json(Path(session_json_path))
    accepted = {
        str(row.get("validation_manifest_path"))
        for row in session_payload.get("accepted_deliveries", [])
        if _clean_text(row.get("validation_manifest_path"))
    }
    return session_manifest_path, accepted


def _lifecycle_status(
    *,
    applied_to_movement_layer: bool,
    validation_outcome: str | None,
    monitor_status: str | None,
) -> str:
    if applied_to_movement_layer:
        return "applied_to_movement_layer"
    if validation_outcome == "accepted_for_ingestion":
        return "accepted_for_ingestion"
    if validation_outcome == "accepted_support_artifact":
        return "support_artifact_validated"
    if validation_outcome == "accepted_with_rejections":
        return "partial_review_required"
    if validation_outcome in {"provider_fix_required", "schema_not_ready", "empty_delivery"}:
        return "provider_fix_required"
    if monitor_status == "ready_for_validation":
        return "ready_for_validation"
    if monitor_status == "multiple_files_manual_review":
        return "manual_review_required"
    return "awaiting_delivery"


def _next_action(
    *,
    lifecycle_status: str,
    next_follow_up_stage: str | None,
    next_follow_up_due_date: str | None,
) -> str:
    if lifecycle_status == "applied_to_movement_layer":
        return "no_action_completed"
    if lifecycle_status == "accepted_for_ingestion":
        return "run_delivery_session"
    if lifecycle_status == "support_artifact_validated":
        return "await_remaining_joinable_deliveries_or_use_support_for_manual_mapping"
    if lifecycle_status == "partial_review_required":
        return "review_rejected_rows_and_decide_ingestion"
    if lifecycle_status == "provider_fix_required":
        return "request_corrected_provider_extract"
    if lifecycle_status == "ready_for_validation":
        return "run_validation_batch"
    if lifecycle_status == "manual_review_required":
        return "select_single_file_in_dropzone"
    if next_follow_up_stage and next_follow_up_due_date:
        return f"await_delivery_then_{next_follow_up_stage}_due_{next_follow_up_due_date}"
    return "await_provider_delivery"


def _report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Lifecycle Report",
        "",
        f"As of {payload['generated_at_utc']}, the Bari signal-phase request, receipt, validation, and application states have been consolidated into a single lifecycle board.",
        "",
        "## Summary",
        "",
        f"- requests: `{payload['summary']['request_count']}`",
        f"- delivery items: `{payload['summary']['delivery_item_count']}`",
        f"- awaiting delivery: `{payload['summary']['awaiting_delivery_count']}`",
        f"- ready for validation: `{payload['summary']['ready_for_validation_count']}`",
        f"- manual-review items: `{payload['summary']['manual_review_count']}`",
        f"- accepted for ingestion: `{payload['summary']['accepted_for_ingestion_count']}`",
        f"- validated support artifacts: `{payload['summary']['support_artifact_validated_count']}`",
        f"- provider-fix items: `{payload['summary']['provider_fix_count']}`",
        f"- applied to movement layer: `{payload['summary']['applied_count']}`",
        f"- pending follow-ups: `{payload['summary']['pending_follow_up_count']}`",
        f"- follow-ups due today or earlier: `{payload['summary']['due_follow_up_count']}`",
        "",
        "## Open Items",
        "",
    ]
    for row in payload["lifecycle_items"][:10]:
        lines.append(
            f"- `{row['delivery_item_id']}` `{row['lifecycle_status']}` -> `{row['next_action']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_lifecycle_report(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_lifecycle/bari",
    dispatch_execution_queue_path: str | Path = "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
    follow_up_tracker_path: str | Path = "data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
    delivery_receipt_register_path: str | Path = "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
    delivery_monitor_queue_path: str | Path = "data/reporting/signal_phase_delivery_monitor/bari/delivery_monitor_queue.csv",
    validation_batch_results_path: str | Path = "data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
    receive_cycle_path: str | Path = "data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    dispatch_input = Path(dispatch_execution_queue_path)
    follow_up_input = Path(follow_up_tracker_path)
    receipt_input = Path(delivery_receipt_register_path)
    monitor_input = Path(delivery_monitor_queue_path)
    validation_input = Path(validation_batch_results_path)
    receive_cycle_input = Path(receive_cycle_path)

    dispatch_rows = _read_csv_rows(dispatch_input)
    follow_up_rows = _read_csv_rows(follow_up_input)
    receipt_rows = _read_csv_rows(receipt_input)
    monitor_rows = _read_csv_rows(monitor_input)
    validation_rows = _read_csv_rows(validation_input)
    session_manifest_path, applied_manifests = _load_applied_validation_manifest_paths(receive_cycle_input)

    dispatch_by_request = {str(row["request_id"]): row for row in dispatch_rows if row.get("request_id")}
    monitor_by_item = {str(row["delivery_item_id"]): row for row in monitor_rows if row.get("delivery_item_id")}
    validation_by_item = {
        str(row["delivery_item_id"]): row for row in validation_rows if row.get("delivery_item_id")
    }
    follow_ups_by_request: dict[str, list[dict[str, str]]] = {}
    for row in follow_up_rows:
        request_id = str(row.get("request_id") or "")
        if not request_id:
            continue
        follow_ups_by_request.setdefault(request_id, []).append(row)

    today = date.today()
    lifecycle_items: list[dict[str, Any]] = []
    follow_up_agenda_rows: list[dict[str, Any]] = []

    for receipt_row in receipt_rows:
        request_id = str(receipt_row.get("request_id") or "")
        delivery_item_id = str(receipt_row.get("delivery_item_id") or "")
        dispatch_row = dispatch_by_request.get(request_id, {})
        monitor_row = monitor_by_item.get(delivery_item_id, {})
        validation_row = validation_by_item.get(delivery_item_id, {})
        item_follow_ups = sorted(
            follow_ups_by_request.get(request_id, []),
            key=lambda row: (_parse_date(row.get("due_date")) or date.max, str(row.get("follow_up_stage") or "")),
        )
        pending_follow_ups = [
            row for row in item_follow_ups if (_clean_text(row.get("completion_status")) or "pending") != "completed"
        ]
        next_follow_up = pending_follow_ups[0] if pending_follow_ups else {}
        next_due_date = _parse_date(next_follow_up.get("due_date"))

        validation_manifest_path = _clean_text(validation_row.get("manifest_path"))
        validation_outcome = _clean_text(validation_row.get("validation_outcome"))
        applied = bool(validation_manifest_path and validation_manifest_path in applied_manifests)
        monitor_status = _clean_text(monitor_row.get("monitor_status")) or _clean_text(receipt_row.get("receipt_status"))
        lifecycle_status = _lifecycle_status(
            applied_to_movement_layer=applied,
            validation_outcome=validation_outcome,
            monitor_status=monitor_status,
        )
        next_action = _next_action(
            lifecycle_status=lifecycle_status,
            next_follow_up_stage=_clean_text(next_follow_up.get("follow_up_stage")),
            next_follow_up_due_date=next_due_date.isoformat() if next_due_date else None,
        )

        lifecycle_row = {
            "dispatch_reference": _clean_text(receipt_row.get("dispatch_reference")),
            "request_id": request_id,
            "junction_id": _clean_text(receipt_row.get("junction_id")),
            "signal_name": _clean_text(receipt_row.get("signal_name")),
            "profile_id": _clean_text(receipt_row.get("profile_id")),
            "delivery_item_id": delivery_item_id,
            "dispatch_status": _clean_text(dispatch_row.get("dispatch_status")),
            "response_status": _clean_text(dispatch_row.get("response_status")),
            "planned_dispatch_date": _clean_text(dispatch_row.get("planned_dispatch_date")),
            "first_follow_up_date": _clean_text(dispatch_row.get("first_follow_up_date")),
            "escalation_date": _clean_text(dispatch_row.get("escalation_date")),
            "receipt_status": _clean_text(receipt_row.get("receipt_status")),
            "monitor_status": monitor_status,
            "detected_file_count": int(float(monitor_row.get("detected_file_count") or 0)),
            "selected_received_file_path": _clean_text(monitor_row.get("selected_received_file_path")),
            "validation_status": _clean_text(receipt_row.get("validation_status")) or _clean_text(
                monitor_row.get("validation_status")
            ),
            "validation_outcome": validation_outcome,
            "validation_manifest_path": validation_manifest_path,
            "applied_to_movement_layer": applied,
            "lifecycle_status": lifecycle_status,
            "next_action": next_action,
            "next_follow_up_stage": _clean_text(next_follow_up.get("follow_up_stage")),
            "next_follow_up_due_date": next_due_date.isoformat() if next_due_date else None,
            "follow_up_due": bool(next_due_date and next_due_date <= today),
        }
        lifecycle_items.append(lifecycle_row)

        for follow_up in pending_follow_ups:
            follow_due_date = _parse_date(follow_up.get("due_date"))
            follow_up_agenda_rows.append(
                {
                    "dispatch_reference": _clean_text(follow_up.get("dispatch_reference")),
                    "request_id": request_id,
                    "junction_id": _clean_text(follow_up.get("junction_id")),
                    "signal_name": _clean_text(follow_up.get("signal_name")),
                    "delivery_item_id": delivery_item_id,
                    "profile_id": _clean_text(receipt_row.get("profile_id")),
                    "follow_up_stage": _clean_text(follow_up.get("follow_up_stage")),
                    "due_date": follow_due_date.isoformat() if follow_due_date else None,
                    "recommended_channel": _clean_text(follow_up.get("recommended_channel")),
                    "recommended_action": _clean_text(follow_up.get("recommended_action")),
                    "lifecycle_status": lifecycle_status,
                    "due_now": bool(follow_due_date and follow_due_date <= today),
                }
            )

    lifecycle_items.sort(key=lambda row: (str(row["request_id"]), str(row["profile_id"])))
    follow_up_agenda_rows.sort(
        key=lambda row: (_parse_date(row.get("due_date")) or date.max, str(row.get("delivery_item_id") or ""))
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len({row["request_id"] for row in lifecycle_items if row.get("request_id")}),
        "delivery_item_count": len(lifecycle_items),
        "awaiting_delivery_count": sum(1 for row in lifecycle_items if row["lifecycle_status"] == "awaiting_delivery"),
        "ready_for_validation_count": sum(
            1 for row in lifecycle_items if row["lifecycle_status"] == "ready_for_validation"
        ),
        "manual_review_count": sum(1 for row in lifecycle_items if row["lifecycle_status"] == "manual_review_required"),
        "accepted_for_ingestion_count": sum(
            1 for row in lifecycle_items if row["lifecycle_status"] == "accepted_for_ingestion"
        ),
        "support_artifact_validated_count": sum(
            1 for row in lifecycle_items if row["lifecycle_status"] == "support_artifact_validated"
        ),
        "provider_fix_count": sum(1 for row in lifecycle_items if row["lifecycle_status"] == "provider_fix_required"),
        "partial_review_count": sum(
            1 for row in lifecycle_items if row["lifecycle_status"] == "partial_review_required"
        ),
        "applied_count": sum(1 for row in lifecycle_items if row["lifecycle_status"] == "applied_to_movement_layer"),
        "pending_follow_up_count": len(follow_up_agenda_rows),
        "due_follow_up_count": sum(1 for row in follow_up_agenda_rows if row["due_now"]),
        "next_follow_up_due_date": (
            next(
                (row["due_date"] for row in follow_up_agenda_rows if row.get("due_date")),
                None,
            )
        ),
    }

    report_json_path = output_root / "signal_phase_lifecycle_report.json"
    report_md_path = output_root / "signal_phase_lifecycle_report.md"
    lifecycle_items_path = output_root / "lifecycle_items.csv"
    follow_up_agenda_path = output_root / "follow_up_agenda.csv"
    manifest_path = output_root / "signal_phase_lifecycle_report.manifest.json"

    _write_csv(
        lifecycle_items_path,
        lifecycle_items,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "profile_id",
            "delivery_item_id",
            "dispatch_status",
            "response_status",
            "planned_dispatch_date",
            "first_follow_up_date",
            "escalation_date",
            "receipt_status",
            "monitor_status",
            "detected_file_count",
            "selected_received_file_path",
            "validation_status",
            "validation_outcome",
            "validation_manifest_path",
            "applied_to_movement_layer",
            "lifecycle_status",
            "next_action",
            "next_follow_up_stage",
            "next_follow_up_due_date",
            "follow_up_due",
        ],
    )
    _write_csv(
        follow_up_agenda_path,
        follow_up_agenda_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "delivery_item_id",
            "profile_id",
            "follow_up_stage",
            "due_date",
            "recommended_channel",
            "recommended_action",
            "lifecycle_status",
            "due_now",
        ],
    )

    payload = {
        "signal_phase_lifecycle_report_version": SIGNAL_PHASE_LIFECYCLE_REPORT_VERSION,
        "signal_phase_lifecycle_report_contract_version": SIGNAL_PHASE_LIFECYCLE_REPORT_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "lifecycle_items": lifecycle_items,
        "follow_up_agenda": follow_up_agenda_rows,
        "receive_cycle_session_manifest_path": session_manifest_path,
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_report_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_lifecycle_report_version": SIGNAL_PHASE_LIFECYCLE_REPORT_VERSION,
        "contract": {
            "resource_name": "signal_phase_lifecycle_report",
            "public_contract_version": SIGNAL_PHASE_LIFECYCLE_REPORT_CONTRACT_VERSION,
            "signal_phase_lifecycle_report_version": SIGNAL_PHASE_LIFECYCLE_REPORT_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_lifecycle_report_builder",
        },
        "inputs": {
            "dispatch_execution_queue_path": str(dispatch_input),
            "follow_up_tracker_path": str(follow_up_input),
            "delivery_receipt_register_path": str(receipt_input),
            "delivery_monitor_queue_path": str(monitor_input),
            "validation_batch_results_path": str(validation_input),
            "receive_cycle_path": str(receive_cycle_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "lifecycle_items_path": str(lifecycle_items_path),
            "lifecycle_items_sha256": _sha256(lifecycle_items_path),
            "follow_up_agenda_path": str(follow_up_agenda_path),
            "follow_up_agenda_sha256": _sha256(follow_up_agenda_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_dispatch_execution_queue", dispatch_input, _sha256(dispatch_input)),
                _artifact_reference("signal_phase_follow_up_tracker", follow_up_input, _sha256(follow_up_input)),
                _artifact_reference("signal_phase_delivery_receipt_register", receipt_input, _sha256(receipt_input)),
                _artifact_reference("signal_phase_delivery_monitor_queue", monitor_input, _sha256(monitor_input)),
                _artifact_reference("signal_phase_validation_batch_results", validation_input, _sha256(validation_input)),
                _artifact_reference("signal_phase_receive_cycle_json", receive_cycle_input, _sha256(receive_cycle_input)),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_lifecycle_report_json", report_json_path, _sha256(report_json_path)),
                _artifact_reference("signal_phase_lifecycle_report_markdown", report_md_path, _sha256(report_md_path)),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_lifecycle_items_csv", lifecycle_items_path, _sha256(lifecycle_items_path)),
                _artifact_reference("signal_phase_follow_up_agenda_csv", follow_up_agenda_path, _sha256(follow_up_agenda_path)),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_lifecycle_report_version": SIGNAL_PHASE_LIFECYCLE_REPORT_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
