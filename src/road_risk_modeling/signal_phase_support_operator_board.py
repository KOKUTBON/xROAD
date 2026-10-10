"""Build a request-level Bari support operator board from support runtime state and profile actions."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_OPERATOR_BOARD_BUNDLE_VERSION = (
    "signal_phase_support_operator_board_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_OPERATOR_BOARD_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_operator_board_bundle_public_v1"
)

DEFAULT_SUPPORT_RUNTIME_COMMAND = (
    "PYTHONPATH=src python3 -m road_risk_modeling run-bari-signal-phase-support-runtime-cycle "
    "--output-dir data/processed/signal_phase_support_runtime_cycles/bari "
    "--signal-phase-support-resolution-bundle-path data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json "
    "--manual-mapping-stub-path data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json "
    "--delivery-checklist-path data/planning/signal_phase_acquisition/bari/delivery_checklist.csv "
    "--movement-objects-path data/processed/movement_objects/bari/road_movement_objects.geojson "
    "--preview-limit 10"
)

_ACTION_PRIORITY = {
    "repair_support_delivery": 1,
    "review_support_validation_results": 2,
    "validate_support_delivery_now": 3,
    "fill_support_workbook_now": 4,
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


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100.0, 2)


def _request_lookup(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        request_id = _clean_text(row.get("request_id"))
        if not request_id:
            continue
        grouped.setdefault(request_id, []).append(row)
    return grouped


def _dominant_profile_row(
    execution_rows: list[dict[str, Any]],
    hold_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_rows = execution_rows if execution_rows else hold_rows
    if not candidate_rows:
        return {}
    return sorted(
        candidate_rows,
        key=lambda row: (
            _ACTION_PRIORITY.get(_clean_text(row.get("action_category")) or "", 999999),
            -_safe_int(row.get("pending_row_count")),
            -_safe_int(row.get("ready_row_count")),
            _clean_text(row.get("profile_id")) or "",
        ),
    )[0]


def _operator_action_category(
    *,
    request_runtime_category: str,
    workbook_fill_count: int,
    validation_count: int,
    review_count: int,
    repair_count: int,
    apply_pending_count: int,
    profile_count: int,
    applied_hold_count: int,
) -> str:
    if request_runtime_category == "fully_applied_to_movement_layer" or (
        profile_count > 0 and applied_hold_count >= profile_count
    ):
        return "support_request_complete"
    if request_runtime_category in {
        "accepted_pending_apply",
        "partially_applied_pending_apply",
        "partially_applied_to_movement_layer",
    }:
        return "support_apply_pending_refresh"
    if request_runtime_category in {
        "validation_review_required",
        "partially_applied_with_review_required",
    }:
        return "review_support_validation_results"
    if request_runtime_category in {
        "ready_for_validation",
        "partially_ready_for_validation",
        "partially_applied_ready_for_validation",
    }:
        return "validate_support_delivery_now"
    if request_runtime_category in {
        "pending_manual_resolution",
        "partially_applied_manual_resolution",
    }:
        return "fill_support_workbook_now"
    if repair_count > 0:
        return "repair_support_delivery"
    if review_count > 0:
        return "review_support_validation_results"
    if validation_count > 0:
        return "validate_support_delivery_now"
    if workbook_fill_count > 0:
        return "fill_support_workbook_now"
    if apply_pending_count > 0:
        return "support_apply_pending_refresh"
    return "support_internal_hold"


def _execution_route(action_category: str) -> str:
    return {
        "fill_support_workbook_now": "analyst_request_workbook_fill",
        "validate_support_delivery_now": "support_runtime_cycle",
        "review_support_validation_results": "analyst_validation_review",
        "repair_support_delivery": "analyst_support_repair",
    }.get(action_category, "")


def _operator_summary(
    *,
    action_category: str,
    request_row: dict[str, Any],
    dominant_row: dict[str, Any],
    workbook_fill_count: int,
    validation_count: int,
    review_count: int,
    repair_count: int,
) -> str:
    request_id = _clean_text(request_row.get("request_id")) or "support_request"
    signal_name = _clean_text(request_row.get("signal_name")) or "unknown signal"
    profile_id = _clean_text(dominant_row.get("profile_id")) or "support_profile"
    if action_category == "fill_support_workbook_now":
        return (
            f"`{request_id}` still needs workbook completion for `{signal_name}` across "
            f"`{workbook_fill_count}` profile(s); start with `{profile_id}`."
        )
    if action_category == "validate_support_delivery_now":
        return (
            f"`{request_id}` has `{validation_count}` support-derived profile(s) ready for validation "
            f"for `{signal_name}`."
        )
    if action_category == "review_support_validation_results":
        return (
            f"`{request_id}` needs review on `{review_count}` validated support-derived profile(s) for `{signal_name}`."
        )
    if action_category == "repair_support_delivery":
        return (
            f"`{request_id}` needs workbook or delivery repair on `{repair_count}` support-derived profile(s) for `{signal_name}`."
        )
    if action_category == "support_apply_pending_refresh":
        return (
            f"`{request_id}` is waiting for apply-state refresh after accepted support validation."
        )
    if action_category == "support_request_complete":
        return f"`{request_id}` is already fully applied to the movement layer."
    return f"No operator-ready support action is available yet for `{request_id}`."


def _operator_hint(
    *,
    action_category: str,
    dominant_row: dict[str, Any],
    runtime_command: str,
) -> str:
    profile_id = _clean_text(dominant_row.get("profile_id")) or "support_profile"
    workbook_path = _clean_text(dominant_row.get("workbook_path")) or ""
    validation_command = _clean_text(dominant_row.get("validation_command")) or ""
    if action_category == "fill_support_workbook_now":
        return (
            f"Fill the request workbook rows, starting with `{profile_id}` at `{workbook_path}`, "
            f"then rerun `{runtime_command}`."
        )
    if action_category == "validate_support_delivery_now":
        if validation_command:
            return (
                f"Either run the request-scoped runtime refresh `{runtime_command}` or use the dominant "
                f"profile validation command `{validation_command}`."
            )
        return f"Run `{runtime_command}` to validate and apply the ready support-derived delivery."
    if action_category == "review_support_validation_results":
        return (
            f"Review the validation output for `{profile_id}`, correct the workbook if needed, then rerun `{runtime_command}`."
        )
    if action_category == "repair_support_delivery":
        return (
            f"Repair the workbook or exported delivery for `{profile_id}`, then rerun `{runtime_command}`."
        )
    if action_category == "support_apply_pending_refresh":
        return "Wait for the apply session to refresh or rerun the support runtime only if the workbooks changed."
    if action_category == "support_request_complete":
        return "No action is required unless new analyst mappings supersede the applied request."
    return "Monitor this request until it becomes operator-ready."


def _packet_markdown(row: dict[str, Any]) -> str:
    lines = [
        f"# {row['request_id']}",
        "",
        f"- signal: `{row['signal_name']}`",
        f"- junction: `{row['junction_id']}`",
        f"- request runtime category: `{row['request_runtime_category']}`",
        f"- operator action: `{row['operator_action_category']}`",
        f"- execution route: `{row['execution_route']}`",
        f"- profile counts: `{row['profile_count']}` total / `{row['applied_profile_count']}` applied",
        f"- ready profiles: `{row['validation_profile_count']}`",
        f"- pending workbook profiles: `{row['workbook_fill_profile_count']}`",
        f"- review profiles: `{row['review_profile_count']}`",
        f"- repair profiles: `{row['repair_profile_count']}`",
        f"- unresolved signalized movements: `{row['unresolved_signalized_movement_count']}` (`{row['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
        f"- unresolved signalized crashes: `{row['unresolved_signalized_crash_total']}` (`{row['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
        "",
        "Key paths:",
        "",
        f"- request packet: `{row['request_packet_md_path']}`",
        f"- dominant profile packet: `{row['dominant_packet_md_path']}`",
        f"- dominant workbook: `{row['dominant_workbook_path']}`",
        f"- dominant delivery csv: `{row['dominant_delivery_csv_path']}`",
        "",
        "Next step:",
        "",
        row["operator_hint"],
        "",
    ]
    if row["runtime_command"]:
        lines.extend(["Runtime command:", "", f"`{row['runtime_command']}`", ""])
    if row["dominant_validation_command"]:
        lines.extend(
            [
                "Dominant validation command:",
                "",
                f"`{row['dominant_validation_command']}`",
                "",
            ]
        )
    return "\n".join(lines)


def _report_markdown(
    summary: dict[str, Any],
    operator_ready_queue: list[dict[str, Any]],
    operator_hold_queue: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Operator Board",
        "",
        "This bundle compresses the Bari support workflow into one request-level operator surface by merging request runtime state with profile-level support actions.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{summary['request_count']}`",
        f"- operator-ready requests: `{summary['operator_ready_count']}`",
        f"- internal holds: `{summary['internal_hold_count']}`",
        f"- workbook-fill requests: `{summary['workbook_fill_request_count']}`",
        f"- validation requests: `{summary['validation_request_count']}`",
        f"- review requests: `{summary['validation_review_request_count']}`",
        f"- repair requests: `{summary['repair_request_count']}`",
        f"- apply-pending requests: `{summary['apply_pending_request_count']}`",
        f"- complete requests: `{summary['complete_request_count']}`",
        f"- requests with unresolved signalized movements: `{summary['requests_with_unresolved_signalized_movements_count']}`",
        f"- unresolved signalized movement rows: `{summary['unresolved_signalized_movement_count_total']}` (`{summary['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
        f"- unresolved signalized crashes: `{summary['unresolved_signalized_crash_total']}` (`{summary['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
        "",
        "## Operator Queue",
        "",
    ]
    if operator_ready_queue:
        for row in operator_ready_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['operator_action_category']}`: "
                f"`{row['unresolved_signalized_movement_count']}` unresolved movements / "
                f"`{row['unresolved_signalized_crash_total']}` unresolved crashes -> `{row['operator_summary']}`"
            )
    else:
        lines.append("- No support requests are operator-ready.")
    if operator_hold_queue:
        lines.extend(["", "## Holds", ""])
        for row in operator_hold_queue[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['operator_action_category']}`: "
                f"`{row['unresolved_signalized_movement_count']}` unresolved movements / "
                f"`{row['unresolved_signalized_crash_total']}` unresolved crashes -> `{row['operator_summary']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_operator_board_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_operator_board/bari",
    signal_phase_support_request_state_bundle_path: str | Path = "data/reporting/signal_phase_support_request_state/bari/signal_phase_support_request_state_bundle.json",
    signal_phase_support_action_queue_path: str | Path = "data/reporting/signal_phase_support_action_queue/bari/signal_phase_support_action_queue.json",
    support_runtime_command: str = DEFAULT_SUPPORT_RUNTIME_COMMAND,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    request_state_input = Path(signal_phase_support_request_state_bundle_path)
    action_queue_input = Path(signal_phase_support_action_queue_path)

    request_state_payload = _load_json(request_state_input)
    action_queue_payload = _load_json(action_queue_input)

    request_rows = request_state_payload.get("request_support_runtime_state", [])
    if not isinstance(request_rows, list):
        raise RuntimeError("Support request-state bundle must expose request_support_runtime_state.")
    execution_ready_rows = action_queue_payload.get("action_execution_ready_queue", [])
    if not isinstance(execution_ready_rows, list):
        raise RuntimeError("Support action queue bundle must expose action_execution_ready_queue.")
    internal_hold_rows = action_queue_payload.get("action_internal_hold_queue", [])
    if not isinstance(internal_hold_rows, list):
        raise RuntimeError("Support action queue bundle must expose action_internal_hold_queue.")

    execution_by_request = _request_lookup(execution_ready_rows)
    holds_by_request = _request_lookup(internal_hold_rows)

    operator_ready_queue: list[dict[str, Any]] = []
    operator_hold_queue: list[dict[str, Any]] = []
    packets_dir = output_root / "request_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)

    for request_row in sorted(
        [row for row in request_rows if isinstance(row, dict)],
        key=lambda row: _clean_text(row.get("request_id")) or "",
    ):
        request_id = _clean_text(request_row.get("request_id")) or ""
        signalized_movement_count = _safe_int(request_row.get("signalized_movement_count"))
        matched_crashes_at_junction_total = _safe_int(
            request_row.get("matched_crashes_at_junction_total")
        )
        unresolved_signalized_movement_count = _safe_int(
            request_row.get("unresolved_signalized_movement_count")
        )
        unresolved_signalized_crash_total = _safe_int(
            request_row.get("unresolved_signalized_crash_total")
        )
        request_execution_rows = execution_by_request.get(request_id, [])
        request_hold_rows = holds_by_request.get(request_id, [])
        dominant_row = _dominant_profile_row(request_execution_rows, request_hold_rows)

        workbook_fill_count = sum(
            1
            for row in request_execution_rows
            if (_clean_text(row.get("action_category")) or "") == "fill_support_workbook_now"
        )
        validation_count = sum(
            1
            for row in request_execution_rows
            if (_clean_text(row.get("action_category")) or "") == "validate_support_delivery_now"
        )
        review_count = sum(
            1
            for row in request_execution_rows
            if (_clean_text(row.get("action_category")) or "")
            == "review_support_validation_results"
        )
        repair_count = sum(
            1
            for row in request_execution_rows
            if (_clean_text(row.get("action_category")) or "") == "repair_support_delivery"
        )
        apply_pending_count = sum(
            1
            for row in request_hold_rows
            if (_clean_text(row.get("action_category")) or "") == "support_apply_pending_refresh"
        )
        applied_hold_count = sum(
            1
            for row in request_hold_rows
            if (_clean_text(row.get("action_category")) or "") == "support_apply_complete"
        )

        operator_action_category = _operator_action_category(
            request_runtime_category=_clean_text(request_row.get("request_runtime_category")) or "",
            workbook_fill_count=workbook_fill_count,
            validation_count=validation_count,
            review_count=review_count,
            repair_count=repair_count,
            apply_pending_count=apply_pending_count,
            profile_count=_safe_int(request_row.get("profile_count")),
            applied_hold_count=applied_hold_count,
        )
        execution_route = _execution_route(operator_action_category)

        row = {
            "support_request_reference": request_id,
            "request_id": request_id,
            "junction_id": _clean_text(request_row.get("junction_id")) or "",
            "signal_name": _clean_text(request_row.get("signal_name")) or "",
            "request_runtime_category": _clean_text(request_row.get("request_runtime_category")) or "",
            "request_runtime_summary": _clean_text(request_row.get("request_runtime_summary")) or "",
            "request_next_action": _clean_text(request_row.get("next_action")) or "",
            "recommended_next_action": _clean_text(request_row.get("recommended_next_action")) or "",
            "profile_count": _safe_int(request_row.get("profile_count")),
            "applied_profile_count": _safe_int(request_row.get("applied_profile_count")),
            "accepted_pending_apply_count": _safe_int(
                request_row.get("accepted_pending_apply_count")
            ),
            "ready_for_validation_count": _safe_int(request_row.get("ready_for_validation_count")),
            "waiting_for_analyst_resolution_count": _safe_int(
                request_row.get("waiting_for_analyst_resolution_count")
            ),
            "signalized_movement_count": signalized_movement_count,
            "matched_crashes_at_junction_total": matched_crashes_at_junction_total,
            "unresolved_signalized_movement_count": unresolved_signalized_movement_count,
            "unresolved_signalized_crash_total": unresolved_signalized_crash_total,
            "unresolved_signalized_movement_share_pct": _safe_pct(
                unresolved_signalized_movement_count,
                signalized_movement_count,
            ),
            "unresolved_signalized_crash_coverage_pct": _safe_pct(
                unresolved_signalized_crash_total,
                matched_crashes_at_junction_total,
            ),
            "workbook_fill_profile_count": workbook_fill_count,
            "validation_profile_count": validation_count,
            "review_profile_count": review_count,
            "repair_profile_count": repair_count,
            "applied_hold_profile_count": applied_hold_count,
            "apply_pending_hold_profile_count": apply_pending_count,
            "operator_action_category": operator_action_category,
            "execution_route": execution_route,
            "due_now": "yes" if execution_route else "no",
            "dominant_profile_id": _clean_text(dominant_row.get("profile_id")) or "",
            "dominant_workbook_path": _clean_text(dominant_row.get("workbook_path")) or "",
            "dominant_delivery_csv_path": _clean_text(dominant_row.get("delivery_csv_path"))
            or "",
            "dominant_validation_command": _clean_text(
                dominant_row.get("validation_command")
            )
            or "",
            "dominant_packet_md_path": _clean_text(dominant_row.get("packet_md_path")) or "",
            "manual_workbook_path": _clean_text(request_row.get("manual_workbook_path")) or "",
            "pedestrian_workbook_path": _clean_text(request_row.get("pedestrian_workbook_path"))
            or "",
            "manual_delivery_path": _clean_text(request_row.get("manual_delivery_path")) or "",
            "pedestrian_delivery_path": _clean_text(request_row.get("pedestrian_delivery_path"))
            or "",
            "request_packet_md_path": _clean_text(request_row.get("packet_md_path")) or "",
            "runtime_command": support_runtime_command,
        }
        row["operator_summary"] = _operator_summary(
            action_category=operator_action_category,
            request_row=request_row,
            dominant_row=dominant_row,
            workbook_fill_count=workbook_fill_count,
            validation_count=validation_count,
            review_count=review_count,
            repair_count=repair_count,
        )
        row["operator_hint"] = _operator_hint(
            action_category=operator_action_category,
            dominant_row=dominant_row,
            runtime_command=support_runtime_command,
        )
        packet_path = packets_dir / f"{request_id}.md"
        packet_path.write_text(_packet_markdown(row), encoding="utf-8")
        row["packet_md_path"] = str(packet_path)

        if execution_route:
            operator_ready_queue.append(row)
        else:
            operator_hold_queue.append(row)

    operator_ready_queue.sort(
        key=lambda row: (
            _ACTION_PRIORITY.get(row["operator_action_category"], 999999),
            row["request_id"],
        )
    )
    operator_hold_queue.sort(
        key=lambda row: (
            _ACTION_PRIORITY.get(row["operator_action_category"], 999999),
            row["request_id"],
        )
    )

    ready_queue_path = output_root / "operator_ready_queue.csv"
    hold_queue_path = output_root / "operator_hold_queue.csv"
    report_json_path = output_root / "signal_phase_support_operator_board_bundle.json"
    report_md_path = output_root / "signal_phase_support_operator_board_bundle.md"
    manifest_path = output_root / "signal_phase_support_operator_board_bundle.manifest.json"

    fieldnames = [
        "support_request_reference",
        "request_id",
        "junction_id",
        "signal_name",
        "request_runtime_category",
        "request_runtime_summary",
        "request_next_action",
        "recommended_next_action",
        "profile_count",
        "applied_profile_count",
        "accepted_pending_apply_count",
        "ready_for_validation_count",
        "waiting_for_analyst_resolution_count",
        "signalized_movement_count",
        "matched_crashes_at_junction_total",
        "unresolved_signalized_movement_count",
        "unresolved_signalized_crash_total",
        "unresolved_signalized_movement_share_pct",
        "unresolved_signalized_crash_coverage_pct",
        "workbook_fill_profile_count",
        "validation_profile_count",
        "review_profile_count",
        "repair_profile_count",
        "applied_hold_profile_count",
        "apply_pending_hold_profile_count",
        "operator_action_category",
        "execution_route",
        "due_now",
        "dominant_profile_id",
        "dominant_workbook_path",
        "dominant_delivery_csv_path",
        "dominant_validation_command",
        "dominant_packet_md_path",
        "manual_workbook_path",
        "pedestrian_workbook_path",
        "manual_delivery_path",
        "pedestrian_delivery_path",
        "request_packet_md_path",
        "runtime_command",
        "operator_summary",
        "operator_hint",
        "packet_md_path",
    ]
    _write_csv(ready_queue_path, operator_ready_queue, fieldnames)
    _write_csv(hold_queue_path, operator_hold_queue, fieldnames)

    operator_rows = operator_ready_queue + operator_hold_queue

    summary = {
        "request_count": len(operator_ready_queue) + len(operator_hold_queue),
        "operator_ready_count": len(operator_ready_queue),
        "internal_hold_count": len(operator_hold_queue),
        "workbook_fill_request_count": sum(
            1
            for row in operator_ready_queue
            if row["operator_action_category"] == "fill_support_workbook_now"
        ),
        "validation_request_count": sum(
            1
            for row in operator_ready_queue
            if row["operator_action_category"] == "validate_support_delivery_now"
        ),
        "validation_review_request_count": sum(
            1
            for row in operator_ready_queue
            if row["operator_action_category"] == "review_support_validation_results"
        ),
        "repair_request_count": sum(
            1
            for row in operator_ready_queue
            if row["operator_action_category"] == "repair_support_delivery"
        ),
        "apply_pending_request_count": sum(
            1
            for row in operator_hold_queue
            if row["operator_action_category"] == "support_apply_pending_refresh"
        ),
        "complete_request_count": sum(
            1
            for row in operator_hold_queue
            if row["operator_action_category"] == "support_request_complete"
        ),
        "requests_with_unresolved_signalized_movements_count": int(
            sum(
                1
                for row in operator_rows
                if int(row["unresolved_signalized_movement_count"]) > 0
            )
        ),
        "unresolved_signalized_movement_count_total": int(
            sum(int(row["unresolved_signalized_movement_count"]) for row in operator_rows)
        ),
        "unresolved_signalized_crash_total": int(
            sum(int(row["unresolved_signalized_crash_total"]) for row in operator_rows)
        ),
        "unresolved_signalized_movement_share_pct": _safe_pct(
            int(
                sum(
                    int(row["unresolved_signalized_movement_count"])
                    for row in operator_rows
                )
            ),
            int(sum(int(row["signalized_movement_count"]) for row in operator_rows)),
        ),
        "unresolved_signalized_crash_coverage_pct": _safe_pct(
            int(sum(int(row["unresolved_signalized_crash_total"]) for row in operator_rows)),
            int(
                sum(
                    int(row["matched_crashes_at_junction_total"])
                    for row in operator_rows
                )
            ),
        ),
    }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_operator_board_bundle_version": SIGNAL_PHASE_SUPPORT_OPERATOR_BOARD_BUNDLE_VERSION,
        "signal_phase_support_operator_board_bundle_contract_version": SIGNAL_PHASE_SUPPORT_OPERATOR_BOARD_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "operator_ready_queue": operator_ready_queue,
        "operator_hold_queue": operator_hold_queue,
        "operator_ready_queue_path": str(ready_queue_path),
        "operator_hold_queue_path": str(hold_queue_path),
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(
        _report_markdown(summary, operator_ready_queue, operator_hold_queue),
        encoding="utf-8",
    )

    manifest = {
        "contract": {
            "resource_name": "signal_phase_support_operator_board_bundle",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_OPERATOR_BOARD_BUNDLE_CONTRACT_VERSION,
        },
        "source": {"adapter": "bari_signal_phase_support_operator_board_builder"},
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "signal_phase_support_request_state_bundle_path": str(request_state_input),
            "signal_phase_support_action_queue_path": str(action_queue_input),
            "support_runtime_command": support_runtime_command,
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "operator_ready_queue_path": str(ready_queue_path),
            "operator_ready_queue_sha256": _sha256(ready_queue_path),
            "operator_hold_queue_path": str(hold_queue_path),
            "operator_hold_queue_sha256": _sha256(hold_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_support_request_state_bundle",
                request_state_input,
                _sha256(request_state_input),
            ),
            _artifact_reference(
                "signal_phase_support_action_queue",
                action_queue_input,
                _sha256(action_queue_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_support_operator_board_report",
                report_json_path,
                _sha256(report_json_path),
            ),
            _artifact_reference(
                "signal_phase_support_operator_board_markdown",
                report_md_path,
                _sha256(report_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_support_operator_ready_queue_csv",
                ready_queue_path,
                _sha256(ready_queue_path),
            ),
            _artifact_reference(
                "signal_phase_support_operator_hold_queue_csv",
                hold_queue_path,
                _sha256(hold_queue_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
