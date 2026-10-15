"""Tests for the admin control-center surface added under issue #91."""
from __future__ import annotations

from pathlib import Path
import sys
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
    ROLE_DATA_OPERATOR,
    ROLE_SUPER_ADMIN,
    get_auth_context,
)
from apps.api.db.session import get_db_session  # noqa: E402
from apps.api.main import create_app  # noqa: E402
from apps.api.services import admin_control  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _ns(**fields: object) -> SimpleNamespace:
    return SimpleNamespace(**fields)


def _fake_data_source(name: str, *, governance_status: str, publication_tier: str):
    return _ns(
        id=uuid4(),
        organization_id="org-1",
        name=name,
        source_type="crash_feed",
        provider_name="Comune di Bari",
        governance_status=governance_status,
        publication_tier=publication_tier,
        refresh_frequency="monthly",
        municipality_id=uuid4(),
        configuration_json={},
        status="active",
        created_at=None,
        updated_at=None,
    )


def _fake_membership(role: str, status: str = "active"):
    user = _ns(
        id=uuid4(),
        subject="user.demo",
        external_subject="user.demo",
        email="user.demo@example.test",
        display_name="Demo User",
        status="active",
    )
    return _ns(
        id=uuid4(),
        organization_id="org-1",
        user_id=user.id,
        role=role,
        status=status,
        user=user,
        created_at=None,
        updated_at=None,
    )


def _fake_job(status: str):
    return _ns(
        id=uuid4(),
        job_type="published_refresh",
        status=status,
        source_id=None,
        municipality_id=None,
        created_at=None,
        started_at=None,
        finished_at=None,
    )


def _fake_audit():
    return _ns(
        id=uuid4(),
        event_type="data_source.approved",
        actor_subject="admin.demo",
        resource_kind="data_source",
        resource_id="data-source-1",
        created_at=None,
    )


def _fake_artifact(publication_tier: str):
    return _ns(publication_tier=publication_tier)


_GOV_MATRIX_PATCHES = (
    (
        "apps.api.services.admin_control.repositories.list_data_sources_for_organization",
        [
            _fake_data_source("Bari crash feed", governance_status="approved", publication_tier="public"),
            _fake_data_source("Bari signals", governance_status="approved", publication_tier="restricted"),
            _fake_data_source("Foggia draft", governance_status="draft", publication_tier="restricted"),
        ],
    ),
)


class AdminControlServiceTests(unittest.TestCase):
    def test_build_governance_matrix_counts_by_status_and_tier(self) -> None:
        sources = [
            _fake_data_source("a", governance_status="approved", publication_tier="public"),
            _fake_data_source("b", governance_status="approved", publication_tier="restricted"),
            _fake_data_source("c", governance_status="draft", publication_tier="restricted"),
        ]
        with mock.patch(
            "apps.api.services.admin_control.repositories.list_data_sources_for_organization",
            return_value=sources,
        ):
            matrix = admin_control.build_governance_matrix(object(), organization_id="org-1")
        self.assertEqual(matrix["contract_version"], admin_control.ADMIN_GOVERNANCE_MATRIX_CONTRACT_VERSION)
        self.assertEqual(matrix["totals"]["data_source_count"], 3)
        self.assertEqual(matrix["totals"]["by_governance_status"], {"approved": 2, "draft": 1})
        self.assertEqual(matrix["totals"]["by_publication_tier"], {"public": 1, "restricted": 2})
        self.assertEqual(len(matrix["rows"]), 3)

    def test_create_governed_data_source_records_audit_log(self) -> None:
        source = _fake_data_source("Bari crash feed", governance_status="approved", publication_tier="public")
        audit = _ns(id=uuid4())
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.get_data_source_by_name",
                return_value=None,
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.create_data_source",
                return_value=source,
            ) as create_source,
            mock.patch(
                "apps.api.services.admin_control.repositories.record_audit_log",
                return_value=audit,
            ) as record_audit,
        ):
            result = admin_control.create_governed_data_source(
                _ns(),
                organization_id="org-1",
                name="Bari crash feed",
                source_type="crash_feed",
                provider_name="Comune di Bari",
                governance_status="approved",
                publication_tier="public",
                refresh_frequency="monthly",
                actor_subject="admin.demo",
                decision_note="Approved source rights.",
            )
        self.assertEqual(result["contract_version"], admin_control.ADMIN_DATA_SOURCE_WRITE_CONTRACT_VERSION)
        self.assertEqual(result["operation"], "created")
        self.assertEqual(result["data_source"]["name"], "Bari crash feed")
        self.assertTrue(result["policy_evaluation"]["public_artifact_review_required"])
        create_source.assert_called_once()
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["action"], "data_source.created")
        self.assertEqual(audit_kwargs["target_type"], "data_source")
        self.assertEqual(audit_kwargs["metadata"]["actor_subject"], "admin.demo")
        self.assertEqual(audit_kwargs["metadata"]["decision_note"], "Approved source rights.")

    def test_update_governed_data_source_changes_policy_and_records_delta(self) -> None:
        source = _fake_data_source("Bari crash feed", governance_status="draft", publication_tier="restricted")
        audit = _ns(id=uuid4())
        session = _ns(flush=lambda: None)
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.get_data_source",
                return_value=source,
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.record_audit_log",
                return_value=audit,
            ) as record_audit,
        ):
            result = admin_control.update_governed_data_source(
                session,
                organization_id="org-1",
                source_id=str(source.id),
                updates={
                    "governance_status": "approved",
                    "publication_tier": "public",
                    "refresh_frequency": "weekly",
                },
                actor_subject="admin.demo",
                decision_note="Provider rights reviewed.",
            )
        self.assertEqual(result["operation"], "policy_updated")
        self.assertEqual(source.governance_status, "approved")
        self.assertEqual(source.publication_tier, "public")
        self.assertEqual(source.refresh_frequency, "weekly")
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["action"], "data_source.policy_updated")
        self.assertIn("governance_status", audit_kwargs["metadata"]["changed_fields"])
        self.assertEqual(audit_kwargs["metadata"]["before"]["governance_status"], "draft")
        self.assertEqual(audit_kwargs["metadata"]["after"]["publication_tier"], "public")

    def test_update_governed_data_source_rejects_public_unrecognized_status(self) -> None:
        source = _fake_data_source("Bari crash feed", governance_status="draft", publication_tier="restricted")
        with mock.patch(
            "apps.api.services.admin_control.repositories.get_data_source",
            return_value=source,
        ):
            with self.assertRaises(admin_control.AdminControlError):
                admin_control.update_governed_data_source(
                    _ns(flush=lambda: None),
                    organization_id="org-1",
                    source_id=str(source.id),
                    updates={"governance_status": "published_everywhere"},
                )

    def test_build_user_roster_counts_roles_and_includes_municipality_links(self) -> None:
        memberships = [_fake_membership("analyst"), _fake_membership("admin"), _fake_membership("analyst")]
        links = [
            _ns(id=uuid4(), municipality_id=uuid4(), access_level="restricted", status="active", created_at=None, updated_at=None),
        ]
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.list_memberships_for_organization",
                return_value=memberships,
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.list_municipality_links_for_organization",
                return_value=links,
            ),
        ):
            roster = admin_control.build_user_roster(object(), organization_id="org-1")
        self.assertEqual(roster["contract_version"], admin_control.ADMIN_USER_ROSTER_CONTRACT_VERSION)
        self.assertEqual(roster["totals"]["membership_count"], 3)
        self.assertEqual(roster["totals"]["by_role"], {"analyst": 2, "admin": 1})
        self.assertEqual(roster["totals"]["municipality_link_count"], 1)

    def test_link_organization_user_upserts_oidc_subject_and_records_audit(self) -> None:
        user = _ns(
            id=uuid4(),
            external_subject="oidc-user-1",
            email="planner@example.test",
            display_name="Planner",
            status="active",
        )
        membership = _fake_membership("analyst")
        membership.user = user
        audit = _ns(id=uuid4())
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.upsert_user_by_subject",
                return_value=user,
            ) as upsert_user,
            mock.patch(
                "apps.api.services.admin_control.repositories.get_membership_for_user",
                return_value=None,
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.add_membership",
                return_value=membership,
            ) as add_membership,
            mock.patch(
                "apps.api.services.admin_control.repositories.record_audit_log",
                return_value=audit,
            ) as record_audit,
        ):
            result = admin_control.link_organization_user(
                _ns(),
                organization_id="org-1",
                subject="oidc-user-1",
                email="planner@example.test",
                display_name="Planner",
                role="analyst",
                actor_subject="admin.demo",
                decision_note="Approved onboarding.",
            )
        self.assertEqual(result["contract_version"], admin_control.ADMIN_ACCESS_WRITE_CONTRACT_VERSION)
        self.assertEqual(result["operation"], "linked")
        self.assertEqual(result["membership"]["user"]["subject"], "oidc-user-1")
        upsert_user.assert_called_once()
        add_membership.assert_called_once()
        self.assertEqual(record_audit.call_args.kwargs["action"], "membership.linked")
        self.assertEqual(record_audit.call_args.kwargs["metadata"]["actor_subject"], "admin.demo")

    def test_update_membership_access_records_delta(self) -> None:
        membership = _fake_membership("analyst")
        audit = _ns(id=uuid4())
        session = _ns(flush=lambda: None)
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.get_membership",
                return_value=membership,
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.record_audit_log",
                return_value=audit,
            ) as record_audit,
        ):
            result = admin_control.update_membership_access(
                session,
                organization_id="org-1",
                membership_id=str(membership.id),
                role="data_operator",
                status="active",
                actor_subject="admin.demo",
                decision_note="Role review.",
            )
        self.assertEqual(result["operation"], "membership_updated")
        self.assertEqual(membership.role, "data_operator")
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["action"], "membership.access_updated")
        self.assertIn("role", audit_kwargs["metadata"]["changed_fields"])

    def test_update_membership_access_blocks_last_admin_removal(self) -> None:
        membership = _fake_membership("admin")
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.get_membership",
                return_value=membership,
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.list_memberships_for_organization",
                return_value=[membership],
            ),
        ):
            with self.assertRaises(admin_control.AdminControlError):
                admin_control.update_membership_access(
                    _ns(flush=lambda: None),
                    organization_id="org-1",
                    membership_id=str(membership.id),
                    role="analyst",
                )

    def test_assign_municipality_access_creates_link_and_audit(self) -> None:
        link = _ns(
            id=uuid4(),
            municipality_id="bari",
            access_level="full",
            status="active",
            created_at=None,
            updated_at=None,
        )
        audit = _ns(id=uuid4())
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.get_organization_municipality_link",
                return_value=None,
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.link_organization_municipality",
                return_value=link,
            ) as create_link,
            mock.patch(
                "apps.api.services.admin_control.repositories.record_audit_log",
                return_value=audit,
            ) as record_audit,
        ):
            result = admin_control.assign_municipality_access(
                _ns(),
                organization_id="org-1",
                municipality_id="bari",
                access_level="full",
                actor_subject="admin.demo",
            )
        self.assertEqual(result["operation"], "municipality_access_assigned")
        self.assertEqual(result["municipality_link"]["municipality_id"], "bari")
        create_link.assert_called_once()
        self.assertEqual(record_audit.call_args.kwargs["action"], "municipality_access.assigned")

    def test_build_automations_roster_renders_provided_beat_schedule(self) -> None:
        schedule = {
            "health-ping-every-1-minute": {
                "task": "services.workers.tasks.health.ping",
                "schedule": 60.0,
                "options": {"queue": "road_risk_default", "expires": 30},
            },
        }
        roster = admin_control.build_automations_roster(
            organization_id="org-1",
            beat_schedule=schedule,
        )
        self.assertEqual(roster["contract_version"], admin_control.ADMIN_AUTOMATIONS_CONTRACT_VERSION)
        self.assertTrue(roster["scheduler_available"])
        self.assertEqual(roster["entry_count"], 1)
        entry = roster["entries"][0]
        self.assertEqual(entry["name"], "health-ping-every-1-minute")
        self.assertEqual(entry["task"], "services.workers.tasks.health.ping")
        self.assertEqual(entry["schedule"], {"kind": "interval_seconds", "value": 60.0})
        self.assertEqual(entry["options"], {"queue": "road_risk_default", "expires": 30})

    def test_build_admin_control_center_bundles_subviews(self) -> None:
        with (
            mock.patch(
                "apps.api.services.admin_control.repositories.list_data_sources_for_organization",
                return_value=[
                    _fake_data_source("a", governance_status="approved", publication_tier="public"),
                ],
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.list_memberships_for_organization",
                return_value=[_fake_membership("admin")],
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.list_municipality_links_for_organization",
                return_value=[],
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.list_ingestion_jobs_for_organization",
                return_value=[_fake_job("validated_ready"), _fake_job("failed")],
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.list_audit_logs_for_organization",
                return_value=[_fake_audit()],
            ),
            mock.patch(
                "apps.api.services.admin_control.repositories.list_artifact_references_for_organization",
                return_value=[_fake_artifact("public"), _fake_artifact("restricted")],
            ),
        ):
            bundle = admin_control.build_admin_control_center(
                object(),
                organization_id="org-1",
                beat_schedule={
                    "noop": {"task": "noop", "schedule": 120.0, "options": {"queue": "road_risk_default"}},
                },
            )
        self.assertEqual(bundle["contract_version"], admin_control.ADMIN_CONTROL_CENTER_CONTRACT_VERSION)
        self.assertEqual(bundle["ingestion_overview"]["total"], 2)
        self.assertEqual(bundle["ingestion_overview"]["by_status"], {"validated_ready": 1, "failed": 1})
        self.assertEqual(bundle["artifact_overview"], {"total": 2, "by_publication_tier": {"public": 1, "restricted": 1}})
        self.assertEqual(bundle["governance_matrix"]["totals"]["data_source_count"], 1)
        self.assertEqual(bundle["user_roster"]["totals"]["membership_count"], 1)
        self.assertEqual(bundle["automations"]["entry_count"], 1)
        self.assertEqual(len(bundle["recent_audit"]["entries"]), 1)


class AdminControlEndpointTests(unittest.TestCase):
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

    def test_control_center_endpoint_requires_admin_role(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ANALYST, ROLE_DATA_OPERATOR}),
            organization_ids=frozenset({"org-1"}),
        )
        response = client.get("/v1/admin/control-center", params={"organization_id": "org-1"})
        self.assertEqual(response.status_code, 403)

    def test_control_center_endpoint_requires_org_scope(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-2"}),
        )
        response = client.get("/v1/admin/control-center", params={"organization_id": "org-1"})
        self.assertEqual(response.status_code, 403)

    def test_control_center_endpoint_returns_bundle_for_admin(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.build_admin_control_center",
            return_value={
                "contract_version": admin_control.ADMIN_CONTROL_CENTER_CONTRACT_VERSION,
                "organization_id": "org-1",
                "generated_at": "2026-05-14T00:00:00+00:00",
                "ingestion_overview": {"total": 0, "by_status": {}, "recent_jobs": []},
                "artifact_overview": {"total": 0, "by_publication_tier": {}},
                "governance_matrix": {"rows": [], "totals": {}},
                "automations": {"entries": [], "scheduler_available": False},
                "user_roster": {"memberships": [], "municipality_links": []},
                "recent_audit": {"limit": 25, "entries": []},
            },
        ) as patched:
            response = client.get(
                "/v1/admin/control-center",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["api_version"], "v1")
        self.assertEqual(body["contract_version"], admin_control.ADMIN_CONTROL_CENTER_CONTRACT_VERSION)
        self.assertEqual(body["organization_id"], "org-1")
        patched.assert_called_once()

    def test_governance_matrix_endpoint_returns_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.build_governance_matrix",
            return_value={
                "contract_version": admin_control.ADMIN_GOVERNANCE_MATRIX_CONTRACT_VERSION,
                "organization_id": "org-1",
                "totals": {"data_source_count": 0, "by_governance_status": {}, "by_publication_tier": {}},
                "rows": [],
            },
        ):
            response = client.get(
                "/v1/admin/governance-matrix",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contract_version"], admin_control.ADMIN_GOVERNANCE_MATRIX_CONTRACT_VERSION)

    def test_automations_endpoint_returns_roster(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.build_automations_roster",
            return_value={
                "contract_version": admin_control.ADMIN_AUTOMATIONS_CONTRACT_VERSION,
                "organization_id": "org-1",
                "scheduler_available": False,
                "entries": [],
                "entry_count": 0,
            },
        ):
            response = client.get(
                "/v1/admin/automations",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["contract_version"], admin_control.ADMIN_AUTOMATIONS_CONTRACT_VERSION)
        self.assertFalse(body["scheduler_available"])

    def test_user_roster_endpoint_returns_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.build_user_roster",
            return_value={
                "contract_version": admin_control.ADMIN_USER_ROSTER_CONTRACT_VERSION,
                "organization_id": "org-1",
                "totals": {"membership_count": 0, "by_role": {}, "by_status": {}, "municipality_link_count": 0},
                "memberships": [],
                "municipality_links": [],
            },
        ):
            response = client.get(
                "/v1/admin/user-roster",
                params={"organization_id": "org-1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contract_version"], admin_control.ADMIN_USER_ROSTER_CONTRACT_VERSION)

    def test_create_data_source_endpoint_requires_admin_role(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ANALYST, ROLE_DATA_OPERATOR}),
            organization_ids=frozenset({"org-1"}),
        )
        response = client.post(
            "/v1/admin/data-sources",
            json={
                "organization_id": "org-1",
                "name": "Bari crash feed",
                "source_type": "crash_feed",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_create_data_source_endpoint_requires_org_scope(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-2"}),
        )
        response = client.post(
            "/v1/admin/data-sources",
            json={
                "organization_id": "org-1",
                "name": "Bari crash feed",
                "source_type": "crash_feed",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_create_data_source_endpoint_returns_write_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.create_governed_data_source",
            return_value={
                "contract_version": admin_control.ADMIN_DATA_SOURCE_WRITE_CONTRACT_VERSION,
                "operation": "created",
                "data_source": {"id": "source-1", "name": "Bari crash feed"},
                "policy_evaluation": {"warnings": [], "blocks_ingestion": False},
                "audit_log_id": "audit-1",
            },
        ) as patched:
            response = client.post(
                "/v1/admin/data-sources",
                json={
                    "organization_id": "org-1",
                    "name": "Bari crash feed",
                    "source_type": "crash_feed",
                    "governance_status": "approved",
                    "publication_tier": "public",
                },
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["api_version"], "v1")
        self.assertEqual(body["operation"], "created")
        patched.assert_called_once()

    def test_update_data_source_endpoint_returns_write_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.update_governed_data_source",
            return_value={
                "contract_version": admin_control.ADMIN_DATA_SOURCE_WRITE_CONTRACT_VERSION,
                "operation": "policy_updated",
                "data_source": {"id": "source-1", "name": "Bari crash feed"},
                "policy_evaluation": {"warnings": [], "blocks_ingestion": False},
                "audit_log_id": "audit-1",
            },
        ) as patched:
            response = client.patch(
                "/v1/admin/data-sources/source-1",
                json={
                    "organization_id": "org-1",
                    "governance_status": "approved",
                    "publication_tier": "public",
                    "decision_note": "Provider rights reviewed.",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["operation"], "policy_updated")
        patched.assert_called_once()

    def test_archive_data_source_endpoint_returns_write_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.archive_governed_data_source",
            return_value={
                "contract_version": admin_control.ADMIN_DATA_SOURCE_WRITE_CONTRACT_VERSION,
                "operation": "archived",
                "data_source": {"id": "source-1", "name": "Bari crash feed"},
                "policy_evaluation": {"warnings": ["blocked"], "blocks_ingestion": True},
                "audit_log_id": "audit-1",
            },
        ):
            response = client.post(
                "/v1/admin/data-sources/source-1/archive",
                json={"organization_id": "org-1", "decision_note": "Superseded source."},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["operation"], "archived")

    def test_link_user_endpoint_returns_access_write_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.link_organization_user",
            return_value={
                "contract_version": admin_control.ADMIN_ACCESS_WRITE_CONTRACT_VERSION,
                "operation": "linked",
                "membership": {"membership_id": "m-1", "role": "analyst", "status": "active"},
                "audit_log_id": "audit-1",
            },
        ) as patched:
            response = client.post(
                "/v1/admin/users/link",
                json={
                    "organization_id": "org-1",
                    "subject": "oidc-user-1",
                    "email": "planner@example.test",
                    "role": "analyst",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["operation"], "linked")
        patched.assert_called_once()

    def test_update_membership_endpoint_returns_access_write_payload(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_ADMIN}),
            organization_ids=frozenset({"org-1"}),
        )
        with mock.patch(
            "apps.api.main.admin_control.update_membership_access",
            return_value={
                "contract_version": admin_control.ADMIN_ACCESS_WRITE_CONTRACT_VERSION,
                "operation": "membership_updated",
                "membership": {"membership_id": "m-1", "role": "data_operator", "status": "active"},
                "audit_log_id": "audit-1",
            },
        ) as patched:
            response = client.patch(
                "/v1/admin/memberships/m-1",
                json={
                    "organization_id": "org-1",
                    "role": "data_operator",
                    "status": "active",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["operation"], "membership_updated")
        patched.assert_called_once()

    def test_municipality_access_endpoint_allows_super_admin_without_org_claim(self) -> None:
        client = self._build_client(
            roles=frozenset({ROLE_SUPER_ADMIN}),
            organization_ids=frozenset(),
        )
        with mock.patch(
            "apps.api.main.admin_control.assign_municipality_access",
            return_value={
                "contract_version": admin_control.ADMIN_ACCESS_WRITE_CONTRACT_VERSION,
                "operation": "municipality_access_assigned",
                "municipality_link": {"municipality_id": "bari", "access_level": "full", "status": "active"},
                "audit_log_id": "audit-1",
            },
        ) as patched:
            response = client.post(
                "/v1/admin/municipality-access",
                json={
                    "organization_id": "org-1",
                    "municipality_id": "bari",
                    "access_level": "full",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["operation"], "municipality_access_assigned")
        patched.assert_called_once()


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
