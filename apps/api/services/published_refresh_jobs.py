"""Backend job wrapper for published refresh and dashboard refresh orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
import traceback
from pathlib import Path
from typing import Any, Callable

from apps.api.db import repositories
from apps.api.storage import resolve_artifact_download
import apps.api.services.artifact_storage as artifact_storage
from road_risk_modeling.published_refresh import build_published_refresh_bundle


PUBLISHED_REFRESH_JOB_TYPE = "published_refresh_bundle"
PUBLISHED_REFRESH_TASK_NAME = "services.workers.tasks.published_refresh.run_job"
PUBLISHED_REFRESH_JOB_LOG_VERSION = "published_refresh_job_log_v1"

PublishedRefreshRunner = Callable[..., dict[str, Any]]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_published_refresh_job_parameters(
    *,
    data_root: str | Path = "data",
    registry_output_dir: str | Path = "data/registry",
    published_index_output_dir: str | Path = "data/published_index",
    dashboard_output_dir: str | Path = "data/dashboard",
    output_dir: str | Path = "data/reporting/published_refresh/latest",
) -> dict[str, str]:
    return {
        "data_root": str(Path(data_root)),
        "registry_output_dir": str(Path(registry_output_dir)),
        "published_index_output_dir": str(Path(published_index_output_dir)),
        "dashboard_output_dir": str(Path(dashboard_output_dir)),
        "output_dir": str(Path(output_dir)),
    }


def create_published_refresh_job(
    session: Any,
    *,
    organization_id: str,
    municipality_id: str | None = None,
    submitted_by_user_id: str | None = None,
    source_id: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> Any:
    return repositories.create_ingestion_job(
        session,
        organization_id=organization_id,
        municipality_id=municipality_id,
        source_id=source_id,
        submitted_by_user_id=submitted_by_user_id,
        job_type=PUBLISHED_REFRESH_JOB_TYPE,
        parameters=dict(parameters or {}),
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _json_log_payload(
    *,
    job: Any,
    status: str,
    log_lines: list[str],
    parameters: dict[str, Any],
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    traceback_text: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "published_refresh_job_log_version": PUBLISHED_REFRESH_JOB_LOG_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "job_id": str(job.id),
        "job_type": job.job_type,
        "status": status,
        "parameters": parameters,
        "log_lines": list(log_lines),
    }
    if result is not None:
        payload["result"] = result
    if error_message is not None:
        payload["error_message"] = error_message
    if traceback_text is not None:
        payload["traceback"] = traceback_text
    return payload


def _persist_job_log(
    session: Any,
    *,
    job: Any,
    parameters: dict[str, Any],
    publication_tier: str,
    status: str,
    log_lines: list[str],
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    traceback_text: str | None = None,
) -> dict[str, Any]:
    return artifact_storage.persist_generated_artifact(
        session,
        organization_id=str(job.organization_id),
        municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        ingestion_job=job,
        created_by_user_id=str(job.submitted_by_user_id) if job.submitted_by_user_id is not None else None,
        artifact_kind="backend_job_execution_log",
        artifact_name=f"Published refresh job log {job.id}",
        filename=f"published_refresh_job_{job.id}_{status}.json",
        payload=_json_log_payload(
            job=job,
            status=status,
            log_lines=log_lines,
            parameters=parameters,
            result=result,
            error_message=error_message,
            traceback_text=traceback_text,
        ),
        publication_tier=publication_tier,
        content_type="application/json",
        linked_objects={
            "job_type": job.job_type,
            "job_status": status,
        },
    )


def _output_paths(parameters: dict[str, Any], refresh_result: dict[str, Any]) -> dict[str, Path]:
    output_dir = Path(parameters["output_dir"])
    registry_output_dir = Path(parameters["registry_output_dir"])
    published_index_output_dir = Path(parameters["published_index_output_dir"])
    dashboard_output_dir = Path(parameters["dashboard_output_dir"])
    return {
        "published_refresh_bundle_json": output_dir / "published_refresh_bundle.json",
        "published_refresh_bundle_markdown": output_dir / "published_refresh_bundle.md",
        "published_refresh_schedule_json": output_dir / "published_refresh_schedule.json",
        "published_refresh_bundle_manifest": Path(refresh_result["manifest_path"]),
        "run_registry_jsonl": registry_output_dir / "run_registry.jsonl",
        "published_resource_index_json": published_index_output_dir / "published_resources.json",
        "dashboard_summary_json": dashboard_output_dir / "dashboard_summary.json",
        "dashboard_summary_manifest": dashboard_output_dir / "dashboard_summary.manifest.json",
    }


def _persist_published_refresh_outputs(
    session: Any,
    *,
    job: Any,
    parameters: dict[str, Any],
    refresh_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    output_paths = _output_paths(parameters, refresh_result)
    shared_kwargs = {
        "session": session,
        "organization_id": str(job.organization_id),
        "municipality_id": str(job.municipality_id) if job.municipality_id is not None else None,
        "ingestion_job": job,
        "created_by_user_id": str(job.submitted_by_user_id) if job.submitted_by_user_id is not None else None,
        "publication_tier": "internal",
        "linked_objects": {
            "local_output_dir": parameters["output_dir"],
            "local_dashboard_output_dir": parameters["dashboard_output_dir"],
            "local_published_index_output_dir": parameters["published_index_output_dir"],
            "local_registry_output_dir": parameters["registry_output_dir"],
        },
        "lineage": {
            "job_type": job.job_type,
            "job_id": str(job.id),
        },
    }

    artifacts: dict[str, dict[str, Any]] = {}
    artifacts["published_refresh_bundle_json"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="published_refresh_bundle_json",
        artifact_name="Published refresh bundle JSON",
        filename=output_paths["published_refresh_bundle_json"].name,
        payload=_read_bytes(output_paths["published_refresh_bundle_json"]),
        content_type="application/json",
    )
    artifacts["published_refresh_bundle_markdown"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="published_refresh_bundle_markdown",
        artifact_name="Published refresh bundle Markdown",
        filename=output_paths["published_refresh_bundle_markdown"].name,
        payload=_read_text(output_paths["published_refresh_bundle_markdown"]),
        content_type="text/markdown",
    )
    artifacts["published_refresh_schedule_json"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="published_refresh_schedule_json",
        artifact_name="Published refresh schedule JSON",
        filename=output_paths["published_refresh_schedule_json"].name,
        payload=_read_bytes(output_paths["published_refresh_schedule_json"]),
        content_type="application/json",
    )
    artifacts["published_refresh_bundle_manifest"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="published_refresh_bundle_manifest",
        artifact_name="Published refresh bundle manifest",
        filename=output_paths["published_refresh_bundle_manifest"].name,
        payload=_read_bytes(output_paths["published_refresh_bundle_manifest"]),
        content_type="application/json",
    )
    artifacts["run_registry_jsonl"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="run_registry_jsonl",
        artifact_name="Run registry JSONL",
        filename=output_paths["run_registry_jsonl"].name,
        payload=_read_bytes(output_paths["run_registry_jsonl"]),
        content_type="application/jsonl",
    )
    artifacts["published_resource_index_json"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="published_resource_index_json",
        artifact_name="Published resource index JSON",
        filename=output_paths["published_resource_index_json"].name,
        payload=_read_bytes(output_paths["published_resource_index_json"]),
        content_type="application/json",
    )
    artifacts["dashboard_summary_json"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="dashboard_summary_json",
        artifact_name="Dashboard summary JSON",
        filename=output_paths["dashboard_summary_json"].name,
        payload=_read_bytes(output_paths["dashboard_summary_json"]),
        content_type="application/json",
    )
    artifacts["dashboard_summary_manifest"] = artifact_storage.persist_generated_artifact(
        **shared_kwargs,
        artifact_kind="dashboard_summary_manifest",
        artifact_name="Dashboard summary manifest",
        filename=output_paths["dashboard_summary_manifest"].name,
        payload=_read_bytes(output_paths["dashboard_summary_manifest"]),
        content_type="application/json",
    )
    return artifacts


def execute_published_refresh_job(
    session: Any,
    job: Any,
    *,
    runner: PublishedRefreshRunner = build_published_refresh_bundle,
) -> dict[str, Any]:
    parameters = dict(job.parameters_json or {})
    log_lines = [
        f"{_utc_now_iso()} queued published refresh execution for job {job.id}",
    ]
    repositories.mark_ingestion_job_running(session, job)
    try:
        log_lines.append(f"{_utc_now_iso()} running published refresh bundle build")
        refresh_result = runner(
            data_root=parameters["data_root"],
            registry_output_dir=parameters["registry_output_dir"],
            published_index_output_dir=parameters["published_index_output_dir"],
            dashboard_output_dir=parameters["dashboard_output_dir"],
            output_dir=parameters["output_dir"],
        )
        log_lines.append(
            f"{_utc_now_iso()} built bundle manifest at {refresh_result['manifest_path']}"
        )
        artifacts = _persist_published_refresh_outputs(
            session,
            job=job,
            parameters=parameters,
            refresh_result=refresh_result,
        )
        log_lines.append(
            f"{_utc_now_iso()} persisted {len(artifacts)} generated artifacts to object storage"
        )
        log_artifact = _persist_job_log(
            session,
            job=job,
            parameters=parameters,
            publication_tier="internal",
            status="completed",
            log_lines=log_lines,
            result=refresh_result,
        )
        manifest_uri = artifacts["published_refresh_bundle_manifest"]["artifact_reference"].storage_uri
        log_uri = log_artifact["artifact_reference"].storage_uri
        repositories.mark_ingestion_job_finished(
            session,
            job,
            status="completed",
            manifest_storage_uri=manifest_uri,
            job_stats={
                "trigger_task_name": PUBLISHED_REFRESH_TASK_NAME,
                "artifact_storage_contract_version": artifact_storage.ARTIFACT_STORAGE_CONTRACT_VERSION,
                "published_refresh_job_log_version": PUBLISHED_REFRESH_JOB_LOG_VERSION,
                "output_artifact_count": len(artifacts),
                "output_artifacts": {
                    key: value["artifact_reference"].storage_uri for key, value in artifacts.items()
                },
                "log_storage_uri": log_uri,
                **dict(refresh_result.get("stats") or {}),
            },
        )
        return serialize_job_status(session, job)
    except Exception as exc:
        traceback_text = traceback.format_exc()
        log_lines.append(f"{_utc_now_iso()} failed with error: {exc}")
        error_artifact = _persist_job_log(
            session,
            job=job,
            parameters=parameters,
            publication_tier="internal",
            status="failed",
            log_lines=log_lines,
            error_message=str(exc),
            traceback_text=traceback_text,
        )
        repositories.mark_ingestion_job_finished(
            session,
            job,
            status="failed",
            error_storage_uri=error_artifact["artifact_reference"].storage_uri,
            job_stats={
                "trigger_task_name": PUBLISHED_REFRESH_TASK_NAME,
                "artifact_storage_contract_version": artifact_storage.ARTIFACT_STORAGE_CONTRACT_VERSION,
                "published_refresh_job_log_version": PUBLISHED_REFRESH_JOB_LOG_VERSION,
                "error_message": str(exc),
                "log_storage_uri": error_artifact["artifact_reference"].storage_uri,
            },
        )
        raise


def serialize_job_status(session: Any, job: Any) -> dict[str, Any]:
    artifacts = repositories.list_artifact_references_for_job(session, str(job.id))
    return {
        "job_id": str(job.id),
        "organization_id": str(job.organization_id),
        "municipality_id": str(job.municipality_id) if job.municipality_id is not None else None,
        "job_type": job.job_type,
        "status": job.status,
        "queued_at": job.queued_at.isoformat() if job.queued_at is not None else None,
        "started_at": job.started_at.isoformat() if job.started_at is not None else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at is not None else None,
        "input_storage_uri": job.input_storage_uri,
        "manifest_storage_uri": job.manifest_storage_uri,
        "error_storage_uri": job.error_storage_uri,
        "parameters": dict(job.parameters_json or {}),
        "stats": dict(job.job_stats_json or {}),
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


def build_job_access_snapshot(session: Any, job: Any) -> dict[str, Any]:
    payload = serialize_job_status(session, job)
    if job.manifest_storage_uri:
        payload["manifest_access"] = resolve_artifact_download(
            job.manifest_storage_uri,
            publication_tier="internal",
        ).as_dict()
    if job.error_storage_uri:
        payload["error_access"] = resolve_artifact_download(
            job.error_storage_uri,
            publication_tier="internal",
        ).as_dict()
    return payload


__all__ = [
    "PUBLISHED_REFRESH_JOB_LOG_VERSION",
    "PUBLISHED_REFRESH_JOB_TYPE",
    "PUBLISHED_REFRESH_TASK_NAME",
    "build_job_access_snapshot",
    "build_published_refresh_job_parameters",
    "create_published_refresh_job",
    "execute_published_refresh_job",
    "serialize_job_status",
]
