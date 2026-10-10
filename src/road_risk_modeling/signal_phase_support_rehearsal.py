"""Run a Bari support-side rehearsal by injecting synthetic workbook completions."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_support_action_queue import build_bari_signal_phase_support_action_queue
from .signal_phase_support_action_execution import (
    build_bari_signal_phase_support_action_execution_bundle,
)
from .signal_phase_support_action_handoff import (
    build_bari_signal_phase_support_action_handoff_bundle,
)
from .signal_phase_support_apply_cycle import run_bari_signal_phase_support_apply_cycle
from .signal_phase_support_apply_status import (
    build_bari_signal_phase_support_apply_status_bundle,
)
from .signal_phase_support_operator_board import (
    build_bari_signal_phase_support_operator_board_bundle,
)
from .signal_phase_support_request_state import (
    build_bari_signal_phase_support_request_state_bundle,
)
from .signal_phase_support_runtime_action_queue import (
    build_bari_signal_phase_support_runtime_action_queue,
)
from .signal_phase_support_runtime_action_execution import (
    build_bari_signal_phase_support_runtime_action_execution_bundle,
)
from .signal_phase_support_runtime_board import (
    build_bari_signal_phase_support_runtime_board_bundle,
)
from .signal_phase_support_status import build_bari_signal_phase_support_status_bundle
from .signal_phase_support_writeback import build_bari_signal_phase_support_writeback_bundle


SIGNAL_PHASE_SUPPORT_REHEARSAL_VERSION = "signal_phase_support_rehearsal_v1"
SIGNAL_PHASE_SUPPORT_REHEARSAL_CONTRACT_VERSION = (
    "signal_phase_support_rehearsal_public_v1"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


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


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _first_catalog_arm(value: Any) -> str:
    for part in str(value or "").split("|"):
        cleaned = part.strip()
        if not cleaned:
            continue
        return cleaned.split("@", 1)[0].strip()
    return ""


def _manual_row_missing_required_fields(row: dict[str, Any]) -> bool:
    return not all(
        _clean_text(row.get(field))
        for field in ("phase_id", "stage_id", "protection_state")
    )


def _pedestrian_row_missing_required_fields(row: dict[str, Any]) -> bool:
    return not all(
        _clean_text(row.get(field))
        for field in ("phase_id", "stage_id", "protection_state")
    )


def _select_manual_row_index(
    rows: list[dict[str, str]],
    *,
    request_id: str,
) -> int:
    candidate_indexes = [
        index
        for index, row in enumerate(rows)
        if (_clean_text(row.get("request_id")) or "") == request_id
    ]
    if not candidate_indexes:
        raise RuntimeError(f"No manual workbook rows found for request `{request_id}`.")

    def _sort_key(index: int) -> tuple[int, int, int, int]:
        row = rows[index]
        return (
            1 if _manual_row_missing_required_fields(row) else 0,
            _safe_int(row.get("source_crash_total")),
            _safe_int(row.get("source_peak_year_crash_count")),
            -index,
        )

    return max(candidate_indexes, key=_sort_key)


def _select_pedestrian_row_index(
    rows: list[dict[str, str]],
    *,
    request_id: str,
) -> int:
    candidate_indexes = [
        index
        for index, row in enumerate(rows)
        if (_clean_text(row.get("request_id")) or "") == request_id
    ]
    if not candidate_indexes:
        raise RuntimeError(
            f"No pedestrian workbook rows found for request `{request_id}`."
        )

    def _sort_key(index: int) -> tuple[int, int, int, int]:
        row = rows[index]
        return (
            1 if _pedestrian_row_missing_required_fields(row) else 0,
            _safe_int(row.get("source_crash_total")),
            _safe_int(row.get("source_peak_year_crash_count")),
            -index,
        )

    return max(candidate_indexes, key=_sort_key)


def _inject_manual_rehearsal_completion(
    workbook_path: Path,
    *,
    request_id: str,
    phase_id: str,
    stage_id: str,
    protection_state: str,
    notes: str,
) -> dict[str, Any]:
    fieldnames, rows = _read_csv_rows(workbook_path)
    row_index = _select_manual_row_index(rows, request_id=request_id)
    selected = dict(rows[row_index])
    selected["phase_id"] = phase_id
    selected["stage_id"] = stage_id
    selected["protection_state"] = protection_state
    selected["outgoing_arm_id"] = _clean_text(selected.get("outgoing_arm_id")) or _first_catalog_arm(
        selected.get("source_candidate_target_arm_catalog")
    )
    selected["notes"] = notes
    rows[row_index] = selected
    _write_csv(workbook_path, rows, fieldnames)
    return {
        "request_id": request_id,
        "profile_id": "arm_phase_mapping_sheet",
        "signal_name": _clean_text(selected.get("signal_name")) or "",
        "junction_id": _clean_text(selected.get("junction_id")) or "",
        "incoming_arm_id": _clean_text(selected.get("incoming_arm_id")) or "",
        "movement_turn": _clean_text(selected.get("movement_turn")) or "",
        "phase_id": phase_id,
        "stage_id": stage_id,
        "protection_state": protection_state,
        "outgoing_arm_id": _clean_text(selected.get("outgoing_arm_id")) or "",
    }


def _inject_pedestrian_rehearsal_completion(
    workbook_path: Path,
    *,
    request_id: str,
    phase_id: str,
    stage_id: str,
    protection_state: str,
    notes: str,
) -> dict[str, Any]:
    fieldnames, rows = _read_csv_rows(workbook_path)
    row_index = _select_pedestrian_row_index(rows, request_id=request_id)
    selected = dict(rows[row_index])
    selected["phase_id"] = phase_id
    selected["stage_id"] = stage_id
    selected["protection_state"] = protection_state
    selected["pedestrian_stage_flag"] = _clean_text(
        selected.get("pedestrian_stage_flag")
    ) or "true"
    selected["notes"] = notes
    rows[row_index] = selected
    _write_csv(workbook_path, rows, fieldnames)
    return {
        "request_id": request_id,
        "profile_id": "pedestrian_stage_mapping_sheet",
        "signal_name": _clean_text(selected.get("signal_name")) or "",
        "junction_id": _clean_text(selected.get("junction_id")) or "",
        "node_object_id": _clean_text(selected.get("node_object_id")) or "",
        "movement_turn": _clean_text(selected.get("movement_turn")) or "",
        "phase_id": phase_id,
        "stage_id": stage_id,
        "protection_state": protection_state,
    }


def _request_state_map(report_json_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(report_json_path)
    rows = payload.get("request_support_status", [])
    if not isinstance(rows, list):
        raise RuntimeError(
            f"Expected request_support_status list in: {report_json_path}"
        )
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        request_id = _clean_text(row.get("request_id"))
        if request_id:
            output[request_id] = row
    return output


def _profile_state_map(report_json_path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    payload = _load_json(report_json_path)
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for queue_type, rows in (
        ("ready", payload.get("action_execution_ready_queue", []) or []),
        ("hold", payload.get("action_internal_hold_queue", []) or []),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            request_id = _clean_text(row.get("request_id"))
            profile_id = _clean_text(row.get("profile_id"))
            if not request_id or not profile_id:
                continue
            output[(request_id, profile_id)] = {
                **row,
                "queue_type": queue_type,
            }
    return output


def _request_runtime_state_map(report_json_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(report_json_path)
    rows = payload.get("request_support_runtime_state", [])
    if not isinstance(rows, list):
        raise RuntimeError(
            f"Expected request_support_runtime_state list in: {report_json_path}"
        )
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        request_id = _clean_text(row.get("request_id"))
        if request_id:
            output[request_id] = row
    return output


def _operator_board_state_map(report_json_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(report_json_path)
    output: dict[str, dict[str, Any]] = {}
    for queue_type, rows in (
        ("ready", payload.get("operator_ready_queue", []) or []),
        ("hold", payload.get("operator_hold_queue", []) or []),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            request_id = _clean_text(row.get("request_id"))
            if not request_id:
                continue
            output[request_id] = {**row, "queue_type": queue_type}
    return output


def _runtime_board_state_map(report_json_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(report_json_path)
    output: dict[str, dict[str, Any]] = {}
    for queue_type, rows in (
        ("ready", payload.get("operator_ready_queue", []) or []),
        ("hold", payload.get("operator_hold_queue", []) or []),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            request_id = _clean_text(row.get("request_id"))
            if not request_id:
                continue
            output[request_id] = {**row, "queue_type": queue_type}
    return output


def _runtime_action_queue_state_map(
    report_json_path: Path,
) -> dict[str, dict[str, Any]]:
    payload = _load_json(report_json_path)
    output: dict[str, dict[str, Any]] = {}
    for queue_type, rows in (
        ("ready", payload.get("action_queue", []) or []),
        ("hold", payload.get("action_hold_queue", []) or []),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            request_id = _clean_text(row.get("request_id"))
            if not request_id:
                continue
            output[request_id] = {**row, "queue_type": queue_type}
    return output


def _runtime_action_execution_state_map(
    report_json_path: Path,
) -> dict[str, dict[str, Any]]:
    payload = _load_json(report_json_path)
    output: dict[str, dict[str, Any]] = {}
    for queue_type, rows in (
        ("ready", payload.get("execution_ready_queue", []) or []),
        ("hold", payload.get("internal_hold_queue", []) or []),
    ):
        for row in rows:
            if not isinstance(row, dict):
                continue
            request_id = _clean_text(row.get("request_id"))
            if not request_id:
                continue
            output[request_id] = {**row, "queue_type": queue_type}
    return output


def _request_comparison_rows(
    pre_states: dict[str, dict[str, Any]],
    post_states: dict[str, dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id in sorted(set(pre_states) | set(post_states)):
        pre = pre_states.get(request_id, {})
        post = post_states.get(request_id, {})
        row = {
            "request_id": request_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "signal_name": _clean_text(post.get("signal_name"))
            or _clean_text(pre.get("signal_name"))
            or "",
            "pre_request_status_category": _clean_text(
                pre.get("request_status_category")
            )
            or "absent",
            "post_request_status_category": _clean_text(
                post.get("request_status_category")
            )
            or "absent",
            "pre_validation_ready_profile_count": _safe_int(
                pre.get("validation_ready_profile_count")
            ),
            "post_validation_ready_profile_count": _safe_int(
                post.get("validation_ready_profile_count")
            ),
            "pre_manual_ready_count": _safe_int(pre.get("manual_ready_count")),
            "post_manual_ready_count": _safe_int(post.get("manual_ready_count")),
            "pre_manual_pending_count": _safe_int(pre.get("manual_pending_count")),
            "post_manual_pending_count": _safe_int(post.get("manual_pending_count")),
            "pre_pedestrian_ready_count": _safe_int(
                pre.get("pedestrian_ready_count")
            ),
            "post_pedestrian_ready_count": _safe_int(
                post.get("pedestrian_ready_count")
            ),
            "pre_pedestrian_pending_count": _safe_int(
                pre.get("pedestrian_pending_count")
            ),
            "post_pedestrian_pending_count": _safe_int(
                post.get("pedestrian_pending_count")
            ),
            "pre_next_action": _clean_text(pre.get("next_action")) or "",
            "post_next_action": _clean_text(post.get("next_action")) or "",
        }
        row["state_changed"] = (
            "yes"
            if any(
                row[field] != row[f"post_{field[4:]}"]
                for field in (
                    "pre_request_status_category",
                    "pre_validation_ready_profile_count",
                    "pre_manual_ready_count",
                    "pre_manual_pending_count",
                    "pre_pedestrian_ready_count",
                    "pre_pedestrian_pending_count",
                    "pre_next_action",
                )
            )
            else "no"
        )
        rows.append(row)
    return rows


def _profile_comparison_rows(
    pre_states: dict[tuple[str, str], dict[str, Any]],
    post_states: dict[tuple[str, str], dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id, profile_id in sorted(set(pre_states) | set(post_states)):
        pre = pre_states.get((request_id, profile_id), {})
        post = post_states.get((request_id, profile_id), {})
        row = {
            "request_id": request_id,
            "profile_id": profile_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "pre_validation_state_category": _clean_text(
                pre.get("validation_state_category")
            )
            or "absent",
            "post_validation_state_category": _clean_text(
                post.get("validation_state_category")
            )
            or "absent",
            "pre_action_category": _clean_text(pre.get("action_category")) or "absent",
            "post_action_category": _clean_text(post.get("action_category"))
            or "absent",
            "pre_ready_row_count": _safe_int(pre.get("ready_row_count")),
            "post_ready_row_count": _safe_int(post.get("ready_row_count")),
            "pre_pending_row_count": _safe_int(pre.get("pending_row_count")),
            "post_pending_row_count": _safe_int(post.get("pending_row_count")),
            "pre_execution_route": _clean_text(pre.get("execution_route")) or "",
            "post_execution_route": _clean_text(post.get("execution_route")) or "",
            "pre_queue_type": _clean_text(pre.get("queue_type")) or "absent",
            "post_queue_type": _clean_text(post.get("queue_type")) or "absent",
        }
        row["state_changed"] = (
            "yes"
            if any(
                row[field] != row[f"post_{field[4:]}"]
                for field in (
                    "pre_validation_state_category",
                    "pre_action_category",
                    "pre_ready_row_count",
                    "pre_pending_row_count",
                    "pre_execution_route",
                    "pre_queue_type",
                )
            )
            else "no"
        )
        rows.append(row)
    return rows


def _request_runtime_comparison_rows(
    pre_states: dict[str, dict[str, Any]],
    post_states: dict[str, dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id in sorted(set(pre_states) | set(post_states)):
        pre = pre_states.get(request_id, {})
        post = post_states.get(request_id, {})
        row = {
            "request_id": request_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "signal_name": _clean_text(post.get("signal_name"))
            or _clean_text(pre.get("signal_name"))
            or "",
            "pre_request_runtime_category": _clean_text(
                pre.get("request_runtime_category")
            )
            or "absent",
            "post_request_runtime_category": _clean_text(
                post.get("request_runtime_category")
            )
            or "absent",
            "pre_applied_profile_count": _safe_int(pre.get("applied_profile_count")),
            "post_applied_profile_count": _safe_int(post.get("applied_profile_count")),
            "pre_ready_for_validation_count": _safe_int(
                pre.get("ready_for_validation_count")
            ),
            "post_ready_for_validation_count": _safe_int(
                post.get("ready_for_validation_count")
            ),
            "pre_waiting_for_analyst_resolution_count": _safe_int(
                pre.get("waiting_for_analyst_resolution_count")
            ),
            "post_waiting_for_analyst_resolution_count": _safe_int(
                post.get("waiting_for_analyst_resolution_count")
            ),
            "pre_request_runtime_summary": _clean_text(
                pre.get("request_runtime_summary")
            )
            or "",
            "post_request_runtime_summary": _clean_text(
                post.get("request_runtime_summary")
            )
            or "",
            "pre_next_action": _clean_text(pre.get("next_action")) or "",
            "post_next_action": _clean_text(post.get("next_action")) or "",
        }
        row["state_changed"] = (
            "yes"
            if any(
                row[field] != row[f"post_{field[4:]}"]
                for field in (
                    "pre_request_runtime_category",
                    "pre_applied_profile_count",
                    "pre_ready_for_validation_count",
                    "pre_waiting_for_analyst_resolution_count",
                    "pre_request_runtime_summary",
                    "pre_next_action",
                )
            )
            else "no"
        )
        rows.append(row)
    return rows


def _operator_board_comparison_rows(
    pre_states: dict[str, dict[str, Any]],
    post_states: dict[str, dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id in sorted(set(pre_states) | set(post_states)):
        pre = pre_states.get(request_id, {})
        post = post_states.get(request_id, {})
        row = {
            "request_id": request_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "signal_name": _clean_text(post.get("signal_name"))
            or _clean_text(pre.get("signal_name"))
            or "",
            "pre_operator_action_category": _clean_text(
                pre.get("operator_action_category")
            )
            or "absent",
            "post_operator_action_category": _clean_text(
                post.get("operator_action_category")
            )
            or "absent",
            "pre_execution_route": _clean_text(pre.get("execution_route")) or "",
            "post_execution_route": _clean_text(post.get("execution_route")) or "",
            "pre_queue_type": _clean_text(pre.get("queue_type")) or "absent",
            "post_queue_type": _clean_text(post.get("queue_type")) or "absent",
            "pre_operator_summary": _clean_text(pre.get("operator_summary")) or "",
            "post_operator_summary": _clean_text(post.get("operator_summary")) or "",
            "pre_dominant_profile_id": _clean_text(pre.get("dominant_profile_id")) or "",
            "post_dominant_profile_id": _clean_text(post.get("dominant_profile_id")) or "",
        }
        row["state_changed"] = (
            "yes"
            if any(
                row[field] != row[f"post_{field[4:]}"]
                for field in (
                    "pre_operator_action_category",
                    "pre_execution_route",
                    "pre_queue_type",
                    "pre_operator_summary",
                    "pre_dominant_profile_id",
                )
            )
            else "no"
        )
        rows.append(row)
    return rows


def _runtime_board_comparison_rows(
    pre_states: dict[str, dict[str, Any]],
    post_states: dict[str, dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id in sorted(set(pre_states) | set(post_states)):
        pre = pre_states.get(request_id, {})
        post = post_states.get(request_id, {})
        row = {
            "request_id": request_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "signal_name": _clean_text(post.get("signal_name"))
            or _clean_text(pre.get("signal_name"))
            or "",
            "pre_action_category": _clean_text(pre.get("action_category")) or "absent",
            "post_action_category": _clean_text(post.get("action_category")) or "absent",
            "pre_execution_route": _clean_text(pre.get("execution_route")) or "",
            "post_execution_route": _clean_text(post.get("execution_route")) or "",
            "pre_handoff_target_kind": _clean_text(pre.get("handoff_target_kind"))
            or "",
            "post_handoff_target_kind": _clean_text(post.get("handoff_target_kind"))
            or "",
            "pre_handoff_target_path": _clean_text(pre.get("handoff_target_path"))
            or "",
            "post_handoff_target_path": _clean_text(post.get("handoff_target_path"))
            or "",
            "pre_queue_type": _clean_text(pre.get("queue_type")) or "absent",
            "post_queue_type": _clean_text(post.get("queue_type")) or "absent",
            "pre_request_runtime_category": _clean_text(
                pre.get("request_runtime_category")
            )
            or "absent",
            "post_request_runtime_category": _clean_text(
                post.get("request_runtime_category")
            )
            or "absent",
        }
        row["state_changed"] = (
            "yes"
            if any(
                row[field] != row[f"post_{field[4:]}"]
                for field in (
                    "pre_action_category",
                    "pre_execution_route",
                    "pre_handoff_target_kind",
                    "pre_handoff_target_path",
                    "pre_queue_type",
                    "pre_request_runtime_category",
                )
            )
            else "no"
        )
        rows.append(row)
    return rows


def _runtime_action_queue_comparison_rows(
    pre_states: dict[str, dict[str, Any]],
    post_states: dict[str, dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id in sorted(set(pre_states) | set(post_states)):
        pre = pre_states.get(request_id, {})
        post = post_states.get(request_id, {})
        row = {
            "request_id": request_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "signal_name": _clean_text(post.get("signal_name"))
            or _clean_text(pre.get("signal_name"))
            or "",
            "pre_final_action_category": _clean_text(pre.get("final_action_category"))
            or "absent",
            "post_final_action_category": _clean_text(
                post.get("final_action_category")
            )
            or "absent",
            "pre_action_category": _clean_text(pre.get("action_category")) or "absent",
            "post_action_category": _clean_text(post.get("action_category")) or "absent",
            "pre_queue_type": _clean_text(pre.get("queue_type")) or "absent",
            "post_queue_type": _clean_text(post.get("queue_type")) or "absent",
            "pre_request_runtime_category": _clean_text(
                pre.get("request_runtime_category")
            )
            or "absent",
            "post_request_runtime_category": _clean_text(
                post.get("request_runtime_category")
            )
            or "absent",
            "pre_action_summary": _clean_text(pre.get("action_summary")) or "",
            "post_action_summary": _clean_text(post.get("action_summary")) or "",
        }
        row["state_changed"] = (
            "yes"
            if any(
                row[field] != row[f"post_{field[4:]}"]
                for field in (
                    "pre_final_action_category",
                    "pre_action_category",
                    "pre_queue_type",
                    "pre_request_runtime_category",
                    "pre_action_summary",
                )
            )
            else "no"
        )
        rows.append(row)
    return rows


def _runtime_action_execution_comparison_rows(
    pre_states: dict[str, dict[str, Any]],
    post_states: dict[str, dict[str, Any]],
    *,
    selected_request_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id in sorted(set(pre_states) | set(post_states)):
        pre = pre_states.get(request_id, {})
        post = post_states.get(request_id, {})
        row = {
            "request_id": request_id,
            "selected_request": "yes" if request_id == selected_request_id else "no",
            "signal_name": _clean_text(post.get("signal_name"))
            or _clean_text(pre.get("signal_name"))
            or "",
            "pre_final_action_category": _clean_text(pre.get("final_action_category"))
            or "absent",
            "post_final_action_category": _clean_text(
                post.get("final_action_category")
            )
            or "absent",
            "pre_execution_route": _clean_text(pre.get("execution_route")) or "",
            "post_execution_route": _clean_text(post.get("execution_route")) or "",
            "pre_execution_target_kind": _clean_text(
                pre.get("execution_target_kind")
            )
            or "",
            "post_execution_target_kind": _clean_text(
                post.get("execution_target_kind")
            )
            or "",
            "pre_execution_target": _clean_text(pre.get("execution_target")) or "",
            "post_execution_target": _clean_text(post.get("execution_target")) or "",
            "pre_queue_type": _clean_text(pre.get("queue_type")) or "absent",
            "post_queue_type": _clean_text(post.get("queue_type")) or "absent",
            "pre_request_runtime_category": _clean_text(
                pre.get("request_runtime_category")
            )
            or "absent",
            "post_request_runtime_category": _clean_text(
                post.get("request_runtime_category")
            )
            or "absent",
            "pre_execution_summary": _clean_text(pre.get("execution_summary"))
            or _clean_text(pre.get("hold_reason"))
            or "",
            "post_execution_summary": _clean_text(post.get("execution_summary"))
            or _clean_text(post.get("hold_reason"))
            or "",
        }
        row["state_changed"] = (
            "yes"
            if any(
                row[field] != row[f"post_{field[4:]}"]
                for field in (
                    "pre_final_action_category",
                    "pre_execution_route",
                    "pre_execution_target_kind",
                    "pre_execution_target",
                    "pre_queue_type",
                    "pre_request_runtime_category",
                    "pre_execution_summary",
                )
            )
            else "no"
        )
        rows.append(row)
    return rows


def _rehearsal_markdown(payload: dict[str, Any]) -> str:
    selected_request = payload["selected_request_transition"]
    lines = [
        "# Bari Signal-Phase Support Rehearsal",
        "",
        f"As of {payload['generated_at_utc']}, the Bari support-derived signal-phase path has been rehearsed by injecting one synthetic arm-phase row and one synthetic pedestrian-stage row for `{payload['selected_request_id']}` into copied workbooks.",
        "",
        "## Summary",
        "",
        f"- requests compared: `{payload['summary']['request_count']}`",
        f"- changed requests: `{payload['summary']['changed_request_count']}`",
        f"- profiles compared: `{payload['summary']['profile_count']}`",
        f"- changed profiles: `{payload['summary']['changed_profile_count']}`",
        f"- selected request changed: `{payload['summary']['selected_request_changed']}`",
        f"- selected request left manual-resolution state: `{payload['summary']['selected_request_left_manual_resolution']}`",
        f"- pre validation actions: `{payload['summary']['pre_validation_action_count']}`",
        f"- post validation actions: `{payload['summary']['post_validation_action_count']}`",
        f"- pre operator-ready requests: `{payload['summary']['pre_operator_ready_count']}`",
        f"- post operator-ready requests: `{payload['summary']['post_operator_ready_count']}`",
        f"- pre runtime-board ready requests: `{payload['summary']['pre_runtime_board_ready_count']}`",
        f"- post runtime-board ready requests: `{payload['summary']['post_runtime_board_ready_count']}`",
        f"- pre runtime-action ready requests: `{payload['summary']['pre_runtime_action_ready_count']}`",
        f"- post runtime-action ready requests: `{payload['summary']['post_runtime_action_ready_count']}`",
        f"- pre runtime-execution ready requests: `{payload['summary']['pre_runtime_execution_ready_count']}`",
        f"- post runtime-execution ready requests: `{payload['summary']['post_runtime_execution_ready_count']}`",
        f"- post executed validations: `{payload['summary']['post_executed_validation_count']}`",
        f"- post accepted validations: `{payload['summary']['post_accepted_for_ingestion_count']}`",
        f"- post delivery session executed: `{payload['summary']['post_delivery_session_executed']}`",
        f"- post movements with phase timing: `{payload['summary']['post_movements_with_phase_timing']}`",
        f"- post movements with phase mapping: `{payload['summary']['post_movements_with_phase_mapping']}`",
        "",
        "## Selected Request",
        "",
        f"- request: `{payload['selected_request_id']}`",
        f"- signal: `{selected_request['signal_name']}`",
        f"- pre status: `{selected_request['pre_request_status_category']}`",
        f"- post status: `{selected_request['post_request_status_category']}`",
        f"- pre validation-ready profiles: `{selected_request['pre_validation_ready_profile_count']}`",
        f"- post validation-ready profiles: `{selected_request['post_validation_ready_profile_count']}`",
        f"- pre runtime category: `{payload['selected_request_runtime_transition']['pre_request_runtime_category']}`",
        f"- post runtime category: `{payload['selected_request_runtime_transition']['post_request_runtime_category']}`",
        f"- pre operator action: `{payload['selected_request_operator_transition']['pre_operator_action_category']}`",
        f"- post operator action: `{payload['selected_request_operator_transition']['post_operator_action_category']}`",
        f"- pre runtime-board action: `{payload['selected_request_runtime_board_transition']['pre_action_category']}`",
        f"- post runtime-board action: `{payload['selected_request_runtime_board_transition']['post_action_category']}`",
        f"- pre final runtime action: `{payload['selected_request_runtime_action_transition']['pre_final_action_category']}`",
        f"- post final runtime action: `{payload['selected_request_runtime_action_transition']['post_final_action_category']}`",
        f"- pre runtime-execution action: `{payload['selected_request_runtime_execution_transition']['pre_final_action_category']}`",
        f"- post runtime-execution action: `{payload['selected_request_runtime_execution_transition']['post_final_action_category']}`",
        "",
        "## Injected Rows",
        "",
        f"- manual: `{payload['injected_rows']['manual']['incoming_arm_id']}` `{payload['injected_rows']['manual']['movement_turn']}` -> `{payload['injected_rows']['manual']['phase_id']}` / `{payload['injected_rows']['manual']['stage_id']}`",
        f"- pedestrian: `{payload['injected_rows']['pedestrian']['node_object_id']}` -> `{payload['injected_rows']['pedestrian']['phase_id']}` / `{payload['injected_rows']['pedestrian']['stage_id']}`",
        "",
        "## Outputs",
        "",
        f"- rehearsal writeback manifest: `{payload['outputs']['rehearsal_writeback_manifest_path']}`",
        f"- request comparison: `{payload['outputs']['request_state_comparison_path']}`",
        f"- request runtime comparison: `{payload['outputs']['request_runtime_comparison_path']}`",
        f"- profile comparison: `{payload['outputs']['profile_state_comparison_path']}`",
        f"- operator board comparison: `{payload['outputs']['operator_board_comparison_path']}`",
        f"- runtime board comparison: `{payload['outputs']['runtime_board_comparison_path']}`",
        f"- runtime action queue comparison: `{payload['outputs']['runtime_action_queue_comparison_path']}`",
        f"- runtime action execution comparison: `{payload['outputs']['runtime_action_execution_comparison_path']}`",
        f"- post apply-cycle manifest: `{payload['outputs']['post_support_apply_cycle_manifest_path']}`",
        f"- post operator board manifest: `{payload['outputs']['post_support_operator_board_manifest_path']}`",
        f"- post runtime board manifest: `{payload['outputs']['post_support_runtime_board_manifest_path']}`",
        f"- post runtime action queue manifest: `{payload['outputs']['post_support_runtime_action_queue_manifest_path']}`",
        f"- post runtime action execution manifest: `{payload['outputs']['post_support_runtime_action_execution_manifest_path']}`",
        "",
    ]
    return "\n".join(lines)


def run_bari_signal_phase_support_rehearsal(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_rehearsal/bari",
    request_id: str = "bari_signal_phase_01",
    signal_phase_support_writeback_bundle_path: str | Path = "data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.json",
    signal_phase_support_resolution_bundle_path: str | Path = "data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json",
    manual_mapping_stub_path: str | Path = "data/planning/signal_phase_intake/bari/mapping_stubs/arm_phase_mapping_sheet_mapping_stub.json",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    manual_phase_id: str = "phase_a",
    manual_stage_id: str = "stage_1",
    manual_protection_state: str = "protected",
    pedestrian_phase_id: str = "ped_phase_a",
    pedestrian_stage_id: str = "stage_p1",
    pedestrian_protection_state: str = "protected",
    preview_limit: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    support_writeback_bundle_input = Path(signal_phase_support_writeback_bundle_path)
    support_resolution_bundle_input = Path(signal_phase_support_resolution_bundle_path)
    manual_mapping_stub_input = Path(manual_mapping_stub_path)
    delivery_checklist_input = Path(delivery_checklist_path)
    movement_objects_input = Path(movement_objects_path)

    live_writeback_bundle = _load_json(support_writeback_bundle_input)
    source_manual_workbook_path = Path(
        str(live_writeback_bundle.get("manual_mapping_workbook_path") or "")
    )
    source_pedestrian_workbook_path = Path(
        str(live_writeback_bundle.get("pedestrian_mapping_workbook_path") or "")
    )
    if not source_manual_workbook_path.exists() or not source_pedestrian_workbook_path.exists():
        raise RuntimeError(
            "Support-writeback bundle must reference existing manual and pedestrian workbook paths."
        )

    pre_status_output_dir = output_root / "pre_support_status"
    pre_action_output_dir = output_root / "pre_support_action_queue"
    pre_apply_output_dir = output_root / "pre_support_apply_cycle"
    pre_apply_status_output_dir = output_root / "pre_support_apply_status"
    pre_request_state_output_dir = output_root / "pre_support_request_state"
    pre_operator_board_output_dir = output_root / "pre_support_operator_board"
    pre_action_execution_output_dir = output_root / "pre_support_action_execution"
    pre_action_handoff_output_dir = output_root / "pre_support_action_handoff"
    pre_runtime_board_output_dir = output_root / "pre_support_runtime_board"
    pre_runtime_action_queue_output_dir = output_root / "pre_support_runtime_action_queue"
    pre_runtime_action_execution_output_dir = (
        output_root / "pre_support_runtime_action_execution"
    )
    support_runtime_cycle_reference_path = (
        output_root / "signal_phase_support_runtime_cycle.rehearsal_reference.manifest.json"
    )

    pre_status_manifest = build_bari_signal_phase_support_status_bundle(
        output_dir=pre_status_output_dir,
        signal_phase_support_writeback_bundle_path=support_writeback_bundle_input,
    )
    pre_status_json_path = Path(pre_status_manifest["outputs"]["report_json_path"])
    pre_action_manifest = build_bari_signal_phase_support_action_queue(
        output_dir=pre_action_output_dir,
        signal_phase_support_status_bundle_path=pre_status_json_path,
    )
    pre_action_json_path = Path(pre_action_manifest["outputs"]["report_json_path"])
    pre_action_queue_path = Path(
        pre_action_manifest["outputs"]["action_execution_ready_queue_path"]
    )
    pre_apply_result = run_bari_signal_phase_support_apply_cycle(
        output_dir=pre_apply_output_dir,
        action_execution_ready_queue_path=pre_action_queue_path,
        delivery_checklist_path=delivery_checklist_input,
        movement_objects_path=movement_objects_input,
        preview_limit=preview_limit,
    )
    pre_apply_cycle_json_path = Path(pre_apply_result["manifest_path"]).with_suffix("").with_suffix(".json")
    pre_apply_status_manifest = build_bari_signal_phase_support_apply_status_bundle(
        output_dir=pre_apply_status_output_dir,
        signal_phase_support_status_bundle_path=pre_status_json_path,
        signal_phase_support_apply_cycle_path=pre_apply_cycle_json_path,
    )
    pre_apply_status_json_path = Path(pre_apply_status_manifest["outputs"]["report_json_path"])
    pre_request_state_manifest = build_bari_signal_phase_support_request_state_bundle(
        output_dir=pre_request_state_output_dir,
        signal_phase_support_status_bundle_path=pre_status_json_path,
        signal_phase_support_apply_status_bundle_path=pre_apply_status_json_path,
    )
    pre_request_state_json_path = Path(pre_request_state_manifest["outputs"]["report_json_path"])
    pre_operator_board_manifest = build_bari_signal_phase_support_operator_board_bundle(
        output_dir=pre_operator_board_output_dir,
        signal_phase_support_request_state_bundle_path=pre_request_state_json_path,
        signal_phase_support_action_queue_path=pre_action_json_path,
    )
    pre_operator_board_json_path = Path(pre_operator_board_manifest["outputs"]["report_json_path"])
    pre_action_execution_manifest = (
        build_bari_signal_phase_support_action_execution_bundle(
            output_dir=pre_action_execution_output_dir,
            signal_phase_support_operator_board_bundle_path=pre_operator_board_json_path,
        )
    )
    pre_action_execution_json_path = Path(
        pre_action_execution_manifest["outputs"]["report_json_path"]
    )
    pre_action_handoff_manifest = build_bari_signal_phase_support_action_handoff_bundle(
        output_dir=pre_action_handoff_output_dir,
        signal_phase_support_action_execution_bundle_path=pre_action_execution_json_path,
        support_runtime_cycle_manifest_path=support_runtime_cycle_reference_path,
    )
    pre_action_handoff_json_path = Path(
        pre_action_handoff_manifest["outputs"]["bundle_json_path"]
    )
    pre_runtime_board_manifest = build_bari_signal_phase_support_runtime_board_bundle(
        output_dir=pre_runtime_board_output_dir,
        signal_phase_support_action_execution_bundle_path=pre_action_execution_json_path,
        signal_phase_support_action_handoff_bundle_path=pre_action_handoff_json_path,
    )
    pre_runtime_board_json_path = Path(
        pre_runtime_board_manifest["outputs"]["bundle_json_path"]
    )
    pre_runtime_action_queue_manifest = (
        build_bari_signal_phase_support_runtime_action_queue(
            output_dir=pre_runtime_action_queue_output_dir,
            signal_phase_support_runtime_board_bundle_path=pre_runtime_board_json_path,
        )
    )
    pre_runtime_action_queue_json_path = Path(
        pre_runtime_action_queue_manifest["outputs"]["report_json_path"]
    )
    pre_runtime_action_execution_manifest = (
        build_bari_signal_phase_support_runtime_action_execution_bundle(
            output_dir=pre_runtime_action_execution_output_dir,
            signal_phase_support_runtime_action_queue_path=pre_runtime_action_queue_json_path,
        )
    )
    pre_runtime_action_execution_json_path = Path(
        pre_runtime_action_execution_manifest["outputs"]["report_json_path"]
    )

    rehearsal_writeback_output_dir = output_root / "rehearsal_writeback"
    rehearsal_workbooks_dir = rehearsal_writeback_output_dir / "workbooks"
    rehearsal_manual_workbook_path = rehearsal_workbooks_dir / source_manual_workbook_path.name
    rehearsal_pedestrian_workbook_path = (
        rehearsal_workbooks_dir / source_pedestrian_workbook_path.name
    )
    _copy_file(source_manual_workbook_path, rehearsal_manual_workbook_path)
    _copy_file(source_pedestrian_workbook_path, rehearsal_pedestrian_workbook_path)

    injected_manual = _inject_manual_rehearsal_completion(
        rehearsal_manual_workbook_path,
        request_id=request_id,
        phase_id=manual_phase_id,
        stage_id=manual_stage_id,
        protection_state=manual_protection_state,
        notes="support rehearsal synthetic arm-phase mapping",
    )
    injected_pedestrian = _inject_pedestrian_rehearsal_completion(
        rehearsal_pedestrian_workbook_path,
        request_id=request_id,
        phase_id=pedestrian_phase_id,
        stage_id=pedestrian_stage_id,
        protection_state=pedestrian_protection_state,
        notes="support rehearsal synthetic pedestrian-stage mapping",
    )

    post_writeback_manifest = build_bari_signal_phase_support_writeback_bundle(
        output_dir=rehearsal_writeback_output_dir,
        signal_phase_support_resolution_bundle_path=support_resolution_bundle_input,
        manual_mapping_stub_path=manual_mapping_stub_input,
    )
    post_writeback_json_path = Path(post_writeback_manifest["outputs"]["report_json_path"])

    post_status_output_dir = output_root / "post_support_status"
    post_action_output_dir = output_root / "post_support_action_queue"
    post_apply_output_dir = output_root / "post_support_apply_cycle"
    post_apply_status_output_dir = output_root / "post_support_apply_status"
    post_request_state_output_dir = output_root / "post_support_request_state"
    post_operator_board_output_dir = output_root / "post_support_operator_board"
    post_action_execution_output_dir = output_root / "post_support_action_execution"
    post_action_handoff_output_dir = output_root / "post_support_action_handoff"
    post_runtime_board_output_dir = output_root / "post_support_runtime_board"
    post_runtime_action_queue_output_dir = output_root / "post_support_runtime_action_queue"
    post_runtime_action_execution_output_dir = (
        output_root / "post_support_runtime_action_execution"
    )

    post_status_manifest = build_bari_signal_phase_support_status_bundle(
        output_dir=post_status_output_dir,
        signal_phase_support_writeback_bundle_path=post_writeback_json_path,
    )
    post_status_json_path = Path(post_status_manifest["outputs"]["report_json_path"])
    post_action_manifest = build_bari_signal_phase_support_action_queue(
        output_dir=post_action_output_dir,
        signal_phase_support_status_bundle_path=post_status_json_path,
    )
    post_action_json_path = Path(post_action_manifest["outputs"]["report_json_path"])
    post_action_queue_path = Path(
        post_action_manifest["outputs"]["action_execution_ready_queue_path"]
    )
    post_apply_result = run_bari_signal_phase_support_apply_cycle(
        output_dir=post_apply_output_dir,
        action_execution_ready_queue_path=post_action_queue_path,
        delivery_checklist_path=delivery_checklist_input,
        movement_objects_path=movement_objects_input,
        preview_limit=preview_limit,
    )
    post_apply_cycle_json_path = Path(post_apply_result["manifest_path"]).with_suffix("").with_suffix(".json")
    post_apply_status_manifest = build_bari_signal_phase_support_apply_status_bundle(
        output_dir=post_apply_status_output_dir,
        signal_phase_support_status_bundle_path=post_status_json_path,
        signal_phase_support_apply_cycle_path=post_apply_cycle_json_path,
    )
    post_apply_status_json_path = Path(post_apply_status_manifest["outputs"]["report_json_path"])
    post_request_state_manifest = build_bari_signal_phase_support_request_state_bundle(
        output_dir=post_request_state_output_dir,
        signal_phase_support_status_bundle_path=post_status_json_path,
        signal_phase_support_apply_status_bundle_path=post_apply_status_json_path,
    )
    post_request_state_json_path = Path(post_request_state_manifest["outputs"]["report_json_path"])
    post_operator_board_manifest = build_bari_signal_phase_support_operator_board_bundle(
        output_dir=post_operator_board_output_dir,
        signal_phase_support_request_state_bundle_path=post_request_state_json_path,
        signal_phase_support_action_queue_path=post_action_json_path,
    )
    post_operator_board_json_path = Path(post_operator_board_manifest["outputs"]["report_json_path"])
    post_action_execution_manifest = (
        build_bari_signal_phase_support_action_execution_bundle(
            output_dir=post_action_execution_output_dir,
            signal_phase_support_operator_board_bundle_path=post_operator_board_json_path,
        )
    )
    post_action_execution_json_path = Path(
        post_action_execution_manifest["outputs"]["report_json_path"]
    )
    post_action_handoff_manifest = build_bari_signal_phase_support_action_handoff_bundle(
        output_dir=post_action_handoff_output_dir,
        signal_phase_support_action_execution_bundle_path=post_action_execution_json_path,
        support_runtime_cycle_manifest_path=support_runtime_cycle_reference_path,
    )
    post_action_handoff_json_path = Path(
        post_action_handoff_manifest["outputs"]["bundle_json_path"]
    )
    post_runtime_board_manifest = build_bari_signal_phase_support_runtime_board_bundle(
        output_dir=post_runtime_board_output_dir,
        signal_phase_support_action_execution_bundle_path=post_action_execution_json_path,
        signal_phase_support_action_handoff_bundle_path=post_action_handoff_json_path,
    )
    post_runtime_board_json_path = Path(
        post_runtime_board_manifest["outputs"]["bundle_json_path"]
    )
    post_runtime_action_queue_manifest = (
        build_bari_signal_phase_support_runtime_action_queue(
            output_dir=post_runtime_action_queue_output_dir,
            signal_phase_support_runtime_board_bundle_path=post_runtime_board_json_path,
        )
    )
    post_runtime_action_queue_json_path = Path(
        post_runtime_action_queue_manifest["outputs"]["report_json_path"]
    )
    post_runtime_action_execution_manifest = (
        build_bari_signal_phase_support_runtime_action_execution_bundle(
            output_dir=post_runtime_action_execution_output_dir,
            signal_phase_support_runtime_action_queue_path=post_runtime_action_queue_json_path,
        )
    )
    post_runtime_action_execution_json_path = Path(
        post_runtime_action_execution_manifest["outputs"]["report_json_path"]
    )

    pre_request_states = _request_state_map(pre_status_json_path)
    post_request_states = _request_state_map(post_status_json_path)
    pre_profile_states = _profile_state_map(pre_action_json_path)
    post_profile_states = _profile_state_map(post_action_json_path)
    pre_runtime_states = _request_runtime_state_map(pre_request_state_json_path)
    post_runtime_states = _request_runtime_state_map(post_request_state_json_path)
    pre_operator_states = _operator_board_state_map(pre_operator_board_json_path)
    post_operator_states = _operator_board_state_map(post_operator_board_json_path)
    pre_runtime_board_states = _runtime_board_state_map(pre_runtime_board_json_path)
    post_runtime_board_states = _runtime_board_state_map(post_runtime_board_json_path)
    pre_runtime_action_states = _runtime_action_queue_state_map(
        pre_runtime_action_queue_json_path
    )
    post_runtime_action_states = _runtime_action_queue_state_map(
        post_runtime_action_queue_json_path
    )
    pre_runtime_execution_states = _runtime_action_execution_state_map(
        pre_runtime_action_execution_json_path
    )
    post_runtime_execution_states = _runtime_action_execution_state_map(
        post_runtime_action_execution_json_path
    )
    request_comparison_rows = _request_comparison_rows(
        pre_request_states,
        post_request_states,
        selected_request_id=request_id,
    )
    profile_comparison_rows = _profile_comparison_rows(
        pre_profile_states,
        post_profile_states,
        selected_request_id=request_id,
    )
    request_runtime_comparison_rows = _request_runtime_comparison_rows(
        pre_runtime_states,
        post_runtime_states,
        selected_request_id=request_id,
    )
    operator_board_comparison_rows = _operator_board_comparison_rows(
        pre_operator_states,
        post_operator_states,
        selected_request_id=request_id,
    )
    runtime_board_comparison_rows = _runtime_board_comparison_rows(
        pre_runtime_board_states,
        post_runtime_board_states,
        selected_request_id=request_id,
    )
    runtime_action_queue_comparison_rows = _runtime_action_queue_comparison_rows(
        pre_runtime_action_states,
        post_runtime_action_states,
        selected_request_id=request_id,
    )
    runtime_action_execution_comparison_rows = (
        _runtime_action_execution_comparison_rows(
            pre_runtime_execution_states,
            post_runtime_execution_states,
            selected_request_id=request_id,
        )
    )

    selected_request_transition = next(
        (
            row
            for row in request_comparison_rows
            if _clean_text(row.get("request_id")) == request_id
        ),
        None,
    )
    if selected_request_transition is None:
        raise RuntimeError(
            f"Could not find request `{request_id}` in support rehearsal outputs."
        )
    selected_request_runtime_transition = next(
        (
            row
            for row in request_runtime_comparison_rows
            if _clean_text(row.get("request_id")) == request_id
        ),
        None,
    )
    if selected_request_runtime_transition is None:
        raise RuntimeError(
            f"Could not find request runtime state for `{request_id}` in support rehearsal outputs."
        )
    selected_request_operator_transition = next(
        (
            row
            for row in operator_board_comparison_rows
            if _clean_text(row.get("request_id")) == request_id
        ),
        None,
    )
    if selected_request_operator_transition is None:
        raise RuntimeError(
            f"Could not find operator board state for `{request_id}` in support rehearsal outputs."
        )
    selected_request_runtime_board_transition = next(
        (
            row
            for row in runtime_board_comparison_rows
            if _clean_text(row.get("request_id")) == request_id
        ),
        None,
    )
    if selected_request_runtime_board_transition is None:
        raise RuntimeError(
            f"Could not find runtime board state for `{request_id}` in support rehearsal outputs."
        )
    selected_request_runtime_action_transition = next(
        (
            row
            for row in runtime_action_queue_comparison_rows
            if _clean_text(row.get("request_id")) == request_id
        ),
        None,
    )
    if selected_request_runtime_action_transition is None:
        raise RuntimeError(
            f"Could not find runtime action state for `{request_id}` in support rehearsal outputs."
        )
    selected_request_runtime_execution_transition = next(
        (
            row
            for row in runtime_action_execution_comparison_rows
            if _clean_text(row.get("request_id")) == request_id
        ),
        None,
    )
    if selected_request_runtime_execution_transition is None:
        raise RuntimeError(
            f"Could not find runtime execution state for `{request_id}` in support rehearsal outputs."
        )

    request_state_comparison_path = output_root / "request_state_comparison.csv"
    request_runtime_comparison_path = output_root / "request_runtime_comparison.csv"
    profile_state_comparison_path = output_root / "profile_state_comparison.csv"
    operator_board_comparison_path = output_root / "operator_board_comparison.csv"
    runtime_board_comparison_path = output_root / "runtime_board_comparison.csv"
    runtime_action_queue_comparison_path = (
        output_root / "runtime_action_queue_comparison.csv"
    )
    runtime_action_execution_comparison_path = (
        output_root / "runtime_action_execution_comparison.csv"
    )
    _write_csv(
        request_state_comparison_path,
        request_comparison_rows,
        [
            "request_id",
            "selected_request",
            "signal_name",
            "pre_request_status_category",
            "post_request_status_category",
            "pre_validation_ready_profile_count",
            "post_validation_ready_profile_count",
            "pre_manual_ready_count",
            "post_manual_ready_count",
            "pre_manual_pending_count",
            "post_manual_pending_count",
            "pre_pedestrian_ready_count",
            "post_pedestrian_ready_count",
            "pre_pedestrian_pending_count",
            "post_pedestrian_pending_count",
            "pre_next_action",
            "post_next_action",
            "state_changed",
        ],
    )
    _write_csv(
        request_runtime_comparison_path,
        request_runtime_comparison_rows,
        [
            "request_id",
            "selected_request",
            "signal_name",
            "pre_request_runtime_category",
            "post_request_runtime_category",
            "pre_applied_profile_count",
            "post_applied_profile_count",
            "pre_ready_for_validation_count",
            "post_ready_for_validation_count",
            "pre_waiting_for_analyst_resolution_count",
            "post_waiting_for_analyst_resolution_count",
            "pre_request_runtime_summary",
            "post_request_runtime_summary",
            "pre_next_action",
            "post_next_action",
            "state_changed",
        ],
    )
    _write_csv(
        profile_state_comparison_path,
        profile_comparison_rows,
        [
            "request_id",
            "profile_id",
            "selected_request",
            "pre_validation_state_category",
            "post_validation_state_category",
            "pre_action_category",
            "post_action_category",
            "pre_ready_row_count",
            "post_ready_row_count",
            "pre_pending_row_count",
            "post_pending_row_count",
            "pre_execution_route",
            "post_execution_route",
            "pre_queue_type",
            "post_queue_type",
            "state_changed",
        ],
    )
    _write_csv(
        operator_board_comparison_path,
        operator_board_comparison_rows,
        [
            "request_id",
            "selected_request",
            "signal_name",
            "pre_operator_action_category",
            "post_operator_action_category",
            "pre_execution_route",
            "post_execution_route",
            "pre_queue_type",
            "post_queue_type",
            "pre_operator_summary",
            "post_operator_summary",
            "pre_dominant_profile_id",
            "post_dominant_profile_id",
            "state_changed",
        ],
    )
    _write_csv(
        runtime_board_comparison_path,
        runtime_board_comparison_rows,
        [
            "request_id",
            "selected_request",
            "signal_name",
            "pre_action_category",
            "post_action_category",
            "pre_execution_route",
            "post_execution_route",
            "pre_handoff_target_kind",
            "post_handoff_target_kind",
            "pre_handoff_target_path",
            "post_handoff_target_path",
            "pre_queue_type",
            "post_queue_type",
            "pre_request_runtime_category",
            "post_request_runtime_category",
            "state_changed",
        ],
    )
    _write_csv(
        runtime_action_queue_comparison_path,
        runtime_action_queue_comparison_rows,
        [
            "request_id",
            "selected_request",
            "signal_name",
            "pre_final_action_category",
            "post_final_action_category",
            "pre_action_category",
            "post_action_category",
            "pre_queue_type",
            "post_queue_type",
            "pre_request_runtime_category",
            "post_request_runtime_category",
            "pre_action_summary",
            "post_action_summary",
            "state_changed",
        ],
    )
    _write_csv(
        runtime_action_execution_comparison_path,
        runtime_action_execution_comparison_rows,
        [
            "request_id",
            "selected_request",
            "signal_name",
            "pre_final_action_category",
            "post_final_action_category",
            "pre_execution_route",
            "post_execution_route",
            "pre_execution_target_kind",
            "post_execution_target_kind",
            "pre_execution_target",
            "post_execution_target",
            "pre_queue_type",
            "post_queue_type",
            "pre_request_runtime_category",
            "post_request_runtime_category",
            "pre_execution_summary",
            "post_execution_summary",
            "state_changed",
        ],
    )

    pre_action_payload = _load_json(pre_action_json_path)
    post_action_payload = _load_json(post_action_json_path)
    pre_operator_payload = _load_json(pre_operator_board_json_path)
    post_operator_payload = _load_json(post_operator_board_json_path)
    pre_runtime_board_payload = _load_json(pre_runtime_board_json_path)
    post_runtime_board_payload = _load_json(post_runtime_board_json_path)
    pre_runtime_action_payload = _load_json(pre_runtime_action_queue_json_path)
    post_runtime_action_payload = _load_json(post_runtime_action_queue_json_path)
    pre_runtime_action_execution_payload = _load_json(
        pre_runtime_action_execution_json_path
    )
    post_runtime_action_execution_payload = _load_json(
        post_runtime_action_execution_json_path
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "request_count": len(request_comparison_rows),
        "changed_request_count": sum(
            1 for row in request_comparison_rows if row.get("state_changed") == "yes"
        ),
        "profile_count": len(profile_comparison_rows),
        "changed_profile_count": sum(
            1 for row in profile_comparison_rows if row.get("state_changed") == "yes"
        ),
        "selected_request_changed": selected_request_transition["state_changed"],
        "selected_request_left_manual_resolution": (
            "yes"
            if selected_request_transition["pre_request_status_category"]
            == "pending_manual_resolution"
            and selected_request_transition["post_request_status_category"]
            != "pending_manual_resolution"
            else "no"
        ),
        "pre_validation_action_count": int(
            pre_action_payload["summary"]["validation_action_count"]
        ),
        "post_validation_action_count": int(
            post_action_payload["summary"]["validation_action_count"]
        ),
        "pre_operator_ready_count": int(
            pre_operator_payload["summary"]["operator_ready_count"]
        ),
        "post_operator_ready_count": int(
            post_operator_payload["summary"]["operator_ready_count"]
        ),
        "pre_runtime_board_ready_count": int(
            pre_runtime_board_payload["summary"]["operator_ready_count"]
        ),
        "post_runtime_board_ready_count": int(
            post_runtime_board_payload["summary"]["operator_ready_count"]
        ),
        "pre_runtime_action_ready_count": int(
            pre_runtime_action_payload["summary"]["immediate_action_count"]
        ),
        "post_runtime_action_ready_count": int(
            post_runtime_action_payload["summary"]["immediate_action_count"]
        ),
        "pre_runtime_execution_ready_count": int(
            pre_runtime_action_execution_payload["summary"]["execution_ready_count"]
        ),
        "post_runtime_execution_ready_count": int(
            post_runtime_action_execution_payload["summary"]["execution_ready_count"]
        ),
        "post_executed_validation_count": int(
            post_apply_result["stats"]["executed_validation_count"]
        ),
        "post_accepted_for_ingestion_count": int(
            post_apply_result["stats"]["accepted_for_ingestion_count"]
        ),
        "post_delivery_session_executed": bool(
            post_apply_result["stats"]["delivery_session_executed"]
        ),
        "post_movements_with_phase_timing": int(
            post_apply_result["stats"]["movements_with_phase_timing"]
        ),
        "post_movements_with_phase_mapping": int(
            post_apply_result["stats"]["movements_with_phase_mapping"]
        ),
    }

    rehearsal_json_path = output_root / "signal_phase_support_rehearsal.json"
    rehearsal_md_path = output_root / "signal_phase_support_rehearsal.md"
    manifest_path = output_root / "signal_phase_support_rehearsal.manifest.json"
    generated_at_utc = summary["generated_at_utc"]

    payload = {
        "signal_phase_support_rehearsal_version": SIGNAL_PHASE_SUPPORT_REHEARSAL_VERSION,
        "signal_phase_support_rehearsal_contract_version": SIGNAL_PHASE_SUPPORT_REHEARSAL_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "selected_request_id": request_id,
        "summary": summary,
        "selected_request_transition": selected_request_transition,
        "selected_request_runtime_transition": selected_request_runtime_transition,
        "selected_request_operator_transition": selected_request_operator_transition,
        "selected_request_runtime_board_transition": (
            selected_request_runtime_board_transition
        ),
        "selected_request_runtime_action_transition": (
            selected_request_runtime_action_transition
        ),
        "selected_request_runtime_execution_transition": (
            selected_request_runtime_execution_transition
        ),
        "injected_rows": {
            "manual": injected_manual,
            "pedestrian": injected_pedestrian,
        },
        "inputs": {
            "signal_phase_support_writeback_bundle_path": str(
                support_writeback_bundle_input
            ),
            "signal_phase_support_resolution_bundle_path": str(
                support_resolution_bundle_input
            ),
            "manual_mapping_stub_path": str(manual_mapping_stub_input),
            "delivery_checklist_path": str(delivery_checklist_input),
            "movement_objects_path": str(movement_objects_input),
            "request_id": request_id,
            "manual_phase_id": manual_phase_id,
            "manual_stage_id": manual_stage_id,
            "manual_protection_state": manual_protection_state,
            "pedestrian_phase_id": pedestrian_phase_id,
            "pedestrian_stage_id": pedestrian_stage_id,
            "pedestrian_protection_state": pedestrian_protection_state,
            "preview_limit": int(preview_limit),
        },
        "outputs": {
            "pre_support_status_manifest_path": str(
                pre_status_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_action_queue_manifest_path": str(
                pre_action_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_apply_cycle_manifest_path": str(pre_apply_result["manifest_path"]),
            "pre_support_apply_status_manifest_path": str(
                pre_apply_status_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_request_state_manifest_path": str(
                pre_request_state_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_operator_board_manifest_path": str(
                pre_operator_board_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_action_execution_manifest_path": str(
                pre_action_execution_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_action_handoff_manifest_path": str(
                pre_action_handoff_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_runtime_board_manifest_path": str(
                pre_runtime_board_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_runtime_action_queue_manifest_path": str(
                pre_runtime_action_queue_manifest["outputs"]["manifest_path"]
            ),
            "pre_support_runtime_action_execution_manifest_path": str(
                pre_runtime_action_execution_manifest["outputs"]["manifest_path"]
            ),
            "rehearsal_writeback_manifest_path": str(
                post_writeback_manifest["outputs"]["manifest_path"]
            ),
            "post_support_status_manifest_path": str(
                post_status_manifest["outputs"]["manifest_path"]
            ),
            "post_support_action_queue_manifest_path": str(
                post_action_manifest["outputs"]["manifest_path"]
            ),
            "post_support_apply_cycle_manifest_path": str(post_apply_result["manifest_path"]),
            "post_support_apply_status_manifest_path": str(
                post_apply_status_manifest["outputs"]["manifest_path"]
            ),
            "post_support_request_state_manifest_path": str(
                post_request_state_manifest["outputs"]["manifest_path"]
            ),
            "post_support_operator_board_manifest_path": str(
                post_operator_board_manifest["outputs"]["manifest_path"]
            ),
            "post_support_action_execution_manifest_path": str(
                post_action_execution_manifest["outputs"]["manifest_path"]
            ),
            "post_support_action_handoff_manifest_path": str(
                post_action_handoff_manifest["outputs"]["manifest_path"]
            ),
            "post_support_runtime_board_manifest_path": str(
                post_runtime_board_manifest["outputs"]["manifest_path"]
            ),
            "post_support_runtime_action_queue_manifest_path": str(
                post_runtime_action_queue_manifest["outputs"]["manifest_path"]
            ),
            "post_support_runtime_action_execution_manifest_path": str(
                post_runtime_action_execution_manifest["outputs"]["manifest_path"]
            ),
            "rehearsal_manual_workbook_path": str(rehearsal_manual_workbook_path),
            "rehearsal_pedestrian_workbook_path": str(
                rehearsal_pedestrian_workbook_path
            ),
            "request_state_comparison_path": str(request_state_comparison_path),
            "request_runtime_comparison_path": str(request_runtime_comparison_path),
            "profile_state_comparison_path": str(profile_state_comparison_path),
            "operator_board_comparison_path": str(operator_board_comparison_path),
            "runtime_board_comparison_path": str(runtime_board_comparison_path),
            "runtime_action_queue_comparison_path": str(
                runtime_action_queue_comparison_path
            ),
            "runtime_action_execution_comparison_path": str(
                runtime_action_execution_comparison_path
            ),
        },
    }
    rehearsal_json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    rehearsal_md_path.write_text(_rehearsal_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_support_rehearsal_version": SIGNAL_PHASE_SUPPORT_REHEARSAL_VERSION,
        "contract": {
            "resource_name": "signal_phase_support_rehearsal",
            "public_contract_version": SIGNAL_PHASE_SUPPORT_REHEARSAL_CONTRACT_VERSION,
            "signal_phase_support_rehearsal_version": SIGNAL_PHASE_SUPPORT_REHEARSAL_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_support_rehearsal_runner",
        },
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "rehearsal_json_path": str(rehearsal_json_path),
            "rehearsal_json_sha256": _sha256(rehearsal_json_path),
            "rehearsal_md_path": str(rehearsal_md_path),
            "rehearsal_md_sha256": _sha256(rehearsal_md_path),
            **payload["outputs"],
        },
        "stats": summary,
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference(
                    "signal_phase_support_writeback_bundle",
                    support_writeback_bundle_input,
                    _sha256(support_writeback_bundle_input),
                ),
                _artifact_reference(
                    "signal_phase_support_resolution_bundle",
                    support_resolution_bundle_input,
                    _sha256(support_resolution_bundle_input),
                ),
                _artifact_reference(
                    "signal_phase_mapping_stub",
                    manual_mapping_stub_input,
                    _sha256(manual_mapping_stub_input),
                ),
                _artifact_reference(
                    "signal_phase_delivery_checklist",
                    delivery_checklist_input,
                    _sha256(delivery_checklist_input),
                ),
                _artifact_reference(
                    "movement_objects",
                    movement_objects_input,
                    _sha256(movement_objects_input),
                ),
                _artifact_reference(
                    "signal_phase_support_manual_workbook",
                    source_manual_workbook_path,
                    _sha256(source_manual_workbook_path),
                ),
                _artifact_reference(
                    "signal_phase_support_pedestrian_workbook",
                    source_pedestrian_workbook_path,
                    _sha256(source_pedestrian_workbook_path),
                ),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_support_rehearsal_json",
                    rehearsal_json_path,
                    _sha256(rehearsal_json_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_markdown",
                    rehearsal_md_path,
                    _sha256(rehearsal_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_support_rehearsal_request_comparison",
                    request_state_comparison_path,
                    _sha256(request_state_comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_profile_comparison",
                    profile_state_comparison_path,
                    _sha256(profile_state_comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_request_runtime_comparison",
                    request_runtime_comparison_path,
                    _sha256(request_runtime_comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_operator_board_comparison",
                    operator_board_comparison_path,
                    _sha256(operator_board_comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_runtime_board_comparison",
                    runtime_board_comparison_path,
                    _sha256(runtime_board_comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_runtime_action_queue_comparison",
                    runtime_action_queue_comparison_path,
                    _sha256(runtime_action_queue_comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_runtime_action_execution_comparison",
                    runtime_action_execution_comparison_path,
                    _sha256(runtime_action_execution_comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_manual_workbook",
                    rehearsal_manual_workbook_path,
                    _sha256(rehearsal_manual_workbook_path),
                ),
                _artifact_reference(
                    "signal_phase_support_rehearsal_pedestrian_workbook",
                    rehearsal_pedestrian_workbook_path,
                    _sha256(rehearsal_pedestrian_workbook_path),
                ),
                _artifact_reference(
                    "signal_phase_support_writeback_bundle",
                    Path(payload["outputs"]["rehearsal_writeback_manifest_path"]),
                    _sha256(Path(payload["outputs"]["rehearsal_writeback_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_status_bundle",
                    Path(payload["outputs"]["pre_support_status_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_status_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_status_bundle",
                    Path(payload["outputs"]["post_support_status_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_status_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_queue",
                    Path(payload["outputs"]["pre_support_action_queue_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_action_queue_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_apply_status_bundle",
                    Path(payload["outputs"]["pre_support_apply_status_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_apply_status_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_request_state_bundle",
                    Path(payload["outputs"]["pre_support_request_state_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_request_state_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_operator_board_bundle",
                    Path(payload["outputs"]["pre_support_operator_board_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_operator_board_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_execution_bundle",
                    Path(payload["outputs"]["pre_support_action_execution_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_action_execution_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_handoff_bundle",
                    Path(payload["outputs"]["pre_support_action_handoff_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_action_handoff_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_board_bundle",
                    Path(payload["outputs"]["pre_support_runtime_board_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_runtime_board_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_queue",
                    Path(payload["outputs"]["pre_support_runtime_action_queue_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_runtime_action_queue_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_execution_bundle",
                    Path(payload["outputs"]["pre_support_runtime_action_execution_manifest_path"]),
                    _sha256(
                        Path(
                            payload["outputs"][
                                "pre_support_runtime_action_execution_manifest_path"
                            ]
                        )
                    ),
                ),
                _artifact_reference(
                    "signal_phase_support_action_queue",
                    Path(payload["outputs"]["post_support_action_queue_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_action_queue_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_apply_status_bundle",
                    Path(payload["outputs"]["post_support_apply_status_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_apply_status_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_request_state_bundle",
                    Path(payload["outputs"]["post_support_request_state_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_request_state_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_operator_board_bundle",
                    Path(payload["outputs"]["post_support_operator_board_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_operator_board_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_execution_bundle",
                    Path(payload["outputs"]["post_support_action_execution_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_action_execution_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_action_handoff_bundle",
                    Path(payload["outputs"]["post_support_action_handoff_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_action_handoff_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_board_bundle",
                    Path(payload["outputs"]["post_support_runtime_board_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_runtime_board_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_queue",
                    Path(payload["outputs"]["post_support_runtime_action_queue_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_runtime_action_queue_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_runtime_action_execution_bundle",
                    Path(payload["outputs"]["post_support_runtime_action_execution_manifest_path"]),
                    _sha256(
                        Path(
                            payload["outputs"][
                                "post_support_runtime_action_execution_manifest_path"
                            ]
                        )
                    ),
                ),
                _artifact_reference(
                    "signal_phase_support_apply_cycle",
                    Path(payload["outputs"]["pre_support_apply_cycle_manifest_path"]),
                    _sha256(Path(payload["outputs"]["pre_support_apply_cycle_manifest_path"])),
                ),
                _artifact_reference(
                    "signal_phase_support_apply_cycle",
                    Path(payload["outputs"]["post_support_apply_cycle_manifest_path"]),
                    _sha256(Path(payload["outputs"]["post_support_apply_cycle_manifest_path"])),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_support_rehearsal_version": SIGNAL_PHASE_SUPPORT_REHEARSAL_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
