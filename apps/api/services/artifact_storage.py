"""Application-layer helpers for object storage and artifact metadata links."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.api.db import repositories
from apps.api.storage import (
    StorageObject,
    build_generated_artifact_key,
    build_manifest_key,
    build_report_key,
    build_upload_key,
    ensure_default_buckets,
    get_storage_settings,
    presign_put,
    put_bytes,
    resolve_artifact_download,
    select_bucket_for_tier,
)


ARTIFACT_STORAGE_CONTRACT_VERSION = "artifact_storage_contract_v1"


def _ensure_storage_ready() -> None:
    if get_storage_settings().auto_create_buckets:
        ensure_default_buckets()


def _storage_metadata(content_type: str | None, *, filename: str) -> dict[str, str]:
    metadata = {"filename": filename}
    if content_type:
        metadata["content_type"] = content_type
    return metadata


def _object_role_for_artifact_kind(artifact_kind: str) -> str:
    if "manifest" in artifact_kind:
        return "manifest"
    if "report" in artifact_kind:
        return "report_output"
    return "generated_artifact"


def _encode_payload(payload: bytes | str | dict[str, Any] | list[Any]) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def build_artifact_storage_contract(
    *,
    organization_id: str,
    storage_object: StorageObject,
    publication_tier: str,
    object_role: str,
    content_type: str | None = None,
    municipality_id: str | None = None,
    source_id: str | None = None,
    ingestion_job_id: str | None = None,
    report_id: str | None = None,
    artifact_kind: str | None = None,
    artifact_name: str | None = None,
    linked_objects: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "artifact_storage_contract_version": ARTIFACT_STORAGE_CONTRACT_VERSION,
        "storage": {
            "bucket": storage_object.bucket,
            "key": storage_object.key,
            "storage_uri": storage_object.uri(),
            "etag": storage_object.etag,
            "version_id": storage_object.version_id,
            "content_type": content_type,
            "publication_tier": publication_tier,
        },
        "entity_links": {
            "organization_id": organization_id,
            "municipality_id": municipality_id,
            "source_id": source_id,
            "ingestion_job_id": ingestion_job_id,
            "report_id": report_id,
            "artifact_kind": artifact_kind,
            "artifact_name": artifact_name,
            "object_role": object_role,
        },
        "linked_objects": dict(linked_objects or {}),
        "metadata": dict(metadata or {}),
    }


def prepare_ingestion_upload(
    session: Any,
    *,
    organization_id: str,
    job_type: str,
    filename: str,
    municipality_id: str | None = None,
    source_id: str | None = None,
    submitted_by_user_id: str | None = None,
    publication_tier: str = "restricted",
    content_type: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_storage_ready()
    key = build_upload_key(
        organization_id,
        filename,
        municipality_id=municipality_id,
        job_type=job_type,
    )
    bucket = select_bucket_for_tier(publication_tier)
    storage_object = StorageObject(bucket=bucket, key=key)
    upload_contract = build_artifact_storage_contract(
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        storage_object=storage_object,
        publication_tier=publication_tier,
        content_type=content_type,
        object_role="upload_input",
        metadata={"filename": Path(filename).name, "job_type": job_type},
    )
    job_parameters = dict(parameters or {})
    job_parameters.update(
        {
            "original_filename": Path(filename).name,
            "content_type": content_type,
            "publication_tier": publication_tier,
            "storage_contract": upload_contract,
        }
    )
    job = repositories.create_ingestion_job(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        submitted_by_user_id=submitted_by_user_id,
        job_type=job_type,
        input_storage_uri=storage_object.uri(),
        parameters=job_parameters,
    )
    return {
        "job": job,
        "storage_object": storage_object,
        "storage_contract": upload_contract,
        "upload_url": presign_put(
            storage_object.key,
            bucket=storage_object.bucket,
            content_type=content_type,
        ),
    }


def prepare_report_output(
    session: Any,
    *,
    organization_id: str,
    report_type: str,
    title: str,
    output_format: str = "pdf",
    municipality_id: str | None = None,
    generated_by_user_id: str | None = None,
    visibility_tier: str = "restricted",
    filename: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_storage_ready()
    resolved_filename = filename or f"{report_type}.{output_format}"
    key = build_report_key(
        organization_id,
        report_type,
        resolved_filename,
        municipality_id=municipality_id,
    )
    bucket = select_bucket_for_tier(visibility_tier)
    storage_object = StorageObject(bucket=bucket, key=key)
    content_type = f"application/{output_format}"
    storage_contract = build_artifact_storage_contract(
        organization_id=organization_id,
        municipality_id=municipality_id,
        storage_object=storage_object,
        publication_tier=visibility_tier,
        content_type=content_type,
        object_role="report_output",
        artifact_kind=report_type,
        artifact_name=title,
        metadata={"filename": Path(resolved_filename).name, "output_format": output_format},
    )
    report_parameters = dict(parameters or {})
    report_parameters["storage_contract"] = storage_contract
    report = repositories.create_report(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        generated_by_user_id=generated_by_user_id,
        report_type=report_type,
        title=title,
        status="pending_upload",
        visibility_tier=visibility_tier,
        output_format=output_format,
        file_storage_uri=storage_object.uri(),
        parameters=report_parameters,
    )
    return {
        "report": report,
        "storage_object": storage_object,
        "storage_contract": storage_contract,
        "upload_url": presign_put(
            storage_object.key,
            bucket=storage_object.bucket,
            content_type=content_type,
        ),
    }


def persist_generated_artifact(
    session: Any,
    *,
    organization_id: str,
    artifact_kind: str,
    artifact_name: str,
    filename: str,
    payload: bytes | str | dict[str, Any] | list[Any],
    municipality_id: str | None = None,
    source_id: str | None = None,
    ingestion_job: Any | None = None,
    report: Any | None = None,
    created_by_user_id: str | None = None,
    publication_tier: str = "restricted",
    content_type: str | None = None,
    linked_objects: dict[str, Any] | None = None,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_storage_ready()
    if "manifest" in artifact_kind:
        key = build_manifest_key(
            organization_id,
            artifact_kind,
            filename,
            municipality_id=municipality_id,
        )
    else:
        key = build_generated_artifact_key(
            organization_id,
            artifact_kind,
            filename,
            municipality_id=municipality_id,
        )

    bucket = select_bucket_for_tier(publication_tier)
    storage_object = put_bytes(
        key,
        _encode_payload(payload),
        bucket=bucket,
        content_type=content_type,
        metadata=_storage_metadata(content_type, filename=Path(filename).name),
    )

    resolved_linked_objects = dict(linked_objects or {})
    if ingestion_job is not None and getattr(ingestion_job, "input_storage_uri", None):
        resolved_linked_objects.setdefault("input_storage_uri", ingestion_job.input_storage_uri)
    if ingestion_job is not None and getattr(ingestion_job, "manifest_storage_uri", None):
        resolved_linked_objects.setdefault(
            "existing_manifest_storage_uri",
            ingestion_job.manifest_storage_uri,
        )
    if report is not None and getattr(report, "file_storage_uri", None):
        resolved_linked_objects.setdefault("report_storage_uri", report.file_storage_uri)

    storage_contract = build_artifact_storage_contract(
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        ingestion_job_id=str(getattr(ingestion_job, "id", "") or "") or None,
        report_id=str(getattr(report, "id", "") or "") or None,
        artifact_kind=artifact_kind,
        artifact_name=artifact_name,
        storage_object=storage_object,
        publication_tier=publication_tier,
        object_role=_object_role_for_artifact_kind(artifact_kind),
        content_type=content_type,
        linked_objects=resolved_linked_objects,
    )
    artifact_lineage = dict(lineage or {})
    artifact_lineage["storage_contract"] = storage_contract

    artifact_reference = repositories.create_artifact_reference(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        ingestion_job_id=getattr(ingestion_job, "id", None),
        created_by_user_id=created_by_user_id,
        artifact_kind=artifact_kind,
        artifact_name=artifact_name,
        storage_uri=storage_object.uri(),
        content_type=content_type,
        publication_tier=publication_tier,
        lineage=artifact_lineage,
    )

    if ingestion_job is not None and "manifest" in artifact_kind:
        repositories.attach_ingestion_job_storage(
            session,
            ingestion_job,
            manifest_storage_uri=storage_object.uri(),
            parameters={"manifest_storage_contract": storage_contract},
        )

    if report is not None:
        repositories.mark_report_generated(
            session,
            report,
            file_storage_uri=storage_object.uri(),
            summary={"storage_contract": storage_contract},
        )

    return {
        "artifact_reference": artifact_reference,
        "storage_object": storage_object,
        "storage_contract": storage_contract,
        "access": resolve_artifact_download(
            storage_object.uri(),
            publication_tier=publication_tier,
        ),
    }
