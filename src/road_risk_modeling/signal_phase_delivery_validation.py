"""Validate received signal-phase deliveries against mapping stubs and checklist rows."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_ingestion import _load_json, _map_row, _normalized_record


SIGNAL_PHASE_DELIVERY_VALIDATION_VERSION = "signal_phase_delivery_validation_v1"
SIGNAL_PHASE_DELIVERY_VALIDATION_CONTRACT_VERSION = "signal_phase_delivery_validation_public_v1"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _resolve_expected_columns(mapping_stub: dict[str, Any]) -> tuple[list[str], list[str]]:
    required: list[str] = []
    optional: list[str] = []
    for mapping in mapping_stub.get("field_mappings", []):
        source_field = _clean_text(mapping.get("source_field")) or ""
        target_field = _clean_text(mapping.get("target_field")) or ""
        expected = target_field
        if source_field and not source_field.startswith("TODO_"):
            expected = source_field
        elif source_field.startswith("TODO_") and "__" in source_field:
            expected = source_field.split("__", 1)[1]
        if bool(mapping.get("required")):
            required.append(expected)
        else:
            optional.append(expected)
    return required, optional


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _recommendation_for_outcome(outcome: str) -> str:
    if outcome == "accepted_for_ingestion":
        return "validated_ready_for_ingestion"
    if outcome == "accepted_support_artifact":
        return "validated_support_artifact"
    if outcome == "accepted_with_rejections":
        return "partial_validation_review"
    if outcome == "empty_delivery":
        return "provider_fix_required"
    return "provider_fix_required"


def _infer_outcome(*, required_columns_missing: int, total_rows: int, accepted_rows: int, rejected_rows: int) -> str:
    if required_columns_missing > 0:
        return "schema_not_ready"
    if total_rows == 0:
        return "empty_delivery"
    if accepted_rows == 0:
        return "provider_fix_required"
    if rejected_rows > 0:
        return "accepted_with_rejections"
    return "accepted_for_ingestion"


def _infer_support_outcome(
    *,
    file_exists: bool,
    file_size_bytes: int,
    extension_allowed: bool,
) -> str:
    if not file_exists:
        return "empty_delivery"
    if file_size_bytes <= 0:
        return "empty_delivery"
    if not extension_allowed:
        return "provider_fix_required"
    return "accepted_support_artifact"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _support_artifact_preview(
    *,
    input_path: Path,
    mapping_stub: dict[str, Any],
    request_id: str | None,
    junction_id: str | None,
    file_size_bytes: int,
) -> dict[str, Any]:
    profile_id = str(mapping_stub.get("profile_id") or "unknown_profile")
    return {
        "signal_phase_support_artifact_id": ":".join(
            [
                profile_id,
                junction_id or "unknown_junction",
                input_path.name,
            ]
        ),
        "profile_id": profile_id,
        "profile_label": mapping_stub.get("profile_label"),
        "profile_type": mapping_stub.get("profile_type"),
        "record_kind": "signal_phase_support_artifact",
        "junction_id": junction_id,
        "request_id": request_id,
        "support_file_name": input_path.name,
        "support_file_extension": input_path.suffix.lower(),
        "support_file_size_bytes": file_size_bytes,
        "support_file_path": str(input_path),
    }


def _report_markdown(payload: dict[str, Any]) -> str:
    is_support_artifact = payload["profile"].get("profile_type") == "support_artifact"
    lines = [
        "# Signal-Phase Delivery Validation Report",
        "",
        f"As of {payload['generated_at_utc']}, the received delivery has been validated against the mapping stub and Bari checklist context.",
        "",
        "## Summary",
        "",
        f"- Profile: `{payload['profile']['profile_id']}`",
        f"- Outcome: `{payload['stats']['validation_outcome']}`",
        f"- Total rows: `{payload['stats']['total_rows']}`",
        f"- Accepted rows: `{payload['stats']['accepted_rows']}`",
        f"- Rejected rows: `{payload['stats']['rejected_rows']}`",
        f"- Matched checklist rows: `{payload['stats']['matched_checklist_rows']}`",
        "",
        "## Schema Check",
        "",
        f"- Required expected columns: `{payload['schema']['required_expected_columns']}`",
        f"- Missing required columns: `{payload['schema']['missing_required_columns']}`",
        f"- Input columns: `{payload['schema']['input_columns']}`",
        "",
    ]
    if is_support_artifact:
        lines.extend(
            [
                "## Support Artifact Check",
                "",
                f"- Allowed extensions: `{payload['schema']['allowed_support_extensions']}`",
                f"- Detected extension: `{payload['schema']['detected_support_extension']}`",
                f"- File size bytes: `{payload['stats']['support_file_size_bytes']}`",
                "",
            ]
        )
    lines.extend(
        [
        "## Next Step",
        "",
        f"Apply checklist recommendation `{payload['stats']['suggested_delivery_status']}` before deciding whether to run the normalized ingestion path.",
        "",
        ]
    )
    return "\n".join(lines)


def validate_signal_phase_delivery(
    input_csv_path: str | Path,
    mapping_stub_path: str | Path,
    output_dir: str | Path,
    *,
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    request_id: str | None = None,
    junction_id: str | None = None,
    preview_limit: int = 10,
) -> dict[str, Any]:
    input_delivery = Path(input_csv_path)
    mapping_stub_input = Path(mapping_stub_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    checklist_path = Path(delivery_checklist_path)
    mapping_stub = _load_json(mapping_stub_input)
    profile_id = str(mapping_stub.get("profile_id") or "unknown_profile")
    profile_type = str(mapping_stub.get("profile_type") or "unknown_profile_type")

    report_json_path = output_root / "signal_phase_delivery_validation.json"
    report_md_path = output_root / "signal_phase_delivery_validation.md"
    preview_records_path = output_root / "accepted_preview.jsonl"
    rejected_rows_path = output_root / "rejected_rows.jsonl"
    checklist_recommendations_path = output_root / "checklist_recommendations.csv"
    manifest_path = output_root / "signal_phase_delivery_validation.manifest.json"

    required_expected_columns, optional_expected_columns = _resolve_expected_columns(mapping_stub)
    total_rows = 0
    accepted_rows = 0
    rejected_rows = 0
    preview_rows_written = 0
    quality_flag_counts: dict[str, int] = {}
    junction_ids_found: set[str] = set()
    input_columns: list[str] = []
    support_extensions = [
        str(extension).strip().lower()
        for extension in (mapping_stub.get("support_validation", {}) or {}).get("allowed_extensions", [])
        if str(extension).strip()
    ]
    detected_support_extension = input_delivery.suffix.lower()
    support_file_size_bytes = input_delivery.stat().st_size if input_delivery.exists() else 0
    missing_required_columns: list[str] = []

    if profile_type == "support_artifact":
        extension_allowed = detected_support_extension in set(support_extensions)
        validation_outcome = _infer_support_outcome(
            file_exists=input_delivery.exists(),
            file_size_bytes=support_file_size_bytes,
            extension_allowed=extension_allowed,
        )
        if junction_id:
            junction_ids_found.add(junction_id)
        if validation_outcome == "accepted_support_artifact":
            total_rows = 1
            accepted_rows = 1
            preview_rows_written = 1 if preview_limit > 0 else 0
            preview_rows = []
            if preview_limit > 0:
                preview_rows.append(
                    _support_artifact_preview(
                        input_path=input_delivery,
                        mapping_stub=mapping_stub,
                        request_id=request_id,
                        junction_id=junction_id,
                        file_size_bytes=support_file_size_bytes,
                    )
                )
            _write_jsonl(preview_records_path, preview_rows)
            _write_jsonl(rejected_rows_path, [])
        else:
            total_rows = 1 if input_delivery.exists() else 0
            rejected_rows = 1 if input_delivery.exists() else 0
            issue_code = (
                f"unsupported_support_extension:{detected_support_extension or 'none'}"
                if input_delivery.exists() and not extension_allowed
                else "empty_support_artifact"
            )
            quality_flag_counts[issue_code] = 1
            _write_jsonl(preview_records_path, [])
            _write_jsonl(
                rejected_rows_path,
                [
                    {
                        "row_number": 1,
                        "errors": [issue_code],
                        "row": {
                            "input_path": str(input_delivery),
                            "file_extension": detected_support_extension,
                            "file_size_bytes": support_file_size_bytes,
                        },
                    }
                ]
                if input_delivery.exists()
                else [],
            )
    else:
        with input_delivery.open(encoding="utf-8", newline="") as input_handle, preview_records_path.open(
            "w",
            encoding="utf-8",
        ) as preview_handle, rejected_rows_path.open("w", encoding="utf-8") as rejected_handle:
            reader = csv.DictReader(input_handle)
            input_columns = list(reader.fieldnames or [])
            missing_required_columns = [column for column in required_expected_columns if column not in input_columns]
            for row in reader:
                total_rows += 1
                mapped, errors = _map_row(row, mapping_stub)
                mapped_junction_id = _clean_text(mapped.get("junction_id"))
                if mapped_junction_id:
                    junction_ids_found.add(mapped_junction_id)
                if errors:
                    rejected_rows += 1
                    rejected_handle.write(
                        json.dumps(
                            {"row_number": total_rows, "errors": errors, "row": row},
                            ensure_ascii=True,
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    for error in errors:
                        quality_flag_counts[error] = quality_flag_counts.get(error, 0) + 1
                    continue
                accepted_rows += 1
                if preview_rows_written < preview_limit:
                    preview_handle.write(
                        json.dumps(_normalized_record(mapped, mapping_stub), ensure_ascii=True, sort_keys=True) + "\n"
                    )
                    preview_rows_written += 1

        if total_rows == 0:
            missing_required_columns = [column for column in required_expected_columns if column not in input_columns]

    checklist_rows: list[dict[str, str]] = []
    if checklist_path.exists():
        with checklist_path.open(encoding="utf-8", newline="") as handle:
            checklist_rows = list(csv.DictReader(handle))

    matched_checklist_rows = [
        row
        for row in checklist_rows
        if row.get("profile_id") == profile_id
        and (request_id is None or row.get("request_id") == request_id)
        and (
            junction_id is not None
            and row.get("junction_id") == junction_id
            or junction_id is None
            and (not junction_ids_found or row.get("junction_id") in junction_ids_found)
        )
    ]

    if profile_type != "support_artifact":
        validation_outcome = _infer_outcome(
            required_columns_missing=len(missing_required_columns),
            total_rows=total_rows,
            accepted_rows=accepted_rows,
            rejected_rows=rejected_rows,
        )
    suggested_delivery_status = _recommendation_for_outcome(validation_outcome)
    checklist_recommendations = [
        {
            "delivery_item_id": row["delivery_item_id"],
            "request_id": row["request_id"],
            "junction_id": row["junction_id"],
            "profile_id": row["profile_id"],
            "current_delivery_status": row["delivery_status"],
            "suggested_delivery_status": suggested_delivery_status,
            "validation_outcome": validation_outcome,
        }
        for row in matched_checklist_rows
    ]
    _write_csv(
        checklist_recommendations_path,
        checklist_recommendations,
        [
            "delivery_item_id",
            "request_id",
            "junction_id",
            "profile_id",
            "current_delivery_status",
            "suggested_delivery_status",
            "validation_outcome",
        ],
    )

    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "total_rows": total_rows,
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "preview_rows_written": preview_rows_written,
        "matched_checklist_rows": len(matched_checklist_rows),
        "validation_outcome": validation_outcome,
        "suggested_delivery_status": suggested_delivery_status,
        "quality_flag_counts": quality_flag_counts,
        "junction_ids_found": sorted(junction_ids_found),
        "support_file_size_bytes": support_file_size_bytes if profile_type == "support_artifact" else 0,
    }
    payload = {
        "signal_phase_delivery_validation_version": SIGNAL_PHASE_DELIVERY_VALIDATION_VERSION,
        "signal_phase_delivery_validation_contract_version": SIGNAL_PHASE_DELIVERY_VALIDATION_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "source": {
            "adapter": "signal_phase_delivery_validator",
        },
        "profile": {
            "profile_id": profile_id,
            "profile_label": mapping_stub.get("profile_label"),
            "profile_type": profile_type,
        },
        "schema": {
            "required_expected_columns": required_expected_columns,
            "optional_expected_columns": optional_expected_columns,
            "missing_required_columns": missing_required_columns,
            "input_columns": input_columns,
            "allowed_support_extensions": support_extensions,
            "detected_support_extension": detected_support_extension if profile_type == "support_artifact" else "",
        },
        "inputs": {
            "input_csv_path": {
                "path": str(input_delivery),
                "role": "signal_phase_input_delivery",
                "sha256": _sha256(input_delivery),
            },
            "mapping_stub_path": {
                "path": str(mapping_stub_input),
                "role": "signal_phase_mapping_stub_json",
                "sha256": _sha256(mapping_stub_input),
            },
            "delivery_checklist_path": {
                "path": str(checklist_path),
                "role": "signal_phase_delivery_checklist",
                "sha256": _sha256(checklist_path) if checklist_path.exists() else None,
            },
            "request_id": request_id,
            "junction_id": junction_id,
            "preview_limit": preview_limit,
        },
        "stats": stats,
        "outputs": {
            "report_json_path": str(report_json_path),
            "report_md_path": str(report_md_path),
            "accepted_preview_path": str(preview_records_path),
            "rejected_rows_path": str(rejected_rows_path),
            "checklist_recommendations_path": str(checklist_recommendations_path),
            "manifest_path": str(manifest_path),
        },
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_report_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_delivery_validation_version": SIGNAL_PHASE_DELIVERY_VALIDATION_VERSION,
        "contract": {
            "resource_name": "signal_phase_delivery_validation",
            "public_contract_version": SIGNAL_PHASE_DELIVERY_VALIDATION_CONTRACT_VERSION,
            "signal_phase_delivery_validation_version": SIGNAL_PHASE_DELIVERY_VALIDATION_VERSION,
        },
        "source": {
            "adapter": "signal_phase_delivery_validator",
        },
        "profile": payload["profile"],
        "schema": payload["schema"],
        "stats": stats,
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "accepted_preview_path": str(preview_records_path),
            "accepted_preview_sha256": _sha256(preview_records_path),
            "rejected_rows_path": str(rejected_rows_path),
            "rejected_rows_sha256": _sha256(rejected_rows_path),
            "checklist_recommendations_path": str(checklist_recommendations_path),
            "checklist_recommendations_sha256": _sha256(checklist_recommendations_path),
        },
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_input_delivery", input_delivery, _sha256(input_delivery)),
                _artifact_reference("signal_phase_mapping_stub_json", mapping_stub_input, _sha256(mapping_stub_input)),
            ]
            + (
                [_artifact_reference("signal_phase_delivery_checklist", checklist_path, _sha256(checklist_path))]
                if checklist_path.exists()
                else []
            ),
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_delivery_validation_report", report_json_path, _sha256(report_json_path)),
                _artifact_reference("signal_phase_delivery_validation_markdown", report_md_path, _sha256(report_md_path)),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_delivery_preview_jsonl", preview_records_path, _sha256(preview_records_path)),
                _artifact_reference("signal_phase_delivery_rejected_rows_jsonl", rejected_rows_path, _sha256(rejected_rows_path)),
                _artifact_reference(
                    "signal_phase_delivery_checklist_recommendations_csv",
                    checklist_recommendations_path,
                    _sha256(checklist_recommendations_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_delivery_validation_version": SIGNAL_PHASE_DELIVERY_VALIDATION_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
    }
