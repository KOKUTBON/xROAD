from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.auth import AuthContext, ROLE_ADMIN, ROLE_ANALYST, ROLE_DATA_OPERATOR, get_auth_context  # noqa: E402
from apps.api.db.session import get_db_session  # noqa: E402
from apps.api.main import APP_TITLE, APP_VERSION, create_app  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class ApiAppTests(unittest.TestCase):
    def test_openapi_health_and_auth_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client = TestClient(create_app(ApiSettings(root_dir=root)))

            openapi_response = client.get("/openapi.json")
            self.assertEqual(openapi_response.status_code, 200)
            openapi_payload = openapi_response.json()
            self.assertEqual(openapi_payload["info"]["title"], APP_TITLE)
            self.assertEqual(openapi_payload["info"]["version"], APP_VERSION)
            self.assertIn("/v1/healthz", openapi_payload["paths"])
            self.assertIn("/v1/public/health", openapi_payload["paths"])
            self.assertIn("/v1/auth/role-matrix", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/uploads", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/upload-center", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/{job_id}", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/{job_id}/validate", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/{job_id}/approve", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/{job_id}/run", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/{job_id}/retry", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/{job_id}/cancel", openapi_payload["paths"])
            self.assertIn("/v1/ingestion-jobs/{job_id}/reject", openapi_payload["paths"])
            self.assertIn("/v1/jobs/published-refresh", openapi_payload["paths"])
            self.assertIn("/v1/jobs/{job_id}", openapi_payload["paths"])
            self.assertIn("/v1/storage/uploads/presign", openapi_payload["paths"])
            self.assertIn("/v1/public/cities", openapi_payload["paths"])
            self.assertIn("/v1/public/cities/{city_key}/risk-map", openapi_payload["paths"])
            self.assertIn("/v1/public/cities/{city_key}/risk-tiles", openapi_payload["paths"])
            self.assertIn("/v1/public/cities/{city_key}/interventions", openapi_payload["paths"])
            self.assertIn("/v1/analyst/cities/{city_key}/risk-map", openapi_payload["paths"])
            self.assertIn("/v1/reports/overview", openapi_payload["paths"])
            self.assertIn("/v1/reports", openapi_payload["paths"])
            self.assertIn("/v1/reports/generate", openapi_payload["paths"])
            self.assertIn("/v1/reports/{report_id}", openapi_payload["paths"])
            self.assertIn("/v1/reports/{report_id}/download", openapi_payload["paths"])
            self.assertIn("/v1/observability/info", openapi_payload["paths"])
            self.assertIn("/v1/observability/readiness", openapi_payload["paths"])
            self.assertIn("/v1/observability/metrics", openapi_payload["paths"])
            self.assertIn("/v1/published-resource/query", openapi_payload["paths"])

            health_response = client.get("/healthz")
            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(
                health_response.json(),
                {
                    "api_version": "published_resource_api_v1",
                    "app_version": APP_VERSION,
                    "status": "ok",
                },
            )

            versioned_health_response = client.get("/v1/healthz")
            self.assertEqual(versioned_health_response.status_code, 200)
            self.assertEqual(versioned_health_response.json()["app_version"], APP_VERSION)

            public_health_response = client.get("/v1/public/health")
            self.assertEqual(public_health_response.status_code, 200)
            self.assertEqual(public_health_response.json()["app_version"], APP_VERSION)

            cors_response = client.get("/v1/healthz", headers={"Origin": "http://localhost:3000"})
            self.assertEqual(cors_response.headers["access-control-allow-origin"], "http://localhost:3000")

            auth_response = client.get("/v1/auth/me")
            self.assertEqual(auth_response.status_code, 200)
            self.assertEqual(
                auth_response.json(),
                {
                    "auth_enabled": False,
                    "assigned_roles": ["public"],
                    "municipality_ids": [],
                    "organization_ids": [],
                    "provider": "disabled",
                    "roles": ["public"],
                    "scopes": [],
                    "subject": None,
                    "scope_catalog": {"organizations": [], "municipalities": []},
                },
            )

            role_matrix_response = client.get("/v1/auth/role-matrix")
            self.assertEqual(role_matrix_response.status_code, 200)
            self.assertEqual(role_matrix_response.json()["selected_provider"], "keycloak")
            self.assertEqual(role_matrix_response.json()["role_matrix_version"], "road_risk_role_matrix_v1")

    def test_storage_presign_and_access_endpoints(self) -> None:
        app = create_app(ApiSettings(root_dir=Path("."), auth_enabled=True))
        fake_session = object()

        def _session_override():
            yield fake_session

        app.dependency_overrides[get_db_session] = _session_override
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="user-1",
            assigned_roles=frozenset({ROLE_ADMIN}),
            roles=frozenset({ROLE_ADMIN, ROLE_ANALYST, "data_operator", "municipality_viewer", "public"}),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=frozenset({"mun-1"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        client = TestClient(app)

        with (
            unittest.mock.patch(
                "apps.api.main.artifact_storage.prepare_ingestion_upload",
                return_value={
                    "job": type("Job", (), {"id": "job-1", "input_storage_uri": "s3://road-risk/uploads/file.csv"})(),
                    "upload_url": "https://signed.example/upload",
                    "storage_contract": {"artifact_storage_contract_version": "artifact_storage_contract_v1"},
                },
            ),
            unittest.mock.patch(
                "apps.api.main.artifact_storage.prepare_report_output",
                return_value={
                    "report": type("Report", (), {"id": "report-1", "file_storage_uri": "s3://road-risk/reports/file.pdf"})(),
                    "upload_url": "https://signed.example/report-upload",
                    "storage_contract": {"artifact_storage_contract_version": "artifact_storage_contract_v1"},
                },
            ),
            unittest.mock.patch(
                "apps.api.main.resolve_artifact_download",
                return_value=type(
                    "Access",
                    (),
                    {
                        "as_dict": lambda self: {  # noqa: ARG005
                            "storage_uri": "s3://road-risk/reports/file.pdf",
                            "publication_tier": "restricted",
                            "access_mode": "presigned_get",
                            "download_url": "https://signed.example/download",
                            "expires_in_s": 3600,
                        }
                    },
                )(),
            ),
        ):
            upload_response = client.post(
                "/v1/storage/uploads/presign",
                json={
                    "organization_id": "org-1",
                    "municipality_id": "mun-1",
                    "source_id": "source-1",
                    "job_type": "crash_ingestion",
                    "filename": "crashes.csv",
                    "publication_tier": "restricted",
                },
            )
            self.assertEqual(upload_response.status_code, 200)
            self.assertEqual(upload_response.json()["job_id"], "job-1")
            self.assertEqual(upload_response.json()["upload_url"], "https://signed.example/upload")

            report_response = client.post(
                "/v1/storage/reports/presign",
                json={
                    "organization_id": "org-1",
                    "municipality_id": "mun-1",
                    "report_type": "monthly_safety_overview",
                    "title": "Bari Monthly Overview",
                    "visibility_tier": "restricted",
                },
            )
            self.assertEqual(report_response.status_code, 200)
            self.assertEqual(report_response.json()["report_id"], "report-1")
            self.assertEqual(
                report_response.json()["upload_url"],
                "https://signed.example/report-upload",
            )

            access_response = client.get(
                "/v1/storage/artifacts/access",
                params={
                    "storage_uri": "s3://road-risk/reports/file.pdf",
                    "publication_tier": "restricted",
                    "organization_id": "org-1",
                },
            )
            self.assertEqual(access_response.status_code, 200)
            self.assertEqual(access_response.json()["access_mode"], "presigned_get")
            self.assertEqual(
                access_response.json()["download_url"],
                "https://signed.example/download",
            )

    def test_ingestion_upload_and_validation_endpoints(self) -> None:
        app = create_app(ApiSettings(root_dir=Path("."), auth_enabled=True))
        fake_session = object()

        def _session_override():
            yield fake_session

        app.dependency_overrides[get_db_session] = _session_override
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="user-1",
            assigned_roles=frozenset({ROLE_ADMIN}),
            roles=frozenset({ROLE_ADMIN, ROLE_ANALYST, "data_operator", "municipality_viewer", "public"}),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=frozenset({"mun-1"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        client = TestClient(app)

        job = type(
            "Job",
            (),
            {
                "id": "job-1",
                "organization_id": "org-1",
                "municipality_id": "mun-1",
                "source_id": "source-1",
                "job_type": "crash_feed_ingestion",
                "status": "pending_upload",
                "queued_at": None,
                "started_at": None,
                "finished_at": None,
                "input_storage_uri": "s3://road-risk/uploads/crashes.csv",
                "manifest_storage_uri": "s3://road-risk/manifests/job-1.json",
                "error_storage_uri": "s3://road-risk/errors/job-1.json",
                "parameters_json": {},
                "job_stats_json": {"log_storage_uri": "s3://road-risk/logs/job-1.json"},
            },
        )()

        with (
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.register_ingestion_upload",
                return_value={
                    "job": job,
                    "upload_url": "https://signed.example/upload",
                    "storage_contract": {"artifact_storage_contract_version": "artifact_storage_contract_v1"},
                    "upload_contract": {"ingestion_upload_contract_version": "ingestion_upload_contract_v1"},
                },
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.serialize_ingestion_job_status",
                return_value={"source": {"source_id": "source-1", "name": "Bari crash feed"}},
            ),
            unittest.mock.patch(
                "apps.api.main.repositories.get_ingestion_job",
                return_value=job,
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.validate_ingestion_job_upload",
                return_value={"job_id": "job-1", "status": "validated_ready"},
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.list_ingestion_job_summaries",
                return_value=[{"job_id": "job-1", "status": "validated_ready"}],
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.build_upload_center_snapshot",
                return_value={
                    "contract_version": "ingestion_upload_center_v1",
                    "organization_id": "org-1",
                    "sources": [{"source_id": "source-1", "name": "Bari crash feed"}],
                    "jobs": [{"job_id": "job-1", "status": "validated_ready"}],
                },
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.build_ingestion_job_access_snapshot",
                return_value={"job_id": "job-1", "status": "validated_ready"},
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.approve_ingestion_job",
                return_value={"job_id": "job-1", "status": "queued"},
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.execute_ingestion_job",
                return_value={"job_id": "job-1", "status": "completed"},
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.retry_ingestion_job",
                return_value={"job_id": "job-1", "status": "queued"},
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.cancel_ingestion_job",
                return_value={"job_id": "job-1", "status": "cancelled"},
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.reject_ingestion_job",
                return_value={"job_id": "job-1", "status": "rejected"},
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.load_ingestion_job_error_summary",
                return_value={
                    "job_id": "job-1",
                    "error_storage_uri": "s3://road-risk/errors/job-1.json",
                    "error_summary": {"error_count": 1},
                    "row_errors": [{"row_number": 2}],
                },
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.load_ingestion_job_manifest",
                return_value={
                    "job_id": "job-1",
                    "manifest_storage_uri": "s3://road-risk/manifests/job-1.json",
                    "manifest": {"stats": {"validation_status": "validated_ready"}},
                },
            ),
            unittest.mock.patch(
                "apps.api.main.ingestion_jobs.load_ingestion_job_log",
                return_value={
                    "job_id": "job-1",
                    "log_storage_uri": "s3://road-risk/logs/job-1.json",
                    "log": {"log_lines": ["validated"]},
                },
            ),
        ):
            register_response = client.post(
                "/v1/ingestion-jobs/uploads",
                json={
                    "organization_id": "org-1",
                    "municipality_id": "mun-1",
                    "source_id": "source-1",
                    "filename": "crashes.csv",
                    "content_type": "text/csv",
                },
            )
            self.assertEqual(register_response.status_code, 200)
            self.assertEqual(register_response.json()["job_id"], "job-1")
            self.assertEqual(
                register_response.json()["upload_contract"]["ingestion_upload_contract_version"],
                "ingestion_upload_contract_v1",
            )

            validate_response = client.post(
                "/v1/ingestion-jobs/job-1/validate",
                json={"organization_id": "org-1"},
            )
            self.assertEqual(validate_response.status_code, 200)
            self.assertEqual(validate_response.json()["job"]["status"], "validated_ready")

            list_response = client.get(
                "/v1/ingestion-jobs",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(list_response.json()["jobs"][0]["job_id"], "job-1")

            upload_center_response = client.get(
                "/v1/ingestion-jobs/upload-center",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(upload_center_response.status_code, 200)
            self.assertEqual(
                upload_center_response.json()["contract_version"],
                "ingestion_upload_center_v1",
            )

            detail_response = client.get(
                "/v1/ingestion-jobs/job-1",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(detail_response.status_code, 200)
            self.assertEqual(detail_response.json()["job"]["status"], "validated_ready")

            errors_response = client.get(
                "/v1/ingestion-jobs/job-1/errors",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(errors_response.status_code, 200)
            self.assertEqual(errors_response.json()["error_summary"]["error_count"], 1)

            manifest_response = client.get(
                "/v1/ingestion-jobs/job-1/manifest",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(manifest_response.status_code, 200)
            self.assertEqual(
                manifest_response.json()["manifest"]["stats"]["validation_status"],
                "validated_ready",
            )

            logs_response = client.get(
                "/v1/ingestion-jobs/job-1/logs",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(logs_response.status_code, 200)
            self.assertEqual(logs_response.json()["log"]["log_lines"], ["validated"])

            approve_response = client.post(
                "/v1/ingestion-jobs/job-1/approve",
                json={"organization_id": "org-1", "decision_note": "clean validation"},
            )
            self.assertEqual(approve_response.status_code, 200)
            self.assertEqual(approve_response.json()["job"]["status"], "queued")

            job.status = "queued"
            run_response = client.post(
                "/v1/ingestion-jobs/job-1/run",
                json={"organization_id": "org-1", "dispatch_mode": "inline"},
            )
            self.assertEqual(run_response.status_code, 200)
            self.assertEqual(run_response.json()["job"]["status"], "completed")

            job.status = "failed"
            retry_response = client.post(
                "/v1/ingestion-jobs/job-1/retry",
                json={"organization_id": "org-1", "decision_note": "fixed mapping"},
            )
            self.assertEqual(retry_response.status_code, 200)
            self.assertEqual(retry_response.json()["job"]["status"], "queued")

            job.status = "queued"
            cancel_response = client.post(
                "/v1/ingestion-jobs/job-1/cancel",
                json={"organization_id": "org-1", "decision_note": "operator stop"},
            )
            self.assertEqual(cancel_response.status_code, 200)
            self.assertEqual(cancel_response.json()["job"]["status"], "cancelled")

            reject_response = client.post(
                "/v1/ingestion-jobs/job-1/reject",
                json={"organization_id": "org-1", "decision_note": "bad coordinates"},
            )
            self.assertEqual(reject_response.status_code, 200)
            self.assertEqual(reject_response.json()["job"]["status"], "rejected")

    def test_upload_center_requires_data_operator_access(self) -> None:
        app = create_app(ApiSettings(root_dir=Path("."), auth_enabled=True))

        def _session_override():
            yield object()

        app.dependency_overrides[get_db_session] = _session_override
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="analyst-1",
            assigned_roles=frozenset({ROLE_ANALYST}),
            roles=frozenset({ROLE_ANALYST, "municipality_viewer", "public"}),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=frozenset({"mun-1"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        client = TestClient(app)

        response = client.get("/v1/ingestion-jobs/upload-center", params={"organization_id": "org-1"})
        self.assertEqual(response.status_code, 403)

        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="operator-1",
            assigned_roles=frozenset({ROLE_DATA_OPERATOR}),
            roles=frozenset({ROLE_DATA_OPERATOR, "municipality_viewer", "public"}),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=frozenset({"mun-1"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        with unittest.mock.patch(
            "apps.api.main.ingestion_jobs.build_upload_center_snapshot",
            return_value={
                "contract_version": "ingestion_upload_center_v1",
                "organization_id": "org-1",
                "sources": [],
                "jobs": [],
            },
        ):
            response = client.get("/v1/ingestion-jobs/upload-center", params={"organization_id": "org-1"})
        self.assertEqual(response.status_code, 200)

    def test_published_refresh_job_trigger_and_status_endpoints(self) -> None:
        app = create_app(ApiSettings(root_dir=Path("."), auth_enabled=True))
        fake_session = type("Session", (), {"commit": lambda self: None})()

        def _session_override():
            yield fake_session

        app.dependency_overrides[get_db_session] = _session_override
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="auth-subject-1",
            assigned_roles=frozenset({ROLE_ADMIN}),
            roles=frozenset({ROLE_ADMIN, ROLE_ANALYST, "municipality_viewer", "public"}),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=frozenset({"mun-1"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        client = TestClient(app)

        job = type(
            "Job",
            (),
            {
                "id": "job-1",
                "organization_id": "org-1",
                "municipality_id": "mun-1",
                "job_type": "published_refresh_bundle",
                "status": "queued",
                "queued_at": None,
                "started_at": None,
                "finished_at": None,
                "input_storage_uri": None,
                "manifest_storage_uri": None,
                "error_storage_uri": None,
                "parameters_json": {},
                "job_stats_json": {},
            },
        )()

        with (
            unittest.mock.patch(
                "apps.api.main.published_refresh_jobs.create_published_refresh_job",
                return_value=job,
            ),
            unittest.mock.patch(
                "apps.api.main._dispatch_published_refresh_job",
                return_value=("inline", None),
            ),
            unittest.mock.patch(
                "apps.api.main.published_refresh_jobs.execute_published_refresh_job",
                return_value={"job_id": "job-1", "status": "completed"},
            ),
            unittest.mock.patch(
                "apps.api.main.repositories.get_ingestion_job",
                return_value=job,
            ),
            unittest.mock.patch(
                "apps.api.main.published_refresh_jobs.build_job_access_snapshot",
                return_value={"job_id": "job-1", "status": "completed", "artifacts": []},
            ),
        ):
            trigger_response = client.post(
                "/v1/jobs/published-refresh",
                json={
                    "organization_id": "org-1",
                    "municipality_id": "mun-1",
                    "dispatch_mode": "inline",
                },
            )
            self.assertEqual(trigger_response.status_code, 200)
            self.assertEqual(trigger_response.json()["dispatch_mode"], "inline")
            self.assertEqual(trigger_response.json()["job"]["job_id"], "job-1")

            status_response = client.get(
                "/v1/jobs/job-1",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(status_response.status_code, 200)
            self.assertEqual(status_response.json()["job"]["status"], "completed")

    def test_relative_configuration_drives_published_index_and_dashboard_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_path = root / "custom" / "published_resources.json"
            summary_path = root / "custom" / "dashboard_summary.json"
            _write_json(
                index_path,
                {
                    "published_resource_index_version": "published_resource_index_v1",
                    "selection_policy": {
                        "published_resource_selection_policy_version": "published_resource_selection_policy_v1"
                    },
                    "catalog": [],
                },
            )
            _write_json(
                summary_path,
                {
                    "dashboard_summary_version": "dashboard_summary_v1",
                    "published_runs": [{"prediction_run_label": "demo_run"}],
                    "transferability_matrix": [],
                },
            )

            settings = ApiSettings(
                root_dir=root,
                published_index_path=Path("custom/published_resources.json"),
                dashboard_summary_path=Path("custom/dashboard_summary.json"),
            )
            client = TestClient(create_app(settings))

            index_response = client.get("/v1/published-index")
            self.assertEqual(index_response.status_code, 200)
            self.assertEqual(index_response.json()["published_index_path"], str(index_path))

            dashboard_response = client.get("/v1/dashboard-summary")
            self.assertEqual(dashboard_response.status_code, 200)
            self.assertEqual(dashboard_response.json()["dashboard_summary_path"], str(summary_path))
            self.assertEqual(
                dashboard_response.json()["summary"]["dashboard_summary_version"],
                "dashboard_summary_v1",
            )

    def test_published_resource_queries_and_dashboard_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_dir = root / "ui" / "dashboard"
            dashboard_dir.mkdir(parents=True, exist_ok=True)
            (dashboard_dir / "index.html").write_text(
                "<html><body>road risk dashboard</body></html>",
                encoding="utf-8",
            )
            (dashboard_dir / "app.js").write_text("console.log('dashboard');", encoding="utf-8")

            store_dir = root / "artifacts" / "demo_run"
            public_geojson_path = store_dir / "segment_scores_public.geojson"
            public_geojson_path.parent.mkdir(parents=True, exist_ok=True)
            public_geojson_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[16.8, 41.1], [16.81, 41.11]],
                                },
                                "properties": {
                                    "segment_score_id": "demo:2021:s1",
                                    "segment_id": "s1",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 98.0,
                                    "public_score_band": "very_high",
                                    "score_decile": 1,
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest_path = store_dir / "segment_scores.manifest.json"
            _write_json(
                manifest_path,
                {
                    "contract": {
                        "resource_name": "segment_scores",
                        "public_contract_version": "segment_scores_public_v1",
                        "analyst_contract_version": "segment_scores_analyst_v1",
                    },
                    "outputs": {
                        "manifest_path": "artifacts/demo_run/segment_scores.manifest.json",
                        "public_geojson_path": "artifacts/demo_run/segment_scores_public.geojson",
                        "analyst_csv_path": "artifacts/demo_run/segment_scores_analyst.csv",
                    },
                    "stats": {
                        "holdout_years": [2021],
                        "prediction_run_label": "demo_run",
                        "prediction_task": "segment_frequency_baseline",
                        "segment_score_rows": 1,
                    },
                },
            )

            index_path = root / "catalog" / "published_resources.json"
            _write_json(
                index_path,
                {
                    "published_resource_index_version": "published_resource_index_v1",
                    "selection_policy": {
                        "published_resource_selection_policy_version": "published_resource_selection_policy_v1"
                    },
                    "catalog": [
                        {
                            "resource_name": "segment_scores",
                            "artifact_kind": "prediction_store",
                            "run_label": "demo_run",
                            "prediction_run_label": "demo_run",
                            "prediction_task": "segment_frequency_baseline",
                            "occurred_years": [2021],
                            "tile_size_m": None,
                            "document_mtime_utc": "2026-03-28T13:30:00+00:00",
                            "manifest_path": "artifacts/demo_run/segment_scores.manifest.json",
                            "contract_versions": {
                                "public_contract_version": "segment_scores_public_v1",
                                "analyst_contract_version": "segment_scores_analyst_v1",
                                "lineage_contract_version": "artifact_lineage_v1",
                            },
                            "selection": {
                                "is_latest_for_prediction_run": True,
                                "published_resource_selection_policy_version": "published_resource_selection_policy_v1",
                            },
                            "lineage_trace": {
                                "source_metrics_path": "data/models/demo_run/frequency_baseline.metrics.json",
                                "trace_status": "resolved",
                            },
                            "views": {
                                "public_segments": {
                                    "path": "artifacts/demo_run/segment_scores_public.geojson",
                                    "contract_version": "segment_scores_public_v1",
                                }
                            },
                            "stats": {
                                "holdout_years": [2021],
                                "prediction_run_label": "demo_run",
                                "prediction_task": "segment_frequency_baseline",
                                "segment_score_rows": 1,
                            },
                        }
                    ],
                },
            )

            settings = ApiSettings(
                root_dir=root,
                published_index_path=Path("catalog/published_resources.json"),
                dashboard_dir=Path("ui/dashboard"),
            )
            client = TestClient(create_app(settings))

            latest_response = client.get(
                "/v1/published-resource/latest",
                params={
                    "resource_name": "segment_scores",
                    "prediction_run_label": "demo_run",
                    "occurred_year": 2021,
                },
            )
            self.assertEqual(latest_response.status_code, 200)
            self.assertEqual(
                latest_response.json()["resolved"]["resolved_view"],
                "public_segments",
            )

            query_response = client.get(
                "/v1/published-resource/query",
                params={
                    "resource_name": "segment_scores",
                    "prediction_run_label": "demo_run",
                    "occurred_year": 2021,
                    "min_score_band": "high",
                    "limit": 1,
                },
            )
            self.assertEqual(query_response.status_code, 200)
            self.assertEqual(query_response.json()["resource"]["resource_name"], "segment_scores")
            self.assertEqual(query_response.json()["resource"]["stats"]["returned_features"], 1)

            dashboard_response = client.get("/dashboard/")
            self.assertEqual(dashboard_response.status_code, 200)
            self.assertIn("road risk dashboard", dashboard_response.text)

            asset_response = client.get("/dashboard/app.js")
            self.assertEqual(asset_response.status_code, 200)
            self.assertIn("console.log", asset_response.text)

    def test_missing_resource_name_returns_422_from_fastapi_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_path = root / "data" / "published_index" / "published_resources.json"
            _write_json(
                index_path,
                {
                    "published_resource_index_version": "published_resource_index_v1",
                    "selection_policy": {
                        "published_resource_selection_policy_version": "published_resource_selection_policy_v1"
                    },
                    "catalog": [],
                },
            )
            client = TestClient(create_app(ApiSettings(root_dir=root)))

            response = client.get("/v1/published-resource/latest")
            self.assertEqual(response.status_code, 422)

    def test_auth_scope_access_endpoints_enforce_organization_and_municipality_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = create_app(ApiSettings(root_dir=root, auth_enabled=True, auth_provider="keycloak"))
            app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                subject="user-1",
                assigned_roles=frozenset({ROLE_ANALYST}),
                roles=frozenset({"public", "municipality_viewer", ROLE_ANALYST}),
                scopes=frozenset({"openid", "profile"}),
                claims={"sub": "user-1"},
                organization_ids=frozenset({"org-bari"}),
                municipality_ids=frozenset({"bari"}),
                is_authenticated=True,
                auth_enabled=True,
                provider="keycloak",
            )
            client = TestClient(app)

            me_response = client.get("/v1/auth/me")
            self.assertEqual(me_response.status_code, 200)
            self.assertEqual(me_response.json()["organization_ids"], ["org-bari"])
            self.assertEqual(me_response.json()["municipality_ids"], ["bari"])

            org_ok_response = client.get("/v1/auth/organizations/org-bari/access")
            self.assertEqual(org_ok_response.status_code, 200)
            self.assertTrue(org_ok_response.json()["authorized"])

            org_denied_response = client.get("/v1/auth/organizations/org-lecce/access")
            self.assertEqual(org_denied_response.status_code, 403)

            municipality_ok_response = client.get("/v1/auth/municipalities/bari/access")
            self.assertEqual(municipality_ok_response.status_code, 200)
            self.assertTrue(municipality_ok_response.json()["authorized"])

            municipality_denied_response = client.get("/v1/auth/municipalities/lecce/access")
            self.assertEqual(municipality_denied_response.status_code, 403)

    def test_analyst_view_requires_internal_role_when_auth_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store_dir = root / "artifacts" / "demo_run"
            store_dir.mkdir(parents=True, exist_ok=True)
            (store_dir / "segment_scores_public.geojson").write_text(
                json.dumps({"type": "FeatureCollection", "features": []}),
                encoding="utf-8",
            )
            _write_json(
                store_dir / "segment_scores.manifest.json",
                {
                    "contract": {
                        "resource_name": "segment_scores",
                        "public_contract_version": "segment_scores_public_v1",
                        "analyst_contract_version": "segment_scores_analyst_v1",
                    },
                    "outputs": {
                        "manifest_path": "artifacts/demo_run/segment_scores.manifest.json",
                        "public_geojson_path": "artifacts/demo_run/segment_scores_public.geojson",
                        "analyst_csv_path": "artifacts/demo_run/segment_scores_analyst.csv",
                    },
                    "stats": {
                        "holdout_years": [2021],
                        "prediction_run_label": "demo_run",
                        "prediction_task": "segment_frequency_baseline",
                        "segment_score_rows": 0,
                    },
                },
            )
            _write_json(
                root / "catalog" / "published_resources.json",
                {
                    "published_resource_index_version": "published_resource_index_v1",
                    "selection_policy": {
                        "published_resource_selection_policy_version": "published_resource_selection_policy_v1"
                    },
                    "catalog": [
                        {
                            "resource_name": "segment_scores",
                            "artifact_kind": "prediction_store",
                            "run_label": "demo_run",
                            "prediction_run_label": "demo_run",
                            "prediction_task": "segment_frequency_baseline",
                            "occurred_years": [2021],
                            "tile_size_m": None,
                            "document_mtime_utc": "2026-03-28T13:30:00+00:00",
                            "manifest_path": "artifacts/demo_run/segment_scores.manifest.json",
                            "contract_versions": {
                                "public_contract_version": "segment_scores_public_v1",
                                "analyst_contract_version": "segment_scores_analyst_v1",
                                "lineage_contract_version": "artifact_lineage_v1",
                            },
                            "selection": {
                                "is_latest_for_prediction_run": True,
                                "published_resource_selection_policy_version": "published_resource_selection_policy_v1",
                            },
                            "lineage_trace": {
                                "source_metrics_path": "data/models/demo_run/frequency_baseline.metrics.json",
                                "trace_status": "resolved",
                            },
                            "views": {
                                "public_segments": {
                                    "path": "artifacts/demo_run/segment_scores_public.geojson",
                                    "contract_version": "segment_scores_public_v1",
                                },
                                "analyst_segments": {
                                    "path": "artifacts/demo_run/segment_scores_public.geojson",
                                    "contract_version": "segment_scores_analyst_v1",
                                },
                            },
                            "stats": {
                                "holdout_years": [2021],
                                "prediction_run_label": "demo_run",
                                "prediction_task": "segment_frequency_baseline",
                                "segment_score_rows": 0,
                            },
                        }
                    ],
                },
            )

            app = create_app(
                ApiSettings(
                    root_dir=root,
                    published_index_path=Path("catalog/published_resources.json"),
                    auth_enabled=True,
                )
            )
            client = TestClient(app)

            app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                subject="viewer-1",
                assigned_roles=frozenset({"public"}),
                roles=frozenset({"public"}),
                scopes=frozenset(),
                claims={"sub": "viewer-1"},
                organization_ids=frozenset({"org-bari"}),
                municipality_ids=frozenset({"bari"}),
                is_authenticated=True,
                auth_enabled=True,
                provider="keycloak",
            )
            denied_response = client.get(
                "/v1/published-resource/latest",
                params={
                    "resource_name": "segment_scores",
                    "prediction_run_label": "demo_run",
                    "occurred_year": 2021,
                    "view": "analyst_segments",
                },
            )
            self.assertEqual(denied_response.status_code, 403)

            app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                subject="analyst-1",
                assigned_roles=frozenset({ROLE_ANALYST}),
                roles=frozenset({"public", "municipality_viewer", ROLE_ANALYST}),
                scopes=frozenset(),
                claims={"sub": "analyst-1"},
                organization_ids=frozenset({"org-bari"}),
                municipality_ids=frozenset({"bari"}),
                is_authenticated=True,
                auth_enabled=True,
                provider="keycloak",
            )
            allowed_response = client.get(
                "/v1/published-resource/latest",
                params={
                    "resource_name": "segment_scores",
                    "prediction_run_label": "demo_run",
                    "occurred_year": 2021,
                    "view": "analyst_segments",
                },
            )
            self.assertEqual(allowed_response.status_code, 200)
            self.assertEqual(allowed_response.json()["resolved"]["resolved_view"], "analyst_segments")
