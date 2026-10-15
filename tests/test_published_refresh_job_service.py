from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.db.repositories import create_ingestion_job  # noqa: E402
from apps.api.services.published_refresh_jobs import (  # noqa: E402
    PUBLISHED_REFRESH_JOB_TYPE,
    build_published_refresh_job_parameters,
    execute_published_refresh_job,
)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flush_count += 1


class PublishedRefreshJobServiceTests(unittest.TestCase):
    def test_execute_published_refresh_job_persists_outputs_and_marks_job_completed(self) -> None:
        session = FakeSession()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            parameters = build_published_refresh_job_parameters(
                data_root=root / "data",
                registry_output_dir=root / "registry",
                published_index_output_dir=root / "published_index",
                dashboard_output_dir=root / "dashboard",
                output_dir=root / "reporting" / "published_refresh" / "latest",
            )
            job = create_ingestion_job(
                session,
                organization_id="org-1",
                municipality_id="mun-1",
                job_type=PUBLISHED_REFRESH_JOB_TYPE,
                parameters=parameters,
            )
            job.id = "job-1"

            captured_artifacts: list[SimpleNamespace] = []

            def fake_persist_generated_artifact(*args, **kwargs):
                artifact_kind = kwargs["artifact_kind"]
                filename = kwargs["filename"]
                artifact = SimpleNamespace(
                    id=f"{artifact_kind}-id",
                    artifact_kind=artifact_kind,
                    artifact_name=kwargs["artifact_name"],
                    storage_uri=f"s3://road-risk/{artifact_kind}/{filename}",
                    publication_tier=kwargs["publication_tier"],
                    content_type=kwargs["content_type"],
                )
                captured_artifacts.append(artifact)
                return {
                    "artifact_reference": artifact,
                    "storage_contract": {"artifact_kind": artifact_kind},
                    "access": SimpleNamespace(download_url="https://signed.example/object"),
                }

            def fake_runner(**kwargs):
                output_dir = Path(kwargs["output_dir"])
                output_dir.mkdir(parents=True, exist_ok=True)
                registry_dir = Path(kwargs["registry_output_dir"])
                registry_dir.mkdir(parents=True, exist_ok=True)
                published_index_dir = Path(kwargs["published_index_output_dir"])
                published_index_dir.mkdir(parents=True, exist_ok=True)
                dashboard_dir = Path(kwargs["dashboard_output_dir"])
                dashboard_dir.mkdir(parents=True, exist_ok=True)

                (output_dir / "published_refresh_bundle.json").write_text(
                    json.dumps({"status": "ok"}),
                    encoding="utf-8",
                )
                (output_dir / "published_refresh_bundle.md").write_text(
                    "# Refresh Bundle\n",
                    encoding="utf-8",
                )
                (output_dir / "published_refresh_schedule.json").write_text(
                    json.dumps({"cadence": "weekly"}),
                    encoding="utf-8",
                )
                manifest_path = output_dir / "published_refresh_bundle.manifest.json"
                manifest_path.write_text(json.dumps({"manifest": True}), encoding="utf-8")
                (registry_dir / "run_registry.jsonl").write_text('{"artifact_kind":"registry"}\n', encoding="utf-8")
                (published_index_dir / "published_resources.json").write_text(
                    json.dumps({"catalog": []}),
                    encoding="utf-8",
                )
                (dashboard_dir / "dashboard_summary.json").write_text(
                    json.dumps({"stats": {"published_run_count": 1}}),
                    encoding="utf-8",
                )
                (dashboard_dir / "dashboard_summary.manifest.json").write_text(
                    json.dumps({"manifest": True}),
                    encoding="utf-8",
                )
                return {
                    "manifest_path": str(manifest_path),
                    "stats": {"latest_published_resource_count": 1},
                }

            with (
                patch(
                    "apps.api.services.published_refresh_jobs.artifact_storage.persist_generated_artifact",
                    side_effect=fake_persist_generated_artifact,
                ),
                patch(
                    "apps.api.services.published_refresh_jobs.repositories.list_artifact_references_for_job",
                    side_effect=lambda _session, _job_id: captured_artifacts,
                ),
            ):
                payload = execute_published_refresh_job(session, job, runner=fake_runner)

        self.assertEqual(job.status, "completed")
        self.assertTrue(job.manifest_storage_uri.endswith("published_refresh_bundle.manifest.json"))
        self.assertEqual(payload["job_type"], PUBLISHED_REFRESH_JOB_TYPE)
        self.assertEqual(payload["stats"]["output_artifact_count"], 8)
        self.assertEqual(len(payload["artifacts"]), 9)
        self.assertIn("published_refresh_bundle_json", payload["stats"]["output_artifacts"])
        self.assertIn("log_storage_uri", payload["stats"])

    def test_execute_published_refresh_job_marks_failure_and_persists_error_log(self) -> None:
        session = FakeSession()
        parameters = build_published_refresh_job_parameters(
            data_root="/tmp/data",
            registry_output_dir="/tmp/registry",
            published_index_output_dir="/tmp/published_index",
            dashboard_output_dir="/tmp/dashboard",
            output_dir="/tmp/reporting/published_refresh/latest",
        )
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            job_type=PUBLISHED_REFRESH_JOB_TYPE,
            parameters=parameters,
        )
        job.id = "job-2"

        with (
            patch(
                "apps.api.services.published_refresh_jobs.artifact_storage.persist_generated_artifact",
                return_value={
                    "artifact_reference": SimpleNamespace(
                        id="error-log",
                        storage_uri="s3://road-risk/backend_job_execution_log/error.json",
                    )
                },
            ),
            patch(
                "apps.api.services.published_refresh_jobs.repositories.list_artifact_references_for_job",
                return_value=[],
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "refresh failed"):
                execute_published_refresh_job(
                    session,
                    job,
                    runner=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("refresh failed")),
                )

        self.assertEqual(job.status, "failed")
        self.assertEqual(
            job.error_storage_uri,
            "s3://road-risk/backend_job_execution_log/error.json",
        )
        self.assertEqual(job.job_stats_json["error_message"], "refresh failed")
