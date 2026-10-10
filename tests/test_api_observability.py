"""Tests for the observability + security hardening surfaces (#96)."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.auth import (  # noqa: E402
    AuthContext,
    ROLE_ADMIN,
    ROLE_ANALYST,
    get_auth_context,
)
from apps.api.db.session import get_db_session  # noqa: E402
from apps.api.main import create_app  # noqa: E402
from apps.api.middleware.operational_hardening import RuntimeMetricsRegistry  # noqa: E402
from apps.api.middleware.security_headers import DEFAULT_SECURITY_HEADERS  # noqa: E402
from apps.api.services import observability  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _ns(**fields: object) -> SimpleNamespace:
    return SimpleNamespace(**fields)


def _fake_job(job_type: str, status: str):
    return _ns(
        id=uuid4(),
        job_type=job_type,
        status=status,
        job_stats_json={},
    )


def _fake_audit(action: str):
    return _ns(id=uuid4(), action=action)


def _fake_data_source(name: str, *, governance_status: str):
    return _ns(
        id=uuid4(),
        name=name,
        governance_status=governance_status,
        status="active",
        refresh_frequency="manual",
        last_refresh_at=None,
    )


def _fake_report(report_type: str, status: str):
    return _ns(id=uuid4(), report_type=report_type, status=status)


def _fake_artifact(artifact_kind: str, *, publication_tier: str = "restricted", size_bytes: int = 0):
    return _ns(
        id=uuid4(),
        artifact_kind=artifact_kind,
        publication_tier=publication_tier,
        lineage_json={"size_bytes": size_bytes},
    )


def _fake_membership(status: str):
    return _ns(id=uuid4(), status=status)


class ObservabilityServiceTests(unittest.TestCase):
    def test_build_info_payload_contains_stable_identity(self) -> None:
        settings = ApiSettings(root_dir=Path("."), auth_enabled=True, auth_provider="keycloak")
        with mock.patch.dict(
            "os.environ",
            {
                "ROAD_RISK_BUILD_SHA": "abc123",
                "ROAD_RISK_BUILD_REF": "main",
                "ROAD_RISK_BUILD_TIMESTAMP": "2026-05-15T00:00:00Z",
                "ROAD_RISK_API_ENV": "staging",
            },
            clear=False,
        ):
            payload = observability.build_info_payload(settings)
        self.assertEqual(
            payload["contract_version"], observability.OBSERVABILITY_INFO_CONTRACT_VERSION,
        )
        self.assertEqual(payload["app_name"], "road-risk-api")
        self.assertEqual(payload["app_environment"], "staging")
        self.assertEqual(payload["build_sha"], "abc123")
        self.assertEqual(payload["auth_enabled"], True)
        self.assertEqual(payload["auth_provider"], "keycloak")
        self.assertIn("python_version", payload)
        self.assertIn("process_uptime_seconds", payload)

    def test_build_info_payload_reports_disabled_auth(self) -> None:
        settings = ApiSettings(root_dir=Path("."), auth_enabled=False)
        payload = observability.build_info_payload(settings)
        self.assertEqual(payload["auth_provider"], "disabled")
        self.assertFalse(payload["auth_enabled"])

    def test_build_readiness_payload_lists_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ApiSettings(root_dir=Path(temp_dir))
            payload = observability.build_readiness_payload(settings)
        self.assertIn("checks", payload)
        names = set(payload["checks"].keys())
        self.assertEqual(
            names,
            {
                "published_index",
                "dashboard_summary",
                "scenario_index",
                "scheduler_module",
                "database_session",
            },
        )
        # No artifacts exist in the tempdir, so the readiness probe must
        # report `degraded` and call out the missing checks.
        self.assertEqual(payload["status"], "degraded")
        self.assertIn("published_index", payload["failing"])
        self.assertIn("dashboard_summary", payload["failing"])

    def test_build_metrics_payload_rolls_up_counts(self) -> None:
        jobs = [
            _fake_job("published_refresh", "completed"),
            _fake_job("manual_refresh", "queued"),
            _fake_job("ingestion_upload", "failed"),
        ]
        jobs[0].job_stats_json = {"total_rows": 10, "written_rows": 9, "rejected_rows": 1}
        audits = [_fake_audit("published_refresh.completed"), _fake_audit("data_source.approved")]
        sources = [
            _fake_data_source("a", governance_status="approved"),
            _fake_data_source("b", governance_status="approved"),
            _fake_data_source("c", governance_status="draft"),
        ]
        reports = [_fake_report("executive_overview", "generated"), _fake_report("technical", "failed")]
        artifacts = [
            _fake_artifact("report", publication_tier="internal", size_bytes=2048),
            _fake_artifact("manifest", publication_tier="restricted", size_bytes=1024),
        ]
        memberships = [_fake_membership("active"), _fake_membership("disabled")]
        with (
            mock.patch(
                "apps.api.services.observability.repositories.list_ingestion_jobs_for_organization",
                return_value=jobs,
            ),
            mock.patch(
                "apps.api.services.observability.repositories.list_audit_logs_for_organization",
                return_value=audits,
            ),
            mock.patch(
                "apps.api.services.observability.repositories.list_data_sources_for_organization",
                return_value=sources,
            ),
            mock.patch(
                "apps.api.services.observability.repositories.list_reports_for_organization",
                return_value=reports,
            ),
            mock.patch(
                "apps.api.services.observability.repositories.list_artifact_references_for_organization",
                return_value=artifacts,
            ),
            mock.patch(
                "apps.api.services.observability.repositories.list_memberships_for_organization",
                return_value=memberships,
            ),
        ):
            payload = observability.build_metrics_payload(
                object(),
                organization_id="org-1",
                settings=ApiSettings(rate_limit_enabled=True, rate_limit_requests=10),
            )
        self.assertEqual(payload["ingestion_jobs"]["total"], 3)
        self.assertEqual(
            payload["ingestion_jobs"]["by_status"],
            {"completed": 1, "queued": 1, "failed": 1},
        )
        self.assertEqual(payload["ingestion_jobs"]["success_rate"], 0.5)
        self.assertEqual(payload["ingestion_jobs"]["row_quality"]["rejection_rate"], 0.1)
        self.assertEqual(payload["audit_log"]["total"], 2)
        self.assertEqual(payload["data_sources"]["by_governance_status"], {"approved": 2, "draft": 1})
        self.assertEqual(payload["reports"]["by_status"], {"generated": 1, "failed": 1})
        self.assertEqual(payload["storage"]["known_total_bytes"], 3072)
        self.assertEqual(payload["active_users"]["active_memberships"], 1)
        self.assertEqual(payload["security_controls"]["rate_limiting"]["requests"], 10)


class ObservabilityEndpointTests(unittest.TestCase):
    def _build_app(self, *, roles: frozenset[str], organization_ids: frozenset[str]):
        app = create_app(ApiSettings(root_dir=Path("."), auth_enabled=True))

        def _session_override():
            yield object()

        app.dependency_overrides[get_db_session] = _session_override
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="admin-1",
            assigned_roles=frozenset(roles),
            roles=frozenset(roles),
            scopes=frozenset(),
            claims={},
            organization_ids=organization_ids,
            municipality_ids=frozenset(),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        return app

    def test_info_endpoint_is_public(self) -> None:
        app = create_app(ApiSettings(root_dir=Path(".")))
        client = TestClient(app)
        response = client.get("/v1/observability/info")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["contract_version"], observability.OBSERVABILITY_INFO_CONTRACT_VERSION,
        )

    def test_readiness_endpoint_returns_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(ApiSettings(root_dir=Path(temp_dir)))
            client = TestClient(app)
            response = client.get("/v1/observability/readiness")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "degraded")
        self.assertIn("published_index", body["checks"])

    def test_metrics_endpoint_requires_admin(self) -> None:
        app = self._build_app(
            roles=frozenset({ROLE_ANALYST}),
            organization_ids=frozenset({"org-1"}),
        )
        client = TestClient(app)
        response = client.get(
            "/v1/observability/metrics",
            params={"organization_id": "org-1"},
        )
        self.assertEqual(response.status_code, 403)

    def test_metrics_endpoint_returns_payload_for_admin(self) -> None:
        app = self._build_app(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        client = TestClient(app)
        with mock.patch(
            "apps.api.main.observability.build_metrics_payload",
            return_value={
                "contract_version": observability.OBSERVABILITY_METRICS_CONTRACT_VERSION,
                "organization_id": "org-1",
                "generated_at": "2026-05-15T00:00:00+00:00",
                "ingestion_jobs": {"total": 0, "by_status": {}, "by_job_type": {}, "recent_window": 0},
                "audit_log": {"total": 0, "by_action": {}},
                "data_sources": {"total": 0, "by_governance_status": {}},
                "api_runtime": {},
                "error_tracking": {},
                "security_controls": {},
            },
        ):
            response = client.get(
                "/v1/observability/metrics",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["contract_version"],
            observability.OBSERVABILITY_METRICS_CONTRACT_VERSION,
        )


class SecurityHeadersMiddlewareTests(unittest.TestCase):
    def test_default_response_has_security_headers(self) -> None:
        app = create_app(ApiSettings(root_dir=Path(".")))
        client = TestClient(app)
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        for name, value in DEFAULT_SECURITY_HEADERS.items():
            self.assertIn(name, response.headers, f"missing header {name}")
            self.assertEqual(response.headers[name], value, f"unexpected value for {name}")

    def test_docs_surface_is_excluded_from_strict_csp(self) -> None:
        app = create_app(ApiSettings(root_dir=Path(".")))
        client = TestClient(app)
        response = client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("content-security-policy", response.headers)


class OperationalHardeningMiddlewareTests(unittest.TestCase):
    def test_request_id_header_is_added_and_preserved(self) -> None:
        app = create_app(ApiSettings(root_dir=Path("."), request_logging_enabled=False))
        client = TestClient(app)
        response = client.get("/healthz", headers={"X-Request-ID": "req-test-1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Request-ID"], "req-test-1")

    def test_rate_limit_returns_429_when_enabled(self) -> None:
        app = create_app(
            ApiSettings(
                root_dir=Path("."),
                request_logging_enabled=False,
                rate_limit_enabled=True,
                rate_limit_requests=1,
                rate_limit_window_seconds=60,
                rate_limit_exempt_paths="/healthz",
            )
        )
        client = TestClient(app)
        first = client.get("/v1/auth/role-matrix")
        second = client.get("/v1/auth/role-matrix")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["rate_limit_contract_version"], "rate_limit_v1")
        self.assertIn("Retry-After", second.headers)

    def test_runtime_metrics_registry_rolls_up_request_health(self) -> None:
        registry = RuntimeMetricsRegistry()
        registry.record_request(
            method="GET",
            route="/v1/test",
            status_code=200,
            duration_ms=12.5,
            auth_context=AuthContext(
                subject="operator-1",
                assigned_roles=frozenset({ROLE_ADMIN}),
                roles=frozenset({ROLE_ADMIN}),
                scopes=frozenset(),
                claims={},
                organization_ids=frozenset({"org-1"}),
                municipality_ids=frozenset(),
                is_authenticated=True,
                auth_enabled=True,
                provider="keycloak",
            ),
        )
        registry.record_request(
            method="GET",
            route="/v1/test",
            status_code=503,
            duration_ms=40.0,
            auth_context=None,
        )
        snapshot = registry.snapshot()
        self.assertEqual(snapshot["total_requests"], 2)
        self.assertEqual(snapshot["total_errors"], 1)
        self.assertEqual(snapshot["error_rate"], 0.5)
        self.assertEqual(snapshot["active_user_count"], 1)


class ProductionHardeningAssetTests(unittest.TestCase):
    def test_production_runbook_documents_required_controls(self) -> None:
        runbook = (REPO_ROOT / "docs" / "production-runbook.md").read_text(encoding="utf-8")
        for expected in (
            "/v1/observability/readiness",
            "RequestObservabilityMiddleware",
            "SecurityHeadersMiddleware",
            "backup_postgres.sh",
            "backup_minio.sh",
            "restore_postgres.sh",
            "restore_minio.sh",
            "security_release_checks.py",
            "incident-response.md",
            "kubectl rollout undo",
        ):
            self.assertIn(expected, runbook)

    def test_kubernetes_manifests_wire_readiness_and_security_context(self) -> None:
        api_manifest = (REPO_ROOT / "infra" / "k8s" / "api.deployment.yaml").read_text(encoding="utf-8")
        worker_manifest = (REPO_ROOT / "infra" / "k8s" / "worker.deployment.yaml").read_text(encoding="utf-8")
        scheduler_manifest = (REPO_ROOT / "infra" / "k8s" / "scheduler.deployment.yaml").read_text(encoding="utf-8")
        namespace_manifest = (REPO_ROOT / "infra" / "k8s" / "namespace.yaml").read_text(encoding="utf-8")

        self.assertIn("kind: Namespace", namespace_manifest)
        self.assertIn("path: /v1/observability/readiness", api_manifest)
        for manifest in (api_manifest, worker_manifest, scheduler_manifest):
            self.assertIn("runAsNonRoot: true", manifest)
            self.assertIn("allowPrivilegeEscalation: false", manifest)
            self.assertIn("drop: [\"ALL\"]", manifest)
            self.assertIn("readOnlyRootFilesystem: true", manifest)

    def test_backup_and_restore_scripts_are_syntax_valid(self) -> None:
        for script_name in (
            "backup_postgres.sh",
            "backup_minio.sh",
            "restore_postgres.sh",
            "restore_minio.sh",
        ):
            script_path = REPO_ROOT / "infra" / "scripts" / script_name
            self.assertTrue(script_path.is_file(), f"missing {script_path}")
            result = subprocess.run(
                ["bash", "-n", str(script_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_security_scan_assets_are_executable(self) -> None:
        workflow = REPO_ROOT / ".github" / "workflows" / "security-scan.yml"
        script = REPO_ROOT / "tools" / "security_release_checks.py"
        incident = REPO_ROOT / "docs" / "incident-response.md"
        for path in (workflow, script, incident):
            self.assertTrue(path.is_file(), f"missing {path}")

        workflow_body = workflow.read_text(encoding="utf-8")
        for expected in ("pip-audit", "bandit", "pip-licenses", "npm audit"):
            self.assertIn(expected, workflow_body)

        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
