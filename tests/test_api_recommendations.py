from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from apps.api.auth import AuthContext, get_auth_context
from apps.api.main import create_app
from apps.api.services import recommendations
from apps.api.settings import ApiSettings


def _write_bundle(root: Path) -> None:
    output = root / "data" / "planning" / "recommendations" / "bari"
    output.mkdir(parents=True)
    properties = {
        "segment_score_id": "run:2022:seg-1",
        "segment_label": "Via Demo",
        "countermeasure_id": "CM-SPD-001",
        "countermeasure_name": "Average-speed enforcement",
        "object_type": "segment",
        "benefit_cost_ratio": 3.2,
        "expected_annual_crashes_prevented": 1.4,
        "effect_ratio_low": 0.5,
        "effect_ratio_central": 0.62,
        "effect_ratio_high": 0.77,
        "cost_band": "medium",
        "evidence_source": "CMF Clearinghouse",
        "evidence_ref": "CMF-1",
        "top_risk_factors": [{"label": "Posted speed", "importance": 0.5}],
    }
    (output / "network_recommendations.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[16.86, 41.11], [16.87, 41.12]],
                        },
                        "properties": properties,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (output / "network_recommendations.manifest.json").write_text(
        json.dumps(
            {
                "outputs": {"recommendations_geojson_sha256": "lineage-123"},
                "recommendation_model_version": "recommendation_model_v1",
            }
        ),
        encoding="utf-8",
    )


def _auth() -> AuthContext:
    return AuthContext(
        subject="engineer-1",
        assigned_roles=frozenset({"traffic_engineer"}),
        roles=frozenset(
            {"traffic_engineer", "analyst", "municipality_viewer", "public"}
        ),
        scopes=frozenset(),
        claims={},
        organization_ids=frozenset({"org-1"}),
        municipality_ids=frozenset({"bari"}),
        is_authenticated=True,
        auth_enabled=True,
        provider="test",
    )


class RecommendationsApiTests(unittest.TestCase):
    def test_model_output_to_reviewed_api_and_approved_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_bundle(root)
            settings = ApiSettings(root_dir=root, auth_enabled=True)
            app = create_app(settings)
            app.dependency_overrides[get_auth_context] = _auth
            client = TestClient(app)

            listed = client.get(
                "/v1/recommendations",
                params={"organization_id": "org-1", "city_key": "bari", "minimum_bcr": 2},
            )
            self.assertEqual(listed.status_code, 200)
            row = listed.json()["recommendations"][0]
            self.assertEqual(row["review_state"], "proposed")
            self.assertEqual(row["geometry"]["type"], "LineString")
            recommendation_id = row["recommendation_id"]

            reviewed = client.post(
                f"/v1/recommendations/{recommendation_id}/review",
                json={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "to_state": "engineer_reviewed",
                    "note": "Site and evidence checked.",
                },
            )
            self.assertEqual(reviewed.status_code, 200)
            approved = client.post(
                f"/v1/recommendations/{recommendation_id}/review",
                json={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "to_state": "approved",
                },
            )
            self.assertEqual(approved.status_code, 200)

            export = client.get(
                "/v1/recommendations/action-plan/export",
                params={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "output_format": "csv",
                },
            )
            self.assertEqual(export.status_code, 200)
            self.assertIn("Average-speed enforcement", export.text)
            self.assertIn("lineage-123", export.text)

            detail = client.get(
                f"/v1/recommendations/{recommendation_id}",
                params={"organization_id": "org-1", "city_key": "bari"},
            )
            self.assertEqual(
                [event["to_state"] for event in detail.json()["audit_events"]],
                ["proposed", "engineer_reviewed", "approved"],
            )

    def test_openapi_contract_publishes_recommendation_routes(self) -> None:
        client = TestClient(create_app(ApiSettings(root_dir=Path("."))))
        paths = client.get("/openapi.json").json()["paths"]
        self.assertIn("/v1/recommendations", paths)
        self.assertIn("/v1/recommendations/{recommendation_id}", paths)
        self.assertIn("/v1/recommendations/{recommendation_id}/review", paths)
        self.assertIn("/v1/recommendations/action-plan/export", paths)

    def test_service_filter_and_rejection_feedback_are_organization_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_bundle(root)
            settings = ApiSettings(root_dir=root)
            hidden = recommendations.list_recommendations(
                settings,
                organization_id="org-a",
                city_key="bari",
                minimum_bcr=10,
            )
            self.assertEqual(hidden["recommendation_count"], 0)
            visible = recommendations.list_recommendations(
                settings, organization_id="org-b", city_key="bari"
            )
            self.assertEqual(visible["recommendations"][0]["review_state"], "proposed")


if __name__ == "__main__":
    unittest.main()
