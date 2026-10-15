from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.storage import (  # noqa: E402
    StorageSettings,
    build_generated_artifact_key,
    build_manifest_key,
    build_report_key,
    build_upload_key,
    ensure_default_buckets,
    presign_put,
    resolve_artifact_download,
    select_bucket_for_tier,
)


class ApiStorageTests(unittest.TestCase):
    def test_storage_key_builders_and_bucket_selection_cover_uploads_reports_and_artifacts(self) -> None:
        settings = StorageSettings(
            bucket="road-risk-private",
            public_bucket="road-risk-public",
            prefix="artifacts",
            uploads_prefix="uploads",
            reports_prefix="reports",
            manifests_prefix="manifests",
        )
        with patch("apps.api.storage.get_storage_settings", return_value=settings):
            self.assertEqual(select_bucket_for_tier("public"), "road-risk-public")
            self.assertEqual(select_bucket_for_tier("restricted"), "road-risk-private")
            self.assertEqual(
                build_upload_key(
                    "org-1",
                    "../crashes.csv",
                    municipality_id="mun-1",
                    job_type="crash_ingestion",
                ),
                "uploads/org-1/mun-1/crash_ingestion/crashes.csv",
            )
            self.assertEqual(
                build_report_key(
                    "org-1",
                    "monthly_safety_overview",
                    "bari-overview.pdf",
                    municipality_id="mun-1",
                ),
                "reports/org-1/mun-1/monthly_safety_overview/bari-overview.pdf",
            )
            self.assertEqual(
                build_manifest_key(
                    "org-1",
                    "dashboard_summary_manifest",
                    "summary.manifest.json",
                    municipality_id="mun-1",
                ),
                "manifests/org-1/mun-1/dashboard_summary_manifest/summary.manifest.json",
            )
            self.assertEqual(
                build_generated_artifact_key(
                    "org-1",
                    "published_resource_index",
                    "published_resources.json",
                    municipality_id="mun-1",
                ),
                "artifacts/org-1/mun-1/published_resource_index/published_resources.json",
            )

    def test_resolve_artifact_download_uses_public_url_or_presigned_get(self) -> None:
        settings = StorageSettings(
            endpoint_url="http://127.0.0.1:9000",
            bucket="road-risk-private",
            public_bucket="road-risk-public",
            presign_expires_s=900,
            use_ssl=False,
            verify_ssl=False,
        )
        client = Mock()
        client.generate_presigned_url.return_value = "https://signed.example/object"
        with (
            patch("apps.api.storage.get_storage_settings", return_value=settings),
            patch("apps.api.storage.get_storage_client", return_value=client),
        ):
            public_access = resolve_artifact_download(
                "s3://road-risk-public/maps/public.geojson",
                publication_tier="public",
            )
            self.assertEqual(public_access.access_mode, "public_url")
            self.assertEqual(
                public_access.download_url,
                "http://127.0.0.1:9000/road-risk-public/maps/public.geojson",
            )
            self.assertIsNone(public_access.expires_in_s)

            restricted_access = resolve_artifact_download(
                "s3://road-risk-private/reports/bari.pdf",
                publication_tier="restricted",
            )
            self.assertEqual(restricted_access.access_mode, "presigned_get")
            self.assertEqual(restricted_access.download_url, "https://signed.example/object")
            self.assertEqual(restricted_access.expires_in_s, 900)
            client.generate_presigned_url.assert_called_with(
                "get_object",
                Params={"Bucket": "road-risk-private", "Key": "reports/bari.pdf"},
                ExpiresIn=900,
            )

    def test_presigned_put_binds_content_type_when_clients_must_send_one(self) -> None:
        settings = StorageSettings(bucket="road-risk-private", presign_expires_s=300)
        client = Mock()
        client.generate_presigned_url.return_value = "https://signed.example/upload"
        with (
            patch("apps.api.storage.get_storage_settings", return_value=settings),
            patch("apps.api.storage.get_storage_client", return_value=client),
        ):
            upload_url = presign_put(
                "uploads/org-1/mun-1/crash_ingestion/crashes.csv",
                bucket="road-risk-private",
                content_type="text/csv",
            )

        self.assertEqual(upload_url, "https://signed.example/upload")
        client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": "road-risk-private",
                "Key": "uploads/org-1/mun-1/crash_ingestion/crashes.csv",
                "ContentType": "text/csv",
            },
            ExpiresIn=300,
        )

    def test_ensure_default_buckets_supports_local_minio_bootstrap(self) -> None:
        settings = StorageSettings(
            bucket="road-risk-private",
            public_bucket="road-risk-public",
            region="us-east-1",
            auto_create_buckets=True,
        )
        client = Mock()
        not_found = ClientError({"Error": {"Code": "404"}}, "HeadBucket")
        client.head_bucket.side_effect = [not_found, not_found]
        with (
            patch("apps.api.storage.get_storage_settings", return_value=settings),
            patch("apps.api.storage.get_storage_client", return_value=client),
        ):
            ensure_default_buckets()
        self.assertEqual(client.create_bucket.call_count, 2)
        client.create_bucket.assert_any_call(Bucket="road-risk-private")
        client.create_bucket.assert_any_call(Bucket="road-risk-public")
