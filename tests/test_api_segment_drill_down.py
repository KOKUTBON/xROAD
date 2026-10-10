"""Tests for the per-segment drill-down surface (Issue 13)."""
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
from apps.api.services import segment_drill_down  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


SEGMENT_ID = "demo:2021:drive:abc:def:0"
OTHER_SEGMENT_ID = "demo:2021:drive:xxx:yyy:0"
TILE_SCORE_ID = "demo:2021:20:16:500m"


def _write_dashboard_summary(root: Path) -> ApiSettings:
    summary_path = root / "data" / "dashboard" / "dashboard_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "published_runs": [
            {
                "city_key": "demo",
                "display_name": "Demo City",
                "prediction_run_label": "demo_frequency",
                "occurred_years": [2020, 2021],
            }
        ],
        "intervention_shortlists": [
            {
                "city_key": "demo",
                "display_name": "Demo City",
                "hotspot_tiles": [
                    {
                        "tile_score_id": TILE_SCORE_ID,
                        "tile_public_score_band": "very_high",
                        "tile_max_public_score_index": 99.5,
                        "tile_segment_count": 12,
                        "tile_high_band_segment_count": 4,
                        "tile_very_high_band_segment_count": 2,
                        "intersection_segment_count": 3,
                        "focus_segment_score_ids": [SEGMENT_ID, OTHER_SEGMENT_ID],
                        "top_segments": [
                            {
                                "segment_score_id": SEGMENT_ID,
                                "segment_id": "drive:abc:def:0",
                                "name": "Via Demo",
                                "highway": "primary",
                                "public_score_band": "very_high",
                                "public_score_index": 98.0,
                                "predicted_crash_count": 4.2,
                                "observed_crash_count": 6.0,
                            },
                            {
                                "segment_score_id": OTHER_SEGMENT_ID,
                                "segment_id": "drive:xxx:yyy:0",
                                "name": "Via Other",
                                "highway": "secondary",
                                "public_score_band": "high",
                                "public_score_index": 72.0,
                                "predicted_crash_count": 2.1,
                                "observed_crash_count": 3.0,
                            },
                        ],
                    }
                ],
                "top_corridors": [
                    {
                        "corridor_label": "Demo Corridor",
                        "segment_count": 6,
                        "tile_count": 2,
                        "predicted_crash_total": 10.5,
                        "observed_crash_total": 14.0,
                        "segment_score_ids": [SEGMENT_ID],
                        "top_segments": [
                            {
                                "segment_score_id": SEGMENT_ID,
                                "segment_id": "drive:abc:def:0",
                                "name": "Via Demo",
                                "public_score_band": "very_high",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    return ApiSettings(root_dir=root)


class SegmentDrillDownServiceTests(unittest.TestCase):
    def test_public_drill_down_redacts_observed_and_predicted_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            payload = segment_drill_down.build_public_segment_drill_down(
                settings, city_key="demo", segment_score_id=SEGMENT_ID,
            )
        self.assertEqual(
            payload["contract_version"],
            segment_drill_down.SEGMENT_DRILL_DOWN_PUBLIC_CONTRACT_VERSION,
        )
        segment = payload["segment"]
        self.assertEqual(segment["segment_score_id"], SEGMENT_ID)
        self.assertEqual(segment["public_score_band"], "very_high")
        # Issue 01 redaction: row-level crash counts must NOT appear in
        # the public drill-down payload.
        self.assertNotIn("predicted_crash_count", segment)
        self.assertNotIn("observed_crash_count", segment)
        self.assertNotIn("segment_id", segment)
        # The containing tile is published, but only with banded fields
        # and counts, no row-level focus list.
        self.assertEqual(payload["containing_tiles"][0]["tile_score_id"], TILE_SCORE_ID)
        self.assertNotIn("focus_segment_score_ids", payload["containing_tiles"][0])
        self.assertEqual(payload["redaction_policy_id"], "public_segment_score_map")

    def test_analyst_drill_down_includes_counts_and_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            payload = segment_drill_down.build_analyst_segment_drill_down(
                settings, city_key="demo", segment_score_id=SEGMENT_ID,
            )
        self.assertEqual(
            payload["contract_version"],
            segment_drill_down.SEGMENT_DRILL_DOWN_ANALYST_CONTRACT_VERSION,
        )
        segment = payload["segment"]
        self.assertEqual(segment["predicted_crash_count"], 4.2)
        self.assertEqual(segment["observed_crash_count"], 6.0)
        self.assertEqual(segment["segment_id"], "drive:abc:def:0")
        tile = payload["containing_tiles"][0]
        self.assertIn(SEGMENT_ID, tile["focus_segment_score_ids"])
        corridor = payload["containing_corridors"][0]
        self.assertEqual(corridor["predicted_crash_total"], 10.5)
        self.assertIn(SEGMENT_ID, corridor["segment_score_ids"])

    def test_drill_down_raises_for_unknown_segment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            with self.assertRaises(segment_drill_down.SegmentDrillDownError):
                segment_drill_down.build_public_segment_drill_down(
                    settings, city_key="demo", segment_score_id="not:a:real:segment",
                )

    def test_drill_down_raises_for_unknown_city(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            with self.assertRaises(segment_drill_down.SegmentDrillDownError):
                segment_drill_down.build_analyst_segment_drill_down(
                    settings, city_key="not-a-city", segment_score_id=SEGMENT_ID,
                )

    def test_drill_down_resolves_segment_from_focus_id_only(self) -> None:
        # Even when the segment is only referenced via `focus_segment_score_ids`
        # (and not via a `top_segments` row), the service should still
        # return the containing tile so the client can render context.
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            payload = segment_drill_down.build_public_segment_drill_down(
                settings, city_key="demo", segment_score_id=OTHER_SEGMENT_ID,
            )
        self.assertEqual(len(payload["containing_tiles"]), 1)


class SegmentDrillDownEndpointTests(unittest.TestCase):
    def _build_client(self, settings: ApiSettings, *, roles: frozenset[str]) -> TestClient:
        app = create_app(ApiSettings(**{**settings.model_dump(), "auth_enabled": True}))
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="user-1",
            assigned_roles=frozenset(roles),
            roles=frozenset(roles),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset(),
            municipality_ids=frozenset({"demo"}) if ROLE_ANALYST in roles else frozenset(),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        return TestClient(app)

    def test_public_drill_down_endpoint_is_public(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            # Even an explicitly anonymous (public-only) client gets the
            # payload back; the endpoint is read-only public.
            client = self._build_client(settings, roles=frozenset({ROLE_PUBLIC}))
            response = client.get(
                f"/v1/public/cities/demo/segments/{SEGMENT_ID}",
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["api_version"], "v1")
        self.assertEqual(
            body["contract_version"],
            segment_drill_down.SEGMENT_DRILL_DOWN_PUBLIC_CONTRACT_VERSION,
        )

    def test_public_drill_down_endpoint_unknown_segment_returns_400(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_PUBLIC}))
            response = client.get("/v1/public/cities/demo/segments/not:a:real:segment")
        self.assertEqual(response.status_code, 400)

    def test_analyst_drill_down_endpoint_requires_analyst(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_PUBLIC}))
            response = client.get(
                f"/v1/analyst/cities/demo/segments/{SEGMENT_ID}",
            )
        self.assertEqual(response.status_code, 403)

    def test_analyst_drill_down_endpoint_returns_payload_for_analyst(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            client = self._build_client(settings, roles=frozenset({ROLE_ANALYST}))
            response = client.get(
                f"/v1/analyst/cities/demo/segments/{SEGMENT_ID}",
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["contract_version"],
            segment_drill_down.SEGMENT_DRILL_DOWN_ANALYST_CONTRACT_VERSION,
        )
        # Analyst payload exposes the row-level crash counts.
        self.assertEqual(body["segment"]["predicted_crash_count"], 4.2)
        self.assertEqual(body["segment"]["observed_crash_count"], 6.0)


class MatrixDrivenRedactionInvariantTests(unittest.TestCase):
    """Cross-policy invariants between data_governance and segment_drill_down.

    These tests prove that the drill-down payload is gated by the
    `segment_score` record-kind matrix from Issue 01 rather than by an
    independent hard-coded field list. Adding a new segment-score field
    in `data_governance.py` will automatically be reflected here without
    code changes.
    """

    def test_public_payload_never_leaks_non_public_segment_score_field(self) -> None:
        from road_risk_modeling.data_governance import (
            SEGMENT_SCORE_FIELD_CLASSIFICATIONS,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            payload = segment_drill_down.build_public_segment_drill_down(
                settings, city_key="demo", segment_score_id=SEGMENT_ID,
            )
        segment_keys = set(payload["segment"].keys())
        for entry in SEGMENT_SCORE_FIELD_CLASSIFICATIONS:
            if "public" not in entry.role_visibility and entry.field_name in segment_keys:
                self.fail(
                    f"Public drill-down leaks `{entry.field_name}` "
                    f"(classification={entry.classification}, "
                    f"role_visibility={entry.role_visibility})"
                )

    def test_public_payload_includes_every_public_segment_score_field(self) -> None:
        from road_risk_modeling.data_governance import (
            publishable_fields_for_role,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            payload = segment_drill_down.build_public_segment_drill_down(
                settings, city_key="demo", segment_score_id=SEGMENT_ID,
            )
        public_fields = set(publishable_fields_for_role("segment_score", "public"))
        # Every public field must be present in the row (value may be
        # None if the underlying summary did not carry it).
        missing = public_fields - set(payload["segment"].keys())
        self.assertFalse(
            missing,
            f"Public drill-down is missing public-matrix fields: {sorted(missing)}",
        )

    def test_analyst_payload_is_superset_of_public_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            public = segment_drill_down.build_public_segment_drill_down(
                settings, city_key="demo", segment_score_id=SEGMENT_ID,
            )
            analyst = segment_drill_down.build_analyst_segment_drill_down(
                settings, city_key="demo", segment_score_id=SEGMENT_ID,
            )
        public_keys = set(public["segment"].keys())
        analyst_keys = set(analyst["segment"].keys())
        self.assertTrue(
            public_keys.issubset(analyst_keys),
            f"Analyst payload is missing public keys: {sorted(public_keys - analyst_keys)}",
        )

    def test_analyst_payload_carries_internal_and_restricted_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = _write_dashboard_summary(Path(temp_dir))
            payload = segment_drill_down.build_analyst_segment_drill_down(
                settings, city_key="demo", segment_score_id=SEGMENT_ID,
            )
        # `segment_id` is internal; `observed_crash_count` is restricted.
        # Both belong on the analyst payload.
        self.assertIn("segment_id", payload["segment"])
        self.assertIn("observed_crash_count", payload["segment"])
        self.assertIn("predicted_crash_count", payload["segment"])


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    unittest.main()
