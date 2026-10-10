"""Build request-level Bari support state from support status and apply-status outputs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_REQUEST_STATE_BUNDLE_VERSION = (
    "signal_phase_support_request_state_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_REQUEST_STATE_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_request_state_bundle_public_v1"
)


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


def _profile_rows_by_request(status_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in status_rows:
        if not isinstance(row, dict):
            continue
        request_id = _clean_text(row.get("request_id"))
        if not request_id:
            continue
        grouped.setdefault(request_id, []).append(row)
    return grouped


def _request_runtime_category(
    *,
    request_status_category: str,
    profile_count: int,
    applied_profile_count: int,
    accepted_pending_apply_count: int,
    validation_review_count: int,
    ready_for_validation_count: int,
    waiting_for_analyst_resolution_count: int,
) -> str:
    if profile_count <= 0:
        return "no_support_profiles"
    if applied_profile_count >= profile_count:
        return "fully_applied_to_movement_layer"
    if applied_profile_count > 0:
        if validation_review_count > 0:
            return "partially_applied_with_review_required"
        if accepted_pending_apply_count > 0:
            return "partially_applied_pending_apply"
        if ready_for_validation_count > 0:
            return "partially_applied_ready_for_validation"
        if waiting_for_analyst_resolution_count > 0:
            return "partially_applied_manual_resolution"
        return "partially_applied_to_movement_layer"
    if validation_review_count > 0:
        return "validation_review_required"
    if accepted_pending_apply_count > 0:
        return "accepted_pending_apply"
    if request_status_category == "ready_for_validation":
        return "ready_for_validation"
    if request_status_category == "partially_ready_for_validation":
        return "partially_ready_for_validation"
    if request_status_category == "pending_manual_resolution":
        return "pending_manual_resolution"
    return request_status_category or "unknown"


def _next_action(
    category: str,
    *,
    request_id: str,
    applied_profile_count: int,
    profile_count: int,
) -> str:
    if category == "fully_applied_to_movement_layer":
        return (
            f"The request `{request_id}` is already fully applied. Do not rerun support validation unless workbook rows change."
        )
    if category.startswith("partially_applied"):
        return (
            f"The request `{request_id}` is partially applied ({applied_profile_count}/{profile_count} profiles). "
            "Continue only the remaining workbook, validation, or review tasks."
        )
    if category == "accepted_pending_apply":
        return (
            f"The request `{request_id}` has accepted profiles pending apply. Inspect the support apply cycle before rerunning validation."
        )
    if category == "validation_review_required":
        return (
            f"The request `{request_id}` needs validation review or repair before more support-derived profiles can be applied."
        )
    if category in {"ready_for_validation", "partially_ready_for_validation"}:
        return (
            f"The request `{request_id}` has profiles ready for validation. Run the support validation/apply path."
        )
    if category == "pending_manual_resolution":
        return (
            f"The request `{request_id}` still needs workbook completion before validation."
        )
    return f"No request-level action is available yet for `{request_id}`."


def _request_markdown(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {row['request_id']}",
            "",
            f"- signal: `{row['signal_name']}`",
            f"- junction: `{row['junction_id']}`",
            f"- request runtime category: `{row['request_runtime_category']}`",
            f"- applied profiles: `{row['applied_profile_count']}` / `{row['profile_count']}`",
            f"- accepted pending apply: `{row['accepted_pending_apply_count']}`",
            f"- validation review profiles: `{row['validation_review_count']}`",
            f"- ready for validation profiles: `{row['ready_for_validation_count']}`",
            f"- waiting for analyst resolution profiles: `{row['waiting_for_analyst_resolution_count']}`",
            f"- unresolved signalized movements: `{row['unresolved_signalized_movement_count']}` (`{row['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
            f"- unresolved signalized crashes: `{row['unresolved_signalized_crash_total']}` (`{row['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
            "",
            "Next step:",
            "",
            row["next_action"],
            "",
        ]
    )


def _report_markdown(
    summary: dict[str, Any],
    active_rows: list[dict[str, Any]],
    hold_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Request State",
        "",
        "This bundle merges request-level support status with profile-level apply status so the Bari support stack can report final request state instead of only pre-apply workbook state.",
        "",
        "## Summary",
        "",
        f"- requests reviewed: `{summary['request_count']}`",
        f"- pending manual requests: `{summary['pending_manual_resolution_count']}`",
        f"- partially ready requests: `{summary['partially_ready_for_validation_count']}`",
        f"- ready-for-validation requests: `{summary['ready_for_validation_count']}`",
        f"- validation-review requests: `{summary['validation_review_required_count']}`",
        f"- accepted-pending-apply requests: `{summary['accepted_pending_apply_count']}`",
        f"- partially applied requests: `{summary['partially_applied_count']}`",
        f"- fully applied requests: `{summary['fully_applied_count']}`",
        f"- requests with unresolved signalized movements: `{summary['requests_with_unresolved_signalized_movements_count']}`",
        f"- unresolved signalized movement rows: `{summary['unresolved_signalized_movement_count_total']}` (`{summary['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
        f"- unresolved signalized crashes: `{summary['unresolved_signalized_crash_total']}` (`{summary['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
        "",
        "## Active Requests",
        "",
    ]
    if active_rows:
        for row in active_rows[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['request_runtime_category']}`: "
                f"`{row['unresolved_signalized_movement_count']}` unresolved movements / "
                f"`{row['unresolved_signalized_crash_total']}` unresolved crashes -> `{row['next_action']}`"
            )
    else:
        lines.append("- No active support requests remain.")
    if hold_rows:
        lines.extend(["", "## Holds", ""])
        for row in hold_rows[:10]:
            lines.append(
                f"- `{row['request_id']}` `{row['request_runtime_category']}`: "
                f"`{row['unresolved_signalized_movement_count']}` unresolved movements / "
                f"`{row['unresolved_signalized_crash_total']}` unresolved crashes -> `{row['next_action']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_request_state_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_request_state/bari",
    signal_phase_support_status_bundle_path: str | Path = "data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.json",
    signal_phase_support_apply_status_bundle_path: str | Path = "data/reporting/signal_phase_support_apply_status/bari/signal_phase_support_apply_status_bundle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    status_bundle_input = Path(signal_phase_support_status_bundle_path)
    apply_status_bundle_input = Path(signal_phase_support_apply_status_bundle_path)
    status_bundle = _load_json(status_bundle_input)
    apply_status_bundle = _load_json(apply_status_bundle_input)

    request_rows = status_bundle.get("request_support_status", [])
    if not isinstance(request_rows, list):
        raise RuntimeError("Support-status bundle must expose request_support_status.")
    status_rows = apply_status_bundle.get("status_rows", [])
    if not isinstance(status_rows, list):
        raise RuntimeError("Support apply-status bundle must expose status_rows.")

    profiles_by_request = _profile_rows_by_request(status_rows)
    request_state_rows: list[dict[str, Any]] = []
    active_rows: list[dict[str, Any]] = []
    hold_rows: list[dict[str, Any]] = []

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
        request_profiles = profiles_by_request.get(request_id, [])
        profile_count = len(request_profiles)
        applied_profile_count = sum(
            1
            for row in request_profiles
            if (_clean_text(row.get("apply_status_category")) or "")
            == "applied_to_movement_layer"
        )
        accepted_pending_apply_count = sum(
            1
            for row in request_profiles
            if (_clean_text(row.get("apply_status_category")) or "")
            == "accepted_for_ingestion_pending_apply"
        )
        validation_review_count = sum(
            1
            for row in request_profiles
            if (_clean_text(row.get("apply_status_category")) or "")
            in {"validation_partial_review", "validation_failed"}
        )
        ready_for_validation_count = sum(
            1
            for row in request_profiles
            if (_clean_text(row.get("apply_status_category")) or "")
            in {"ready_for_validation", "partially_ready_for_validation"}
        )
        waiting_for_analyst_resolution_count = sum(
            1
            for row in request_profiles
            if (_clean_text(row.get("apply_status_category")) or "")
            == "waiting_for_analyst_resolution"
        )

        request_runtime_category = _request_runtime_category(
            request_status_category=_clean_text(request_row.get("request_status_category")) or "",
            profile_count=profile_count,
            applied_profile_count=applied_profile_count,
            accepted_pending_apply_count=accepted_pending_apply_count,
            validation_review_count=validation_review_count,
            ready_for_validation_count=ready_for_validation_count,
            waiting_for_analyst_resolution_count=waiting_for_analyst_resolution_count,
        )

        row = {
            **request_row,
            "profile_count": profile_count,
            "applied_profile_count": applied_profile_count,
            "accepted_pending_apply_count": accepted_pending_apply_count,
            "validation_review_count": validation_review_count,
            "ready_for_validation_count": ready_for_validation_count,
            "waiting_for_analyst_resolution_count": waiting_for_analyst_resolution_count,
            "request_runtime_category": request_runtime_category,
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
        }
        row["next_action"] = _next_action(
            request_runtime_category,
            request_id=request_id,
            applied_profile_count=applied_profile_count,
            profile_count=profile_count,
        )
        row["request_runtime_summary"] = (
            f"{request_runtime_category}: {applied_profile_count}/{profile_count} applied, "
            f"{ready_for_validation_count} ready, {waiting_for_analyst_resolution_count} waiting"
        )

        packet_path = packets_dir / f"{request_id}.md"
        packet_path.write_text(_request_markdown(row), encoding="utf-8")
        row["packet_md_path"] = str(packet_path)
        request_state_rows.append(row)

        if request_runtime_category == "fully_applied_to_movement_layer":
            hold_rows.append(row)
        else:
            active_rows.append(row)

    request_state_path = output_root / "request_support_runtime_state.csv"
    active_queue_path = output_root / "request_active_queue.csv"
    hold_queue_path = output_root / "request_hold_queue.csv"
    report_json_path = output_root / "signal_phase_support_request_state_bundle.json"
    report_md_path = output_root / "signal_phase_support_request_state_bundle.md"
    manifest_path = output_root / "signal_phase_support_request_state_bundle.manifest.json"

    fieldnames = [
        "request_id",
        "junction_id",
        "signal_name",
        "request_status_category",
        "request_runtime_category",
        "profile_count",
        "applied_profile_count",
        "accepted_pending_apply_count",
        "validation_review_count",
        "ready_for_validation_count",
        "waiting_for_analyst_resolution_count",
        "manual_workbook_row_count",
        "manual_ready_count",
        "manual_pending_count",
        "pedestrian_workbook_row_count",
        "pedestrian_ready_count",
        "pedestrian_pending_count",
        "validation_ready_profile_count",
        "signalized_movement_count",
        "matched_crashes_at_junction_total",
        "unresolved_signalized_movement_count",
        "unresolved_signalized_crash_total",
        "unresolved_signalized_movement_share_pct",
        "unresolved_signalized_crash_coverage_pct",
        "manual_workbook_path",
        "pedestrian_workbook_path",
        "manual_delivery_path",
        "pedestrian_delivery_path",
        "recommended_next_action",
        "next_action",
        "request_runtime_summary",
        "packet_md_path",
    ]
    _write_csv(request_state_path, request_state_rows, fieldnames)
    _write_csv(active_queue_path, active_rows, fieldnames)
    _write_csv(hold_queue_path, hold_rows, fieldnames)

    summary = {
        "request_count": len(request_state_rows),
        "pending_manual_resolution_count": sum(
            1 for row in request_state_rows if row["request_runtime_category"] == "pending_manual_resolution"
        ),
        "partially_ready_for_validation_count": sum(
            1
            for row in request_state_rows
            if row["request_runtime_category"] == "partially_ready_for_validation"
        ),
        "ready_for_validation_count": sum(
            1 for row in request_state_rows if row["request_runtime_category"] == "ready_for_validation"
        ),
        "validation_review_required_count": sum(
            1
            for row in request_state_rows
            if row["request_runtime_category"]
            in {"validation_review_required", "partially_applied_with_review_required"}
        ),
        "accepted_pending_apply_count": sum(
            1
            for row in request_state_rows
            if row["request_runtime_category"]
            in {"accepted_pending_apply", "partially_applied_pending_apply"}
        ),
        "partially_applied_count": sum(
            1
            for row in request_state_rows
            if row["request_runtime_category"].startswith("partially_applied")
        ),
        "fully_applied_count": sum(
            1
            for row in request_state_rows
            if row["request_runtime_category"] == "fully_applied_to_movement_layer"
        ),
        "requests_with_unresolved_signalized_movements_count": int(
            sum(
                1
                for row in request_state_rows
                if int(row["unresolved_signalized_movement_count"]) > 0
            )
        ),
        "unresolved_signalized_movement_count_total": int(
            sum(int(row["unresolved_signalized_movement_count"]) for row in request_state_rows)
        ),
        "unresolved_signalized_crash_total": int(
            sum(int(row["unresolved_signalized_crash_total"]) for row in request_state_rows)
        ),
        "unresolved_signalized_movement_share_pct": _safe_pct(
            int(
                sum(
                    int(row["unresolved_signalized_movement_count"])
                    for row in request_state_rows
                )
            ),
            int(sum(int(row["signalized_movement_count"]) for row in request_state_rows)),
        ),
        "unresolved_signalized_crash_coverage_pct": _safe_pct(
            int(sum(int(row["unresolved_signalized_crash_total"]) for row in request_state_rows)),
            int(
                sum(
                    int(row["matched_crashes_at_junction_total"])
                    for row in request_state_rows
                )
            ),
        ),
        "active_request_count": len(active_rows),
        "hold_request_count": len(hold_rows),
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_request_state_bundle_version": SIGNAL_PHASE_SUPPORT_REQUEST_STATE_BUNDLE_VERSION,
        "signal_phase_support_request_state_bundle_contract_version": SIGNAL_PHASE_SUPPORT_REQUEST_STATE_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "request_support_runtime_state": request_state_rows,
        "request_active_queue_path": str(active_queue_path),
        "request_hold_queue_path": str(hold_queue_path),
        "request_support_runtime_state_path": str(request_state_path),
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_report_markdown(summary, active_rows, hold_rows), encoding="utf-8")

    manifest = {
        "source": {"adapter": "bari_signal_phase_support_request_state_bundle_builder"},
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_request_state_bundle_version": SIGNAL_PHASE_SUPPORT_REQUEST_STATE_BUNDLE_VERSION,
        "contract_version": SIGNAL_PHASE_SUPPORT_REQUEST_STATE_BUNDLE_CONTRACT_VERSION,
        "inputs": {
            "signal_phase_support_status_bundle_path": str(status_bundle_input),
            "signal_phase_support_apply_status_bundle_path": str(apply_status_bundle_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "request_support_runtime_state_path": str(request_state_path),
            "request_support_runtime_state_sha256": _sha256(request_state_path),
            "request_active_queue_path": str(active_queue_path),
            "request_active_queue_sha256": _sha256(active_queue_path),
            "request_hold_queue_path": str(hold_queue_path),
            "request_hold_queue_sha256": _sha256(hold_queue_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_support_status_bundle",
                status_bundle_input,
                _sha256(status_bundle_input),
            ),
            _artifact_reference(
                "signal_phase_support_apply_status_bundle",
                apply_status_bundle_input,
                _sha256(apply_status_bundle_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_support_request_state_bundle_json",
                report_json_path,
                _sha256(report_json_path),
            ),
            _artifact_reference(
                "signal_phase_support_request_state_bundle_markdown",
                report_md_path,
                _sha256(report_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_support_request_runtime_state_csv",
                request_state_path,
                _sha256(request_state_path),
            ),
            _artifact_reference(
                "signal_phase_support_request_active_queue_csv",
                active_queue_path,
                _sha256(active_queue_path),
            ),
            _artifact_reference(
                "signal_phase_support_request_hold_queue_csv",
                hold_queue_path,
                _sha256(hold_queue_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
