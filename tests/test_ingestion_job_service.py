from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.db.repositories import create_ingestion_job  # noqa: E402
from apps.api.services.ingestion_jobs import (  # noqa: E402
    INGESTION_STATUS_CANCELLED,
    INGESTION_STATUS_COMPLETED,
    INGESTION_STATUS_FAILED,
    INGESTION_STATUS_PENDING_UPLOAD,
    INGESTION_STATUS_QUEUED,
    INGESTION_STATUS_VALIDATED_WITH_ERRORS,
    INGESTION_STATUS_VALIDATION_FAILED,
    approve_ingestion_job,
    build_upload_center_snapshot,
    cancel_ingestion_job,
    execute_ingestion_job,
    register_ingestion_upload,
    reject_ingestion_job,
    retry_ingestion_job,
    validate_ingestion_job_upload,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flush_count += 1


def _fake_access(uri: str) -> SimpleNamespace:
    return SimpleNamespace(
        as_dict=lambda: {  # noqa: ARG005
            "storage_uri": uri,
            "publication_tier": "internal",
            "access_mode": "presigned_get",
            "download_url": f"https://signed.example/{Path(uri).name}",
            "expires_in_s": 3600,
        }
    )


class IngestionJobServiceTests(unittest.TestCase):
    def test_register_ingestion_upload_sets_pending_upload_contract(self) -> None:
        session = FakeSession()
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Bari crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="approved",
            publication_tier="internal",
            status="active",
            configuration_json={"required_columns": ["crash_id", "lat"]},
        )

        def fake_prepare_ingestion_upload(
            _session,
            *,
            organization_id: str,
            municipality_id: str | None,
            source_id: str | None,
            job_type: str,
            filename: str,
            publication_tier: str,
            content_type: str | None,
            parameters: dict[str, object] | None,
            submitted_by_user_id=None,  # noqa: ANN001, ARG001
        ) -> dict[str, object]:
            job = create_ingestion_job(
                session,
                organization_id=organization_id,
                municipality_id=municipality_id,
                source_id=source_id,
                job_type=job_type,
                input_storage_uri=f"s3://road-risk/uploads/{filename}",
                parameters=parameters,
            )
            job.id = "job-upload-1"
            return {
                "job": job,
                "upload_url": "https://signed.example/upload",
                "storage_contract": {
                    "artifact_storage_contract_version": "artifact_storage_contract_v1",
                    "storage": {"publication_tier": publication_tier},
                    "metadata": {"content_type": content_type},
                },
            }

        with (
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch(
                "apps.api.services.ingestion_jobs.artifact_storage.prepare_ingestion_upload",
                side_effect=fake_prepare_ingestion_upload,
            ),
        ):
            payload = register_ingestion_upload(
                session,
                organization_id="org-1",
                source_id="source-1",
                municipality_id="mun-1",
                filename="crashes.csv",
                content_type="text/csv",
                submitted_by_subject="demo.user",
            )

        job = payload["job"]
        self.assertEqual(job.status, INGESTION_STATUS_PENDING_UPLOAD)
        self.assertEqual(payload["upload_url"], "https://signed.example/upload")
        self.assertEqual(job.parameters_json["publication_tier"], "internal")
        self.assertEqual(
            job.parameters_json["ingestion_upload_contract"]["source"]["name"],
            "Bari crash feed",
        )

    def test_validate_ingestion_job_upload_persists_manifest_errors_and_log(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            input_storage_uri="s3://road-risk/uploads/crashes.csv",
            parameters={
                "original_filename": "crashes.csv",
                "content_type": "text/csv",
                "publication_tier": "internal",
            },
        )
        job.id = "job-1"
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Bari crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="approved",
            publication_tier="internal",
            status="active",
            configuration_json={
                "required_columns": ["crash_id", "lat"],
                "delimiter": ",",
                "preview_row_limit": 2,
                "error_excerpt_limit": 10,
                "scan_row_limit": 10,
            },
        )
        captured_artifacts: list[SimpleNamespace] = []

        def fake_persist_generated_artifact(*args, **kwargs):
            artifact_kind = kwargs["artifact_kind"]
            artifact = SimpleNamespace(
                id=f"{artifact_kind}-id",
                artifact_kind=artifact_kind,
                artifact_name=kwargs["artifact_name"],
                storage_uri=f"s3://road-risk/{artifact_kind}/{kwargs['filename']}",
                publication_tier=kwargs["publication_tier"],
                content_type=kwargs["content_type"],
            )
            captured_artifacts.append(artifact)
            return {
                "artifact_reference": artifact,
                "storage_contract": {"artifact_kind": artifact_kind},
                "access": _fake_access(artifact.storage_uri),
            }

        with (
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch(
                "apps.api.services.ingestion_jobs.artifact_storage.persist_generated_artifact",
                side_effect=fake_persist_generated_artifact,
            ),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job",
                side_effect=lambda _session, _job_id: captured_artifacts,
            ),
            patch(
                "apps.api.services.ingestion_jobs.resolve_artifact_download",
                side_effect=lambda uri, publication_tier: _fake_access(uri),  # noqa: ARG005
            ),
        ):
            payload = validate_ingestion_job_upload(
                session,
                job,
                storage_reader=lambda _uri: b"crash_id,lat\n1,41.1\n,41.2\n",
            )

        self.assertEqual(job.status, INGESTION_STATUS_VALIDATED_WITH_ERRORS)
        self.assertTrue(str(job.manifest_storage_uri).endswith("_manifest.json"))
        self.assertTrue(str(job.error_storage_uri).endswith("_errors.json"))
        self.assertEqual(payload["stats"]["validation_outcome"], "preview_row_errors_detected")
        self.assertEqual(payload["stats"]["error_count"], 1)
        self.assertEqual(len(payload["artifacts"]), 3)
        self.assertIn("log_access", payload)

    def test_validate_ingestion_job_upload_blocks_non_approved_governance(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            input_storage_uri="s3://road-risk/uploads/crashes.csv",
            parameters={
                "original_filename": "crashes.csv",
                "content_type": "text/csv",
                "publication_tier": "internal",
            },
        )
        job.id = "job-2"
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Draft crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="draft",
            publication_tier="internal",
            status="active",
            configuration_json={"required_columns": ["crash_id"]},
        )
        captured_artifacts: list[SimpleNamespace] = []

        def fake_persist_generated_artifact(*args, **kwargs):
            artifact_kind = kwargs["artifact_kind"]
            artifact = SimpleNamespace(
                id=f"{artifact_kind}-id",
                artifact_kind=artifact_kind,
                artifact_name=kwargs["artifact_name"],
                storage_uri=f"s3://road-risk/{artifact_kind}/{kwargs['filename']}",
                publication_tier=kwargs["publication_tier"],
                content_type=kwargs["content_type"],
            )
            captured_artifacts.append(artifact)
            return {
                "artifact_reference": artifact,
                "storage_contract": {"artifact_kind": artifact_kind},
                "access": _fake_access(artifact.storage_uri),
            }

        with (
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch(
                "apps.api.services.ingestion_jobs.artifact_storage.persist_generated_artifact",
                side_effect=fake_persist_generated_artifact,
            ),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job",
                side_effect=lambda _session, _job_id: captured_artifacts,
            ),
            patch(
                "apps.api.services.ingestion_jobs.resolve_artifact_download",
                side_effect=lambda uri, publication_tier: _fake_access(uri),  # noqa: ARG005
            ),
        ):
            payload = validate_ingestion_job_upload(
                session,
                job,
                storage_reader=lambda _uri: b"crash_id\n1\n",
            )

        self.assertEqual(job.status, INGESTION_STATUS_VALIDATION_FAILED)
        self.assertEqual(payload["stats"]["validation_outcome"], "governance_blocked")
        self.assertEqual(payload["stats"]["governance_check_status"], "blocked")

    def test_validate_ingestion_job_upload_applies_field_mapping_and_quality_checks(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            input_storage_uri="s3://road-risk/uploads/crashes.csv",
            parameters={
                "original_filename": "crashes.csv",
                "content_type": "text/csv",
                "publication_tier": "internal",
                "field_mapping": {
                    "crash_id": "incident_id",
                    "latitude": "lat",
                    "longitude": "lon",
                },
            },
        )
        job.id = "job-mapped"
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Mapped crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="approved",
            publication_tier="internal",
            status="active",
            configuration_json={
                "required_columns": ["crash_id", "latitude", "longitude"],
                "preview_row_limit": 5,
                "error_excerpt_limit": 10,
                "scan_row_limit": 10,
            },
        )
        captured_artifacts: list[SimpleNamespace] = []

        def fake_persist_generated_artifact(*args, **kwargs):
            artifact_kind = kwargs["artifact_kind"]
            artifact = SimpleNamespace(
                id=f"{artifact_kind}-id",
                artifact_kind=artifact_kind,
                artifact_name=kwargs["artifact_name"],
                storage_uri=f"s3://road-risk/{artifact_kind}/{kwargs['filename']}",
                publication_tier=kwargs["publication_tier"],
                content_type=kwargs["content_type"],
            )
            captured_artifacts.append(artifact)
            return {
                "artifact_reference": artifact,
                "storage_contract": {"artifact_kind": artifact_kind},
                "access": _fake_access(artifact.storage_uri),
            }

        with (
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch(
                "apps.api.services.ingestion_jobs.artifact_storage.persist_generated_artifact",
                side_effect=fake_persist_generated_artifact,
            ),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job",
                side_effect=lambda _session, _job_id: captured_artifacts,
            ),
            patch(
                "apps.api.services.ingestion_jobs.resolve_artifact_download",
                side_effect=lambda uri, publication_tier: _fake_access(uri),  # noqa: ARG005
            ),
        ):
            payload = validate_ingestion_job_upload(
                session,
                job,
                storage_reader=lambda _uri: (
                    b"incident_id,lat,lon\n"
                    b"1,91,16.8\n"
                    b"2,41.1,16.8\n"
                    b"2,41.1,16.8\n"
                ),
            )

        self.assertEqual(job.status, INGESTION_STATUS_VALIDATED_WITH_ERRORS)
        self.assertEqual(payload["stats"]["missing_required_columns"], [])
        self.assertEqual(payload["stats"]["field_mapping"]["crash_id"], "incident_id")
        self.assertEqual(payload["stats"]["invalid_coordinate_count"], 1)
        self.assertEqual(payload["stats"]["duplicate_row_count"], 1)
        self.assertEqual(payload["workflow"]["required_next_action"], "review_validation_then_approve_or_reject")

    def test_upload_center_snapshot_includes_sources_jobs_and_supported_formats(self) -> None:
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Bari crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="approved",
            publication_tier="internal",
            status="active",
            configuration_json={"required_columns": ["crash_id", "latitude"]},
        )
        job = create_ingestion_job(
            FakeSession(),
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            status="validated_ready",
        )
        job.id = "job-1"
        with (
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_data_sources_for_organization",
                return_value=[source],
            ),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_ingestion_jobs_for_organization",
                return_value=[job],
            ),
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job",
                return_value=[],
            ),
        ):
            snapshot = build_upload_center_snapshot(
                object(),
                organization_id="org-1",
                municipality_id="mun-1",
            )

        self.assertEqual(snapshot["contract_version"], "ingestion_upload_center_v1")
        self.assertEqual(snapshot["supported_formats"], ["csv", "geojson", "json", "zip"])
        self.assertTrue(snapshot["sources"][0]["upload_enabled"])
        self.assertEqual(snapshot["sources"][0]["required_columns"], ["crash_id", "latitude"])
        self.assertEqual(snapshot["jobs"][0]["job_id"], "job-1")

    def test_approve_and_reject_ingestion_job_decisions_update_status(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            status="validated_ready",
        )
        job.id = "job-decision"
        with (
            patch("apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job", return_value=[]),
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=None),
            patch("apps.api.services.ingestion_jobs.repositories.record_audit_log"),
        ):
            approved = approve_ingestion_job(
                session,
                job,
                approved_by_subject="operator.demo",
                decision_note="ready",
            )

        self.assertEqual(job.status, INGESTION_STATUS_QUEUED)
        self.assertEqual(approved["workflow"]["required_next_action"], "run_ingestion_worker_execution")

        job.status = "validated_with_errors"
        with (
            patch("apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job", return_value=[]),
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=None),
            patch("apps.api.services.ingestion_jobs.repositories.record_audit_log"),
        ):
            rejected = reject_ingestion_job(
                session,
                job,
                rejected_by_subject="operator.demo",
                decision_note="bad rows",
            )

        self.assertEqual(job.status, "rejected")
        self.assertEqual(rejected["workflow"]["required_next_action"], "no_action_rejected")

    def test_execute_ingestion_job_runs_crash_engine_and_persists_artifacts(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            status=INGESTION_STATUS_QUEUED,
            input_storage_uri="s3://road-risk/uploads/crashes.csv",
            parameters={
                "original_filename": "crashes.csv",
                "content_type": "text/csv",
                "publication_tier": "internal",
                "source_year": 2025,
            },
        )
        job.id = "job-execute-crash"
        job.manifest_storage_uri = "s3://road-risk/validation/job-execute-crash.json"
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Bari crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="approved",
            publication_tier="internal",
            status="active",
            configuration_json={"engine_adapter": "bari_open_data_crashes"},
        )
        captured_artifacts: list[SimpleNamespace] = []
        captured_payloads: dict[str, object] = {}

        def fake_engine(output_dir, *, raw_dir, sources, limit=None):  # noqa: ANN001, ARG001
            output_root = Path(output_dir)
            output_root.mkdir(parents=True, exist_ok=True)
            records_path = output_root / "bari_open_data_canonical.jsonl"
            manifest_path = output_root / "bari_open_data_canonical.manifest.json"
            records_path.write_text('{"crash_id":"demo"}\n', encoding="utf-8")
            manifest = {
                "outputs": {
                    "records_path": str(records_path),
                    "manifest_path": str(manifest_path),
                },
                "stats": {"total_records": 1},
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            return manifest

        def fake_persist_generated_artifact(*args, **kwargs):
            artifact_kind = kwargs["artifact_kind"]
            captured_payloads[artifact_kind] = kwargs["payload"]
            artifact = SimpleNamespace(
                id=f"{artifact_kind}-id",
                artifact_kind=artifact_kind,
                artifact_name=kwargs["artifact_name"],
                storage_uri=f"s3://road-risk/{artifact_kind}/{kwargs['filename']}",
                publication_tier=kwargs["publication_tier"],
                content_type=kwargs["content_type"],
            )
            captured_artifacts.append(artifact)
            return {
                "artifact_reference": artifact,
                "storage_contract": {"artifact_kind": artifact_kind},
                "access": _fake_access(artifact.storage_uri),
            }

        with (
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch("apps.api.services.ingestion_jobs.ingest_bari_open_data_crashes", side_effect=fake_engine),
            patch(
                "apps.api.services.ingestion_jobs.artifact_storage.persist_generated_artifact",
                side_effect=fake_persist_generated_artifact,
            ),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job",
                side_effect=lambda _session, _job_id: captured_artifacts,
            ),
            patch(
                "apps.api.services.ingestion_jobs.resolve_artifact_download",
                side_effect=lambda uri, publication_tier: _fake_access(uri),  # noqa: ARG005
            ),
            patch("apps.api.services.ingestion_jobs.repositories.record_audit_log"),
        ):
            payload = execute_ingestion_job(
                session,
                job,
                storage_reader=lambda _uri: b"Data incidente;lat;lon\n01/01/2025;41.1;16.8\n",
            )

        self.assertEqual(job.status, INGESTION_STATUS_COMPLETED, job.job_stats_json)
        self.assertEqual(payload["stats"]["execution_status"], INGESTION_STATUS_COMPLETED)
        self.assertEqual(payload["stats"]["execution_engine"], "crash_csv")
        self.assertEqual(payload["stats"]["engine_stats"]["total_records"], 1)
        self.assertIn("ingestion_execution_manifest", captured_payloads)
        self.assertTrue(any(artifact.artifact_kind == "ingestion_execution_records" for artifact in captured_artifacts))
        self.assertTrue(str(job.manifest_storage_uri).endswith("_execution_manifest.json"))

    def test_execute_ingestion_job_marks_runtime_failure_with_actionable_error(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            status=INGESTION_STATUS_QUEUED,
            input_storage_uri="s3://road-risk/uploads/crashes.csv",
            parameters={"original_filename": "crashes.csv", "publication_tier": "internal"},
        )
        job.id = "job-execute-failed"
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Bari crash feed",
            source_type="crash_feed",
            provider_name="Comune di Bari",
            governance_status="approved",
            publication_tier="internal",
            status="active",
            configuration_json={"engine_adapter": "bari_open_data_crashes"},
        )
        captured_artifacts: list[SimpleNamespace] = []
        captured_payloads: dict[str, object] = {}

        def fake_persist_generated_artifact(*args, **kwargs):
            artifact_kind = kwargs["artifact_kind"]
            captured_payloads[artifact_kind] = kwargs["payload"]
            artifact = SimpleNamespace(
                id=f"{artifact_kind}-id",
                artifact_kind=artifact_kind,
                artifact_name=kwargs["artifact_name"],
                storage_uri=f"s3://road-risk/{artifact_kind}/{kwargs['filename']}",
                publication_tier=kwargs["publication_tier"],
                content_type=kwargs["content_type"],
            )
            captured_artifacts.append(artifact)
            return {
                "artifact_reference": artifact,
                "storage_contract": {"artifact_kind": artifact_kind},
                "access": _fake_access(artifact.storage_uri),
            }

        with (
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch("apps.api.services.ingestion_jobs.ingest_bari_open_data_crashes", side_effect=RuntimeError("bad runtime")),
            patch(
                "apps.api.services.ingestion_jobs.artifact_storage.persist_generated_artifact",
                side_effect=fake_persist_generated_artifact,
            ),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job",
                side_effect=lambda _session, _job_id: captured_artifacts,
            ),
            patch(
                "apps.api.services.ingestion_jobs.resolve_artifact_download",
                side_effect=lambda uri, publication_tier: _fake_access(uri),  # noqa: ARG005
            ),
            patch("apps.api.services.ingestion_jobs.repositories.record_audit_log"),
        ):
            payload = execute_ingestion_job(session, job, storage_reader=lambda _uri: b"bad\n")

        self.assertEqual(job.status, INGESTION_STATUS_FAILED)
        self.assertEqual(payload["stats"]["execution_status"], INGESTION_STATUS_FAILED)
        self.assertIn("bad runtime", payload["stats"]["error_message"])
        error_payload = captured_payloads["ingestion_execution_errors"]
        self.assertIn("Fix the upload", error_payload["summary"]["required_next_action"])
        self.assertTrue(str(job.error_storage_uri).endswith("_execution_errors.json"))

    def test_execute_ingestion_job_runs_exposure_connector_engine_with_mapping_stub(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="exposure_connector_ingestion",
            status=INGESTION_STATUS_QUEUED,
            input_storage_uri="s3://road-risk/uploads/connector.csv",
            parameters={
                "original_filename": "connector.csv",
                "publication_tier": "restricted",
                "mapping_stub": {"capability_code": "motorized_exposure", "field_mappings": []},
            },
        )
        job.id = "job-exposure"
        source = SimpleNamespace(
            id="source-1",
            organization_id="org-1",
            municipality_id="mun-1",
            name="Counter connector",
            source_type="exposure_connector",
            provider_name="Municipal counters",
            governance_status="approved",
            publication_tier="restricted",
            status="active",
            configuration_json={},
        )
        captured_artifacts: list[SimpleNamespace] = []

        def fake_engine(input_csv_path, mapping_stub_path, output_dir, *, limit=None, governance_bundle_path=None):  # noqa: ANN001, ARG001
            self.assertTrue(Path(input_csv_path).is_file())
            self.assertEqual(json.loads(Path(mapping_stub_path).read_text(encoding="utf-8"))["capability_code"], "motorized_exposure")
            output_root = Path(output_dir)
            output_root.mkdir(parents=True, exist_ok=True)
            observations_path = output_root / "connector_observations.jsonl"
            rejected_rows_path = output_root / "connector_rejected_rows.jsonl"
            manifest_path = output_root / "connector_observations.manifest.json"
            observations_path.write_text('{"source_record_id":"demo"}\n', encoding="utf-8")
            rejected_rows_path.write_text("", encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "observations_path": str(observations_path),
                            "rejected_rows_path": str(rejected_rows_path),
                            "manifest_path": str(manifest_path),
                        },
                        "stats": {"written_rows": 1, "rejected_rows": 0},
                    }
                ),
                encoding="utf-8",
            )
            return {
                "manifest_path": str(manifest_path),
                "stats": {"written_rows": 1, "rejected_rows": 0},
            }

        def fake_persist_generated_artifact(*args, **kwargs):
            artifact_kind = kwargs["artifact_kind"]
            artifact = SimpleNamespace(
                id=f"{artifact_kind}-id",
                artifact_kind=artifact_kind,
                artifact_name=kwargs["artifact_name"],
                storage_uri=f"s3://road-risk/{artifact_kind}/{kwargs['filename']}",
                publication_tier=kwargs["publication_tier"],
                content_type=kwargs["content_type"],
            )
            captured_artifacts.append(artifact)
            return {
                "artifact_reference": artifact,
                "storage_contract": {"artifact_kind": artifact_kind},
                "access": _fake_access(artifact.storage_uri),
            }

        with (
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=source),
            patch("apps.api.services.ingestion_jobs.ingest_exposure_connector_extract", side_effect=fake_engine),
            patch(
                "apps.api.services.ingestion_jobs.artifact_storage.persist_generated_artifact",
                side_effect=fake_persist_generated_artifact,
            ),
            patch(
                "apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job",
                side_effect=lambda _session, _job_id: captured_artifacts,
            ),
            patch(
                "apps.api.services.ingestion_jobs.resolve_artifact_download",
                side_effect=lambda uri, publication_tier: _fake_access(uri),  # noqa: ARG005
            ),
            patch("apps.api.services.ingestion_jobs.repositories.record_audit_log"),
        ):
            payload = execute_ingestion_job(
                session,
                job,
                storage_reader=lambda _uri: b"source_record_id\n1\n",
            )

        self.assertEqual(job.status, INGESTION_STATUS_COMPLETED, job.job_stats_json)
        self.assertEqual(payload["stats"]["execution_engine"], "exposure_connector")
        self.assertTrue(any(artifact.artifact_kind == "ingestion_execution_rejected_rows" for artifact in captured_artifacts))

    def test_retry_and_cancel_ingestion_job_update_execution_lifecycle(self) -> None:
        session = FakeSession()
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_feed_ingestion",
            status=INGESTION_STATUS_FAILED,
        )
        job.id = "job-retry"
        with (
            patch("apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job", return_value=[]),
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=None),
            patch("apps.api.services.ingestion_jobs.repositories.record_audit_log"),
        ):
            retried = retry_ingestion_job(
                session,
                job,
                retried_by_subject="operator.demo",
                decision_note="fixed mapping",
            )

        self.assertEqual(job.status, INGESTION_STATUS_QUEUED)
        self.assertEqual(job.job_stats_json["retry_count"], 1)
        self.assertEqual(retried["workflow"]["required_next_action"], "run_ingestion_worker_execution")

        with (
            patch("apps.api.services.ingestion_jobs.repositories.list_artifact_references_for_job", return_value=[]),
            patch("apps.api.services.ingestion_jobs.repositories.get_data_source", return_value=None),
            patch("apps.api.services.ingestion_jobs.repositories.record_audit_log"),
        ):
            cancelled = cancel_ingestion_job(
                session,
                job,
                cancelled_by_subject="operator.demo",
                decision_note="stop",
            )

        self.assertEqual(job.status, INGESTION_STATUS_CANCELLED)
        self.assertEqual(cancelled["workflow"]["required_next_action"], "retry_or_archive_cancelled_job")
