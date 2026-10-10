from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from apps.api.auth import AuthContext, get_auth_context
from apps.api.main import create_app
from apps.api.settings import ApiSettings


def _fixture_bundle(root: Path) -> None:
    output = root / "data" / "planning" / "siting" / "bari"
    output.mkdir(parents=True)
    result = {
        "candidate_id": "bari-park-01",
        "rank": 1,
        "asset_type": "park",
        "school_grade": None,
        "suitability_score": 0.82,
        "served_population_estimate": 4200,
        "access_route_risk_percentile": 22.0,
        "geometry": {"type": "Point", "coordinates": [16.87, 41.12]},
        "compliance": {
            "overall_status": "pass",
            "mandatory_failure_count": 0,
            "mandatory_insufficient_data_count": 0,
            "results": [
                {
                    "rule_id": "IT-DM1444-GREEN-04",
                    "status": "pass",
                    "severity": "mandatory",
                    "citation": "DM 2 April 1968 n.1444, art.3(c)",
                    "source_url": "https://example.test/dm1444",
                    "description": "Minimum public green allocation.",
                }
            ],
        },
        "criteria_scores": {"population_served": 0.8},
        "companion_interventions": [],
    }
    (output / "top_park_sites.json").write_text(
        json.dumps({"top_candidates": [result]}), encoding="utf-8"
    )


def _auth() -> AuthContext:
    return AuthContext(
        subject="planner-1",
        assigned_roles=frozenset({"analyst"}),
        roles=frozenset({"analyst", "municipality_viewer", "public"}),
        scopes=frozenset(),
        claims={},
        organization_ids=frozenset({"org-1"}),
        municipality_ids=frozenset({"bari"}),
        is_authenticated=True,
        auth_enabled=True,
        provider="test",
    )


class SitingAdvisorApiTests(unittest.TestCase):
    def test_end_to_end_analysis_poll_results_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _fixture_bundle(root)
            app = create_app(ApiSettings(root_dir=root, auth_enabled=True))
            app.dependency_overrides[get_auth_context] = _auth
            client = TestClient(app)

            created = client.post(
                "/v1/siting-analyses",
                json={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "facility_type": "park",
                    "target_catchment": "district-1",
                    "constraints": {
                        "minimum_served_population": 1000,
                        "maximum_access_route_risk_percentile": 50,
                    },
                },
            )
            self.assertEqual(created.status_code, 200)
            analysis_id = created.json()["analysis_id"]
            self.assertEqual(created.json()["status"], "completed")

            status = client.get(
                f"/v1/siting-analyses/{analysis_id}",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["result_count"], 1)

            results = client.get(
                f"/v1/siting-analyses/{analysis_id}/results",
                params={"organization_id": "org-1"},
            )
            self.assertEqual(results.status_code, 200)
            payload = results.json()
            self.assertEqual(payload["results"][0]["compliance"]["overall_status"], "pass")
            self.assertTrue(
                payload["results"][0]["compliance"]["results"][0]["citation"]
            )
            self.assertEqual(payload["provision_gap"]["availability"], "unavailable")
            self.assertTrue(payload["data_freshness"]["caveats"])

            export = client.get(
                f"/v1/siting-analyses/{analysis_id}/export",
                params={"organization_id": "org-1", "output_format": "csv"},
            )
            self.assertEqual(export.status_code, 200)
            self.assertIn("bari-park-01", export.text)

    def test_analysis_is_organization_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _fixture_bundle(root)
            app = create_app(ApiSettings(root_dir=root, auth_enabled=True))
            app.dependency_overrides[get_auth_context] = _auth
            client = TestClient(app)
            created = client.post(
                "/v1/siting-analyses",
                json={
                    "organization_id": "org-1",
                    "city_key": "bari",
                    "facility_type": "park",
                },
            )
            response = client.get(
                f"/v1/siting-analyses/{created.json()['analysis_id']}",
                params={"organization_id": "org-other"},
            )
            self.assertEqual(response.status_code, 403)

    def test_openapi_exposes_siting_contract(self) -> None:
        paths = TestClient(create_app(ApiSettings(root_dir=Path(".")))).get(
            "/openapi.json"
        ).json()["paths"]
        self.assertIn("/v1/siting-analyses", paths)
        self.assertIn("/v1/siting-analyses/{analysis_id}", paths)
        self.assertIn("/v1/siting-analyses/{analysis_id}/results", paths)
        self.assertIn("/v1/siting-analyses/{analysis_id}/export", paths)


if __name__ == "__main__":
    unittest.main()
