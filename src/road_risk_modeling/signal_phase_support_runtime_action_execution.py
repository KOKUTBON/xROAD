"""Build a final Bari support-side execution bundle from the support runtime action queue."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_EXECUTION_BUNDLE_VERSION = (
    "signal_phase_support_runtime_action_execution_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_runtime_action_execution_bundle_public_v1"
)

_EXECUTION_ROUTE_BY_FINAL_ACTION = {
    "support_fill_workbook_now": "support_workbook_fill",
    "support_runtime_rerun_now": "support_runtime_rerun",
    "support_validation_review_now": "support_validation_review",
    "support_repair_workbook_now": "support_workbook_repair",
}

_ACTION_PRIORITY = {
    "support_repair_workbook_now": 1,
    "support_validation_review_now": 2,
    "support_runtime_rerun_now": 3,
    "support_fill_workbook_now": 4,
    "support_apply_pending_refresh": 5,
    "support_request_complete": 6,
    "support_internal_hold": 7,
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


def _priority_value(final_action_category: str) -> int:
    return _ACTION_PRIORITY.get(final_action_category, 999999)


def _execution_route(final_action_category: str) -> str:
    return _EXECUTION_ROUTE_BY_FINAL_ACTION.get(final_action_category, "")


def _target_fields(row: dict[str, Any], final_action_category: str) -> tuple[str, str]:
    if final_action_category in {
        "support_fill_workbook_now",
        "support_repair_workbook_now",
    }:
        return (
            _clean_text(row.get("handoff_target_kind")) or "support_workbook_csv",
            _clean_text(row.get("handoff_target_path"))
            or _clean_text(row.get("execution_target"))
            or "",
        )
    if final_action_category == "support_runtime_rerun_now":
        return (
            _clean_text(row.get("handoff_target_kind"))
            or _clean_text(row.get("execution_target_kind"))
            or "support_runtime_cycle_command",
            _clean_text(row.get("handoff_target_path"))
            or _clean_text(row.get("execution_target"))
            or "",
        )
    if final_action_category == "support_validation_review_now":
        return (
            _clean_text(row.get("handoff_target_kind"))
            or "support_request_packet",
            _clean_text(row.get("handoff_target_path"))
            or _clean_text(row.get("request_packet_md_path"))
            or _clean_text(row.get("packet_md_path"))
            or "",
        )
    return ("", "")


def _execution_summary(final_action_category: str, row: dict[str, Any]) -> str:
    request_id = _clean_text(row.get("request_id")) or "support_request"
    signal_name = _clean_text(row.get("signal_name")) or "unknown signal"
    dominant_profile_id = _clean_text(row.get("dominant_profile_id")) or "support_profile"
    if final_action_category == "support_fill_workbook_now":
        return (
            f"Complete the live support workbook for `{request_id}` on `{signal_name}`, "
            f"starting with `{dominant_profile_id}`."
        )
    if final_action_category == "support_runtime_rerun_now":
        return (
            f"Rerun the live support runtime for `{request_id}` so completed support-derived rows can validate and apply."
        )
    if final_action_category == "support_validation_review_now":
        return (
            f"Review the validation packet for `{request_id}`, correct any rejected support-derived rows, then rerun the support runtime."
        )
    if final_action_category == "support_repair_workbook_now":
        return (
            f"Repair the live support workbook for `{request_id}`, then rerun the support runtime."
        )
    return _clean_text(row.get("action_summary")) or (
        f"No execution step is required right now for `{request_id}`."
    )


def _hold_reason(final_action_category: str, row: dict[str, Any]) -> str:
    if final_action_category == "support_apply_pending_refresh":
        return (
            "Support-derived rows are waiting for apply-state refresh after accepted validation."
        )
    if final_action_category == "support_request_complete":
        return "The support request is already fully applied to the movement layer."
    return _clean_text(row.get("action_summary")) or (
        "No support runtime execution is required right now."
    )


def _packet_markdown(row: dict[str, Any]) -> str:
    execution_route = _clean_text(row.get("execution_route")) or ""
    execution_target_kind = _clean_text(row.get("execution_target_kind")) or ""
    execution_target = _clean_text(row.get("execution_target")) or ""
    lines = [
        f"# {row['request_id']}",
        "",
        f"- signal: `{row['signal_name']}`",
        f"- junction: `{row['junction_id']}`",
        f"- final action: `{row['final_action_category']}`",
        f"- execution route: `{execution_route}`",
        f"- target kind: `{execution_target_kind}`",
        f"- dominant profile: `{row['dominant_profile_id']}`",
        "",
        "Execution target:",
        "",
        f"`{execution_target}`" if execution_target else "`n/a`",
        "",
        "Next step:",
        "",
        row["execution_summary"] if execution_route else row["hold_reason"],
        "",
    ]
    if row.get("handoff_command"):
        lines.extend(
            [
                "Suggested command:",
                "",
                f"`{row['handoff_command']}`",
                "",
            ]
        )
    return "\n".join(lines)


def _bundle_markdown(
    summary: dict[str, Any],
    execution_ready_queue: list[dict[str, Any]],
    internal_hold_queue: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Runtime Action Execution Bundle",
        "",
        "This bundle converts the final Bari support runtime action queue into an execution-ready queue plus a hold queue.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{summary['request_count']}`",
        f"- execution-ready requests: `{summary['execution_ready_count']}`",
        f"- internal holds: `{summary['internal_hold_count']}`",
        f"- workbook-fill requests: `{summary['workbook_fill_request_count']}`",
        f"- runtime-rerun requests: `{summary['runtime_rerun_request_count']}`",
        f"- validation-review requests: `{summary['validation_review_request_count']}`",
        f"- repair requests: `{summary['repair_request_count']}`",
        f"- apply-pending holds: `{summary['apply_pending_hold_count']}`",
        f"- complete holds: `{summary['complete_hold_count']}`",
        "",
        "## Execution Queue",
        "",
    ]
    if execution_ready_queue:
        for row in execution_ready_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['execution_route']}` -> `{row['execution_summary']}`"
            )
    else:
        lines.append("- No support runtime requests are execution-ready.")
    if internal_hold_queue:
        lines.extend(["", "## Holds", ""])
        for row in internal_hold_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['final_action_category']}` -> `{row['hold_reason']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_runtime_action_execution_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_runtime_action_execution/bari",
    signal_phase_support_runtime_action_queue_path: str | Path = "data/reporting/signal_phase_support_runtime_action_queue/bari/signal_phase_support_runtime_action_queue.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    runtime_action_queue_input = Path(signal_phase_support_runtime_action_queue_path)
    runtime_action_queue_payload = _load_json(runtime_action_queue_input)

    ready_rows = runtime_action_queue_payload.get("action_queue", [])
    if not isinstance(ready_rows, list):
        raise RuntimeError("Support runtime action queue must expose action_queue.")
    hold_rows = runtime_action_queue_payload.get("action_hold_queue", [])
    if not isinstance(hold_rows, list):
        raise RuntimeError(
            "Support runtime action queue must expose action_hold_queue."
        )

    execution_ready_queue: list[dict[str, Any]] = []
    internal_hold_queue: list[dict[str, Any]] = []
    packets_dir = output_root / "execution_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)

    for row in sorted(
        [item for item in ready_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(_clean_text(item.get("final_action_category")) or ""),
            _clean_text(item.get("request_id")) or "",
        ),
    ):
        final_action_category = _clean_text(row.get("final_action_category")) or ""
        execution_route = _execution_route(final_action_category)
        target_kind, target_value = _target_fields(row, final_action_category)
        payload = {
            "support_request_reference": _clean_text(
                row.get("support_request_reference")
            ),
            "request_id": _clean_text(row.get("request_id")),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "request_runtime_category": _clean_text(
                row.get("request_runtime_category")
            ),
            "action_category": _clean_text(row.get("action_category")),
            "final_action_category": final_action_category,
            "due_now": _clean_text(row.get("due_now")) or "no",
            "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
            "execution_route": execution_route,
            "execution_target_kind": target_kind,
            "execution_target": target_value,
            "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
            "packet_md_path": _clean_text(row.get("packet_md_path")),
            "handoff_command": _clean_text(row.get("handoff_command")),
            "handoff_instructions": _clean_text(row.get("handoff_instructions")),
            "action_summary": _clean_text(row.get("action_summary")),
        }
        payload["execution_summary"] = _execution_summary(final_action_category, row)
        packet_path = packets_dir / f"{payload['request_id']}.md"
        packet_path.write_text(_packet_markdown(payload), encoding="utf-8")
        payload["execution_packet_md_path"] = str(packet_path)
        execution_ready_queue.append(payload)

    for row in sorted(
        [item for item in hold_rows if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(_clean_text(item.get("final_action_category")) or ""),
            _clean_text(item.get("request_id")) or "",
        ),
    ):
        final_action_category = _clean_text(row.get("final_action_category")) or ""
        payload = {
            "support_request_reference": _clean_text(
                row.get("support_request_reference")
            ),
            "request_id": _clean_text(row.get("request_id")),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "request_runtime_category": _clean_text(
                row.get("request_runtime_category")
            ),
            "action_category": _clean_text(row.get("action_category")),
            "final_action_category": final_action_category,
            "due_now": _clean_text(row.get("due_now")) or "no",
            "dominant_profile_id": _clean_text(row.get("dominant_profile_id")),
            "request_packet_md_path": _clean_text(row.get("request_packet_md_path")),
            "packet_md_path": _clean_text(row.get("packet_md_path")),
            "action_summary": _clean_text(row.get("action_summary")),
        }
        payload["hold_reason"] = _hold_reason(final_action_category, row)
        packet_path = packets_dir / f"{payload['request_id']}.md"
        packet_path.write_text(_packet_markdown(payload), encoding="utf-8")
        payload["execution_packet_md_path"] = str(packet_path)
        internal_hold_queue.append(payload)

    ready_queue_path = output_root / "action_execution_ready_queue.csv"
    hold_queue_path = output_root / "action_internal_hold_queue.csv"
    bundle_json_path = output_root / "signal_phase_support_runtime_action_execution_bundle.json"
    bundle_md_path = output_root / "signal_phase_support_runtime_action_execution_bundle.md"
    manifest_path = output_root / "signal_phase_support_runtime_action_execution_bundle.manifest.json"

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
        "handoff_command",
        "handoff_instructions",
        "action_summary",
        "execution_summary",
        "execution_packet_md_path",
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
        "action_summary",
        "hold_reason",
        "execution_packet_md_path",
    ]
    _write_csv(ready_queue_path, execution_ready_queue, ready_fieldnames)
    _write_csv(hold_queue_path, internal_hold_queue, hold_fieldnames)

    summary = {
        "request_count": len(execution_ready_queue) + len(internal_hold_queue),
        "execution_ready_count": len(execution_ready_queue),
        "internal_hold_count": len(internal_hold_queue),
        "workbook_fill_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_workbook_fill"
        ),
        "runtime_rerun_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_runtime_rerun"
        ),
        "validation_review_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_validation_review"
        ),
        "repair_request_count": sum(
            1
            for row in execution_ready_queue
            if row["execution_route"] == "support_workbook_repair"
        ),
        "apply_pending_hold_count": sum(
            1
            for row in internal_hold_queue
            if row["final_action_category"] == "support_apply_pending_refresh"
        ),
        "complete_hold_count": sum(
            1
            for row in internal_hold_queue
            if row["final_action_category"] == "support_request_complete"
        ),
    }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_runtime_action_execution_bundle_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_EXECUTION_BUNDLE_VERSION,
        "signal_phase_support_runtime_action_execution_bundle_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "execution_ready_queue": execution_ready_queue,
        "internal_hold_queue": internal_hold_queue,
        "execution_ready_queue_path": str(ready_queue_path),
        "internal_hold_queue_path": str(hold_queue_path),
    }
    bundle_json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    bundle_md_path.write_text(
        _bundle_markdown(summary, execution_ready_queue, internal_hold_queue),
        encoding="utf-8",
    )

    manifest = {
        "contract": {
            "resource_name": "signal_phase_support_runtime_action_execution_bundle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_RUNTIME_ACTION_EXECUTION_BUNDLE_CONTRACT_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_support_runtime_action_execution_builder"
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "signal_phase_support_runtime_action_queue_path": str(
                runtime_action_queue_input
            ),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(bundle_json_path),
            "report_json_sha256": _sha256(bundle_json_path),
            "report_md_path": str(bundle_md_path),
            "report_md_sha256": _sha256(bundle_md_path),
            "execution_ready_queue_path": str(ready_queue_path),
            "execution_ready_queue_sha256": _sha256(ready_queue_path),
            "internal_hold_queue_path": str(hold_queue_path),
            "internal_hold_queue_sha256": _sha256(hold_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_support_runtime_action_queue_json",
                runtime_action_queue_input,
                _sha256(runtime_action_queue_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_support_runtime_action_execution_report",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_support_runtime_action_execution_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_support_runtime_action_execution_ready_queue_csv",
                ready_queue_path,
                _sha256(ready_queue_path),
            ),
            _artifact_reference(
                "signal_phase_support_runtime_action_internal_hold_queue_csv",
                hold_queue_path,
                _sha256(hold_queue_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
