"""Build support-side apply status from Bari support validation and apply outputs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_APPLY_STATUS_BUNDLE_VERSION = (
    "signal_phase_support_apply_status_bundle_v1"
)
SIGNAL_PHASE_SUPPORT_APPLY_STATUS_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_support_apply_status_bundle_public_v1"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
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


def _profile_key(*, request_id: Any, profile_id: Any) -> tuple[str, str]:
    return (_clean_text(request_id) or "", _clean_text(profile_id) or "")


def _load_validation_results(apply_cycle_payload: dict[str, Any]) -> list[dict[str, Any]]:
    batch_manifest_path = Path(
        str(apply_cycle_payload["outputs"]["support_validation_batch_manifest_path"])
    )
    batch_manifest = _load_json(batch_manifest_path)
    batch_json_path = Path(str(batch_manifest["outputs"]["batch_json_path"]))
    batch_payload = _load_json(batch_json_path)
    results = batch_payload.get("validation_results", [])
    if not isinstance(results, list):
        raise RuntimeError("Support validation batch must expose validation_results.")
    return [row for row in results if isinstance(row, dict)]


def _applied_profiles(
    apply_cycle_payload: dict[str, Any],
) -> tuple[dict[tuple[str, str], dict[str, Any]], str]:
    delivery_session_manifest_value = _clean_text(
        apply_cycle_payload["outputs"].get("delivery_session_manifest_path")
    )
    if not delivery_session_manifest_value:
        return {}, ""
    delivery_session_manifest_path = Path(delivery_session_manifest_value)
    delivery_session_manifest = _load_json(delivery_session_manifest_path)
    delivery_session_json_path = Path(
        str(delivery_session_manifest["outputs"]["session_json_path"])
    )
    delivery_session_payload = _load_json(delivery_session_json_path)
    accepted_deliveries = delivery_session_payload.get("accepted_deliveries", [])
    if not isinstance(accepted_deliveries, list):
        raise RuntimeError("Signal-phase delivery session must expose accepted_deliveries.")

    output: dict[tuple[str, str], dict[str, Any]] = {}
    for row in accepted_deliveries:
        if not isinstance(row, dict):
            continue
        validation_manifest_path = Path(str(row.get("validation_manifest_path") or ""))
        if not validation_manifest_path.exists():
            continue
        validation_manifest = _load_json(validation_manifest_path)
        key = _profile_key(
            request_id=validation_manifest["inputs"].get("request_id"),
            profile_id=validation_manifest["profile"].get("profile_id"),
        )
        if not key[0] or not key[1]:
            continue
        output[key] = {
            "validation_manifest_path": str(validation_manifest_path),
            "ingested_manifest_path": _clean_text(row.get("ingested_manifest_path")) or "",
            "movement_signal_phase_manifest_path": _clean_text(
                delivery_session_payload["outputs"].get("movement_signal_phase_manifest_path")
            )
            or "",
            "delivery_session_manifest_path": str(delivery_session_manifest_path),
        }
    return output, str(delivery_session_manifest_path)


def _apply_status_category(
    *,
    validation_state_category: str,
    validation_outcome: str,
    applied_to_movement_layer: bool,
) -> str:
    if applied_to_movement_layer:
        return "applied_to_movement_layer"
    if validation_outcome == "accepted_for_ingestion":
        return "accepted_for_ingestion_pending_apply"
    if validation_outcome == "accepted_with_rejections":
        return "validation_partial_review"
    if validation_outcome in {"provider_fix_required", "schema_not_ready", "empty_delivery"}:
        return "validation_failed"
    return validation_state_category or "no_rows"


def _apply_status_summary(category: str, *, profile_id: str, pending_row_count: int) -> str:
    if category == "applied_to_movement_layer":
        return (
            f"The `{profile_id}` delivery has already been accepted and joined onto the movement layer."
        )
    if category == "accepted_for_ingestion_pending_apply":
        return (
            f"The `{profile_id}` delivery validated cleanly, but no applied delivery-session state was found."
        )
    if category == "validation_partial_review":
        return (
            f"The `{profile_id}` delivery validated with rejections; review the rejected rows before rerunning apply."
        )
    if category == "validation_failed":
        return (
            f"The `{profile_id}` delivery failed validation and needs workbook or export corrections before rerun."
        )
    if category in {"ready_for_validation", "partially_ready_for_validation"}:
        return (
            f"The `{profile_id}` delivery is ready for validation with `{pending_row_count}` rows still pending."
            if pending_row_count > 0
            else f"The `{profile_id}` delivery is ready for validation."
        )
    if category == "waiting_for_analyst_resolution":
        return f"The `{profile_id}` workbook still needs analyst completion before validation."
    return f"No active apply-state transition exists yet for `{profile_id}`."


def _next_action(category: str) -> str:
    if category == "applied_to_movement_layer":
        return "Do not rerun validation for this profile unless the live workbook rows change."
    if category == "accepted_for_ingestion_pending_apply":
        return "Inspect the support apply cycle and delivery-session outputs before rerunning this profile."
    if category == "validation_partial_review":
        return "Review rejected rows, update the workbook export, and rerun support validation."
    if category == "validation_failed":
        return "Fix workbook or delivery export problems and rerun support validation."
    if category in {"ready_for_validation", "partially_ready_for_validation"}:
        return "Run the support validation/apply path for this profile."
    if category == "waiting_for_analyst_resolution":
        return "Continue filling the workbook rows for this profile."
    return "No action required."


def _status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Support Apply Status",
        "",
        f"As of {payload['generated_at_utc']}, the Bari support-derived profile state has been synchronized across support status, validation outcomes, and delivery-session application.",
        "",
        "## Summary",
        "",
        f"- profiles reviewed: `{payload['summary']['profile_count']}`",
        f"- applied profiles: `{payload['summary']['applied_profile_count']}`",
        f"- accepted but not applied: `{payload['summary']['accepted_pending_apply_count']}`",
        f"- validation partial review: `{payload['summary']['validation_partial_review_count']}`",
        f"- validation failed: `{payload['summary']['validation_failed_count']}`",
        f"- ready for validation: `{payload['summary']['ready_for_validation_count']}`",
        f"- waiting for analyst resolution: `{payload['summary']['waiting_for_analyst_resolution_count']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["status_rows"][:10]:
        lines.append(
            f"- `{row['request_id']}` `{row['profile_id']}` `{row['apply_status_category']}` -> `{row['action_summary']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_apply_status_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_apply_status/bari",
    signal_phase_support_status_bundle_path: str | Path = "data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.json",
    signal_phase_support_apply_cycle_path: str | Path = "data/processed/signal_phase_support_apply_cycles/bari/signal_phase_support_apply_cycle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    status_bundle_input = Path(signal_phase_support_status_bundle_path)
    apply_cycle_input = Path(signal_phase_support_apply_cycle_path)

    status_bundle = _load_json(status_bundle_input)
    apply_cycle_payload = _load_json(apply_cycle_input)

    validation_ready_queue_path = Path(str(status_bundle.get("validation_ready_queue_path") or ""))
    validation_hold_queue_path = Path(str(status_bundle.get("validation_hold_queue_path") or ""))
    input_rows = _read_csv_rows(validation_ready_queue_path) + _read_csv_rows(
        validation_hold_queue_path
    )

    validation_results = _load_validation_results(apply_cycle_payload)
    validation_by_key = {
        _profile_key(request_id=row.get("request_id"), profile_id=row.get("profile_id")): row
        for row in validation_results
        if _profile_key(request_id=row.get("request_id"), profile_id=row.get("profile_id")) != ("", "")
    }
    applied_by_key, delivery_session_manifest_path = _applied_profiles(apply_cycle_payload)

    status_rows: list[dict[str, Any]] = []
    applied_rows: list[dict[str, Any]] = []
    pending_rows: list[dict[str, Any]] = []

    for row in sorted(
        input_rows,
        key=lambda item: (
            _clean_text(item.get("request_id")) or "",
            _clean_text(item.get("profile_id")) or "",
        ),
    ):
        key = _profile_key(request_id=row.get("request_id"), profile_id=row.get("profile_id"))
        validation_row = validation_by_key.get(key, {})
        applied_row = applied_by_key.get(key, {})
        validation_state_category = _clean_text(row.get("validation_state_category")) or ""
        validation_outcome = _clean_text(validation_row.get("validation_outcome")) or ""
        apply_status_category = _apply_status_category(
            validation_state_category=validation_state_category,
            validation_outcome=validation_outcome,
            applied_to_movement_layer=bool(applied_row),
        )
        status_row = {
            "request_id": key[0],
            "profile_id": key[1],
            "junction_id": _clean_text(row.get("junction_id")) or "",
            "signal_name": _clean_text(row.get("signal_name")) or "",
            "total_row_count": _safe_int(row.get("total_row_count")),
            "ready_row_count": _safe_int(row.get("ready_row_count")),
            "pending_row_count": _safe_int(row.get("pending_row_count")),
            "validation_state_category": validation_state_category,
            "validation_outcome": validation_outcome,
            "batch_outcome": _clean_text(validation_row.get("batch_outcome")) or "",
            "validation_manifest_path": _clean_text(validation_row.get("manifest_path")) or "",
            "delivery_csv_path": _clean_text(row.get("delivery_csv_path")) or "",
            "workbook_path": _clean_text(row.get("workbook_path")) or "",
            "mapping_stub_path": _clean_text(row.get("mapping_stub_path")) or "",
            "validation_command": _clean_text(row.get("validation_command")) or "",
            "apply_status_category": apply_status_category,
            "ingested_manifest_path": _clean_text(applied_row.get("ingested_manifest_path")) or "",
            "movement_signal_phase_manifest_path": _clean_text(
                applied_row.get("movement_signal_phase_manifest_path")
            )
            or "",
            "delivery_session_manifest_path": _clean_text(
                applied_row.get("delivery_session_manifest_path")
            )
            or delivery_session_manifest_path,
        }
        status_row["action_summary"] = _apply_status_summary(
            apply_status_category,
            profile_id=status_row["profile_id"],
            pending_row_count=int(status_row["pending_row_count"]),
        )
        status_row["next_action"] = _next_action(apply_status_category)
        status_rows.append(status_row)
        if apply_status_category == "applied_to_movement_layer":
            applied_rows.append(status_row)
        else:
            pending_rows.append(status_row)

    support_apply_status_path = output_root / "support_apply_status.csv"
    applied_profile_queue_path = output_root / "applied_profile_queue.csv"
    pending_profile_queue_path = output_root / "pending_profile_queue.csv"
    bundle_json_path = output_root / "signal_phase_support_apply_status_bundle.json"
    bundle_md_path = output_root / "signal_phase_support_apply_status_bundle.md"
    manifest_path = output_root / "signal_phase_support_apply_status_bundle.manifest.json"

    fieldnames = [
        "request_id",
        "profile_id",
        "junction_id",
        "signal_name",
        "total_row_count",
        "ready_row_count",
        "pending_row_count",
        "validation_state_category",
        "validation_outcome",
        "batch_outcome",
        "validation_manifest_path",
        "delivery_csv_path",
        "workbook_path",
        "mapping_stub_path",
        "validation_command",
        "apply_status_category",
        "ingested_manifest_path",
        "movement_signal_phase_manifest_path",
        "delivery_session_manifest_path",
        "action_summary",
        "next_action",
    ]
    _write_csv(support_apply_status_path, status_rows, fieldnames)
    _write_csv(applied_profile_queue_path, applied_rows, fieldnames)
    _write_csv(pending_profile_queue_path, pending_rows, fieldnames)

    summary = {
        "profile_count": len(status_rows),
        "applied_profile_count": len(applied_rows),
        "accepted_pending_apply_count": sum(
            1
            for row in status_rows
            if row["apply_status_category"] == "accepted_for_ingestion_pending_apply"
        ),
        "validation_partial_review_count": sum(
            1 for row in status_rows if row["apply_status_category"] == "validation_partial_review"
        ),
        "validation_failed_count": sum(
            1 for row in status_rows if row["apply_status_category"] == "validation_failed"
        ),
        "ready_for_validation_count": sum(
            1
            for row in status_rows
            if row["apply_status_category"] in {"ready_for_validation", "partially_ready_for_validation"}
        ),
        "waiting_for_analyst_resolution_count": sum(
            1 for row in status_rows if row["apply_status_category"] == "waiting_for_analyst_resolution"
        ),
    }
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_apply_status_bundle_version": SIGNAL_PHASE_SUPPORT_APPLY_STATUS_BUNDLE_VERSION,
        "signal_phase_support_apply_status_bundle_contract_version": SIGNAL_PHASE_SUPPORT_APPLY_STATUS_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "status_rows": status_rows,
        "support_apply_status_path": str(support_apply_status_path),
        "applied_profile_queue_path": str(applied_profile_queue_path),
        "pending_profile_queue_path": str(pending_profile_queue_path),
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_status_markdown(payload), encoding="utf-8")

    manifest = {
        "source": {
            "adapter": "bari_signal_phase_support_apply_status_bundle_builder",
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_apply_status_bundle_version": SIGNAL_PHASE_SUPPORT_APPLY_STATUS_BUNDLE_VERSION,
        "contract_version": SIGNAL_PHASE_SUPPORT_APPLY_STATUS_BUNDLE_CONTRACT_VERSION,
        "inputs": {
            "signal_phase_support_status_bundle_path": str(status_bundle_input),
            "signal_phase_support_apply_cycle_path": str(apply_cycle_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(bundle_json_path),
            "report_json_sha256": _sha256(bundle_json_path),
            "report_md_path": str(bundle_md_path),
            "report_md_sha256": _sha256(bundle_md_path),
            "support_apply_status_path": str(support_apply_status_path),
            "support_apply_status_sha256": _sha256(support_apply_status_path),
            "applied_profile_queue_path": str(applied_profile_queue_path),
            "applied_profile_queue_sha256": _sha256(applied_profile_queue_path),
            "pending_profile_queue_path": str(pending_profile_queue_path),
            "pending_profile_queue_sha256": _sha256(pending_profile_queue_path),
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
                "signal_phase_support_apply_cycle",
                apply_cycle_input,
                _sha256(apply_cycle_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_support_apply_status_bundle_json",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_support_apply_status_bundle_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_support_apply_status_csv",
                support_apply_status_path,
                _sha256(support_apply_status_path),
            ),
            _artifact_reference(
                "signal_phase_support_applied_profile_queue_csv",
                applied_profile_queue_path,
                _sha256(applied_profile_queue_path),
            ),
            _artifact_reference(
                "signal_phase_support_pending_profile_queue_csv",
                pending_profile_queue_path,
                _sha256(pending_profile_queue_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
