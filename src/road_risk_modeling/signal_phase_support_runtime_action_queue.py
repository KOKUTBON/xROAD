"""Build a final Bari support-side request action queue from the support runtime board."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_QUEUE_VERSION = (
    "signal_phase_support_runtime_action_queue_v1"
)
SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_QUEUE_CONTRACT_VERSION = (
    "signal_phase_support_runtime_action_queue_public_v1"
)

_ACTION_PRIORITY = {
    "repair_support_delivery": 1,
    "review_support_validation_results": 2,
    "validate_support_delivery_now": 3,
    "fill_support_workbook_now": 4,
    "support_apply_pending_refresh": 5,
    "support_request_complete": 6,
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


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


def _priority_value(action_category: Any) -> int:
    return _ACTION_PRIORITY.get(_clean_text(action_category) or "", 999999)


def _final_action_category(row: dict[str, Any]) -> str:
    action_category = _clean_text(row.get("action_category")) or ""
    if action_category == "fill_support_workbook_now":
        return "support_fill_workbook_now"
    if action_category == "validate_support_delivery_now":
        return "support_runtime_rerun_now"
    if action_category == "review_support_validation_results":
        return "support_validation_review_now"
    if action_category == "repair_support_delivery":
        return "support_repair_workbook_now"
    if action_category == "support_apply_pending_refresh":
        return "support_apply_pending_refresh"
    if action_category == "support_request_complete":
        return "support_request_complete"
    return "support_internal_hold"


def _action_summary(row: dict[str, Any], final_action_category: str) -> str:
    request_id = _clean_text(row.get("request_id")) or "support_request"
    signal_name = _clean_text(row.get("signal_name")) or "unknown signal"
    dominant_profile_id = _clean_text(row.get("dominant_profile_id")) or "support_profile"
    handoff_target_kind = _clean_text(row.get("handoff_target_kind")) or ""
    handoff_target_path = _clean_text(row.get("handoff_target_path")) or ""
    if final_action_category == "support_fill_workbook_now":
        return (
            f"Complete the live support workbook for `{request_id}` at `{handoff_target_path or 'n/a'}`, "
            f"starting with `{dominant_profile_id}` for `{signal_name}`."
        )
    if final_action_category == "support_runtime_rerun_now":
        return (
            f"Rerun the live support runtime for `{request_id}` using the resolved runtime target "
            f"`{handoff_target_path or 'n/a'}`."
        )
    if final_action_category == "support_validation_review_now":
        return (
            f"Review the validation packet for `{request_id}` at `{handoff_target_path or 'n/a'}` "
            f"before rerun."
        )
    if final_action_category == "support_repair_workbook_now":
        return (
            f"Repair the support workbook for `{request_id}` at `{handoff_target_path or 'n/a'}` "
            f"before another runtime rerun."
        )
    if final_action_category == "support_apply_pending_refresh":
        return (
            f"`{request_id}` is waiting for apply-state refresh after accepted support-derived validation."
        )
    if final_action_category == "support_request_complete":
        return f"`{request_id}` is already fully applied to the movement layer."
    return (
        f"`{request_id}` is in a hold state and does not currently expose a runnable support action "
        f"(target kind `{handoff_target_kind or 'n/a'}`)."
    )


def _queue_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Support Runtime Action Queue",
        "",
        f"As of {payload['generated_at_utc']}, the Bari support runtime board has been condensed into one final request-level action queue.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{payload['summary']['request_count']}`",
        f"- immediate actions: `{payload['summary']['immediate_action_count']}`",
        f"- internal holds: `{payload['summary']['internal_hold_count']}`",
        f"- workbook actions: `{payload['summary']['workbook_action_count']}`",
        f"- runtime-rerun actions: `{payload['summary']['runtime_rerun_action_count']}`",
        f"- validation-review actions: `{payload['summary']['validation_review_action_count']}`",
        f"- repair actions: `{payload['summary']['repair_action_count']}`",
        f"- apply-pending holds: `{payload['summary']['apply_pending_hold_count']}`",
        f"- complete holds: `{payload['summary']['complete_hold_count']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["action_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['final_action_category']}` -> `{row['action_summary']}`"
        )
    if payload["action_hold_queue"]:
        lines.extend(["", "## Holds", ""])
        for row in payload["action_hold_queue"]:
            lines.append(
                f"- `{row['request_id']}` `{row['final_action_category']}` -> `{row['action_summary']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_runtime_action_queue(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_runtime_action_queue/bari",
    signal_phase_support_runtime_board_bundle_path: str | Path = "data/reporting/signal_phase_support_runtime_board/bari/signal_phase_support_runtime_board_bundle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_board_input = Path(signal_phase_support_runtime_board_bundle_path)
    runtime_board_payload = _load_json(runtime_board_input)

    ready_rows = list(runtime_board_payload.get("operator_ready_queue", []) or [])
    hold_rows = list(runtime_board_payload.get("operator_hold_queue", []) or [])

    action_queue: list[dict[str, Any]] = []
    action_hold_queue: list[dict[str, Any]] = []

    for row in sorted(
        [item for item in ready_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(item.get("action_category")),
            str(item.get("request_id") or ""),
        ),
    ):
        final_action_category = _final_action_category(row)
        action_queue.append(
            {
                "support_request_reference": _clean_text(row.get("support_request_reference")),
                "request_id": _clean_text(row.get("request_id")),
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "request_runtime_category": _clean_text(row.get("request_runtime_category")),
                "action_category": _clean_text(row.get("action_category")),
                "final_action_category": final_action_category,
                "due_now": _clean_text(row.get("due_now")) or "yes",
                "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
                "execution_route": _clean_text(row.get("execution_route")),
                "execution_target_kind": _clean_text(row.get("execution_target_kind")),
                "execution_target": _clean_text(row.get("execution_target")),
                "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
                "packet_md_path": _clean_text(row.get("packet_md_path")),
                "handoff_target_kind": _clean_text(row.get("handoff_target_kind")),
                "handoff_target_path": _clean_text(row.get("handoff_target_path")),
                "handoff_status": _clean_text(row.get("handoff_status")),
                "handoff_command": _clean_text(row.get("handoff_command")),
                "handoff_instructions": _clean_text(row.get("handoff_instructions")),
                "action_summary": _action_summary(row, final_action_category),
            }
        )

    for row in sorted(
        [item for item in hold_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(item.get("action_category")),
            str(item.get("request_id") or ""),
        ),
    ):
        final_action_category = _final_action_category(row)
        action_hold_queue.append(
            {
                "support_request_reference": _clean_text(row.get("support_request_reference")),
                "request_id": _clean_text(row.get("request_id")),
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "request_runtime_category": _clean_text(row.get("request_runtime_category")),
                "action_category": _clean_text(row.get("action_category")),
                "final_action_category": final_action_category,
                "due_now": _clean_text(row.get("due_now")) or "no",
                "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
                "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
                "packet_md_path": _clean_text(row.get("packet_md_path")),
                "hold_reason": _clean_text(row.get("hold_reason")),
                "action_summary": _action_summary(row, final_action_category),
            }
        )

    action_queue_path = output_root / "action_queue.csv"
    action_hold_queue_path = output_root / "action_hold_queue.csv"
    report_json_path = output_root / "signal_phase_support_runtime_action_queue.json"
    report_md_path = output_root / "signal_phase_support_runtime_action_queue.md"
    manifest_path = output_root / "signal_phase_support_runtime_action_queue.manifest.json"

    ready_fieldnames = [
        "support_request_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "request_runtime_category",
        "action_category",
        "final_action_category",
        "due_now",
        "dominant_profile_id",
        "execution_route",
        "execution_target_kind",
        "execution_target",
        "request_packet_md_path",
        "packet_md_path",
        "handoff_target_kind",
        "handoff_target_path",
        "handoff_status",
        "handoff_command",
        "handoff_instructions",
        "action_summary",
    ]
    hold_fieldnames = [
        "support_request_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "request_runtime_category",
        "action_category",
        "final_action_category",
        "due_now",
        "dominant_profile_id",
        "request_packet_md_path",
        "packet_md_path",
        "hold_reason",
        "action_summary",
    ]
    _write_csv(action_queue_path, action_queue, ready_fieldnames)
    _write_csv(action_hold_queue_path, action_hold_queue, hold_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(action_queue) + len(action_hold_queue),
        "immediate_action_count": len(action_queue),
        "internal_hold_count": len(action_hold_queue),
        "workbook_action_count": sum(
            1
            for row in action_queue
            if row["final_action_category"] == "support_fill_workbook_now"
        ),
        "runtime_rerun_action_count": sum(
            1
            for row in action_queue
            if row["final_action_category"] == "support_runtime_rerun_now"
        ),
        "validation_review_action_count": sum(
            1
            for row in action_queue
            if row["final_action_category"] == "support_validation_review_now"
        ),
        "repair_action_count": sum(
            1
            for row in action_queue
            if row["final_action_category"] == "support_repair_workbook_now"
        ),
        "apply_pending_hold_count": sum(
            1
            for row in action_hold_queue
            if row["final_action_category"] == "support_apply_pending_refresh"
        ),
        "complete_hold_count": sum(
            1
            for row in action_hold_queue
            if row["final_action_category"] == "support_request_complete"
        ),
    }

    payload = {
        "signal_phase_support_runtime_action_queue_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_QUEUE_VERSION,
        "signal_phase_support_runtime_action_queue_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_QUEUE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "action_queue": action_queue,
        "action_hold_queue": action_hold_queue,
        "inputs": {
            "signal_phase_support_runtime_board_bundle_path": str(runtime_board_input),
        },
        "outputs": {
            "action_queue_path": str(action_queue_path),
            "action_hold_queue_path": str(action_hold_queue_path),
        },
    }
    report_json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    report_md_path.write_text(_queue_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_support_runtime_action_queue_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_QUEUE_VERSION,
        "contract": {
            "resource_name": "signal_phase_support_runtime_action_queue",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_QUEUE_CONTRACT_VERSION,
            "signal_phase_support_runtime_action_queue_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_QUEUE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_support_runtime_action_queue_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "action_queue_path": str(action_queue_path),
            "action_queue_sha256": _sha256(action_queue_path),
            "action_hold_queue_path": str(action_hold_queue_path),
            "action_hold_queue_sha256": _sha256(action_hold_queue_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_support_runtime_board_bundle_json",
                    runtime_board_input,
                    _sha256(runtime_board_input),
                )
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_support_runtime_action_queue_json",
                    report_json_path,
                    _sha256(report_json_path),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_queue_markdown",
                    report_md_path,
                    _sha256(report_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_support_runtime_action_queue_csv",
                    action_queue_path,
                    _sha256(action_queue_path),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_hold_queue_csv",
                    action_hold_queue_path,
                    _sha256(action_hold_queue_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
