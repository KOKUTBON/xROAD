from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.export_openapi_contract import (  # noqa: E402
    OPENAPI_CONTRACT_VERSION,
    ROUTE_CONTRACT_VERSION,
    export_contracts,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_dir = REPO_ROOT / "docs" / "api"
        self.openapi_path = self.contract_dir / "openapi-v1.json"
        self.route_contract_path = self.contract_dir / "v1-route-contract.json"

    def test_checked_in_contracts_match_generated_fastapi_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            generated_openapi_path, generated_route_path = export_contracts(Path(temp_dir))

            self.assertEqual(_read_json(generated_openapi_path), _read_json(self.openapi_path))
            self.assertEqual(_read_json(generated_route_path), _read_json(self.route_contract_path))

    def test_route_contract_freezes_core_v1_surface_and_policy_metadata(self) -> None:
        openapi_payload = _read_json(self.openapi_path)
        self.assertEqual(openapi_payload["info"]["x-contract-version"], OPENAPI_CONTRACT_VERSION)

        route_contract = _read_json(self.route_contract_path)
        self.assertEqual(route_contract["contract_version"], ROUTE_CONTRACT_VERSION)
        self.assertEqual(route_contract["route_count"], 137)
        self.assertEqual(route_contract["operation_count"], 140)

        routes = {route["path"]: route for route in route_contract["routes"]}
        expected_categories = {
            "admin",
            "analyst",
            "auth",
            "automation",
            "core",
            "ingestion",
            "intervention",
            "observability",
            "public",
            "published_resource",
            "recommendation",
            "reporting",
            "scenario",
            "siting",
            "traffic_operations",
        }
        self.assertTrue(expected_categories.issubset({route["category"] for route in routes.values()}))

        self.assertEqual(routes["/v1/public/health"]["auth"], "none")
        self.assertEqual(routes["/v1/public/health"]["roles"], ["public"])
        self.assertEqual(routes["/v1/public/cities/{city_key}/risk-tiles"]["category"], "public")
        self.assertEqual(routes["/v1/public/cities/{city_key}/risk-tiles"]["publication_tier"], "public aggregated only")
        self.assertEqual(routes["/v1/ingestion-jobs/uploads"]["roles"], ["data_operator", "admin", "super_admin"])
        self.assertEqual(routes["/v1/observability/metrics"]["roles"], ["admin", "super_admin"])
        self.assertEqual(
            routes["/v1/recommendations/{recommendation_id}/review"]["roles"],
            ["traffic_engineer", "admin", "super_admin"],
        )
        self.assertEqual(
            routes["/v1/recommendations/action-plan/export"]["publication_tier"],
            "internal; exports contain approved records only",
        )
        self.assertEqual(
            routes["/v1/siting-analyses"]["roles"],
            ["analyst", "traffic_engineer", "admin", "super_admin"],
        )
        self.assertEqual(
            routes["/v1/published-resource/query"]["publication_tier"],
            "public/internal/restricted according to source policy",
        )

    def test_docs_examples_and_ci_contract_gate_are_present(self) -> None:
        contract_doc = (self.contract_dir / "v1-api-contract.md").read_text(encoding="utf-8")
        integration_doc = (self.contract_dir / "integration-guide.md").read_text(encoding="utf-8")
        readme_doc = (self.contract_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("Product-Plan Reconciliation", contract_doc)
        self.assertIn("Publication Tiers", contract_doc)
        self.assertIn("Backward Compatibility Gate", contract_doc)
        self.assertIn("Upload And Ingestion Integration", integration_doc)
        self.assertIn("Compatibility Policy", readme_doc)

        for example_path in sorted((self.contract_dir / "examples").glob("*.json")):
            with self.subTest(example=example_path.name):
                json.loads(example_path.read_text(encoding="utf-8"))

        workflow = (REPO_ROOT / ".github" / "workflows" / "python-ci.yml").read_text(encoding="utf-8")
        self.assertIn("tools/export_openapi_contract.py", workflow)
        self.assertIn("git diff --exit-code docs/api/openapi-v1.json docs/api/v1-route-contract.json", workflow)
        self.assertRegex(workflow, r"actions/upload-artifact@(?:[0-9a-f]{40}|v[0-9]+)")


if __name__ == "__main__":
    unittest.main()
