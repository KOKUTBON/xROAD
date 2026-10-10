"""Tests for the VRU + signal-phase operational product surface (#93)."""
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
    ROLE_TRAFFIC_ENGINEER,
    get_auth_context,
)
from apps.api.main import create_app  # noqa: E402
from apps.api.services import vru_signals  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _scaffold_artifacts(root: Path) -> ApiSettings:
    vru_path = root / vru_signals.DEFAULT_VRU_BUNDLE_RELATIVE_PATH
    coverage_path = root / vru_signals.DEFAULT_SIGNAL_PHASE_COVERAGE_RELATIVE_PATH
    targets_path = root / vru_signals.DEFAULT_SIGNAL_PHASE_TARGETS_RELATIVE_PATH
    operator_path = root / vru_signals.DEFAULT_SIGNAL_PHASE_OPERATOR_BOARD_RELATIVE_PATH

    _write_json(
        vru_path,
        {
            "city_key": "bari",
            "display_name": "Bari",
            "generated_at_utc": "2026-05-15T00:00:00+00:00",
            "layer_status": "proxy_backed",
            "planning_summary": {
                "top_pedestrian_segment": {
                    "segment_id": "seg-1",
                    "segment_label": "Corso Senatore",
                    "predicted_crash_count": 4.2,
                    "public_score_index": 99.5,
                },
                "top_cyclist_segment": {
                    "segment_id": "seg-2",
                    "segment_label": "Viale Tatarella",
                    "predicted_crash_count": 3.1,
                    "public_score_index": 95.0,
                },
                "top_crossing_candidate": {
                    "crossing_id": "x-1",
                    "crossing_name": "Via Capruzzi",
                    "predicted_crash_count": 1.6,
                    "pedestrian_crossing_priority_score": 77.0,
                    "control_state": "uncontrolled",
                },
            },
            "stats": {
                "segment_feature_count": 100,
                "crossing_feature_count": 25,
                "corridor_profile_count": 12,
            },
            "top_corridor_profiles": [
                {
                    "corridor_label": "Lungomare",
                    "crossing_count": 8,
                    "protected_crossing_gap_count": 4,
                    "micromobility_corridor_segment_count": 6,
                    "micromobility_gap_score": 70.1,
                    "predicted_crash_total": 5.3,
                },
                {
                    "corridor_label": "Via Capruzzi",
                    "crossing_count": 5,
                    "protected_crossing_gap_count": 2,
                    "micromobility_corridor_segment_count": 4,
                    "micromobility_gap_score": 65.0,
                    "predicted_crash_total": 4.7,
                },
            ],
        },
    )

    _write_json(
        coverage_path,
        {
            "generated_at_utc": "2026-05-15T00:00:00+00:00",
            "signal_phase_coverage_contract_version": "signal_phase_coverage_public_v1",
            "summary": {
                "movement_count": 100,
                "signalized_movement_count": 60,
                "movements_with_provider_data": 12,
                "movements_with_phase_timing": 1,
                "movements_with_phase_mapping": 1,
                "matched_signalized_crash_count": 200,
                "uncovered_signalized_hotspot_count": 50,
                "target_junction_count": 6,
            },
        },
    )

    _write_json(
        targets_path,
        {
            "generated_at_utc": "2026-05-15T00:00:00+00:00",
            "signal_phase_target_bundle_contract_version": "signal_phase_target_bundle_public_v1",
            "summary": {
                "target_count": 2,
                "packet_count": 2,
                "matched_signalized_crash_total": 200,
                "targets_with_provider_data": 1,
            },
            "targets": [
                {
                    "junction_id": "it-bari-signal-93",
                    "coverage_state": "partial_phase_coverage",
                    "dominant_day_type": "weekday",
                    "gap_priority_score": 6443,
                    "matched_signalized_crash_count": 120,
                    "crashes_without_phase_timing": 59,
                    "movements_with_phase_mapping": 1,
                    "movements_with_phase_timing": 1,
                    "movements_with_provider_data": 12,
                    "movements_without_phase_timing": 11,
                },
                {
                    "junction_id": "it-bari-signal-94",
                    "coverage_state": "uncovered",
                    "matched_signalized_crash_count": 80,
                    "movements_with_provider_data": 0,
                },
            ],
        },
    )

    _write_json(
        operator_path,
        {
            "generated_at_utc": "2026-05-15T00:00:00+00:00",
            "operator_ready_queue": [
                {
                    "action_category": "dispatch_request_now",
                    "action_summary": "Send the initial request.",
                    "due_date": "2026-05-20",
                    "due_now": "yes",
                    "execution_route": "dispatch_send",
                    "junction_id": "it-bari-signal-93",
                    "handoff_status": "ready_for_operator",
                    "handoff_target_kind": "dispatch_execution_log",
                    "handoff_reference_key": "request_id",
                    "handoff_reference_value": "bari_signal_phase_01",
                    "packet_available": "yes",
                    "dispatch_reference": "BARI-SPD-20260520-01",
                    "execution_summary": "Send the initial request packet.",
                    "handoff_instructions": "Fill the dispatch execution log row.",
                }
            ],
            "operator_hold_queue": [],
        },
    )
    return ApiSettings(root_dir=root)


class VruSignalsServiceTests(unittest.TestCase):
    def test_build_traffic_operations_capabilities_marks_bari_v1_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            payload = vru_signals.build_traffic_operations_capabilities(
                settings, city_key="bari",
            )

        self.assertEqual(
            payload["contract_version"],
            vru_signals.TRAFFIC_OPERATIONS_CAPABILITIES_CONTRACT_VERSION,
        )
        self.assertTrue(payload["production_scope"]["supported_for_v1"])
        self.assertTrue(payload["ui_policy"]["fetch_vru_summary"])
        self.assertTrue(payload["ui_policy"]["fetch_signal_phase_overview"])
        self.assertFalse(payload["ui_policy"]["allow_signal_write_actions"])
        statuses = {row["capability_id"]: row["status"] for row in payload["capabilities"]}
        self.assertEqual(statuses["vru_priority_intelligence"], "v1_supported")
        self.assertEqual(statuses["signal_phase_operator_board"], "preview")
        self.assertIn("live signal-phase dispatch send", payload["release_boundary"]["v1_0_excluded"])

    def test_build_traffic_operations_capabilities_marks_unsupported_city(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            payload = vru_signals.build_traffic_operations_capabilities(
                settings, city_key="lecce",
            )

        self.assertFalse(payload["production_scope"]["supported_for_v1"])
        self.assertFalse(payload["ui_policy"]["show_operations_board"])
        self.assertFalse(payload["ui_policy"]["fetch_vru_summary"])
        self.assertIn("Bari pilot only", payload["ui_policy"]["unsupported_message"])
        self.assertEqual(
            {row["status"] for row in payload["capabilities"]},
            {"unsupported_city"},
        )

    def test_build_traffic_operations_capabilities_honors_signal_preview_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            settings = ApiSettings(
                **{
                    **settings.model_dump(),
                    "traffic_operations_signal_preview_enabled": False,
                }
            )
            payload = vru_signals.build_traffic_operations_capabilities(
                settings, city_key="bari",
            )

        self.assertTrue(payload["ui_policy"]["fetch_vru_summary"])
        self.assertFalse(payload["ui_policy"]["fetch_signal_phase_overview"])
        self.assertEqual(payload["release_boundary"]["v1_0_preview"], [])
        statuses = {row["capability_id"]: row["status"] for row in payload["capabilities"]}
        self.assertEqual(statuses["signal_phase_coverage"], "v1_5_gated")

    def test_build_traffic_operations_capabilities_marks_missing_signal_artifacts_no_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _scaffold_artifacts(root)
            (
                root / vru_signals.DEFAULT_SIGNAL_PHASE_OPERATOR_BOARD_RELATIVE_PATH
            ).unlink()
            payload = vru_signals.build_traffic_operations_capabilities(
                settings, city_key="bari",
            )

        self.assertTrue(payload["ui_policy"]["show_operations_board"])
        self.assertTrue(payload["ui_policy"]["fetch_vru_summary"])
        self.assertFalse(payload["ui_policy"]["fetch_signal_phase_overview"])
        statuses = {row["capability_id"]: row["status"] for row in payload["capabilities"]}
        self.assertEqual(statuses["signal_phase_operator_board"], "no_data")

    def test_build_vru_summary_returns_planning_highlights_and_stats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            summary = vru_signals.build_vru_summary(settings, city_key="bari")
        self.assertEqual(summary["contract_version"], vru_signals.VRU_SUMMARY_CONTRACT_VERSION)
        self.assertEqual(summary["layer_status"], "proxy_backed")
        self.assertEqual(summary["stats"]["segment_feature_count"], 100)
        self.assertEqual(
            summary["planning_highlights"]["top_pedestrian_segment"]["segment_id"],
            "seg-1",
        )
        self.assertEqual(
            summary["planning_highlights"]["top_crossing_candidate"]["crossing_id"],
            "x-1",
        )

    def test_build_vru_top_corridors_respects_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            payload = vru_signals.build_vru_top_corridors(
                settings, city_key="bari", limit=1,
            )
        self.assertEqual(payload["corridor_count"], 1)
        self.assertEqual(payload["corridors"][0]["corridor_label"], "Lungomare")

    def test_build_vru_summary_unknown_city_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            with self.assertRaises(vru_signals.VruSignalsError):
                vru_signals.build_vru_summary(settings, city_key="rome")

    def test_build_signal_phase_coverage_returns_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            payload = vru_signals.build_signal_phase_coverage(settings, city_key="bari")
        self.assertEqual(payload["contract_version"], vru_signals.SIGNAL_PHASE_COVERAGE_CONTRACT_VERSION)
        self.assertEqual(payload["summary"]["movement_count"], 100)
        self.assertEqual(payload["summary"]["uncovered_signalized_hotspot_count"], 50)

    def test_build_signal_phase_targets_supports_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            payload = vru_signals.build_signal_phase_targets(
                settings, city_key="bari", limit=1,
            )
        self.assertEqual(payload["target_count"], 1)
        self.assertEqual(payload["targets"][0]["junction_id"], "it-bari-signal-93")

    def test_build_signal_phase_operator_board_separates_ready_and_holds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            payload = vru_signals.build_signal_phase_operator_board(
                settings, city_key="bari",
            )
        self.assertEqual(payload["totals"], {"ready_count": 1, "hold_count": 0})
        self.assertEqual(payload["ready_queue"][0]["junction_id"], "it-bari-signal-93")
        self.assertEqual(payload["ready_queue"][0]["action_category"], "dispatch_request_now")

    def test_build_signal_phase_overview_collapses_three_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            payload = vru_signals.build_signal_phase_overview(settings, city_key="bari")
        self.assertEqual(payload["target_count"], 2)
        self.assertEqual(payload["coverage"]["summary"]["target_junction_count"], 6)
        self.assertEqual(payload["operator_board"]["totals"], {"ready_count": 1, "hold_count": 0})
        self.assertEqual(len(payload["operator_board"]["ready_queue_head"]), 1)


class VruSignalsEndpointTests(unittest.TestCase):
    def _build_client(
        self,
        settings: ApiSettings,
        *,
        roles: frozenset[str],
        municipality_ids: frozenset[str] = frozenset({"bari"}),
    ) -> TestClient:
        app = create_app(ApiSettings(**{**settings.model_dump(), "auth_enabled": True}))
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="analyst-1",
            assigned_roles=frozenset(roles),
            roles=frozenset(roles),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-1"}),
            municipality_ids=municipality_ids,
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        return TestClient(app)

    def test_traffic_operations_capabilities_requires_traffic_engineer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get("/v1/traffic-operations/cities/bari/capabilities")
            self.assertEqual(response.status_code, 403)

    def test_traffic_operations_capabilities_returns_unsupported_city_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(
                settings,
                roles=frozenset({ROLE_TRAFFIC_ENGINEER}),
                municipality_ids=frozenset({"lecce"}),
            )
            response = client.get("/v1/traffic-operations/cities/lecce/capabilities")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertFalse(body["production_scope"]["supported_for_v1"])
            self.assertFalse(body["ui_policy"]["show_operations_board"])

    def test_traffic_operations_capabilities_enforces_municipality_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(
                settings,
                roles=frozenset({ROLE_TRAFFIC_ENGINEER}),
                municipality_ids=frozenset({"bari"}),
            )
            response = client.get("/v1/traffic-operations/cities/lecce/capabilities")
            self.assertEqual(response.status_code, 403)

    def test_vru_summary_endpoint_requires_analyst(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_PUBLIC}))
            response = client.get("/v1/vru/cities/bari/summary")
            self.assertEqual(response.status_code, 403)

    def test_vru_summary_endpoint_returns_payload_for_analyst(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get("/v1/vru/cities/bari/summary")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["api_version"], "v1")
            self.assertEqual(body["contract_version"], vru_signals.VRU_SUMMARY_CONTRACT_VERSION)

    def test_vru_summary_endpoint_unknown_city_returns_400(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(
                settings,
                roles=frozenset({ROLE_ANALYST}),
                municipality_ids=frozenset({"rome"}),
            )
            response = client.get("/v1/vru/cities/rome/summary")
            self.assertEqual(response.status_code, 400)

    def test_vru_top_corridors_endpoint_supports_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get(
                "/v1/vru/cities/bari/top-corridors", params={"limit": 1},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["corridor_count"], 1)

    def test_signal_phase_coverage_endpoint_returns_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_TRAFFIC_ENGINEER}))
            response = client.get("/v1/signal-phase/cities/bari/coverage")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["summary"]["target_junction_count"], 6)

    def test_signal_phase_coverage_endpoint_rejects_analyst_only_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get("/v1/signal-phase/cities/bari/coverage")
            self.assertEqual(response.status_code, 403)

    def test_signal_phase_targets_endpoint_supports_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_TRAFFIC_ENGINEER}))
            response = client.get(
                "/v1/signal-phase/cities/bari/targets", params={"limit": 1},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["target_count"], 1)

    def test_signal_phase_operator_board_endpoint_returns_queues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_TRAFFIC_ENGINEER}))
            response = client.get("/v1/signal-phase/cities/bari/operator-board")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["totals"]["ready_count"], 1)
            self.assertEqual(body["totals"]["hold_count"], 0)

    def test_signal_phase_overview_endpoint_collapses_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _scaffold_artifacts(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_TRAFFIC_ENGINEER}))
            response = client.get("/v1/signal-phase/cities/bari/overview")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["target_count"], 2)
            self.assertEqual(body["operator_board"]["totals"]["ready_count"], 1)


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
