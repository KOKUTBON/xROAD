"""Build a unified Bari support runtime board from support action execution and handoff bundles."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_RUNTIME_BOARD_BUNDLE_VERSION = (
    "signal_phase_support_runtime_board_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_RUNTIME_BOARD_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_runtime_board_bundle_public_v1"
)


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


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _board_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Support Runtime Board",
        "",
        f"As of {payload['generated_at_utc']}, the Bari support-side request execution and handoff surfaces have been merged into one final runtime board.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{payload['summary']['request_count']}`",
        f"- operator-ready requests: `{payload['summary']['operator_ready_count']}`",
        f"- internal holds: `{payload['summary']['internal_hold_count']}`",
        f"- workbook rows: `{payload['summary']['workbook_row_count']}`",
        f"- runtime-rerun rows: `{payload['summary']['runtime_rerun_row_count']}`",
        f"- validation-review rows: `{payload['summary']['validation_review_row_count']}`",
        f"- repair rows: `{payload['summary']['repair_row_count']}`",
        f"- apply-pending holds: `{payload['summary']['apply_pending_hold_count']}`",
        f"- complete holds: `{payload['summary']['complete_hold_count']}`",
        "",
        "## Operator Queue",
        "",
    ]
    for row in payload["operator_ready_queue"]:
        lines.append(
            f"- `{row['request_id']}` `{row['execution_route']}` -> `{row['handoff_target_kind']}` "
            f"(target=`{row['handoff_target_path'] or 'n/a'}`)"
        )
    if payload["operator_hold_queue"]:
        lines.extend(["", "## Holds", ""])
        for row in payload["operator_hold_queue"]:
            lines.append(
                f"- `{row['request_id']}` `{row['action_category']}` -> `{row['hold_reason']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_runtime_board_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_runtime_board/bari",
    signal_phase_support_action_execution_bundle_path: str | Path = "data/reporting/signal_phase_support_action_execution/bari/signal_phase_support_action_execution_bundle.json",
    signal_phase_support_action_handoff_bundle_path: str | Path = "data/reporting/signal_phase_support_action_handoff/bari/signal_phase_support_action_handoff_bundle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    action_execution_input = Path(signal_phase_support_action_execution_bundle_path)
    action_handoff_input = Path(signal_phase_support_action_handoff_bundle_path)

    action_execution_bundle = _load_json(action_execution_input)
    action_handoff_bundle = _load_json(action_handoff_input)

    execution_ready_rows = list(action_execution_bundle.get("execution_ready_queue", []) or [])
    execution_hold_rows = list(action_execution_bundle.get("internal_hold_queue", []) or [])
    handoff_ready_rows = list(action_handoff_bundle.get("handoff_ready_queue", []) or [])

    handoff_by_request = {
        str(row.get("request_id") or ""): row
        for row in handoff_ready_rows
        if isinstance(row, dict) and row.get("request_id")
    }

    operator_ready_queue: list[dict[str, Any]] = []
    operator_hold_queue: list[dict[str, Any]] = []

    for row in sorted(
        [item for item in execution_ready_rows if isinstance(item, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("request_id") or "")),
    ):
        request_id = _clean_text(row.get("request_id")) or ""
        handoff_row = handoff_by_request.get(request_id, {})
        operator_ready_queue.append(
            {
                "support_request_reference": _clean_text(row.get("support_request_reference")),
                "request_id": request_id,
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "request_runtime_category": _clean_text(row.get("request_runtime_category")),
                "action_category": _clean_text(row.get("action_category")),
                "execution_route": _clean_text(row.get("execution_route")),
                "due_now": _clean_text(row.get("due_now")) or "no",
                "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
                "execution_target_kind": _clean_text(row.get("execution_target_kind")),
                "execution_target": _clean_text(row.get("execution_target")),
                "execution_summary": _clean_text(row.get("execution_summary")),
                "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
                "packet_md_path": _clean_text(row.get("packet_md_path")),
                "handoff_target_kind": _clean_text(handoff_row.get("handoff_target_kind")),
                "handoff_target_path": _clean_text(handoff_row.get("handoff_target_path")),
                "handoff_status": _clean_text(handoff_row.get("handoff_status")),
                "handoff_command": _clean_text(handoff_row.get("handoff_command")),
                "handoff_instructions": _clean_text(handoff_row.get("handoff_instructions")),
                "handoff_reference_key": _clean_text(handoff_row.get("handoff_reference_key")),
                "handoff_reference_value": _clean_text(handoff_row.get("handoff_reference_value")),
            }
        )

    for row in sorted(
        [item for item in execution_hold_rows if isinstance(item, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("request_id") or "")),
    ):
        operator_hold_queue.append(
            {
                "support_request_reference": _clean_text(row.get("support_request_reference")),
                "request_id": _clean_text(row.get("request_id")),
                "junction_id": _clean_text(row.get("junction_id")),
                "signal_name": _clean_text(row.get("signal_name")),
                "request_runtime_category": _clean_text(row.get("request_runtime_category")),
                "action_category": _clean_text(row.get("action_category")),
                "execution_route": _clean_text(row.get("execution_route")),
                "due_now": _clean_text(row.get("due_now")) or "no",
                "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
                "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
                "packet_md_path": _clean_text(row.get("packet_md_path")),
                "hold_reason": _clean_text(row.get("hold_reason")),
            }
        )

    operator_ready_path = output_root / "operator_ready_queue.csv"
    operator_hold_path = output_root / "operator_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_support_runtime_board_bundle.json"
    bundle_md_path = output_root / "signal_phase_support_runtime_board_bundle.md"
    manifest_path = output_root / "signal_phase_support_runtime_board_bundle.manifest.json"

    ready_fieldnames = [
        "support_request_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "request_runtime_category",
        "action_category",
        "execution_route",
        "due_now",
        "dominant_profile_id",
        "execution_target_kind",
        "execution_target",
        "execution_summary",
        "request_packet_md_path",
        "packet_md_path",
        "handoff_target_kind",
        "handoff_target_path",
        "handoff_status",
        "handoff_command",
        "handoff_instructions",
        "handoff_reference_key",
        "handoff_reference_value",
    ]
    hold_fieldnames = [
        "support_request_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "request_runtime_category",
        "action_category",
        "execution_route",
        "due_now",
        "dominant_profile_id",
        "request_packet_md_path",
        "packet_md_path",
        "hold_reason",
    ]
    _write_csv(operator_ready_path, operator_ready_queue, ready_fieldnames)
    _write_csv(operator_hold_path, operator_hold_queue, hold_fieldnames)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(operator_ready_queue) + len(operator_hold_queue),
        "operator_ready_count": len(operator_ready_queue),
        "internal_hold_count": len(operator_hold_queue),
        "workbook_row_count": sum(
            1
            for row in operator_ready_queue
            if row["handoff_target_kind"] == "support_workbook_csv"
        ),
        "runtime_rerun_row_count": sum(
            1
            for row in operator_ready_queue
            if row["handoff_target_kind"] == "support_runtime_cycle_command"
        ),
        "validation_review_row_count": sum(
            1
            for row in operator_ready_queue
            if row["handoff_target_kind"] == "support_request_packet"
        ),
        "repair_row_count": sum(
            1
            for row in operator_ready_queue
            if row["action_category"] == "repair_support_delivery"
        ),
        "apply_pending_hold_count": sum(
            1
            for row in operator_hold_queue
            if row["action_category"] == "support_apply_pending_refresh"
        ),
        "complete_hold_count": sum(
            1 for row in operator_hold_queue if row["action_category"] == "support_request_complete"
        ),
    }

    payload = {
        "signal_phase_support_runtime_board_bundle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_BOARD_BUNDLE_VERSION,
        "signal_phase_support_runtime_board_bundle_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_BOARD_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "operator_ready_queue": operator_ready_queue,
        "operator_hold_queue": operator_hold_queue,
        "inputs": {
            "signal_phase_support_action_execution_bundle_path": str(action_execution_input),
            "signal_phase_support_action_handoff_bundle_path": str(action_handoff_input),
        },
        "outputs": {
            "operator_ready_queue_path": str(operator_ready_path),
            "operator_hold_queue_path": str(operator_hold_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_board_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_support_runtime_board_bundle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_BOARD_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_support_runtime_board_bundle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_BOARD_BUNDLE_CONTRACT_VERSION,
            "signal_phase_support_runtime_board_bundle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_BOARD_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_support_runtime_board_builder",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "operator_ready_queue_path": str(operator_ready_path),
            "operator_ready_queue_sha256": _sha256(operator_ready_path),
            "operator_hold_queue_path": str(operator_hold_path),
            "operator_hold_queue_sha256": _sha256(operator_hold_path),
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_support_action_execution_bundle_json",
                    action_execution_input,
                    _sha256(action_execution_input),
                ),
                _artifact_reference(
                    "signal_phase_support_action_handoff_bundle_json",
                    action_handoff_input,
                    _sha256(action_handoff_input),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_support_runtime_board_bundle_json",
                    bundle_json_path,
                    _sha256(bundle_json_path),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_board_bundle_markdown",
                    bundle_md_path,
                    _sha256(bundle_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_support_runtime_board_ready_queue",
                    operator_ready_path,
                    _sha256(operator_ready_path),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_board_hold_queue",
                    operator_hold_path,
                    _sha256(operator_hold_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
