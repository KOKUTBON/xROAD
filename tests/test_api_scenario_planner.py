"""Tests for the scenario planner surface added under issue #92."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

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
from apps.api.main import create_app  # noqa: E402
from apps.api.services import scenario_planner  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _scaffold_scenario_bundle(root: Path) -> ApiSettings:
    bundle_dir = (
        root
        / "data"
        / "planning"
        / "scenario_countermeasures"
        / "demo_bari_frequency_bundle"
    )
    bundle_path = bundle_dir / "scenario_bundle.json"
    index_path = root / "data" / "planning" / "scenario_countermeasures" / "scenario_countermeasure_index.json"
    library_path = root / "data" / "planning" / "scenario_countermeasures" / "intervention_library.json"

    _write_json(
        index_path,
        {
            "generated_at_utc": "2026-05-14T00:00:00+00:00",
            "intervention_library_path": str(library_path.relative_to(root)),
            "scenario_bundles": [
                {
                    "city_key": "bari",
                    "display_name": "Bari",
                    "manifest_path": "data/planning/scenario_countermeasures/demo_bari_frequency_bundle/scenario_bundle.manifest.json",
                    "prediction_run_label": "demo_bari_frequency",
                    "scenario_bundle_path": str(bundle_path.relative_to(root)),
                    "scenario_markdown_path": "data/planning/scenario_countermeasures/demo_bari_frequency_bundle/scenario_bundle.md",
                    "scenario_spec_path": "data/planning/scenario_countermeasures/demo_bari_frequency_bundle/scenario_spec.json",
                }
            ],
            "scenario_countermeasure_bundle_version": "scenario_countermeasure_bundle_v1",
            "source_dashboard_summary_path": "data/dashboard/dashboard_summary.json",
            "stats": {"library_intervention_count": 2, "scenario_bundle_count": 1},
        },
    )

    _write_json(
        library_path,
        {
            "generated_at_utc": "2026-05-14T00:00:00+00:00",
            "intervention_library_version": "scenario_intervention_library_v1",
            "interventions": [
                {
                    "intervention_code": "speed_management",
                    "label": "Speed management",
                    "category": "speed",
                    "description": "Lower operating speeds on high-risk links.",
                    "supported_asset_types": ["segment"],
                    "baseline_reduction_bounds": {"central": 0.18, "high": 0.28, "low": 0.08},
                    "default_assumptions": ["Posted speeds can be reduced toward 50 km/h."],
                    "rule_summary": ["Cap maxspeed-derived exposure on treated segments."],
                },
                {
                    "intervention_code": "crossing_protection",
                    "label": "Crossing protection",
                    "category": "crossing_protection",
                    "description": "Upgrade pedestrian crossings.",
                    "supported_asset_types": ["node"],
                    "baseline_reduction_bounds": {"central": 0.19, "high": 0.27, "low": 0.12},
                    "default_assumptions": ["Crossings can be upgraded."],
                    "rule_summary": ["Protect the crossing approach."],
                },
            ],
        },
    )

    _write_json(
        bundle_path,
        {
            "city_key": "bari",
            "display_name": "Bari",
            "prediction_run_label": "demo_bari_frequency",
            "generated_at_utc": "2026-05-14T00:00:00+00:00",
            "intervention_library_version": "scenario_intervention_library_v1",
            "planning_brief_summary": {
                "recommended_scenario": {
                    "scenario_id": "demo:speed_management",
                    "title": "Reduce operating speeds on Tangenziale",
                    "intervention_code": "speed_management",
                    "expected_crash_reduction": 10.96,
                    "expected_relative_reduction": 0.28,
                },
                "recommended_portfolio": {
                    "portfolio_id": "portfolio:demo:speed_management__demo:crossing_protection",
                    "title": "Combined treatment",
                    "expected_crash_reduction": 14.5,
                    "expected_relative_reduction": 0.41,
                },
            },
            "scenario_rankings": [
                {
                    "scenario_id": "demo:speed_management",
                    "scenario_rank": 1,
                    "intervention_code": "speed_management",
                    "title": "Reduce operating speeds on Tangenziale",
                    "target_context_label": "Tangenziale di Bari",
                    "target_context_key": "top_corridor",
                    "linked_segment_count": 5,
                    "target_asset_count": 5,
                    "target_asset_types": ["segment"],
                    "expected_crash_reduction": 10.96,
                    "expected_crash_reduction_low": 9.4,
                    "expected_crash_reduction_high": 12.5,
                    "expected_relative_reduction": 0.28,
                    "baseline_predicted_crash_total": 39.14,
                    "counterfactual_predicted_crash_total": 28.18,
                    "assumptions": ["Posted speeds can be reduced."],
                    "affected_assets": [
                        {
                            "asset_id": "demo:seg:1",
                            "asset_label": "Tangenziale di Bari",
                            "asset_type": "segment",
                            "linked_segment_score_ids": ["demo:seg:1"],
                        }
                    ],
                    "linked_segment_score_ids": ["demo:seg:1"],
                },
                {
                    "scenario_id": "demo:crossing_protection",
                    "scenario_rank": 2,
                    "intervention_code": "crossing_protection",
                    "title": "Protect a crossing",
                    "target_context_label": "Crossing",
                    "linked_segment_count": 1,
                    "target_asset_count": 1,
                    "target_asset_types": ["node"],
                    "expected_crash_reduction": 4.2,
                    "expected_relative_reduction": 0.19,
                    "baseline_predicted_crash_total": 22.1,
                    "counterfactual_predicted_crash_total": 17.9,
                    "assumptions": [],
                    "affected_assets": [],
                    "linked_segment_score_ids": [],
                },
            ],
            "portfolio_rankings": [
                {
                    "portfolio_id": "portfolio:demo:speed_management__demo:crossing_protection",
                    "portfolio_rank": 1,
                    "portfolio_note": "Sequentially compounds.",
                    "scenario_ids": ["demo:speed_management", "demo:crossing_protection"],
                    "scenario_titles": ["Reduce speeds", "Protect crossing"],
                    "scenario_count": 2,
                    "distinct_segment_count": 6,
                    "overlap_segment_count": 0,
                    "expected_crash_reduction": 14.5,
                    "expected_relative_reduction": 0.41,
                    "baseline_predicted_crash_total": 39.14,
                    "counterfactual_predicted_crash_total": 24.64,
                },
            ],
        },
    )
    return ApiSettings(root_dir=root)


class ScenarioPlannerServiceTests(unittest.TestCase):
    def test_build_scenario_catalog_lists_city_with_counts_and_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            catalog = scenario_planner.build_scenario_catalog(settings)
            self.assertEqual(catalog["contract_version"], scenario_planner.SCENARIO_PLANNER_CATALOG_CONTRACT_VERSION)
            self.assertEqual(catalog["stats"]["city_count"], 1)
            self.assertEqual(catalog["stats"]["scenario_bundle_count"], 1)
            self.assertEqual(len(catalog["cities"]), 1)
            city = catalog["cities"][0]
            self.assertEqual(city["city_key"], "bari")
            self.assertEqual(city["scenario_count"], 2)
            self.assertEqual(city["portfolio_count"], 1)
            self.assertEqual(
                city["planning_brief_summary"]["recommended_scenario"]["scenario_id"],
                "demo:speed_management",
            )

    def test_build_intervention_library_returns_normalized_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            library = scenario_planner.build_intervention_library(settings)
            self.assertEqual(library["intervention_count"], 2)
            codes = {row["intervention_code"] for row in library["interventions"]}
            self.assertEqual(codes, {"speed_management", "crossing_protection"})

    def test_build_city_scenario_bundle_respects_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            bundle = scenario_planner.build_city_scenario_bundle(
                settings, city_key="bari", scenario_limit=1, portfolio_limit=1,
            )
            self.assertEqual(bundle["totals"]["scenario_count"], 2)
            self.assertEqual(bundle["totals"]["portfolio_count"], 1)
            self.assertEqual(len(bundle["scenarios"]), 1)
            self.assertEqual(bundle["scenarios"][0]["scenario_id"], "demo:speed_management")
            self.assertEqual(len(bundle["portfolios"]), 1)

    def test_build_city_scenario_bundle_unknown_city_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            with self.assertRaises(scenario_planner.ScenarioPlannerError):
                scenario_planner.build_city_scenario_bundle(settings, city_key="unknown")

    def test_build_scenario_detail_returns_assets_and_assumptions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            detail = scenario_planner.build_scenario_detail(
                settings, city_key="bari", scenario_id="demo:speed_management",
            )
            self.assertEqual(detail["scenario"]["scenario_id"], "demo:speed_management")
            self.assertEqual(detail["scenario"]["assumptions"], ["Posted speeds can be reduced."])
            self.assertEqual(
                detail["scenario"]["affected_assets"][0]["asset_id"], "demo:seg:1",
            )

    def test_build_scenario_detail_unknown_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            with self.assertRaises(scenario_planner.ScenarioPlannerError):
                scenario_planner.build_scenario_detail(
                    settings, city_key="bari", scenario_id="demo:missing",
                )

    def test_create_run_and_list_scenario_draft_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            draft_payload = scenario_planner.create_scenario_draft(
                settings,
                organization_id="org-1",
                city_key="bari",
                name="Speed package",
                intervention_code="speed_management",
                target_context_key="top_corridor",
                actor_subject="analyst-1",
            )
            draft = draft_payload["draft"]
            self.assertEqual(draft["contract_version"], scenario_planner.SCENARIO_PLANNER_DRAFT_CONTRACT_VERSION)
            self.assertEqual(draft["validation"]["status"], "valid")
            self.assertEqual(draft["parameters"]["baseline_predicted_crash_total"], 39.14)

            run_payload = scenario_planner.run_scenario_draft(
                settings,
                organization_id="org-1",
                scenario_draft_id=draft["scenario_draft_id"],
                actor_subject="analyst-1",
            )
            run = run_payload["run"]
            self.assertEqual(run["contract_version"], scenario_planner.SCENARIO_PLANNER_RUN_CONTRACT_VERSION)
            self.assertEqual(run["status"], "completed")
            self.assertAlmostEqual(run["before_after"]["expected_crash_reduction"], 7.0452)
            self.assertAlmostEqual(run["before_after"]["counterfactual_predicted_crash_total"], 32.0948)

            drafts = scenario_planner.list_scenario_drafts(
                settings,
                organization_id="org-1",
                city_key="bari",
            )
            runs = scenario_planner.list_scenario_runs(
                settings,
                organization_id="org-1",
                city_key="bari",
            )
            self.assertEqual(drafts["draft_count"], 1)
            self.assertEqual(drafts["drafts"][0]["latest_run_id"], run["scenario_run_id"])
            self.assertEqual(runs["run_count"], 1)

    def test_scenario_drafts_are_organization_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            draft = scenario_planner.create_scenario_draft(
                settings,
                organization_id="org-1",
                city_key="bari",
                name="Speed package",
                intervention_code="speed_management",
                target_context_key="top_corridor",
            )["draft"]

            with self.assertRaises(scenario_planner.ScenarioPlannerError):
                scenario_planner.get_scenario_draft(
                    settings,
                    organization_id="org-2",
                    scenario_draft_id=draft["scenario_draft_id"],
                )

    def test_invalid_draft_is_saved_but_cannot_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            draft = scenario_planner.create_scenario_draft(
                settings,
                organization_id="org-1",
                city_key="bari",
                name="Invalid baseline",
                intervention_code="speed_management",
                target_context_key="top_corridor",
                parameters={"baseline_predicted_crash_total": -1},
            )["draft"]

            self.assertEqual(draft["status"], "needs_input")
            self.assertEqual(draft["validation"]["status"], "needs_input")
            validation = scenario_planner.validate_scenario_draft(
                settings,
                organization_id="org-1",
                scenario_draft_id=draft["scenario_draft_id"],
            )
            self.assertEqual(validation["validation"]["status"], "needs_input")
            with self.assertRaises(scenario_planner.ScenarioPlannerError):
                scenario_planner.run_scenario_draft(
                    settings,
                    organization_id="org-1",
                    scenario_draft_id=draft["scenario_draft_id"],
                )

    # ---- matrix-filter regression coverage (scenario record-kind) ----

    def test_scenario_record_for_role_public_strips_internal_fields(self) -> None:
        raw_scenario = {
            "scenario_id": "demo:speed_management",
            "scenario_rank": 1,
            "intervention_code": "speed_management",
            "title": "Reduce speeds",
            "target_context_label": "Tangenziale",
            "target_context_key": "top_corridor",
            "linked_segment_count": 5,
            "target_asset_count": 5,
            "target_asset_types": ["segment"],
            "expected_relative_reduction": 0.28,
            # Internal-classified fields that must be default-denied for public:
            "expected_crash_reduction": 10.96,
            "expected_crash_reduction_low": 9.4,
            "expected_crash_reduction_high": 12.5,
            "baseline_predicted_crash_total": 39.14,
            "counterfactual_predicted_crash_total": 28.18,
            "linked_segment_score_ids": ["demo:seg:1"],
            "affected_assets": [{"asset_id": "demo:seg:1"}],
            "assumptions": ["Posted speeds can be reduced."],
        }
        public_row = scenario_planner._scenario_record_for_role(raw_scenario, "public")
        # Public-classified fields flow through:
        self.assertEqual(public_row["scenario_id"], "demo:speed_management")
        self.assertEqual(public_row["intervention_code"], "speed_management")
        self.assertEqual(public_row["expected_relative_reduction"], 0.28)
        self.assertEqual(public_row["assumptions"], ["Posted speeds can be reduced."])
        # Internal-only fields are default-denied for public:
        for stripped in (
            "scenario_rank",
            "expected_crash_reduction",
            "expected_crash_reduction_low",
            "expected_crash_reduction_high",
            "baseline_predicted_crash_total",
            "counterfactual_predicted_crash_total",
            "linked_segment_score_ids",
            "affected_assets",
        ):
            self.assertNotIn(stripped, public_row)

    def test_scenario_record_for_role_analyst_keeps_internal_fields(self) -> None:
        raw_scenario = {
            "scenario_id": "demo:speed_management",
            "scenario_rank": 1,
            "intervention_code": "speed_management",
            "title": "Reduce speeds",
            "expected_crash_reduction": 10.96,
            "baseline_predicted_crash_total": 39.14,
            "linked_segment_score_ids": ["demo:seg:1"],
            "affected_assets": [{"asset_id": "demo:seg:1"}],
            "assumptions": ["Posted speeds can be reduced."],
        }
        row = scenario_planner._scenario_record_for_role(raw_scenario, "analyst")
        for kept in (
            "scenario_id",
            "scenario_rank",
            "expected_crash_reduction",
            "baseline_predicted_crash_total",
            "linked_segment_score_ids",
            "affected_assets",
            "assumptions",
        ):
            self.assertIn(kept, row)

    def test_scenario_record_for_role_strips_unregistered_fields(self) -> None:
        raw_scenario = {
            "scenario_id": "demo:speed_management",
            "scenario_rank": 1,
            "intervention_code": "speed_management",
            "title": "Reduce speeds",
            # Unregistered debug column - the matrix has never heard of it,
            # so it must be default-denied for every role.
            "_debug_internal_leak": "do not ship this",
        }
        for role in ("public", "analyst"):
            row = scenario_planner._scenario_record_for_role(raw_scenario, role)
            self.assertNotIn(
                "_debug_internal_leak", row,
                msg=f"Unregistered field leaked for role={role!r}",
            )

    def test_build_city_scenario_bundle_attaches_redaction_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            bundle = scenario_planner.build_city_scenario_bundle(
                settings, city_key="bari",
            )
            self.assertIn("redaction_policy", bundle)
            self.assertEqual(bundle["redaction_policy"]["record_kind"], "scenario")
            self.assertEqual(bundle["redaction_policy"]["role"], "analyst")
            # Every scenario row keeps the analyst-only internal fields:
            first = bundle["scenarios"][0]
            for kept in (
                "scenario_rank",
                "expected_crash_reduction",
                "baseline_predicted_crash_total",
                "counterfactual_predicted_crash_total",
            ):
                self.assertIn(kept, first)

    def test_build_city_scenario_bundle_public_role_redacts_internal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            bundle = scenario_planner.build_city_scenario_bundle(
                settings, city_key="bari", role="public",
            )
            self.assertEqual(bundle["redaction_policy"]["role"], "public")
            first = bundle["scenarios"][0]
            # Public-visible scalars flow through:
            self.assertEqual(first["scenario_id"], "demo:speed_management")
            self.assertEqual(first["intervention_code"], "speed_management")
            # Internal fields default-denied:
            for stripped in (
                "scenario_rank",
                "expected_crash_reduction",
                "expected_crash_reduction_low",
                "expected_crash_reduction_high",
                "baseline_predicted_crash_total",
                "counterfactual_predicted_crash_total",
            ):
                self.assertNotIn(stripped, first)

    def test_build_scenario_detail_attaches_redaction_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            detail = scenario_planner.build_scenario_detail(
                settings, city_key="bari", scenario_id="demo:speed_management",
            )
            self.assertIn("redaction_policy", detail)
            self.assertEqual(detail["redaction_policy"]["record_kind"], "scenario")
            self.assertEqual(detail["redaction_policy"]["role"], "analyst")
            # The detail surface keeps the detail-extra fields the summary drops:
            scenario_block = detail["scenario"]
            self.assertEqual(scenario_block["assumptions"], ["Posted speeds can be reduced."])
            self.assertEqual(
                scenario_block["affected_assets"][0]["asset_id"], "demo:seg:1",
            )
            self.assertEqual(scenario_block["linked_segment_score_ids"], ["demo:seg:1"])


class ScenarioPlannerEndpointTests(unittest.TestCase):
    def _build_client(self, settings: ApiSettings, *, roles: frozenset[str]) -> TestClient:
        app = create_app(ApiSettings(**{**settings.model_dump(), "auth_enabled": True}))
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="analyst-1",
            assigned_roles=frozenset(roles),
            roles=frozenset(roles),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=frozenset(),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        return TestClient(app)

    def test_catalog_endpoint_requires_analyst_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_PUBLIC}))
            response = client.get("/v1/scenarios/catalog")
            self.assertEqual(response.status_code, 403)

    def test_catalog_endpoint_returns_payload_for_analyst(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get("/v1/scenarios/catalog")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["api_version"], "v1")
            self.assertEqual(body["contract_version"], scenario_planner.SCENARIO_PLANNER_CATALOG_CONTRACT_VERSION)
            self.assertEqual(len(body["cities"]), 1)

    def test_intervention_library_endpoint_returns_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get("/v1/scenarios/intervention-library")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["intervention_count"], 2)

    def test_city_bundle_endpoint_supports_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get(
                "/v1/scenarios/cities/bari",
                params={"scenario_limit": 1, "portfolio_limit": 1},
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(len(body["scenarios"]), 1)
            self.assertEqual(len(body["portfolios"]), 1)

    def test_city_bundle_endpoint_unknown_city_returns_400(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get("/v1/scenarios/cities/unknown")
            self.assertEqual(response.status_code, 400)

    def test_scenario_detail_endpoint_returns_affected_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get(
                "/v1/scenarios/cities/bari/scenarios/demo:speed_management"
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["scenario"]["scenario_id"], "demo:speed_management")
            self.assertEqual(len(body["scenario"]["affected_assets"]), 1)

    def test_portfolio_endpoint_returns_rankings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get("/v1/scenarios/cities/bari/portfolios")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(len(body["portfolios"]), 1)
            self.assertEqual(body["portfolios"][0]["portfolio_rank"], 1)

    def test_draft_run_endpoints_persist_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            create_response = client.post(
                "/v1/scenarios/drafts",
                json={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "name": "Speed package",
                    "intervention_code": "speed_management",
                    "target_context_key": "top_corridor",
                },
            )
            self.assertEqual(create_response.status_code, 200)
            draft = create_response.json()["draft"]
            self.assertEqual(draft["validation"]["status"], "valid")

            run_response = client.post(
                f"/v1/scenarios/drafts/{draft['scenario_draft_id']}/run",
                json={"organization_id": "org-1"},
            )
            self.assertEqual(run_response.status_code, 200)
            run = run_response.json()["run"]
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["organization_id"], "org-1")

            drafts_response = client.get(
                "/v1/scenarios/drafts",
                params={"organization_id": "org-1", "city_key": "bari"},
            )
            runs_response = client.get(
                "/v1/scenarios/runs",
                params={"organization_id": "org-1", "city_key": "bari"},
            )
            self.assertEqual(drafts_response.status_code, 200)
            self.assertEqual(runs_response.status_code, 200)
            self.assertEqual(drafts_response.json()["draft_count"], 1)
            self.assertEqual(runs_response.json()["run_count"], 1)

    def test_draft_endpoint_rejects_unscoped_organization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_scenario_bundle(Path(temp_dir))
            scenario_planner.reset_scenario_planner_cache()
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.post(
                "/v1/scenarios/drafts",
                json={
                    "organization_id": "org-2",
                    "city_key": "bari",
                    "name": "Speed package",
                    "intervention_code": "speed_management",
                    "target_context_key": "top_corridor",
                },
            )
            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
