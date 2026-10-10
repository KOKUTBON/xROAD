"""Upload-center oriented ingestion job registration and validation helpers."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import io
import json
from pathlib import Path
import tempfile
import traceback
from typing import Any, Callable

from apps.api.db import repositories
from apps.api.settings import get_settings
from apps.api.storage import get_bytes, parse_storage_uri, resolve_artifact_download
import apps.api.services.artifact_storage as artifact_storage
import apps.api.services.postgis_domain as postgis_domain
from road_risk_modeling.exposure_connector_ingestion import ingest_exposure_connector_extract
from road_risk_modeling.ingestion import ingest_bari_open_data_crashes


INGESTION_UPLOAD_CONTRACT_VERSION = "ingestion_upload_contract_v1"
INGESTION_VALIDATION_CONTRACT_VERSION = "ingestion_validation_contract_v1"
INGESTION_VALIDATION_LOG_VERSION = "ingestion_validation_log_v1"
INGESTION_UPLOAD_CENTER_CONTRACT_VERSION = "ingestion_upload_center_v1"
INGESTION_EXECUTION_CONTRACT_VERSION = "ingestion_execution_contract_v1"
INGESTION_EXECUTION_LOG_VERSION = "ingestion_execution_log_v1"
INGESTION_EXECUTION_TASK_NAME = "services.workers.tasks.ingestion.run_job"

INGESTION_STATUS_PENDING_UPLOAD = "pending_upload"
INGESTION_STATUS_VALIDATING = "validating"
INGESTION_STATUS_VALIDATED_READY = "validated_ready"
INGESTION_STATUS_VALIDATED_WITH_ERRORS = "validated_with_errors"
INGESTION_STATUS_VALIDATION_FAILED = "validation_failed"
INGESTION_STATUS_APPROVED = "approved"
INGESTION_STATUS_MANUAL_REVIEW_REQUIRED = "manual_review_required"
INGESTION_STATUS_MANUAL_REVIEW = "manual_review"
INGESTION_STATUS_FAILED = "failed"
INGESTION_STATUS_QUEUED = "queued"
INGESTION_STATUS_RUNNING = "running"
INGESTION_STATUS_COMPLETED = "completed"
INGESTION_STATUS_CANCELLED = "cancelled"
INGESTION_STATUS_REJECTED = "rejected"

APPROVED_GOVERNANCE_STATUSES = frozenset({"approved"})
ACTIVE_SOURCE_STATUSES = frozenset({"active"})
EXECUTABLE_CRASH_SOURCE_TYPES = frozenset({"crash_feed", "crash_csv", "crash_records"})
EXECUTABLE_EXPOSURE_SOURCE_TYPES = frozenset({"exposure_connector", "exposure_connector_extract"})
APPROVABLE_INGESTION_STATUSES = frozenset(
    {
        INGESTION_STATUS_VALIDATED_READY,
        INGESTION_STATUS_VALIDATED_WITH_ERRORS,
        INGESTION_STATUS_MANUAL_REVIEW_REQUIRED,
    }
)
REJECTABLE_INGESTION_STATUSES = APPROVABLE_INGESTION_STATUSES | frozenset(
    {
        INGESTION_STATUS_PENDING_UPLOAD,
        INGESTION_STATUS_VALIDATION_FAILED,
        INGESTION_STATUS_FAILED,
        INGESTION_STATUS_MANUAL_REVIEW,
    }
)
RUNNABLE_INGESTION_STATUSES = frozenset({INGESTION_STATUS_QUEUED, INGESTION_STATUS_APPROVED})
RETRYABLE_INGESTION_STATUSES = frozenset(
    {
        INGESTION_STATUS_FAILED,
        INGESTION_STATUS_CANCELLED,
        INGESTION_STATUS_MANUAL_REVIEW,
    }
)
CANCELLABLE_INGESTION_STATUSES = frozenset({INGESTION_STATUS_QUEUED, INGESTION_STATUS_RUNNING})
SUPPORTED_UPLOAD_FORMATS = ("csv", "geojson", "json", "zip")

StorageReader = Callable[[str], bytes]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize(value: str | None, *, default: str = "") -> str:
    return (value or default).strip().lower()


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    resolved = str(value).strip()
    return resolved or None


def read_storage_bytes(storage_uri: str) -> bytes:
    storage_object = parse_storage_uri(storage_uri)
    return get_bytes(storage_object.key, bucket=storage_object.bucket)


def _data_source_snapshot(source: Any | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "source_id": str(source.id),
        "name": source.name,
        "source_type": source.source_type,
        "provider_name": source.provider_name,
        "organization_id": str(source.organization_id),
        "municipality_id": _as_optional_str(source.municipality_id),
        "governance_status": source.governance_status,
        "publication_tier": source.publication_tier,
        "status": source.status,
        "configuration": dict(source.configuration_json or {}),
    }


def _data_source_upload_row(source: Any) -> dict[str, Any]:
    configuration = dict(getattr(source, "configuration_json", {}) or {})
    upload_enabled = _normalize(getattr(source, "status", None)) in ACTIVE_SOURCE_STATUSES
    if not upload_enabled:
        blocked_reason = f"Source status `{getattr(source, 'status', None)}` does not accept uploads."
    elif _normalize(getattr(source, "governance_status", None)) not in APPROVED_GOVERNANCE_STATUSES:
        blocked_reason = "Source can register uploads, but validation will block until governance is approved."
    else:
        blocked_reason = None
    return {
        **(_data_source_snapshot(source) or {}),
        "required_columns": _required_columns(source),
        "supported_formats": list(SUPPORTED_UPLOAD_FORMATS),
        "upload_enabled": upload_enabled,
        "blocked_reason": blocked_reason,
        "schema_hints": {
            "delimiter": configuration.get("delimiter"),
            "preview_row_limit": configuration.get("preview_row_limit"),
            "scan_row_limit": configuration.get("scan_row_limit"),
        },
    }


def _publication_tier(source: Any | None) -> str:
    return getattr(source, "publication_tier", None) or "restricted"


def _job_scope_snapshot(job: Any) -> dict[str, Any]:
    return {
        "job_id": str(job.id),
        "organization_id": str(job.organization_id),
        "municipality_id": _as_optional_str(job.municipality_id),
        "source_id": _as_optional_str(job.source_id),
        "job_type": job.job_type,
    }


def _job_filename(job: Any) -> str:
    parameters = dict(job.parameters_json or {})
    return str(parameters.get("original_filename") or parameters.get("filename") or "upload.bin")


def _content_type(job: Any) -> str | None:
    parameters = dict(job.parameters_json or {})
    content_type = parameters.get("content_type")
    return str(content_type) if content_type else None


def _field_mapping(job: Any) -> dict[str, str]:
    parameters = dict(job.parameters_json or {})
    raw_mapping = parameters.get("field_mapping") or parameters.get("schema_mapping") or {}
    if not isinstance(raw_mapping, dict):
        return {}
    return {
        str(canonical).strip(): str(uploaded).strip()
        for canonical, uploaded in raw_mapping.items()
        if str(canonical).strip() and str(uploaded).strip()
    }


def _job_log_storage_uri(job: Any) -> str | None:
    return _as_optional_str(dict(job.job_stats_json or {}).get("log_storage_uri"))


def _workflow_stage(status: str, stats: dict[str, Any]) -> dict[str, Any]:
    can_validate = status == INGESTION_STATUS_PENDING_UPLOAD
    can_approve = status in APPROVABLE_INGESTION_STATUSES
    can_reject = status in REJECTABLE_INGESTION_STATUSES
    can_run = status in RUNNABLE_INGESTION_STATUSES
    can_retry = status in RETRYABLE_INGESTION_STATUSES
    can_cancel = status in CANCELLABLE_INGESTION_STATUSES
    if status == INGESTION_STATUS_PENDING_UPLOAD:
        required_next_action = "upload_object_then_validate"
    elif status == INGESTION_STATUS_VALIDATING:
        required_next_action = "wait_for_validation_result"
    elif status in APPROVABLE_INGESTION_STATUSES:
        required_next_action = "review_validation_then_approve_or_reject"
    elif status == INGESTION_STATUS_QUEUED:
        required_next_action = "run_ingestion_worker_execution"
    elif status == INGESTION_STATUS_RUNNING:
        required_next_action = "wait_for_ingestion_worker_completion"
    elif status == INGESTION_STATUS_COMPLETED:
        required_next_action = "review_completed_artifacts"
    elif status == INGESTION_STATUS_FAILED:
        required_next_action = "review_failure_then_retry_or_cancel"
    elif status == INGESTION_STATUS_CANCELLED:
        required_next_action = "retry_or_archive_cancelled_job"
    elif status == INGESTION_STATUS_MANUAL_REVIEW:
        required_next_action = "complete_manual_execution_review"
    elif status == INGESTION_STATUS_REJECTED:
        required_next_action = "no_action_rejected"
    else:
        required_next_action = stats.get("required_next_action") or "review_status"
    return {
        "lifecycle_stage": stats.get("lifecycle_stage") or status,
        "required_next_action": required_next_action,
        "can_validate": can_validate,
        "can_approve": can_approve,
        "can_reject": can_reject,
        "can_run": can_run,
        "can_retry": can_retry,
        "can_cancel": can_cancel,
        "progress_steps": [
            {
                "step": "register_upload",
                "status": "completed" if status != INGESTION_STATUS_PENDING_UPLOAD else "active",
            },
            {
                "step": "validate_payload",
                "status": (
                    "completed"
                    if status
                    in {
                        INGESTION_STATUS_VALIDATED_READY,
                        INGESTION_STATUS_VALIDATED_WITH_ERRORS,
                        INGESTION_STATUS_VALIDATION_FAILED,
                        INGESTION_STATUS_MANUAL_REVIEW_REQUIRED,
                        INGESTION_STATUS_QUEUED,
                        INGESTION_STATUS_RUNNING,
                        INGESTION_STATUS_COMPLETED,
                        INGESTION_STATUS_FAILED,
                        INGESTION_STATUS_CANCELLED,
                        INGESTION_STATUS_MANUAL_REVIEW,
                        INGESTION_STATUS_REJECTED,
                    }
                    else "active"
                    if status == INGESTION_STATUS_VALIDATING
                    else "pending"
                ),
            },
            {
                "step": "operator_decision",
                "status": (
                    "completed"
                    if status
                    in {
                        INGESTION_STATUS_QUEUED,
                        INGESTION_STATUS_RUNNING,
                        INGESTION_STATUS_COMPLETED,
                        INGESTION_STATUS_FAILED,
                        INGESTION_STATUS_CANCELLED,
                        INGESTION_STATUS_MANUAL_REVIEW,
                        INGESTION_STATUS_REJECTED,
                    }
                    else "active"
                    if can_approve
                    else "pending"
                ),
            },
            {
                "step": "execute_ingestion",
                "status": (
                    "completed"
                    if status == INGESTION_STATUS_COMPLETED
                    else "failed"
                    if status in {INGESTION_STATUS_FAILED, INGESTION_STATUS_MANUAL_REVIEW}
                    else "cancelled"
                    if status == INGESTION_STATUS_CANCELLED
                    else "active"
                    if status == INGESTION_STATUS_RUNNING
                    else "ready"
                    if status == INGESTION_STATUS_QUEUED
                    else "pending"
                ),
            },
        ],
    }


def _build_job_type(source: Any) -> str:
    return f"{source.source_type}_ingestion"


def _delimiter_for_text(text: str, configured_delimiter: str | None) -> str:
    if configured_delimiter:
        return configured_delimiter
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        if sample.count("\t") > sample.count(","):
            return "\t"
        if sample.count(";") > sample.count(","):
            return ";"
        return ","


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        resolved_key = str(key or "").strip()
        if isinstance(value, str):
            cleaned[resolved_key] = value.strip()
        else:
            cleaned[resolved_key] = value
    return cleaned


def _required_columns(source: Any | None) -> list[str]:
    configuration = dict(getattr(source, "configuration_json", {}) or {})
    raw_required = configuration.get("required_columns") or []
    return [str(column).strip() for column in raw_required if str(column).strip()]


def _mapped_column(column: str, field_mapping: dict[str, str]) -> str:
    return field_mapping.get(column, column)


def _missing_required_columns(
    required_columns: list[str],
    detected_columns: list[str],
    field_mapping: dict[str, str],
) -> list[str]:
    detected = set(detected_columns)
    return [column for column in required_columns if _mapped_column(column, field_mapping) not in detected]


def _value_for_column(
    row: dict[str, Any],
    column: str,
    field_mapping: dict[str, str],
) -> Any:
    return row.get(_mapped_column(column, field_mapping))


def _coordinate_columns(
    detected_columns: list[str],
    field_mapping: dict[str, str],
) -> tuple[str | None, str | None]:
    lowered = {column.lower(): column for column in detected_columns}
    lat_candidates = ("latitude", "lat", "y")
    lon_candidates = ("longitude", "lon", "lng", "x")
    mapped_lat = field_mapping.get("latitude") or field_mapping.get("lat")
    mapped_lon = field_mapping.get("longitude") or field_mapping.get("lon") or field_mapping.get("lng")
    lat_column = mapped_lat if mapped_lat in detected_columns else None
    lon_column = mapped_lon if mapped_lon in detected_columns else None
    if lat_column is None:
        lat_column = next((lowered[name] for name in lat_candidates if name in lowered), None)
    if lon_column is None:
        lon_column = next((lowered[name] for name in lon_candidates if name in lowered), None)
    return lat_column, lon_column


def _invalid_coordinate_error(
    row_number: int,
    row: dict[str, Any],
    *,
    lat_column: str | None,
    lon_column: str | None,
) -> dict[str, Any] | None:
    if lat_column is None or lon_column is None:
        return None
    try:
        lat = float(str(row.get(lat_column) or "").replace(",", "."))
        lon = float(str(row.get(lon_column) or "").replace(",", "."))
    except ValueError:
        return {
            "row_number": row_number,
            "error_code": "invalid_coordinates",
            "message": "Row contains non-numeric latitude or longitude values.",
            "values": {lat_column: row.get(lat_column), lon_column: row.get(lon_column)},
        }
    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return {
            "row_number": row_number,
            "error_code": "invalid_coordinates",
            "message": "Row latitude or longitude is outside valid WGS84 bounds.",
            "values": {lat_column: row.get(lat_column), lon_column: row.get(lon_column)},
        }
    return None


def _row_fingerprint(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in row.items()))


def _preview_limits(source: Any | None) -> tuple[int, int, int]:
    configuration = dict(getattr(source, "configuration_json", {}) or {})
    preview_row_limit = int(configuration.get("preview_row_limit") or 10)
    error_excerpt_limit = int(configuration.get("error_excerpt_limit") or 25)
    scan_row_limit = int(configuration.get("scan_row_limit") or 500)
    return max(preview_row_limit, 1), max(error_excerpt_limit, 1), max(scan_row_limit, 1)


def _governance_checks(source: Any | None, job: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if source is None:
        return [
            {
                "check": "source_exists",
                "status": "failed",
                "message": "Referenced data source could not be resolved for this ingestion job.",
            }
        ]

    if _normalize(source.status) in ACTIVE_SOURCE_STATUSES:
        checks.append(
            {
                "check": "source_status",
                "status": "passed",
                "message": f"Source status `{source.status}` allows upload validation.",
            }
        )
    else:
        checks.append(
            {
                "check": "source_status",
                "status": "failed",
                "message": f"Source status `{source.status}` blocks ingestion validation.",
            }
        )

    if _normalize(source.governance_status) in APPROVED_GOVERNANCE_STATUSES:
        checks.append(
            {
                "check": "governance_approval",
                "status": "passed",
                "message": f"Governance status `{source.governance_status}` is approved for ingestion.",
            }
        )
    else:
        checks.append(
            {
                "check": "governance_approval",
                "status": "failed",
                "message": (
                    f"Governance status `{source.governance_status}` is not approved for ingestion."
                ),
            }
        )

    source_municipality_id = _as_optional_str(source.municipality_id)
    job_municipality_id = _as_optional_str(job.municipality_id)
    if source_municipality_id and job_municipality_id and source_municipality_id != job_municipality_id:
        checks.append(
            {
                "check": "municipality_scope",
                "status": "failed",
                "message": (
                    f"Source municipality `{source_municipality_id}` does not match job municipality "
                    f"`{job_municipality_id}`."
                ),
            }
        )
    else:
        checks.append(
            {
                "check": "municipality_scope",
                "status": "passed",
                "message": "Source municipality scope aligns with the ingestion job.",
            }
        )

    parameters = dict(job.parameters_json or {})
    requested_tier = _normalize(parameters.get("publication_tier"), default=_publication_tier(source))
    source_tier = _normalize(source.publication_tier, default="restricted")
    if requested_tier == source_tier:
        checks.append(
            {
                "check": "publication_tier",
                "status": "passed",
                "message": f"Upload tier `{requested_tier}` matches the governed source tier.",
            }
        )
    else:
        checks.append(
            {
                "check": "publication_tier",
                "status": "failed",
                "message": (
                    f"Upload tier `{requested_tier}` does not match source tier `{source_tier}`."
                ),
            }
        )
    return checks


def _governance_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [check for check in checks if check["status"] != "passed"]
    return {
        "checks": checks,
        "status": "approved" if not failed else "blocked",
        "failed_check_count": len(failed),
    }


def _validate_csv_text(
    text: str,
    *,
    required_columns: list[str],
    field_mapping: dict[str, str],
    configured_delimiter: str | None,
    preview_row_limit: int,
    error_excerpt_limit: int,
    scan_row_limit: int,
) -> dict[str, Any]:
    normalized_text = text.lstrip("\ufeff")
    if not normalized_text.strip():
        return {
            "format": "csv",
            "delimiter": configured_delimiter or ",",
            "detected_columns": [],
            "missing_required_columns": list(required_columns),
            "field_mapping": dict(field_mapping),
            "preview_rows": [],
            "row_errors": [
                {
                    "row_number": None,
                    "error_code": "empty_upload",
                    "message": "Uploaded file is empty.",
                }
            ],
            "scanned_row_count": 0,
            "preview_row_count": 0,
            "accepted_preview_rows": 0,
            "rejected_preview_rows": 0,
            "invalid_coordinate_count": 0,
            "duplicate_row_count": 0,
            "truncated": False,
        }

    delimiter = _delimiter_for_text(normalized_text, configured_delimiter)
    reader = csv.DictReader(io.StringIO(normalized_text), delimiter=delimiter)
    detected_columns = [str(column).strip() for column in (reader.fieldnames or []) if str(column).strip()]
    missing_required_columns = _missing_required_columns(required_columns, detected_columns, field_mapping)
    lat_column, lon_column = _coordinate_columns(detected_columns, field_mapping)
    preview_rows: list[dict[str, Any]] = []
    row_errors: list[dict[str, Any]] = []
    scanned_row_count = 0
    accepted_preview_rows = 0
    rejected_preview_rows = 0
    invalid_coordinate_count = 0
    duplicate_row_count = 0
    truncated = False
    seen_rows: set[tuple[tuple[str, str], ...]] = set()

    if missing_required_columns:
        row_errors.append(
            {
                "row_number": None,
                "error_code": "missing_required_columns",
                "message": "Input file is missing required columns.",
                "missing_required_columns": missing_required_columns,
            }
        )

    for row_number, row in enumerate(reader, start=2):
        if scanned_row_count >= scan_row_limit:
            truncated = True
            break
        scanned_row_count += 1
        cleaned_row = _clean_row(row)
        if len(preview_rows) < preview_row_limit:
            preview_rows.append({"row_number": row_number, "values": cleaned_row})

        row_missing = [
            column
            for column in required_columns
            if not str(_value_for_column(cleaned_row, column, field_mapping) or "").strip()
        ]
        row_failed = False
        if row_missing:
            row_failed = True
            rejected_preview_rows += 1
            if len(row_errors) < error_excerpt_limit:
                row_errors.append(
                    {
                        "row_number": row_number,
                        "error_code": "missing_required_values",
                        "message": "Row is missing one or more required values.",
                        "missing_required_columns": row_missing,
                        "values": {
                            _mapped_column(column, field_mapping): _value_for_column(
                                cleaned_row,
                                column,
                                field_mapping,
                            )
                            for column in row_missing
                        },
                    }
                )

        coordinate_error = _invalid_coordinate_error(
            row_number,
            cleaned_row,
            lat_column=lat_column,
            lon_column=lon_column,
        )
        if coordinate_error is not None:
            invalid_coordinate_count += 1
            if not row_failed:
                rejected_preview_rows += 1
                row_failed = True
            if len(row_errors) < error_excerpt_limit:
                row_errors.append(coordinate_error)

        fingerprint = _row_fingerprint(cleaned_row)
        if fingerprint in seen_rows:
            duplicate_row_count += 1
            if not row_failed:
                rejected_preview_rows += 1
                row_failed = True
            if len(row_errors) < error_excerpt_limit:
                row_errors.append(
                    {
                        "row_number": row_number,
                        "error_code": "duplicate_record",
                        "message": "Row duplicates an earlier scanned record.",
                    }
                )
        else:
            seen_rows.add(fingerprint)

        if not row_failed:
            accepted_preview_rows += 1

    return {
        "format": "csv",
        "delimiter": delimiter,
        "detected_columns": detected_columns,
        "missing_required_columns": missing_required_columns,
        "field_mapping": dict(field_mapping),
        "preview_rows": preview_rows,
        "row_errors": row_errors,
        "scanned_row_count": scanned_row_count,
        "preview_row_count": len(preview_rows),
        "accepted_preview_rows": accepted_preview_rows,
        "rejected_preview_rows": rejected_preview_rows,
        "invalid_coordinate_count": invalid_coordinate_count,
        "duplicate_row_count": duplicate_row_count,
        "truncated": truncated,
    }


def _validate_json_text(
    text: str,
    *,
    required_columns: list[str],
    field_mapping: dict[str, str],
    preview_row_limit: int,
    error_excerpt_limit: int,
    scan_row_limit: int,
) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {
            "format": "json",
            "detected_columns": [],
            "missing_required_columns": list(required_columns),
            "field_mapping": dict(field_mapping),
            "preview_rows": [],
            "row_errors": [
                {
                    "row_number": None,
                    "error_code": "json_decode_error",
                    "message": str(exc),
                }
            ],
            "scanned_row_count": 0,
            "preview_row_count": 0,
            "accepted_preview_rows": 0,
            "rejected_preview_rows": 0,
            "invalid_coordinate_count": 0,
            "duplicate_row_count": 0,
            "truncated": False,
        }

    records: list[dict[str, Any]]
    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        records = [
            _clean_row(feature.get("properties") or {})
            for feature in payload["features"]
            if isinstance(feature, dict)
        ]
    elif isinstance(payload, list):
        records = [_clean_row(item) for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        records = [_clean_row(payload)]
    else:
        records = []

    detected_columns: list[str] = []
    for record in records:
        for key in record:
            if key not in detected_columns:
                detected_columns.append(key)

    missing_required_columns = _missing_required_columns(required_columns, detected_columns, field_mapping)
    lat_column, lon_column = _coordinate_columns(detected_columns, field_mapping)
    preview_rows: list[dict[str, Any]] = []
    row_errors: list[dict[str, Any]] = []
    scanned_row_count = 0
    accepted_preview_rows = 0
    rejected_preview_rows = 0
    invalid_coordinate_count = 0
    duplicate_row_count = 0
    truncated = False
    seen_rows: set[tuple[tuple[str, str], ...]] = set()

    if missing_required_columns:
        row_errors.append(
            {
                "row_number": None,
                "error_code": "missing_required_columns",
                "message": "Input payload is missing required columns.",
                "missing_required_columns": missing_required_columns,
            }
        )

    for index, record in enumerate(records, start=1):
        if scanned_row_count >= scan_row_limit:
            truncated = True
            break
        scanned_row_count += 1
        if len(preview_rows) < preview_row_limit:
            preview_rows.append({"row_number": index, "values": record})
        row_missing = [
            column
            for column in required_columns
            if not str(_value_for_column(record, column, field_mapping) or "").strip()
        ]
        row_failed = False
        if row_missing:
            row_failed = True
            rejected_preview_rows += 1
            if len(row_errors) < error_excerpt_limit:
                row_errors.append(
                    {
                        "row_number": index,
                        "error_code": "missing_required_values",
                        "message": "Record is missing one or more required values.",
                        "missing_required_columns": row_missing,
                        "values": {
                            _mapped_column(column, field_mapping): _value_for_column(
                                record,
                                column,
                                field_mapping,
                            )
                            for column in row_missing
                        },
                    }
                )

        coordinate_error = _invalid_coordinate_error(
            index,
            record,
            lat_column=lat_column,
            lon_column=lon_column,
        )
        if coordinate_error is not None:
            invalid_coordinate_count += 1
            if not row_failed:
                rejected_preview_rows += 1
                row_failed = True
            if len(row_errors) < error_excerpt_limit:
                row_errors.append(coordinate_error)

        fingerprint = _row_fingerprint(record)
        if fingerprint in seen_rows:
            duplicate_row_count += 1
            if not row_failed:
                rejected_preview_rows += 1
                row_failed = True
            if len(row_errors) < error_excerpt_limit:
                row_errors.append(
                    {
                        "row_number": index,
                        "error_code": "duplicate_record",
                        "message": "Record duplicates an earlier scanned record.",
                    }
                )
        else:
            seen_rows.add(fingerprint)

        if not row_failed:
            accepted_preview_rows += 1

    return {
        "format": "json",
        "detected_columns": detected_columns,
        "missing_required_columns": missing_required_columns,
        "field_mapping": dict(field_mapping),
        "preview_rows": preview_rows,
        "row_errors": row_errors,
        "scanned_row_count": scanned_row_count,
        "preview_row_count": len(preview_rows),
        "accepted_preview_rows": accepted_preview_rows,
        "rejected_preview_rows": rejected_preview_rows,
        "invalid_coordinate_count": invalid_coordinate_count,
        "duplicate_row_count": duplicate_row_count,
        "truncated": truncated,
    }


def _validate_uploaded_payload(
    job: Any,
    source: Any | None,
    *,
    storage_reader: StorageReader,
) -> dict[str, Any]:
    required_columns = _required_columns(source)
    field_mapping = _field_mapping(job)
    preview_row_limit, error_excerpt_limit, scan_row_limit = _preview_limits(source)
    filename = _job_filename(job)
    suffix = Path(filename).suffix.lower()
    content_type = _content_type(job) or ""

    try:
        raw_bytes = storage_reader(str(job.input_storage_uri))
    except Exception as exc:
        return {
            "format": "unavailable",
            "detected_columns": [],
            "missing_required_columns": list(required_columns),
            "field_mapping": dict(field_mapping),
            "preview_rows": [],
            "row_errors": [
                {
                    "row_number": None,
                    "error_code": "storage_read_failed",
                    "message": str(exc),
                }
            ],
            "scanned_row_count": 0,
            "preview_row_count": 0,
            "accepted_preview_rows": 0,
            "rejected_preview_rows": 0,
            "invalid_coordinate_count": 0,
            "duplicate_row_count": 0,
            "truncated": False,
        }

    if suffix == ".zip" or "zip" in content_type:
        return {
            "format": "archive",
            "detected_columns": [],
            "missing_required_columns": list(required_columns),
            "field_mapping": dict(field_mapping),
            "preview_rows": [],
            "row_errors": [
                {
                    "row_number": None,
                    "error_code": "manual_review_required",
                    "message": "Archive uploads require manual validation before ingestion.",
                }
            ],
            "scanned_row_count": 0,
            "preview_row_count": 0,
            "accepted_preview_rows": 0,
            "rejected_preview_rows": 0,
            "invalid_coordinate_count": 0,
            "duplicate_row_count": 0,
            "truncated": False,
        }

    text = raw_bytes.decode("utf-8", errors="replace")
    configured_delimiter = dict(getattr(source, "configuration_json", {}) or {}).get("delimiter")
    if suffix in {".json", ".geojson", ".jsonl", ".ndjson"} or "json" in content_type:
        return _validate_json_text(
            text,
            required_columns=required_columns,
            field_mapping=field_mapping,
            preview_row_limit=preview_row_limit,
            error_excerpt_limit=error_excerpt_limit,
            scan_row_limit=scan_row_limit,
        )
    return _validate_csv_text(
        text,
        required_columns=required_columns,
        field_mapping=field_mapping,
        configured_delimiter=configured_delimiter,
        preview_row_limit=preview_row_limit,
        error_excerpt_limit=error_excerpt_limit,
        scan_row_limit=scan_row_limit,
    )


def _determine_validation_state(
    governance: dict[str, Any],
    preview: dict[str, Any],
) -> tuple[str, str]:
    if governance["status"] != "approved":
        return INGESTION_STATUS_VALIDATION_FAILED, "governance_blocked"
    if preview["format"] == "archive":
        return INGESTION_STATUS_MANUAL_REVIEW_REQUIRED, "manual_archive_review"
    if preview["row_errors"] and any(
        error["error_code"] == "storage_read_failed" for error in preview["row_errors"]
    ):
        return INGESTION_STATUS_VALIDATION_FAILED, "storage_read_failed"
    if preview["row_errors"] and any(
        error["error_code"] in {"json_decode_error", "missing_required_columns", "empty_upload"}
        for error in preview["row_errors"]
    ):
        return INGESTION_STATUS_VALIDATION_FAILED, "schema_or_payload_invalid"
    if preview["rejected_preview_rows"] > 0:
        return INGESTION_STATUS_VALIDATED_WITH_ERRORS, "preview_row_errors_detected"
    return INGESTION_STATUS_VALIDATED_READY, "ready_for_ingestion"


def _validation_stats(
    *,
    source: Any | None,
    governance: dict[str, Any],
    preview: dict[str, Any],
    validation_status: str,
    validation_outcome: str,
    log_storage_uri: str | None,
) -> dict[str, Any]:
    return {
        "ingestion_validation_contract_version": INGESTION_VALIDATION_CONTRACT_VERSION,
        "ingestion_validation_log_version": INGESTION_VALIDATION_LOG_VERSION,
        "validation_status": validation_status,
        "validation_outcome": validation_outcome,
        "source_name": getattr(source, "name", None),
        "source_type": getattr(source, "source_type", None),
        "governance_status": getattr(source, "governance_status", None),
        "publication_tier": _publication_tier(source),
        "governance_check_status": governance["status"],
        "governance_failed_check_count": governance["failed_check_count"],
        "format": preview["format"],
        "detected_columns": list(preview["detected_columns"]),
        "missing_required_columns": list(preview["missing_required_columns"]),
        "field_mapping": dict(preview.get("field_mapping") or {}),
        "scanned_row_count": preview["scanned_row_count"],
        "preview_row_count": preview["preview_row_count"],
        "accepted_preview_rows": preview["accepted_preview_rows"],
        "rejected_preview_rows": preview["rejected_preview_rows"],
        "invalid_coordinate_count": preview.get("invalid_coordinate_count", 0),
        "duplicate_row_count": preview.get("duplicate_row_count", 0),
        "error_count": len(preview["row_errors"]),
        "preview_truncated": bool(preview["truncated"]),
        "preview_rows": list(preview["preview_rows"][:5]),
        "error_excerpt": list(preview["row_errors"][:5]),
        "log_storage_uri": log_storage_uri,
    }


def _validation_manifest_payload(
    *,
    job: Any,
    source: Any | None,
    governance: dict[str, Any],
    preview: dict[str, Any],
    validation_status: str,
    validation_outcome: str,
) -> dict[str, Any]:
    return {
        "ingestion_validation_contract_version": INGESTION_VALIDATION_CONTRACT_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "job": _job_scope_snapshot(job),
        "source": _data_source_snapshot(source),
        "input": {
            "filename": _job_filename(job),
            "content_type": _content_type(job),
            "input_storage_uri": job.input_storage_uri,
        },
        "governance": governance,
        "schema": {
            "format": preview["format"],
            "detected_columns": preview["detected_columns"],
            "missing_required_columns": preview["missing_required_columns"],
            "field_mapping": dict(preview.get("field_mapping") or {}),
            "delimiter": preview.get("delimiter"),
            "preview_truncated": preview["truncated"],
        },
        "quality": {
            "invalid_coordinate_count": preview.get("invalid_coordinate_count", 0),
            "duplicate_row_count": preview.get("duplicate_row_count", 0),
        },
        "stats": {
            "validation_status": validation_status,
            "validation_outcome": validation_outcome,
            "scanned_row_count": preview["scanned_row_count"],
            "preview_row_count": preview["preview_row_count"],
            "accepted_preview_rows": preview["accepted_preview_rows"],
            "rejected_preview_rows": preview["rejected_preview_rows"],
            "invalid_coordinate_count": preview.get("invalid_coordinate_count", 0),
            "duplicate_row_count": preview.get("duplicate_row_count", 0),
            "error_count": len(preview["row_errors"]),
        },
        "preview_rows": preview["preview_rows"],
    }


def _validation_errors_payload(
    *,
    job: Any,
    preview: dict[str, Any],
    validation_status: str,
    validation_outcome: str,
) -> dict[str, Any]:
    return {
        "ingestion_validation_contract_version": INGESTION_VALIDATION_CONTRACT_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "job": _job_scope_snapshot(job),
        "summary": {
            "validation_status": validation_status,
            "validation_outcome": validation_outcome,
            "error_count": len(preview["row_errors"]),
            "missing_required_columns": preview["missing_required_columns"],
            "invalid_coordinate_count": preview.get("invalid_coordinate_count", 0),
            "duplicate_row_count": preview.get("duplicate_row_count", 0),
            "preview_truncated": preview["truncated"],
        },
        "row_errors": preview["row_errors"],
    }


def _validation_log_payload(
    *,
    job: Any,
    source: Any | None,
    validation_status: str,
    validation_outcome: str,
    log_lines: list[str],
    error_message: str | None = None,
    traceback_text: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ingestion_validation_log_version": INGESTION_VALIDATION_LOG_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "job": _job_scope_snapshot(job),
        "source": _data_source_snapshot(source),
        "validation_status": validation_status,
        "validation_outcome": validation_outcome,
        "log_lines": list(log_lines),
    }
    if error_message is not None:
        payload["error_message"] = error_message
    if traceback_text is not None:
        payload["traceback"] = traceback_text
    return payload


def _artifact_rows_by_uri(session: Any, job: Any) -> dict[str, Any]:
    rows = repositories.list_artifact_references_for_job(session, str(job.id))
    return {row.storage_uri: row for row in rows}


def _artifact_access_snapshot(storage_uri: str, publication_tier: str) -> dict[str, Any]:
    return resolve_artifact_download(
        storage_uri,
        publication_tier=publication_tier,
    ).as_dict()


def _json_payload_from_storage(storage_uri: str, *, storage_reader: StorageReader) -> dict[str, Any]:
    raw_bytes = storage_reader(storage_uri)
    return json.loads(raw_bytes.decode("utf-8"))


def _source_for_job(session: Any, job: Any) -> Any | None:
    source_id = _as_optional_str(job.source_id)
    if source_id is None:
        return None
    return repositories.get_data_source(session, source_id)


def _source_configuration(source: Any | None) -> dict[str, Any]:
    configuration = getattr(source, "configuration_json", None) if source is not None else None
    return dict(configuration or {})


def _job_parameters(job: Any) -> dict[str, Any]:
    return dict(job.parameters_json or {})


def _execution_setting(job: Any, source: Any | None, key: str, default: Any = None) -> Any:
    parameters = _job_parameters(job)
    configuration = _source_configuration(source)
    return parameters.get(key, configuration.get(key, default))


def _safe_file_stem(value: str) -> str:
    stem = Path(value).stem or "upload"
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem)
    return safe.strip("_") or "upload"


def _write_uploaded_input(
    work_root: Path,
    job: Any,
    *,
    raw_bytes: bytes,
) -> Path:
    input_path = work_root / Path(_job_filename(job)).name
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(raw_bytes)
    return input_path


def _load_optional_json(path_value: Any) -> dict[str, Any] | None:
    if not path_value:
        return None
    path = Path(str(path_value))
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_mapping_stub_if_needed(work_root: Path, job: Any, source: Any | None) -> Path:
    parameters = _job_parameters(job)
    configuration = _source_configuration(source)
    inline_stub = parameters.get("mapping_stub") or configuration.get("mapping_stub")
    if isinstance(inline_stub, dict):
        path = work_root / "mapping_stub.json"
        path.write_text(json.dumps(inline_stub, indent=2, sort_keys=True), encoding="utf-8")
        return path

    path_value = parameters.get("mapping_stub_path") or configuration.get("mapping_stub_path")
    if not path_value:
        raise RuntimeError(
            "Exposure connector ingestion requires `mapping_stub_path` or inline `mapping_stub` "
            "in the data-source configuration or job parameters."
        )
    path = Path(str(path_value))
    if not path.is_file():
        raise RuntimeError(f"Exposure connector mapping stub not found: {path}")
    return path


def _engine_output_artifacts(engine_manifest: dict[str, Any]) -> list[dict[str, str]]:
    outputs = engine_manifest.get("outputs") or {}
    rows: list[dict[str, str]] = []
    for key, value in outputs.items():
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        if not path.is_file():
            continue
        artifact_kind = "ingestion_execution_output"
        content_type = "application/octet-stream"
        if "rejected" in key:
            artifact_kind = "ingestion_execution_rejected_rows"
            content_type = "application/x-ndjson"
        elif "records" in key or "observations" in key:
            artifact_kind = "ingestion_execution_records"
            content_type = "application/x-ndjson"
        elif "manifest" in key:
            artifact_kind = "ingestion_execution_engine_manifest"
            content_type = "application/json"
        elif path.suffix.lower() == ".json":
            content_type = "application/json"
        elif path.suffix.lower() == ".csv":
            content_type = "text/csv"
        rows.append(
            {
                "role": key,
                "path": str(path),
                "filename": path.name,
                "artifact_kind": artifact_kind,
                "content_type": content_type,
            }
        )
    return rows


def _persist_engine_outputs(
    session: Any,
    job: Any,
    source: Any | None,
    *,
    engine_manifest: dict[str, Any],
    publication_tier: str,
) -> list[dict[str, Any]]:
    persisted: list[dict[str, Any]] = []
    for output in _engine_output_artifacts(engine_manifest):
        path = Path(output["path"])
        artifact = artifact_storage.persist_generated_artifact(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            source_id=_as_optional_str(job.source_id),
            ingestion_job=job,
            artifact_kind=output["artifact_kind"],
            artifact_name=f"{output['role']} for ingestion job {job.id}",
            filename=f"ingestion_job_{job.id}_{output['filename']}",
            payload=path.read_bytes(),
            publication_tier=publication_tier,
            content_type=output["content_type"],
            linked_objects={"engine_output_role": output["role"], "engine_output_path": str(path)},
            lineage={
                "job_type": job.job_type,
                "job_id": str(job.id),
                "source": _data_source_snapshot(source),
                "engine_manifest_path": engine_manifest.get("outputs", {}).get("manifest_path"),
            },
        )
        persisted.append(
            {
                "role": output["role"],
                "artifact_kind": output["artifact_kind"],
                "storage_uri": artifact["artifact_reference"].storage_uri,
                "content_type": output["content_type"],
            }
        )
    return persisted


def _execute_crash_csv_engine(
    work_root: Path,
    job: Any,
    source: Any | None,
    *,
    input_path: Path,
) -> dict[str, Any]:
    adapter = str(_execution_setting(job, source, "engine_adapter", "generic_crash_csv"))
    if adapter == "generic_crash_csv":
        return _execute_generic_crash_csv_engine(work_root, job, source, input_path=input_path)
    if adapter != "bari_open_data_crashes":
        raise RuntimeError(
            f"Unsupported crash ingestion engine_adapter `{adapter}`. "
            "Supported v1 adapters: `generic_crash_csv`, `bari_open_data_crashes`."
        )
    output_dir = work_root / "crash_records"
    source_year = int(_execution_setting(job, source, "source_year", datetime.now(UTC).year))
    label = str(_execution_setting(job, source, "source_label", _safe_file_stem(_job_filename(job))))
    limit_value = _execution_setting(job, source, "limit", None)
    limit = int(limit_value) if limit_value not in {None, ""} else None
    return ingest_bari_open_data_crashes(
        output_dir,
        raw_dir=work_root / "raw_crash_uploads",
        sources=[{"year": source_year, "label": label, "url": str(input_path)}],
        limit=limit,
    )


def _execute_generic_crash_csv_engine(
    work_root: Path,
    job: Any,
    source: Any | None,
    *,
    input_path: Path,
) -> dict[str, Any]:
    output_dir = work_root / "generic_crash_records"
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "crash_records_canonical.jsonl"
    rejected_rows_path = output_dir / "crash_records_rejected_rows.jsonl"
    manifest_path = output_dir / "crash_records_canonical.manifest.json"
    text = input_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    delimiter = _delimiter_for_text(text, _source_configuration(source).get("delimiter"))
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    detected_columns = [str(column).strip() for column in (reader.fieldnames or []) if str(column).strip()]
    field_mapping = _field_mapping(job)
    required_columns = _required_columns(source)
    lat_column, lon_column = _coordinate_columns(detected_columns, field_mapping)
    total_rows = 0
    written_rows = 0
    rejected_rows = 0
    invalid_coordinate_count = 0

    with records_path.open("w", encoding="utf-8") as output_handle, rejected_rows_path.open(
        "w",
        encoding="utf-8",
    ) as rejected_handle:
        for row_number, row in enumerate(reader, start=2):
            total_rows += 1
            cleaned_row = _clean_row(row)
            missing = [
                column
                for column in required_columns
                if not str(_value_for_column(cleaned_row, column, field_mapping) or "").strip()
            ]
            coordinate_error = _invalid_coordinate_error(
                row_number,
                cleaned_row,
                lat_column=lat_column,
                lon_column=lon_column,
            )
            if coordinate_error is not None:
                invalid_coordinate_count += 1
            if missing or coordinate_error is not None:
                rejected_rows += 1
                rejected_handle.write(
                    json.dumps(
                        {
                            "row_number": row_number,
                            "errors": [
                                *(f"missing_required_value:{column}" for column in missing),
                                *(
                                    [str(coordinate_error["error_code"])]
                                    if coordinate_error is not None
                                    else []
                                ),
                            ],
                            "row": cleaned_row,
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                    + "\n"
                )
                continue

            canonical = {
                column: _value_for_column(cleaned_row, column, field_mapping)
                for column in required_columns
            }
            if lat_column is not None:
                canonical["latitude"] = float(str(cleaned_row.get(lat_column) or "").replace(",", "."))
            if lon_column is not None:
                canonical["longitude"] = float(str(cleaned_row.get(lon_column) or "").replace(",", "."))
            canonical["source_row_number"] = row_number
            canonical["source_id"] = _as_optional_str(job.source_id)
            canonical["raw_payload"] = cleaned_row
            output_handle.write(json.dumps(canonical, ensure_ascii=True, sort_keys=True) + "\n")
            written_rows += 1

    manifest = {
        "crash_records_ingestion_version": "generic_crash_csv_ingestion_v1",
        "inputs": {
            "input_csv_path": str(input_path),
            "field_mapping": field_mapping,
            "required_columns": required_columns,
        },
        "outputs": {
            "records_path": str(records_path),
            "rejected_rows_path": str(rejected_rows_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "crash_records",
            "public_contract_version": "crash_records_internal_v1",
        },
        "stats": {
            "total_rows": total_rows,
            "written_rows": written_rows,
            "rejected_rows": rejected_rows,
            "invalid_coordinate_count": invalid_coordinate_count,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _execute_exposure_connector_engine(
    work_root: Path,
    job: Any,
    source: Any | None,
    *,
    input_path: Path,
) -> dict[str, Any]:
    mapping_stub_path = _write_mapping_stub_if_needed(work_root, job, source)
    output_dir = work_root / "exposure_connector_observations"
    limit_value = _execution_setting(job, source, "limit", None)
    limit = int(limit_value) if limit_value not in {None, ""} else None
    governance_bundle = _execution_setting(
        job,
        source,
        "governance_bundle_path",
        "data/governance/governance_interoperability_bundle.json",
    )
    payload = ingest_exposure_connector_extract(
        input_path,
        mapping_stub_path,
        output_dir,
        limit=limit,
        governance_bundle_path=governance_bundle,
    )
    manifest = _load_optional_json(payload.get("manifest_path")) or {
        "outputs": {"manifest_path": payload.get("manifest_path")},
        "stats": payload.get("stats") or {},
    }
    return manifest


def _run_engine_for_job(
    work_root: Path,
    job: Any,
    source: Any | None,
    *,
    input_path: Path,
) -> tuple[str, dict[str, Any]]:
    source_type = _normalize(getattr(source, "source_type", None))
    if source_type in EXECUTABLE_CRASH_SOURCE_TYPES:
        return "crash_csv", _execute_crash_csv_engine(work_root, job, source, input_path=input_path)
    if source_type in EXECUTABLE_EXPOSURE_SOURCE_TYPES:
        return "exposure_connector", _execute_exposure_connector_engine(
            work_root,
            job,
            source,
            input_path=input_path,
        )
    raise RuntimeError(
        f"Data source type `{source_type or 'unknown'}` is not executable by the v1 ingestion worker. "
        "Supported v1 source types are crash_feed/crash_csv and exposure_connector."
    )


def _postgis_sync_trigger(session: Any, job: Any, source: Any | None) -> dict[str, Any]:
    city_key = _execution_setting(job, source, "postgis_sync_city_key")
    municipality_id = _as_optional_str(job.municipality_id)
    if not city_key or not municipality_id:
        return {
            "enabled": False,
            "reason": "postgis_sync_city_key and municipality_id are required for automatic domain sync.",
        }
    try:
        payload = postgis_domain.sync_published_artifacts_to_domain(
            session,
            get_settings(),
            organization_id=str(job.organization_id),
            municipality_id=municipality_id,
            city_key=str(city_key),
            source_id=_as_optional_str(job.source_id),
            ingestion_job_id=str(job.id),
        )
    except Exception as exc:  # keep ingestion successful; domain sync is a downstream refresh.
        return {
            "enabled": True,
            "status": "failed",
            "city_key": str(city_key),
            "error_message": str(exc),
        }
    return {
        "enabled": True,
        "status": "completed",
        "city_key": str(city_key),
        "result": payload,
    }


def _execution_manifest_payload(
    *,
    job: Any,
    source: Any | None,
    engine_name: str,
    engine_manifest: dict[str, Any],
    persisted_outputs: list[dict[str, Any]],
    postgis_sync: dict[str, Any],
    log_storage_uri: str | None,
    validation_manifest_storage_uri: str | None,
) -> dict[str, Any]:
    return {
        "ingestion_execution_contract_version": INGESTION_EXECUTION_CONTRACT_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "job": _job_scope_snapshot(job),
        "source": _data_source_snapshot(source),
        "input": {
            "filename": _job_filename(job),
            "content_type": _content_type(job),
            "input_storage_uri": job.input_storage_uri,
        },
        "engine": {
            "name": engine_name,
            "manifest": engine_manifest,
        },
        "outputs": persisted_outputs,
        "lineage": {
            "input_storage_uri": job.input_storage_uri,
            "validation_manifest_storage_uri": validation_manifest_storage_uri,
            "engine_manifest_path": engine_manifest.get("outputs", {}).get("manifest_path"),
            "artifact_count": len(persisted_outputs),
        },
        "dashboard_refresh_trigger": {
            "enabled": True,
            "mode": "deferred",
            "next_action": "run published refresh or dashboard refresh after accepted domain updates.",
        },
        "postgis_sync": postgis_sync,
        "log_storage_uri": log_storage_uri,
    }


def _execution_error_payload(
    *,
    job: Any,
    source: Any | None,
    error_message: str,
    traceback_text: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ingestion_execution_contract_version": INGESTION_EXECUTION_CONTRACT_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "job": _job_scope_snapshot(job),
        "source": _data_source_snapshot(source),
        "summary": {
            "execution_status": INGESTION_STATUS_FAILED,
            "error_count": 1,
            "error_message": error_message,
            "required_next_action": "Fix the upload, source configuration, or mapping stub, then retry.",
        },
        "row_errors": [
            {
                "row_number": None,
                "error_code": "ingestion_execution_failed",
                "message": error_message,
            }
        ],
    }
    if traceback_text is not None:
        payload["traceback"] = traceback_text
    return payload


def _execution_log_payload(
    *,
    job: Any,
    source: Any | None,
    execution_status: str,
    log_lines: list[str],
    error_message: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ingestion_execution_log_version": INGESTION_EXECUTION_LOG_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "job": _job_scope_snapshot(job),
        "source": _data_source_snapshot(source),
        "execution_status": execution_status,
        "log_lines": list(log_lines),
    }
    if error_message is not None:
        payload["error_message"] = error_message
    return payload


def register_ingestion_upload(
    session: Any,
    *,
    organization_id: str,
    source_id: str,
    filename: str,
    municipality_id: str | None = None,
    content_type: str | None = None,
    parameters: dict[str, Any] | None = None,
    submitted_by_subject: str | None = None,
) -> dict[str, Any]:
    source = repositories.get_data_source(session, source_id)
    if source is None or str(source.organization_id) != organization_id:
        raise RuntimeError("Data source not found for the requested organization.")
    if _normalize(source.status) not in ACTIVE_SOURCE_STATUSES:
        raise RuntimeError("Data source is not active and cannot accept uploads.")

    source_municipality_id = _as_optional_str(source.municipality_id)
    resolved_municipality_id = municipality_id or source_municipality_id
    if municipality_id and source_municipality_id and municipality_id != source_municipality_id:
        raise RuntimeError("Requested municipality does not match the configured data source.")

    resolved_parameters = dict(parameters or {})
    resolved_parameters.update(
        {
            "source_name": source.name,
            "source_type": source.source_type,
            "publication_tier": _publication_tier(source),
            "submitted_by_subject": submitted_by_subject,
        }
    )
    plan = artifact_storage.prepare_ingestion_upload(
        session,
        organization_id=organization_id,
        municipality_id=resolved_municipality_id,
        source_id=source_id,
        job_type=_build_job_type(source),
        filename=filename,
        publication_tier=_publication_tier(source),
        content_type=content_type,
        parameters=resolved_parameters,
    )
    upload_contract = {
        "ingestion_upload_contract_version": INGESTION_UPLOAD_CONTRACT_VERSION,
        "source": _data_source_snapshot(source),
        "job": _job_scope_snapshot(plan["job"]),
        "next_step": f"/v1/ingestion-jobs/{plan['job'].id}/validate",
    }
    repositories.attach_ingestion_job_storage(
        session,
        plan["job"],
        status=INGESTION_STATUS_PENDING_UPLOAD,
        parameters={"ingestion_upload_contract": upload_contract},
        job_stats={
            "ingestion_upload_contract_version": INGESTION_UPLOAD_CONTRACT_VERSION,
            "lifecycle_stage": "upload_registered",
            "required_next_action": "upload_object_then_validate",
        },
    )
    return {
        "job": plan["job"],
        "source": source,
        "upload_url": plan["upload_url"],
        "storage_contract": plan["storage_contract"],
        "upload_contract": upload_contract,
    }


def validate_ingestion_job_upload(
    session: Any,
    job: Any,
    *,
    storage_reader: StorageReader = read_storage_bytes,
) -> dict[str, Any]:
    source = _source_for_job(session, job)
    log_lines = [f"{_utc_now_iso()} queued validation for ingestion job {job.id}"]
    repositories.mark_ingestion_job_running(session, job, status=INGESTION_STATUS_VALIDATING)
    try:
        governance = _governance_summary(_governance_checks(source, job))
        preview = _validate_uploaded_payload(job, source, storage_reader=storage_reader)
        validation_status, validation_outcome = _determine_validation_state(governance, preview)
        log_lines.append(
            f"{_utc_now_iso()} governance status={governance['status']} "
            f"format={preview['format']} outcome={validation_outcome}"
        )
        errors_payload = _validation_errors_payload(
            job=job,
            preview=preview,
            validation_status=validation_status,
            validation_outcome=validation_outcome,
        )
        manifest_payload = _validation_manifest_payload(
            job=job,
            source=source,
            governance=governance,
            preview=preview,
            validation_status=validation_status,
            validation_outcome=validation_outcome,
        )
        error_artifact = artifact_storage.persist_generated_artifact(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            source_id=_as_optional_str(job.source_id),
            ingestion_job=job,
            artifact_kind="ingestion_validation_errors",
            artifact_name=f"Ingestion validation errors {job.id}",
            filename=f"ingestion_job_{job.id}_errors.json",
            payload=errors_payload,
            publication_tier=_publication_tier(source),
            content_type="application/json",
            linked_objects={"validation_outcome": validation_outcome},
            lineage={"job_type": job.job_type, "job_id": str(job.id)},
        )
        manifest_artifact = artifact_storage.persist_generated_artifact(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            source_id=_as_optional_str(job.source_id),
            ingestion_job=job,
            artifact_kind="ingestion_validation_manifest",
            artifact_name=f"Ingestion validation manifest {job.id}",
            filename=f"ingestion_job_{job.id}_manifest.json",
            payload=manifest_payload,
            publication_tier=_publication_tier(source),
            content_type="application/json",
            linked_objects={"error_storage_uri": error_artifact["artifact_reference"].storage_uri},
            lineage={"job_type": job.job_type, "job_id": str(job.id)},
        )
        log_artifact = artifact_storage.persist_generated_artifact(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            source_id=_as_optional_str(job.source_id),
            ingestion_job=job,
            artifact_kind="ingestion_validation_log",
            artifact_name=f"Ingestion validation log {job.id}",
            filename=f"ingestion_job_{job.id}_log.json",
            payload=_validation_log_payload(
                job=job,
                source=source,
                validation_status=validation_status,
                validation_outcome=validation_outcome,
                log_lines=log_lines,
            ),
            publication_tier=_publication_tier(source),
            content_type="application/json",
            linked_objects={
                "manifest_storage_uri": manifest_artifact["artifact_reference"].storage_uri,
                "error_storage_uri": error_artifact["artifact_reference"].storage_uri,
            },
            lineage={"job_type": job.job_type, "job_id": str(job.id)},
        )
        repositories.attach_ingestion_job_storage(
            session,
            job,
            error_storage_uri=error_artifact["artifact_reference"].storage_uri,
            parameters={
                "ingestion_validation_contract": {
                    "ingestion_validation_contract_version": INGESTION_VALIDATION_CONTRACT_VERSION,
                    "source_id": _as_optional_str(job.source_id),
                    "validation_outcome": validation_outcome,
                }
            },
        )
        repositories.mark_ingestion_job_finished(
            session,
            job,
            status=validation_status,
            manifest_storage_uri=manifest_artifact["artifact_reference"].storage_uri,
            error_storage_uri=error_artifact["artifact_reference"].storage_uri,
            job_stats=_validation_stats(
                source=source,
                governance=governance,
                preview=preview,
                validation_status=validation_status,
                validation_outcome=validation_outcome,
                log_storage_uri=log_artifact["artifact_reference"].storage_uri,
            ),
        )
        return build_ingestion_job_access_snapshot(session, job)
    except Exception as exc:
        traceback_text = traceback.format_exc()
        log_lines.append(f"{_utc_now_iso()} validation failed with error: {exc}")
        error_log = artifact_storage.persist_generated_artifact(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            source_id=_as_optional_str(job.source_id),
            ingestion_job=job,
            artifact_kind="ingestion_validation_log",
            artifact_name=f"Ingestion validation log {job.id}",
            filename=f"ingestion_job_{job.id}_log_failed.json",
            payload=_validation_log_payload(
                job=job,
                source=source,
                validation_status=INGESTION_STATUS_FAILED,
                validation_outcome="unexpected_runtime_error",
                log_lines=log_lines,
                error_message=str(exc),
                traceback_text=traceback_text,
            ),
            publication_tier=_publication_tier(source),
            content_type="application/json",
            linked_objects={"job_status": INGESTION_STATUS_FAILED},
            lineage={"job_type": job.job_type, "job_id": str(job.id)},
        )
        repositories.mark_ingestion_job_finished(
            session,
            job,
            status=INGESTION_STATUS_FAILED,
            error_storage_uri=error_log["artifact_reference"].storage_uri,
            job_stats={
                "ingestion_validation_contract_version": INGESTION_VALIDATION_CONTRACT_VERSION,
                "ingestion_validation_log_version": INGESTION_VALIDATION_LOG_VERSION,
                "validation_status": INGESTION_STATUS_FAILED,
                "validation_outcome": "unexpected_runtime_error",
                "error_message": str(exc),
                "log_storage_uri": error_log["artifact_reference"].storage_uri,
            },
        )
        raise


def execute_ingestion_job(
    session: Any,
    job: Any,
    *,
    storage_reader: StorageReader = read_storage_bytes,
) -> dict[str, Any]:
    if job.status not in RUNNABLE_INGESTION_STATUSES:
        raise RuntimeError(f"Ingestion job status `{job.status}` cannot be executed by a worker.")
    source = _source_for_job(session, job)
    publication_tier = _publication_tier(source)
    log_lines = [f"{_utc_now_iso()} queued execution for ingestion job {job.id}"]
    repositories.mark_ingestion_job_running(session, job, status=INGESTION_STATUS_RUNNING)
    repositories.attach_ingestion_job_storage(
        session,
        job,
        job_stats={
            "ingestion_execution_contract_version": INGESTION_EXECUTION_CONTRACT_VERSION,
            "lifecycle_stage": "worker_execution_running",
            "required_next_action": "wait_for_ingestion_worker_completion",
        },
    )
    try:
        raw_bytes = storage_reader(str(job.input_storage_uri))
        with tempfile.TemporaryDirectory(prefix=f"road-risk-ingestion-{job.id}-") as temp_dir:
            work_root = Path(temp_dir)
            input_path = _write_uploaded_input(work_root, job, raw_bytes=raw_bytes)
            engine_name, engine_manifest = _run_engine_for_job(
                work_root,
                job,
                source,
                input_path=input_path,
            )
            log_lines.append(
                f"{_utc_now_iso()} engine={engine_name} completed "
                f"outputs={sorted((engine_manifest.get('outputs') or {}).keys())}"
            )
            validation_manifest_storage_uri = job.manifest_storage_uri
            persisted_outputs = _persist_engine_outputs(
                session,
                job,
                source,
                engine_manifest=engine_manifest,
                publication_tier=publication_tier,
            )
            postgis_sync = _postgis_sync_trigger(session, job, source)
            log_artifact = artifact_storage.persist_generated_artifact(
                session,
                organization_id=str(job.organization_id),
                municipality_id=_as_optional_str(job.municipality_id),
                source_id=_as_optional_str(job.source_id),
                ingestion_job=job,
                artifact_kind="ingestion_execution_log",
                artifact_name=f"Ingestion execution log {job.id}",
                filename=f"ingestion_job_{job.id}_execution_log.json",
                payload=_execution_log_payload(
                    job=job,
                    source=source,
                    execution_status=INGESTION_STATUS_COMPLETED,
                    log_lines=log_lines,
                ),
                publication_tier=publication_tier,
                content_type="application/json",
                linked_objects={"execution_status": INGESTION_STATUS_COMPLETED},
                lineage={"job_type": job.job_type, "job_id": str(job.id)},
            )
            manifest_payload = _execution_manifest_payload(
                job=job,
                source=source,
                engine_name=engine_name,
                engine_manifest=engine_manifest,
                persisted_outputs=persisted_outputs,
                postgis_sync=postgis_sync,
                log_storage_uri=log_artifact["artifact_reference"].storage_uri,
                validation_manifest_storage_uri=validation_manifest_storage_uri,
            )
            manifest_artifact = artifact_storage.persist_generated_artifact(
                session,
                organization_id=str(job.organization_id),
                municipality_id=_as_optional_str(job.municipality_id),
                source_id=_as_optional_str(job.source_id),
                ingestion_job=job,
                artifact_kind="ingestion_execution_manifest",
                artifact_name=f"Ingestion execution manifest {job.id}",
                filename=f"ingestion_job_{job.id}_execution_manifest.json",
                payload=manifest_payload,
                publication_tier=publication_tier,
                content_type="application/json",
                linked_objects={
                    "log_storage_uri": log_artifact["artifact_reference"].storage_uri,
                    "engine_name": engine_name,
                },
                lineage={
                    "job_type": job.job_type,
                    "job_id": str(job.id),
                    "engine_name": engine_name,
                    "output_artifact_count": len(persisted_outputs),
                },
            )
            repositories.mark_ingestion_job_finished(
                session,
                job,
                status=INGESTION_STATUS_COMPLETED,
                manifest_storage_uri=manifest_artifact["artifact_reference"].storage_uri,
                job_stats={
                    "ingestion_execution_contract_version": INGESTION_EXECUTION_CONTRACT_VERSION,
                    "ingestion_execution_log_version": INGESTION_EXECUTION_LOG_VERSION,
                    "execution_status": INGESTION_STATUS_COMPLETED,
                    "execution_engine": engine_name,
                    "lifecycle_stage": "worker_execution_completed",
                    "required_next_action": "review_completed_artifacts",
                    "output_artifact_count": len(persisted_outputs),
                    "log_storage_uri": log_artifact["artifact_reference"].storage_uri,
                    "postgis_sync": postgis_sync,
                    "dashboard_refresh_trigger": manifest_payload["dashboard_refresh_trigger"],
                    "engine_stats": dict(engine_manifest.get("stats") or {}),
                },
            )
            repositories.record_audit_log(
                session,
                organization_id=str(job.organization_id),
                municipality_id=_as_optional_str(job.municipality_id),
                action="ingestion_job.execution_completed",
                target_type="ingestion_job",
                target_id=str(job.id),
                metadata={
                    "execution_engine": engine_name,
                    "output_artifact_count": len(persisted_outputs),
                    "postgis_sync": postgis_sync,
                },
            )
            return build_ingestion_job_access_snapshot(session, job)
    except Exception as exc:
        traceback_text = traceback.format_exc()
        log_lines.append(f"{_utc_now_iso()} execution failed with error: {exc}")
        error_artifact = artifact_storage.persist_generated_artifact(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            source_id=_as_optional_str(job.source_id),
            ingestion_job=job,
            artifact_kind="ingestion_execution_errors",
            artifact_name=f"Ingestion execution errors {job.id}",
            filename=f"ingestion_job_{job.id}_execution_errors.json",
            payload=_execution_error_payload(
                job=job,
                source=source,
                error_message=str(exc),
                traceback_text=traceback_text,
            ),
            publication_tier=publication_tier,
            content_type="application/json",
            linked_objects={"execution_status": INGESTION_STATUS_FAILED},
            lineage={"job_type": job.job_type, "job_id": str(job.id)},
        )
        log_artifact = artifact_storage.persist_generated_artifact(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            source_id=_as_optional_str(job.source_id),
            ingestion_job=job,
            artifact_kind="ingestion_execution_log",
            artifact_name=f"Ingestion execution log {job.id}",
            filename=f"ingestion_job_{job.id}_execution_log_failed.json",
            payload=_execution_log_payload(
                job=job,
                source=source,
                execution_status=INGESTION_STATUS_FAILED,
                log_lines=log_lines,
                error_message=str(exc),
            ),
            publication_tier=publication_tier,
            content_type="application/json",
            linked_objects={
                "execution_status": INGESTION_STATUS_FAILED,
                "error_storage_uri": error_artifact["artifact_reference"].storage_uri,
            },
            lineage={"job_type": job.job_type, "job_id": str(job.id)},
        )
        repositories.mark_ingestion_job_finished(
            session,
            job,
            status=INGESTION_STATUS_FAILED,
            error_storage_uri=error_artifact["artifact_reference"].storage_uri,
            job_stats={
                "ingestion_execution_contract_version": INGESTION_EXECUTION_CONTRACT_VERSION,
                "ingestion_execution_log_version": INGESTION_EXECUTION_LOG_VERSION,
                "execution_status": INGESTION_STATUS_FAILED,
                "lifecycle_stage": "worker_execution_failed",
                "required_next_action": "review_failure_then_retry_or_cancel",
                "error_message": str(exc),
                "error_count": 1,
                "log_storage_uri": log_artifact["artifact_reference"].storage_uri,
            },
        )
        repositories.record_audit_log(
            session,
            organization_id=str(job.organization_id),
            municipality_id=_as_optional_str(job.municipality_id),
            action="ingestion_job.execution_failed",
            target_type="ingestion_job",
            target_id=str(job.id),
            metadata={"error_message": str(exc)},
        )
        return build_ingestion_job_access_snapshot(session, job)


def retry_ingestion_job(
    session: Any,
    job: Any,
    *,
    retried_by_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    if job.status not in RETRYABLE_INGESTION_STATUSES:
        raise RuntimeError(f"Ingestion job status `{job.status}` cannot be retried.")
    stats = dict(job.job_stats_json or {})
    retry_count = int(stats.get("retry_count") or 0) + 1
    repositories.attach_ingestion_job_storage(
        session,
        job,
        status=INGESTION_STATUS_QUEUED,
        job_stats={
            "lifecycle_stage": "execution_retry_queued",
            "required_next_action": "run_ingestion_worker_execution",
            "retry_count": retry_count,
            "retry_decision": {
                "decided_at_utc": _utc_now_iso(),
                "decided_by_subject": retried_by_subject,
                "decision_note": decision_note,
            },
        },
    )
    repositories.record_audit_log(
        session,
        organization_id=str(job.organization_id),
        municipality_id=_as_optional_str(job.municipality_id),
        action="ingestion_job.retry_queued",
        target_type="ingestion_job",
        target_id=str(job.id),
        metadata={"retry_count": retry_count, "decided_by_subject": retried_by_subject},
    )
    return build_ingestion_job_access_snapshot(session, job)


def cancel_ingestion_job(
    session: Any,
    job: Any,
    *,
    cancelled_by_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    if job.status not in CANCELLABLE_INGESTION_STATUSES:
        raise RuntimeError(f"Ingestion job status `{job.status}` cannot be cancelled.")
    previous_status = job.status
    repositories.mark_ingestion_job_finished(
        session,
        job,
        status=INGESTION_STATUS_CANCELLED,
        job_stats={
            "ingestion_execution_contract_version": INGESTION_EXECUTION_CONTRACT_VERSION,
            "execution_status": INGESTION_STATUS_CANCELLED,
            "lifecycle_stage": "execution_cancelled",
            "required_next_action": "retry_or_archive_cancelled_job",
            "cancellation": {
                "cancelled_at_utc": _utc_now_iso(),
                "cancelled_by_subject": cancelled_by_subject,
                "decision_note": decision_note,
                "previous_status": previous_status,
                "best_effort": previous_status == INGESTION_STATUS_RUNNING,
            },
        },
    )
    repositories.record_audit_log(
        session,
        organization_id=str(job.organization_id),
        municipality_id=_as_optional_str(job.municipality_id),
        action="ingestion_job.cancelled",
        target_type="ingestion_job",
        target_id=str(job.id),
        metadata={"previous_status": previous_status, "cancelled_by_subject": cancelled_by_subject},
    )
    return build_ingestion_job_access_snapshot(session, job)


def serialize_ingestion_job_status(session: Any, job: Any) -> dict[str, Any]:
    source = _source_for_job(session, job)
    artifacts = repositories.list_artifact_references_for_job(session, str(job.id))
    stats = dict(job.job_stats_json or {})
    return {
        **_job_scope_snapshot(job),
        "status": job.status,
        "queued_at": job.queued_at.isoformat() if job.queued_at is not None else None,
        "started_at": job.started_at.isoformat() if job.started_at is not None else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at is not None else None,
        "input_storage_uri": job.input_storage_uri,
        "manifest_storage_uri": job.manifest_storage_uri,
        "error_storage_uri": job.error_storage_uri,
        "source": _data_source_snapshot(source),
        "parameters": dict(job.parameters_json or {}),
        "stats": stats,
        "workflow": _workflow_stage(job.status, stats),
        "artifacts": [
            {
                "artifact_id": str(row.id),
                "artifact_kind": row.artifact_kind,
                "artifact_name": row.artifact_name,
                "storage_uri": row.storage_uri,
                "publication_tier": row.publication_tier,
                "content_type": row.content_type,
            }
            for row in artifacts
        ],
    }


def serialize_ingestion_job_summary(session: Any, job: Any) -> dict[str, Any]:
    payload = serialize_ingestion_job_status(session, job)
    return {
        "job_id": payload["job_id"],
        "organization_id": payload["organization_id"],
        "municipality_id": payload["municipality_id"],
        "source_id": payload["source_id"],
        "job_type": payload["job_type"],
        "status": payload["status"],
        "queued_at": payload["queued_at"],
        "finished_at": payload["finished_at"],
        "source_name": (payload["source"] or {}).get("name"),
        "validation_outcome": payload["stats"].get("validation_outcome"),
        "execution_status": payload["stats"].get("execution_status"),
        "execution_engine": payload["stats"].get("execution_engine"),
        "output_artifact_count": payload["stats"].get("output_artifact_count"),
        "error_count": payload["stats"].get("error_count"),
        "manifest_storage_uri": payload["manifest_storage_uri"],
        "error_storage_uri": payload["error_storage_uri"],
    }


def list_ingestion_job_summaries(
    session: Any,
    *,
    organization_id: str,
    municipality_id: str | None = None,
    source_id: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    jobs = repositories.list_ingestion_jobs_for_organization(
        session,
        organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        status=status,
        limit=limit,
    )
    return [serialize_ingestion_job_summary(session, job) for job in jobs]


def build_upload_center_snapshot(
    session: Any,
    *,
    organization_id: str,
    municipality_id: str | None = None,
    source_id: str | None = None,
    status: str | None = None,
    limit: int | None = 50,
) -> dict[str, Any]:
    sources = repositories.list_data_sources_for_organization(session, organization_id)
    if municipality_id is not None:
        sources = [
            source
            for source in sources
            if _as_optional_str(getattr(source, "municipality_id", None)) in {None, municipality_id}
        ]
    source_rows = [_data_source_upload_row(source) for source in sources]
    jobs = list_ingestion_job_summaries(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        status=status,
        limit=limit,
    )
    return {
        "contract_version": INGESTION_UPLOAD_CENTER_CONTRACT_VERSION,
        "organization_id": organization_id,
        "municipality_id": municipality_id,
        "generated_at": _utc_now_iso(),
        "supported_formats": list(SUPPORTED_UPLOAD_FORMATS),
        "sources": source_rows,
        "jobs": jobs,
        "operator_actions": {
            "register": "POST /v1/ingestion-jobs/uploads",
            "validate": "POST /v1/ingestion-jobs/{job_id}/validate",
            "approve": "POST /v1/ingestion-jobs/{job_id}/approve",
            "run": "POST /v1/ingestion-jobs/{job_id}/run",
            "retry": "POST /v1/ingestion-jobs/{job_id}/retry",
            "cancel": "POST /v1/ingestion-jobs/{job_id}/cancel",
            "reject": "POST /v1/ingestion-jobs/{job_id}/reject",
        },
    }


def approve_ingestion_job(
    session: Any,
    job: Any,
    *,
    approved_by_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    if job.status not in APPROVABLE_INGESTION_STATUSES:
        raise RuntimeError(f"Ingestion job status `{job.status}` cannot be approved for queueing.")
    repositories.attach_ingestion_job_storage(
        session,
        job,
        status=INGESTION_STATUS_QUEUED,
        job_stats={
            "lifecycle_stage": "approved_for_ingestion",
            "required_next_action": "run_ingestion_worker_execution",
            "operator_decision": {
                "decision": "approved",
                "decided_at_utc": _utc_now_iso(),
                "decided_by_subject": approved_by_subject,
                "decision_note": decision_note,
            },
        },
    )
    repositories.record_audit_log(
        session,
        organization_id=str(job.organization_id),
        municipality_id=_as_optional_str(job.municipality_id),
        action="ingestion_job.approved_for_queue",
        target_type="ingestion_job",
        target_id=str(job.id),
        metadata={
            "status": INGESTION_STATUS_QUEUED,
            "previous_status": "validated",
            "decided_by_subject": approved_by_subject,
        },
    )
    return build_ingestion_job_access_snapshot(session, job)


def reject_ingestion_job(
    session: Any,
    job: Any,
    *,
    rejected_by_subject: str | None = None,
    decision_note: str | None = None,
) -> dict[str, Any]:
    if job.status not in REJECTABLE_INGESTION_STATUSES:
        raise RuntimeError(f"Ingestion job status `{job.status}` cannot be rejected from upload review.")
    previous_status = job.status
    repositories.attach_ingestion_job_storage(
        session,
        job,
        status=INGESTION_STATUS_REJECTED,
        job_stats={
            "lifecycle_stage": "rejected_by_operator",
            "required_next_action": "no_action_rejected",
            "operator_decision": {
                "decision": "rejected",
                "decided_at_utc": _utc_now_iso(),
                "decided_by_subject": rejected_by_subject,
                "decision_note": decision_note,
            },
        },
    )
    repositories.record_audit_log(
        session,
        organization_id=str(job.organization_id),
        municipality_id=_as_optional_str(job.municipality_id),
        action="ingestion_job.rejected",
        target_type="ingestion_job",
        target_id=str(job.id),
        metadata={
            "status": INGESTION_STATUS_REJECTED,
            "previous_status": previous_status,
            "decided_by_subject": rejected_by_subject,
        },
    )
    return build_ingestion_job_access_snapshot(session, job)


def build_ingestion_job_access_snapshot(session: Any, job: Any) -> dict[str, Any]:
    payload = serialize_ingestion_job_status(session, job)
    artifacts_by_uri = _artifact_rows_by_uri(session, job)
    if job.manifest_storage_uri and job.manifest_storage_uri in artifacts_by_uri:
        manifest_row = artifacts_by_uri[job.manifest_storage_uri]
        payload["manifest_access"] = _artifact_access_snapshot(
            manifest_row.storage_uri,
            manifest_row.publication_tier,
        )
    if job.error_storage_uri and job.error_storage_uri in artifacts_by_uri:
        error_row = artifacts_by_uri[job.error_storage_uri]
        payload["error_access"] = _artifact_access_snapshot(
            error_row.storage_uri,
            error_row.publication_tier,
        )
    log_storage_uri = _job_log_storage_uri(job)
    if log_storage_uri and log_storage_uri in artifacts_by_uri:
        log_row = artifacts_by_uri[log_storage_uri]
        payload["log_access"] = _artifact_access_snapshot(
            log_row.storage_uri,
            log_row.publication_tier,
        )
    return payload


def load_ingestion_job_manifest(
    session: Any,
    job: Any,
    *,
    storage_reader: StorageReader = read_storage_bytes,
) -> dict[str, Any]:
    if not job.manifest_storage_uri:
        return {
            "job_id": str(job.id),
            "manifest_storage_uri": None,
            "manifest": None,
        }
    artifacts_by_uri = _artifact_rows_by_uri(session, job)
    manifest_row = artifacts_by_uri.get(job.manifest_storage_uri)
    publication_tier = manifest_row.publication_tier if manifest_row is not None else "restricted"
    return {
        "job_id": str(job.id),
        "manifest_storage_uri": job.manifest_storage_uri,
        "manifest_access": _artifact_access_snapshot(job.manifest_storage_uri, publication_tier),
        "manifest": _json_payload_from_storage(job.manifest_storage_uri, storage_reader=storage_reader),
    }


def load_ingestion_job_error_summary(
    session: Any,
    job: Any,
    *,
    storage_reader: StorageReader = read_storage_bytes,
) -> dict[str, Any]:
    if not job.error_storage_uri:
        return {
            "job_id": str(job.id),
            "error_storage_uri": None,
            "error_summary": None,
        }
    artifacts_by_uri = _artifact_rows_by_uri(session, job)
    error_row = artifacts_by_uri.get(job.error_storage_uri)
    publication_tier = error_row.publication_tier if error_row is not None else "restricted"
    payload = _json_payload_from_storage(job.error_storage_uri, storage_reader=storage_reader)
    return {
        "job_id": str(job.id),
        "error_storage_uri": job.error_storage_uri,
        "error_access": _artifact_access_snapshot(job.error_storage_uri, publication_tier),
        "error_summary": payload.get("summary"),
        "row_errors": payload.get("row_errors"),
    }


def load_ingestion_job_log(
    session: Any,
    job: Any,
    *,
    storage_reader: StorageReader = read_storage_bytes,
) -> dict[str, Any]:
    log_storage_uri = _job_log_storage_uri(job)
    if not log_storage_uri:
        return {
            "job_id": str(job.id),
            "log_storage_uri": None,
            "log": None,
        }
    artifacts_by_uri = _artifact_rows_by_uri(session, job)
    log_row = artifacts_by_uri.get(log_storage_uri)
    publication_tier = log_row.publication_tier if log_row is not None else "restricted"
    return {
        "job_id": str(job.id),
        "log_storage_uri": log_storage_uri,
        "log_access": _artifact_access_snapshot(log_storage_uri, publication_tier),
        "log": _json_payload_from_storage(log_storage_uri, storage_reader=storage_reader),
    }


__all__ = [
    "INGESTION_STATUS_FAILED",
    "INGESTION_STATUS_APPROVED",
    "INGESTION_STATUS_CANCELLED",
    "INGESTION_STATUS_COMPLETED",
    "INGESTION_STATUS_MANUAL_REVIEW_REQUIRED",
    "INGESTION_STATUS_MANUAL_REVIEW",
    "INGESTION_STATUS_PENDING_UPLOAD",
    "INGESTION_STATUS_QUEUED",
    "INGESTION_STATUS_REJECTED",
    "INGESTION_STATUS_RUNNING",
    "INGESTION_STATUS_VALIDATED_READY",
    "INGESTION_STATUS_VALIDATED_WITH_ERRORS",
    "INGESTION_STATUS_VALIDATING",
    "INGESTION_STATUS_VALIDATION_FAILED",
    "INGESTION_EXECUTION_CONTRACT_VERSION",
    "INGESTION_EXECUTION_LOG_VERSION",
    "INGESTION_EXECUTION_TASK_NAME",
    "INGESTION_UPLOAD_CENTER_CONTRACT_VERSION",
    "INGESTION_UPLOAD_CONTRACT_VERSION",
    "INGESTION_VALIDATION_CONTRACT_VERSION",
    "INGESTION_VALIDATION_LOG_VERSION",
    "approve_ingestion_job",
    "build_upload_center_snapshot",
    "build_ingestion_job_access_snapshot",
    "cancel_ingestion_job",
    "execute_ingestion_job",
    "list_ingestion_job_summaries",
    "load_ingestion_job_error_summary",
    "load_ingestion_job_log",
    "load_ingestion_job_manifest",
    "register_ingestion_upload",
    "reject_ingestion_job",
    "retry_ingestion_job",
    "serialize_ingestion_job_status",
    "validate_ingestion_job_upload",
]
