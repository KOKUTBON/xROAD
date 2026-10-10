from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.db.repositories import create_ingestion_job, create_report  # noqa: E402
from apps.api.services.artifact_storage import (  # noqa: E402
    ARTIFACT_STORAGE_CONTRACT_VERSION,
    persist_generated_artifact,
    prepare_ingestion_upload,
    prepare_report_output,
)
from apps.api.storage import ArtifactAccess, StorageObject, StorageSettings  # noqa: E402


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_count = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flush_count += 1


class ApiArtifactStorageServiceTests(unittest.TestCase):
    def test_prepare_ingestion_upload_creates_remote_job_slot_and_storage_contract(self) -> None:
        session = FakeSession()
        settings = StorageSettings(
            bucket="road-risk-private",
            public_bucket="road-risk-public",
            auto_create_buckets=True,
        )
        with (
            patch("apps.api.services.artifact_storage.get_storage_settings", return_value=settings),
            patch("apps.api.services.artifact_storage.ensure_default_buckets") as ensure_buckets,
            patch(
                "apps.api.services.artifact_storage.select_bucket_for_tier",
                return_value="road-risk-private",
            ),
            patch(
                "apps.api.services.artifact_storage.presign_put",
                return_value="https://signed.example/upload",
            ) as presign_put_mock,
        ):
            result = prepare_ingestion_upload(
                session,
                organization_id="org-1",
                municipality_id="mun-1",
                source_id="source-1",
                job_type="crash_ingestion",
                filename="../crashes.csv",
                publication_tier="restricted",
                content_type="text/csv",
                parameters={"dry_run": False},
            )
        ensure_buckets.assert_called_once()
        job = result["job"]
        self.assertEqual(
            job.input_storage_uri,
            "s3://road-risk-private/uploads/org-1/mun-1/crash_ingestion/crashes.csv",
        )
        self.assertEqual(result["upload_url"], "https://signed.example/upload")
        self.assertEqual(
            job.parameters_json["storage_contract"]["artifact_storage_contract_version"],
            ARTIFACT_STORAGE_CONTRACT_VERSION,
        )
        self.assertEqual(job.parameters_json["content_type"], "text/csv")
        presign_put_mock.assert_called_once_with(
            "uploads/org-1/mun-1/crash_ingestion/crashes.csv",
            bucket="road-risk-private",
            content_type="text/csv",
        )

    def test_prepare_report_output_creates_remote_report_slot(self) -> None:
        session = FakeSession()
        settings = StorageSettings(
            bucket="road-risk-private",
            public_bucket="road-risk-public",
            auto_create_buckets=True,
        )
        with (
            patch("apps.api.services.artifact_storage.get_storage_settings", return_value=settings),
            patch("apps.api.services.artifact_storage.ensure_default_buckets") as ensure_buckets,
            patch(
                "apps.api.services.artifact_storage.select_bucket_for_tier",
                return_value="road-risk-private",
            ),
            patch(
                "apps.api.services.artifact_storage.presign_put",
                return_value="https://signed.example/report-upload",
            ) as presign_put_mock,
        ):
            result = prepare_report_output(
                session,
                organization_id="org-1",
                municipality_id="mun-1",
                report_type="monthly_safety_overview",
                title="Bari Monthly Overview",
                output_format="pdf",
                visibility_tier="restricted",
                filename="bari-overview.pdf",
            )
        ensure_buckets.assert_called_once()
        report = result["report"]
        self.assertEqual(report.status, "pending_upload")
        self.assertEqual(
            report.file_storage_uri,
            "s3://road-risk-private/reports/org-1/mun-1/monthly_safety_overview/bari-overview.pdf",
        )
        self.assertEqual(result["upload_url"], "https://signed.example/report-upload")
        self.assertEqual(
            report.parameters_json["storage_contract"]["entity_links"]["artifact_kind"],
            "monthly_safety_overview",
        )
        presign_put_mock.assert_called_once_with(
            "reports/org-1/mun-1/monthly_safety_overview/bari-overview.pdf",
            bucket="road-risk-private",
            content_type="application/pdf",
        )

    def test_persist_generated_artifact_registers_artifact_and_links_manifest_and_report(self) -> None:
        session = FakeSession()
        settings = StorageSettings(bucket="road-risk-private", public_bucket="road-risk-public")
        job = create_ingestion_job(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            source_id="source-1",
            job_type="crash_ingestion",
            input_storage_uri="s3://road-risk-private/uploads/org-1/mun-1/crash_ingestion/crashes.csv",
        )
        report = create_report(
            session,
            organization_id="org-1",
            municipality_id="mun-1",
            report_type="monthly_safety_overview",
            title="Bari Monthly Overview",
            visibility_tier="restricted",
        )
        with (
            patch("apps.api.services.artifact_storage.get_storage_settings", return_value=settings),
            patch(
                "apps.api.services.artifact_storage.put_bytes",
                return_value=StorageObject(
                    bucket="road-risk-private",
                    key="manifests/org-1/mun-1/dashboard_summary_manifest/summary.manifest.json",
                    etag="etag-1",
                ),
            ),
            patch(
                "apps.api.services.artifact_storage.resolve_artifact_download",
                return_value=ArtifactAccess(
                    storage_uri=(
                        "s3://road-risk-private/manifests/org-1/mun-1/"
                        "dashboard_summary_manifest/summary.manifest.json"
                    ),
                    publication_tier="restricted",
                    access_mode="presigned_get",
                    download_url="https://signed.example/download",
                    expires_in_s=3600,
                ),
            ),
        ):
            result = persist_generated_artifact(
                session,
                organization_id="org-1",
                municipality_id="mun-1",
                source_id="source-1",
                ingestion_job=job,
                report=report,
                artifact_kind="dashboard_summary_manifest",
                artifact_name="Bari dashboard summary manifest",
                filename="summary.manifest.json",
                payload={"status": "ok"},
                publication_tier="restricted",
                content_type="application/json",
                linked_objects={"dashboard_summary_uri": "s3://road-risk-private/artifacts/org-1/demo.json"},
            )
        artifact = result["artifact_reference"]
        self.assertEqual(
            artifact.storage_uri,
            "s3://road-risk-private/manifests/org-1/mun-1/dashboard_summary_manifest/summary.manifest.json",
        )
        self.assertEqual(job.manifest_storage_uri, artifact.storage_uri)
        self.assertEqual(report.status, "generated")
        self.assertEqual(report.file_storage_uri, artifact.storage_uri)
        self.assertEqual(result["access"].download_url, "https://signed.example/download")
        storage_contract = artifact.lineage_json["storage_contract"]
        self.assertEqual(
            storage_contract["artifact_storage_contract_version"],
            ARTIFACT_STORAGE_CONTRACT_VERSION,
        )
        self.assertEqual(
            storage_contract["linked_objects"]["dashboard_summary_uri"],
            "s3://road-risk-private/artifacts/org-1/demo.json",
        )
        self.assertEqual(
            storage_contract["linked_objects"]["input_storage_uri"],
            "s3://road-risk-private/uploads/org-1/mun-1/crash_ingestion/crashes.csv",
        )
