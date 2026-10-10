"""Tests for the automation controls surface (#94)."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from datetime import datetime, timedelta, timezone
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
from apps.api.services import automation_controls  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402
from services.scheduler.beat_schedule import build_beat_schedule  # noqa: E402
from services.workers.settings import WorkerSettings  # noqa: E402


def _ns(**fields: object) -> SimpleNamespace:
    return SimpleNamespace(**fields)


def _fake_job(job_type: str, status: str):
    return _ns(
        id=uuid4(),
        job_type=job_type,
        status=status,
        municipality_id=None,
        source_id=None,
        submitted_by_user_id=None,
        created_at=None,
        started_at=None,
        finished_at=None,
    )


def _fake_audit(action: str):
    return _ns(
        id=uuid4(),
        action=action,
        target_type="ingestion_job",
        target_id="job-1",
        status="recorded",
        user_id=None,
        created_at=None,
        metadata_json={"job_type": "manual_refresh"},
    )


def _fake_source(name: str, refresh_frequency: str, last_refresh_at: datetime | None):
    return _ns(
        id=uuid4(),
        name=name,
        source_type="crash_feed",
        municipality_id=None,
        refresh_frequency=refresh_frequency,
        last_refresh_at=last_refresh_at,
    )


class AutomationControlsServiceTests(unittest.TestCase):
    def test_beat_schedule_registers_production_refresh_policies(self) -> None:
        schedule = build_beat_schedule(WorkerSettings())
        self.assertIn("published-refresh-daily", schedule)
        self.assertIn("dashboard-refresh-daily", schedule)
        self.assertIn("stale-source-check-daily", schedule)
        self.assertIn("data-quality-check-daily", schedule)
        self.assertIn("monthly-report-generation", schedule)
        self.assertEqual(
            schedule["stale-source-check-daily"]["task"],
            "services.workers.tasks.automation.run_stale_source_check_policy",
        )

    def test_list_automation_schedules_marks_paused_entries(self) -> None:
        schedule = {
            "health-ping-every-1-minute": {
                "task": "services.workers.tasks.health.ping",
                "schedule": 60.0,
                "options": {"queue": "road_risk_default", "expires": 30},
            },
            "health-worker-summary-every-5-minutes": {
                "task": "services.workers.tasks.health.worker_summary",
                "schedule": 300.0,
                "options": {"queue": "road_risk_default", "expires": 60},
            },
        }
        payload = automation_controls.list_automation_schedules(
            beat_schedule=schedule,
            paused_entries={"health-ping-every-1-minute"},
        )
        self.assertEqual(payload["contract_version"], automation_controls.AUTOMATION_SCHEDULES_CONTRACT_VERSION)
        self.assertTrue(payload["scheduler_available"])
        self.assertEqual(payload["entry_count"], 2)
        self.assertEqual(payload["paused_count"], 1)
        names_by_state = {entry["name"]: entry["paused"] for entry in payload["entries"]}
        self.assertTrue(names_by_state["health-ping-every-1-minute"])
        self.assertFalse(names_by_state["health-worker-summary-every-5-minutes"])
        self.assertEqual(payload["entries"][0]["configuration_source"], "environment")

    def test_list_automation_schedules_applies_audit_backed_controls(self) -> None:
        schedule = {
            "stale-source-check-daily": {
                "task": "services.workers.tasks.automation.run_stale_source_check_policy",
                "schedule": 86_400.0,
                "options": {"queue": "road_risk_automation"},
            },
        }
        logs = [
            _ns(
                id=uuid4(),
                action="automation.schedule.updated",
                metadata_json={
                    "schedule_name": "stale-source-check-daily",
                    "schedule_seconds": 3_600,
                    "notification_channels": ["email_outbox"],
                },
            ),
            _ns(
                id=uuid4(),
                action="automation.schedule.paused",
                metadata_json={"schedule_name": "stale-source-check-daily"},
            ),
        ]
        with mock.patch(
            "apps.api.services.automation_controls.repositories.list_audit_logs_for_organization",
            return_value=logs,
        ):
            payload = automation_controls.list_automation_schedules(
                session=object(),
                organization_id="org-1",
                beat_schedule=schedule,
            )
        entry = payload["entries"][0]
        self.assertTrue(entry["paused"])
        self.assertEqual(entry["schedule"]["value"], 3600.0)
        self.assertEqual(entry["notification_channels"], ["email_outbox"])
        self.assertEqual(entry["policy"]["policy_kind"], "stale_source_detection")

    def test_list_automation_runs_filters_to_automation_job_types(self) -> None:
        jobs = [
            _fake_job("published_refresh", "completed"),
            _fake_job("manual_refresh", "queued"),
            _fake_job("ingestion_upload", "queued"),  # filtered out
            _fake_job("scheduled_refresh", "running"),
        ]
        with mock.patch(
            "apps.api.services.automation_controls.repositories.list_ingestion_jobs_for_organization",
            return_value=jobs,
        ):
            payload = automation_controls.list_automation_runs(
                object(), organization_id="org-1",
            )
        job_types = {row["job_type"] for row in payload["runs"]}
        self.assertEqual(job_types, {"published_refresh", "manual_refresh", "scheduled_refresh"})
        self.assertEqual(payload["totals"]["total"], 3)
        self.assertEqual(payload["totals"]["by_status"], {"completed": 1, "queued": 1, "running": 1})

    def test_list_automation_runs_supports_explicit_job_type_filter(self) -> None:
        jobs = [
            _fake_job("published_refresh", "completed"),
            _fake_job("manual_refresh", "queued"),
        ]
        with mock.patch(
            "apps.api.services.automation_controls.repositories.list_ingestion_jobs_for_organization",
            return_value=jobs,
        ):
            payload = automation_controls.list_automation_runs(
                object(), organization_id="org-1", job_type="manual_refresh",
            )
        self.assertEqual(payload["totals"]["total"], 1)
        self.assertEqual(payload["runs"][0]["job_type"], "manual_refresh")

    def test_list_notifications_filters_to_relevant_actions(self) -> None:
        logs = [
            _fake_audit("published_refresh.completed"),
            _fake_audit("manual_refresh.triggered"),
            _fake_audit("user_logged_in"),  # filtered out
            _fake_audit("ingestion_job.failed"),
        ]
        with mock.patch(
            "apps.api.services.automation_controls.repositories.list_audit_logs_for_organization",
            return_value=logs,
        ):
            payload = automation_controls.list_notifications(
                object(), organization_id="org-1",
            )
        actions = {row["action"] for row in payload["notifications"]}
        self.assertEqual(
            actions,
            {"published_refresh.completed", "manual_refresh.triggered", "ingestion_job.failed"},
        )
        self.assertEqual(payload["totals"]["total"], 3)

    def test_trigger_manual_refresh_creates_job_and_audit(self) -> None:
        created_job = _fake_job("manual_refresh", "queued")
        created_audit = _fake_audit("manual_refresh.triggered")
        with (
            mock.patch(
                "apps.api.services.automation_controls.repositories.create_ingestion_job",
                return_value=created_job,
            ) as create_job,
            mock.patch(
                "apps.api.services.automation_controls.repositories.record_audit_log",
                return_value=created_audit,
            ) as record_audit,
        ):
            payload = automation_controls.trigger_manual_refresh(
                object(),
                organization_id="org-1",
                submitted_by_user_id="user-9",
                parameters={"reason": "test"},
            )
        create_job.assert_called_once()
        record_audit.assert_called_once()
        self.assertEqual(
            payload["contract_version"],
            automation_controls.AUTOMATION_MANUAL_TRIGGER_CONTRACT_VERSION,
        )
        self.assertEqual(payload["job"]["job_type"], "manual_refresh")
        self.assertEqual(payload["audit_log_id"], str(created_audit.id))

    def test_build_automation_overview_collapses_sub_bundles(self) -> None:
        jobs = [_fake_job("published_refresh", "completed")]
        logs = [_fake_audit("published_refresh.completed")]
        schedule = {
            "noop": {
                "task": "noop",
                "schedule": 120.0,
                "options": {"queue": "road_risk_default"},
            }
        }
        with (
            mock.patch(
                "apps.api.services.automation_controls.repositories.list_ingestion_jobs_for_organization",
                return_value=jobs,
            ),
            mock.patch(
                "apps.api.services.automation_controls.repositories.list_audit_logs_for_organization",
                return_value=logs,
            ),
            mock.patch(
                "apps.api.services.automation_controls.repositories.list_data_sources_for_organization",
                return_value=[],
            ),
        ):
            payload = automation_controls.build_automation_overview(
                object(),
                organization_id="org-1",
                beat_schedule=schedule,
            )
        self.assertEqual(
            payload["contract_version"],
            automation_controls.AUTOMATION_OVERVIEW_CONTRACT_VERSION,
        )
        self.assertEqual(payload["schedules"]["entry_count"], 1)
        self.assertEqual(payload["runs"]["totals"]["total"], 1)
        self.assertEqual(payload["notifications"]["totals"]["total"], 1)
        self.assertEqual(payload["stale_sources"]["totals"]["stale_count"], 0)

    def test_control_schedule_records_audit_log(self) -> None:
        audit = _fake_audit("automation.schedule.paused")
        with (
            mock.patch(
                "apps.api.services.automation_controls.repositories.list_audit_logs_for_organization",
                return_value=[],
            ),
            mock.patch(
                "apps.api.services.automation_controls.repositories.record_audit_log",
                return_value=audit,
            ) as record_audit,
        ):
            payload = automation_controls.control_schedule(
                object(),
                organization_id="org-1",
                schedule_name="health-ping-every-1-minute",
                action="pause",
                actor_user_id="admin-1",
            )
        self.assertEqual(payload["contract_version"], automation_controls.AUTOMATION_SCHEDULE_CONTROL_CONTRACT_VERSION)
        record_audit.assert_called_once()
        self.assertEqual(payload["schedule_name"], "health-ping-every-1-minute")

    def test_detect_stale_sources_records_notifications(self) -> None:
        now = datetime(2026, 6, 3, tzinfo=timezone.utc)
        sources = [
            _fake_source("Daily crash feed", "daily", now - timedelta(days=3)),
            _fake_source("Fresh traffic feed", "daily", now - timedelta(hours=2)),
            _fake_source("Never refreshed speed feed", "weekly", None),
        ]
        with (
            mock.patch(
                "apps.api.services.automation_controls.repositories.list_data_sources_for_organization",
                return_value=sources,
            ),
            mock.patch(
                "apps.api.services.automation_controls.repositories.record_audit_log",
                side_effect=[_fake_audit("data_source.stale"), _fake_audit("data_source.stale")],
            ) as record_audit,
        ):
            payload = automation_controls.detect_stale_sources(
                object(),
                organization_id="org-1",
                now=now,
            )
        self.assertEqual(payload["contract_version"], automation_controls.AUTOMATION_STALE_SOURCES_CONTRACT_VERSION)
        self.assertEqual(payload["totals"]["source_count"], 3)
        self.assertEqual(payload["totals"]["stale_count"], 2)
        self.assertEqual(record_audit.call_count, 2)

    def test_deliver_notifications_records_delivery_audit(self) -> None:
        logs = [_fake_audit("data_source.stale"), _fake_audit("ingestion_job.failed")]
        audit = _fake_audit("automation.notification.delivered")
        with (
            mock.patch(
                "apps.api.services.automation_controls.repositories.list_audit_logs_for_organization",
                return_value=logs,
            ),
            mock.patch(
                "apps.api.services.automation_controls.repositories.record_audit_log",
                return_value=audit,
            ) as record_audit,
        ):
            payload = automation_controls.deliver_notifications(
                object(),
                organization_id="org-1",
                email_recipients=["ops@example.gov"],
                dry_run=True,
            )
        self.assertEqual(payload["contract_version"], automation_controls.AUTOMATION_NOTIFICATION_DELIVERY_CONTRACT_VERSION)
        self.assertEqual(payload["notification_count"], 2)
        self.assertEqual(payload["channels"][0]["channel"], "email_outbox")
        self.assertEqual(payload["channels"][0]["subject"], payload["digest"]["subject"])
        self.assertEqual(payload["channels"][0]["message_formats"], ["html", "text"])
        self.assertIn("xROAD automation digest", payload["digest"]["subject"])
        self.assertIn("xROAD", payload["digest"]["html"])
        record_audit.assert_called_once()

    def test_render_notification_digest_brands_html_and_text(self) -> None:
        generated_at = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)
        rows = [
            {
                "action": "ingestion_job.failed",
                "status": "failed",
                "target_type": "ingestion_job",
                "target_id": "job-1",
                "created_at": "2026-07-06T08:30:00+00:00",
            },
            {
                "action": "data_source.approved",
                "status": "approved",
                "target_type": "data_source",
                "target_id": "src-1",
                "created_at": "2026-07-06T08:45:00+00:00",
            },
        ]
        digest = automation_controls.render_notification_digest(
            "org-1", rows, generated_at=generated_at,
        )
        self.assertEqual(
            digest["contract_version"],
            automation_controls.AUTOMATION_NOTIFICATION_DIGEST_CONTRACT_VERSION,
        )
        self.assertEqual(digest["notification_count"], 2)
        # Failure is surfaced in the subject and accent palette.
        self.assertIn("1 needing attention", digest["subject"])
        self.assertIn("#FF4B3E", digest["html"])  # Application hazard red for the failure row
        self.assertIn("#101317", digest["html"])  # Application asphalt letterhead
        self.assertIn("Ingestion job failed", digest["html"])
        # Human-readable plain-text fallback.
        self.assertIn("xROAD — Road Accident Risk Modeling", digest["text"])
        self.assertIn("• Ingestion job failed", digest["text"])
        self.assertIn("Data source approved", digest["text"])

    def test_render_notification_digest_handles_empty_feed(self) -> None:
        digest = automation_controls.render_notification_digest("org-1", [])
        self.assertEqual(digest["notification_count"], 0)
        self.assertIn("all monitored feeds steady", digest["subject"])
        self.assertIn("All monitored feeds are steady", digest["text"])
        self.assertIn("All monitored feeds are steady", digest["html"])

    def test_render_notification_digest_escapes_untrusted_values(self) -> None:
        rows = [
            {
                "action": "data_source.stale",
                "status": "stale",
                "target_type": "<script>",
                "target_id": "x&y",
                "created_at": "2026-07-06T08:30:00+00:00",
            },
        ]
        digest = automation_controls.render_notification_digest("org-<b>", rows)
        self.assertNotIn("<script>", digest["html"])
        self.assertIn("&lt;script&gt;", digest["html"])
        self.assertIn("org-&lt;b&gt;", digest["html"])


class AutomationControlsEndpointTests(unittest.TestCase):
    def _build_client(self, *, roles: frozenset[str], organization_ids: frozenset[str]) -> TestClient:
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
        return TestClient(app)

    def test_schedules_endpoint_requires_admin(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ANALYST}),
            organization_ids=frozenset({"org-1"}),
        )
        response = client.get("/v1/automation/schedules")
        self.assertEqual(response.status_code, 403)

    def test_schedules_endpoint_returns_payload_for_admin(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.list_automation_schedules",
            return_value={
                "contract_version": automation_controls.AUTOMATION_SCHEDULES_CONTRACT_VERSION,
                "scheduler_available": True,
                "entry_count": 0,
                "paused_count": 0,
                "entries": [],
            },
        ):
            response = client.get("/v1/automation/schedules")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["contract_version"],
            automation_controls.AUTOMATION_SCHEDULES_CONTRACT_VERSION,
        )

    def test_schedule_control_endpoint_updates_schedule(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.control_schedule",
            return_value={
                "contract_version": automation_controls.AUTOMATION_SCHEDULE_CONTROL_CONTRACT_VERSION,
                "organization_id": "org-1",
                "action": "pause",
                "schedule_name": "stale-source-check-daily",
                "audit_log_id": "audit-1",
                "schedules": {"entries": []},
            },
        ) as patched:
            response = client.patch(
                "/v1/automation/schedules/stale-source-check-daily",
                json={"organization_id": "org-1", "action": "pause"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contract_version"], automation_controls.AUTOMATION_SCHEDULE_CONTROL_CONTRACT_VERSION)
        patched.assert_called_once()

    def test_runs_endpoint_returns_filtered_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.list_automation_runs",
            return_value={
                "contract_version": automation_controls.AUTOMATION_RUNS_CONTRACT_VERSION,
                "organization_id": "org-1",
                "filters": {"job_type": "manual_refresh", "limit": 50},
                "totals": {"total": 0, "by_status": {}, "by_job_type": {}},
                "runs": [],
            },
        ) as patched:
            response = client.get(
                "/v1/automation/runs",
                params={"organization_id": "org-1", "job_type": "manual_refresh"},
            )
        self.assertEqual(response.status_code, 200)
        patched.assert_called_once()
        _, kwargs = patched.call_args
        self.assertEqual(kwargs["job_type"], "manual_refresh")

    def test_runs_endpoint_requires_org_scope(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-2"}),
        )
        response = client.get(
            "/v1/automation/runs",
            params={"organization_id": "org-1"},
        )
        self.assertEqual(response.status_code, 403)

    def test_runs_trigger_endpoint_creates_job(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.trigger_manual_refresh",
            return_value={
                "contract_version": automation_controls.AUTOMATION_MANUAL_TRIGGER_CONTRACT_VERSION,
                "organization_id": "org-1",
                "job": {"job_id": "job-1", "job_type": "manual_refresh", "status": "queued"},
                "audit_log_id": "audit-1",
            },
        ) as patched:
            response = client.post(
                "/v1/automation/runs/trigger",
                json={"organization_id": "org-1", "parameters": {"reason": "test"}},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["job"]["job_type"], "manual_refresh")
        patched.assert_called_once()

    def test_notifications_endpoint_returns_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.list_notifications",
            return_value={
                "contract_version": automation_controls.AUTOMATION_NOTIFICATIONS_CONTRACT_VERSION,
                "organization_id": "org-1",
                "filters": {"actions": [], "limit": 50},
                "totals": {"total": 0, "by_action": {}},
                "notifications": [],
            },
        ):
            response = client.get(
                "/v1/automation/notifications",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["contract_version"],
            automation_controls.AUTOMATION_NOTIFICATIONS_CONTRACT_VERSION,
        )

    def test_notifications_delivery_endpoint_records_delivery(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.deliver_notifications",
            return_value={
                "contract_version": automation_controls.AUTOMATION_NOTIFICATION_DELIVERY_CONTRACT_VERSION,
                "organization_id": "org-1",
                "dry_run": True,
                "notification_count": 1,
                "channels": [{"channel": "email_outbox"}],
                "audit_log_id": "audit-1",
            },
        ):
            response = client.post(
                "/v1/automation/notifications/deliver",
                json={"organization_id": "org-1", "email_recipients": ["ops@example.gov"]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contract_version"], automation_controls.AUTOMATION_NOTIFICATION_DELIVERY_CONTRACT_VERSION)

    def test_stale_sources_endpoint_returns_policy_breaches(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.detect_stale_sources",
            return_value={
                "contract_version": automation_controls.AUTOMATION_STALE_SOURCES_CONTRACT_VERSION,
                "organization_id": "org-1",
                "totals": {"source_count": 1, "stale_count": 1},
                "stale_sources": [{"source_id": "source-1"}],
                "audit_log_ids": [],
            },
        ):
            response = client.get(
                "/v1/automation/stale-sources",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contract_version"], automation_controls.AUTOMATION_STALE_SOURCES_CONTRACT_VERSION)

    def test_overview_endpoint_returns_bundle(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.automation_controls.build_automation_overview",
            return_value={
                "contract_version": automation_controls.AUTOMATION_OVERVIEW_CONTRACT_VERSION,
                "organization_id": "org-1",
                "generated_at": "2026-05-15T00:00:00+00:00",
                "schedules": {
                    "scheduler_available": True,
                    "entry_count": 0,
                    "paused_count": 0,
                    "entries": [],
                },
                "runs": {"limit": 10, "totals": {"total": 0, "by_status": {}, "by_job_type": {}}, "rows": []},
                "notifications": {"limit": 10, "totals": {"total": 0, "by_action": {}}, "rows": []},
                "stale_sources": {"totals": {"source_count": 0, "stale_count": 0}, "stale_sources": []},
            },
        ):
            response = client.get(
                "/v1/automation/overview",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["contract_version"],
            automation_controls.AUTOMATION_OVERVIEW_CONTRACT_VERSION,
        )


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
