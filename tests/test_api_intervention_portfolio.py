"""Tests for managed intervention portfolio lifecycle (#137)."""

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
    ROLE_ANALYST,
    ROLE_PUBLIC,
    get_auth_context,
)
from apps.api.db.session import get_db_session  # noqa: E402
from apps.api.main import create_app  # noqa: E402
from apps.api.services import intervention_portfolio  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _record(**overrides: object) -> SimpleNamespace:
    fields = {
        "id": uuid4(),
        "organization_id": "org-1",
        "municipality_id": None,
        "scenario_run_id": None,
        "target_object_type": "scenario_target",
        "target_object_id": "top_corridor",
        "intervention_type": "speed_management",
        "cost_class": "medium",
        "expected_benefit": 7.0452,
        "priority_score": 3.5226,
        "status": "shortlisted",
        "owner_subject": "analyst-1",
        "planned_start_date": None,
        "planned_completion_date": None,
        "completed_at": None,
        "notes": "Review with traffic engineering.",
        "source_kind": "scenario_run",
        "properties_json": {
            "city_key": "bari",
            "target_label": "Tangenziale di Bari",
            "scenario_workspace_run_id": "run:abc",
            "before_after": {
                "baseline_predicted_crash_total": 39.14,
                "expected_crash_reduction": 7.0452,
            },
        },
        "created_at": None,
        "updated_at": None,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class InterventionPortfolioServiceTests(unittest.TestCase):
    def test_build_portfolio_ranks_rows_and_summarizes_status(self) -> None:
        rows = [
            _record(id=uuid4(), target_object_id="a", expected_benefit=4.0, priority_score=2.0, status="planned"),
            _record(id=uuid4(), target_object_id="b", expected_benefit=8.0, priority_score=8.0, status="shortlisted"),
        ]
        with mock.patch(
            "apps.api.services.intervention_portfolio.repositories.list_interventions_for_organization",
            return_value=rows,
        ):
            payload = intervention_portfolio.build_portfolio(object(), organization_id="org-1", city_key="bari")

        self.assertEqual(payload["contract_version"], intervention_portfolio.INTERVENTION_PORTFOLIO_CONTRACT_VERSION)
        self.assertEqual(payload["totals"]["portfolio_count"], 2)
        self.assertEqual(payload["totals"]["by_status"], {"shortlisted": 1, "planned": 1})
        self.assertEqual(payload["rows"][0]["target_object_id"], "b")

    def test_create_portfolio_item_from_scenario_run_records_audit(self) -> None:
        scenario_run = {
            "scenario_run_id": "run:abc",
            "organization_id": "org-1",
            "city_key": "bari",
            "name": "Speed package",
            "intervention_code": "speed_management",
            "cost_class": "medium",
            "confidence": "medium",
            "target": {
                "target_context_key": "top_corridor",
                "target_context_label": "Tangenziale di Bari",
            },
            "before_after": {
                "baseline_predicted_crash_total": 39.14,
                "expected_crash_reduction": 7.0452,
            },
            "assumptions": ["Speed limit review approved."],
        }
        record = _record()
        with (
            mock.patch(
                "apps.api.services.intervention_portfolio.scenario_planner.get_scenario_run",
                return_value={"run": scenario_run},
            ),
            mock.patch(
                "apps.api.services.intervention_portfolio.repositories.create_intervention",
                return_value=record,
            ) as create_intervention,
            mock.patch(
                "apps.api.services.intervention_portfolio.repositories.record_audit_log",
                return_value=None,
            ) as record_audit,
        ):
            payload = intervention_portfolio.create_portfolio_item(
                object(),
                ApiSettings(),
                organization_id="org-1",
                scenario_run_id="run:abc",
                status="shortlisted",
                actor_subject="analyst-1",
            )

        self.assertEqual(payload["operation"], "created")
        create_kwargs = create_intervention.call_args.kwargs
        self.assertEqual(create_kwargs["target_object_id"], "top_corridor")
        self.assertEqual(create_kwargs["expected_benefit"], 7.0452)
        self.assertEqual(create_kwargs["priority_score"], 3.5226)
        record_audit.assert_called_once()
        self.assertEqual(record_audit.call_args.kwargs["action"], "intervention_portfolio.created")

    def test_update_portfolio_item_records_changed_fields_and_completion(self) -> None:
        record = _record(status="planned", completed_at=None)
        with (
            mock.patch(
                "apps.api.services.intervention_portfolio.repositories.get_intervention",
                return_value=record,
            ),
            mock.patch(
                "apps.api.services.intervention_portfolio.repositories.update_intervention",
                side_effect=lambda _session, item, **kwargs: _apply_updates(item, kwargs),
            ),
            mock.patch(
                "apps.api.services.intervention_portfolio.repositories.record_audit_log",
                return_value=None,
            ) as record_audit,
        ):
            payload = intervention_portfolio.update_portfolio_item(
                object(),
                organization_id="org-1",
                intervention_id=str(record.id),
                updates={"status": "completed", "after_observed_crashes": 2.0},
                actor_subject="analyst-1",
            )

        self.assertEqual(payload["portfolio_item"]["status"], "completed")
        self.assertIsNotNone(record.completed_at)
        audit_metadata = record_audit.call_args.kwargs["metadata"]
        self.assertIn("status", audit_metadata["changed_fields"])

    def test_build_portfolio_export_returns_report_ready_rows(self) -> None:
        with mock.patch(
            "apps.api.services.intervention_portfolio.repositories.list_interventions_for_organization",
            return_value=[_record()],
        ):
            payload = intervention_portfolio.build_portfolio_export(object(), organization_id="org-1", city_key="bari")
        self.assertEqual(payload["contract_version"], intervention_portfolio.INTERVENTION_PORTFOLIO_EXPORT_CONTRACT_VERSION)
        self.assertEqual(payload["rows"][0]["priority_rank"], 1)
        self.assertEqual(payload["rows"][0]["target"], "Tangenziale di Bari")


def _apply_updates(item: SimpleNamespace, kwargs: dict[str, object]) -> SimpleNamespace:
    for key, value in kwargs.items():
        if value is not None and key != "properties":
            setattr(item, key, value)
    if kwargs.get("properties"):
        item.properties_json.update(kwargs["properties"])
    return item


class InterventionPortfolioEndpointTests(unittest.TestCase):
    def _build_client(self, *, roles: frozenset[str]) -> TestClient:
        app = create_app(ApiSettings(auth_enabled=True))
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="analyst-1",
            assigned_roles=frozenset(roles),
            roles=frozenset(roles),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=frozenset({"bari"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )

        def _session_override():
            yield object()

        app.dependency_overrides[get_db_session] = _session_override
        return TestClient(app)

    def test_portfolio_endpoint_requires_analyst_role(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_PUBLIC}))
        response = client.get("/v1/interventions/portfolio", params={"organization_id": "org-1", "city_key": "bari"})
        self.assertEqual(response.status_code, 403)

    def test_portfolio_endpoint_returns_rows_for_analyst(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_ANALYST}))
        with mock.patch(
            "apps.api.services.intervention_portfolio.build_portfolio",
            return_value={
                "contract_version": intervention_portfolio.INTERVENTION_PORTFOLIO_CONTRACT_VERSION,
                "organization_id": "org-1",
                "city_key": "bari",
                "availability": "available",
                "unavailable_reason": None,
                "totals": {"portfolio_count": 1, "expected_benefit": 7.0, "by_status": {"planned": 1}},
                "rows": [
                    {
                        "intervention_id": "intervention-1",
                        "target_label": "Tangenziale di Bari",
                        "intervention_type": "speed_management",
                        "status": "planned",
                    }
                ],
            },
        ):
            response = client.get("/v1/interventions/portfolio", params={"organization_id": "org-1", "city_key": "bari"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["totals"]["portfolio_count"], 1)

    def test_create_endpoint_rejects_unscoped_organization(self) -> None:
        client = self._build_client(roles=frozenset({ROLE_ANALYST}))
        response = client.post(
            "/v1/interventions/portfolio",
            json={
                "organization_id": "org-2",
                "city_key": "bari",
                "target_object_type": "corridor",
                "target_object_id": "top_corridor",
                "intervention_type": "speed_management",
            },
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
