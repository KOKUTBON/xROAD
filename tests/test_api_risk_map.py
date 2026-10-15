from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.auth import AuthContext, ROLE_ANALYST, get_auth_context  # noqa: E402
from apps.api.main import create_app  # noqa: E402
from apps.api.services.postgis_domain import build_domain_sync_plan  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class ApiRiskMapTests(unittest.TestCase):
    def _build_sample_root(self, root: Path) -> ApiSettings:
        public_segments_path = root / "artifacts" / "demo_bari" / "segment_scores_public.geojson"
        analyst_segments_path = root / "artifacts" / "demo_bari" / "segment_scores_analyst.csv"
        segment_manifest_path = root / "artifacts" / "demo_bari" / "segment_scores.manifest.json"
        public_tiles_path = root / "artifacts" / "demo_bari_tiles" / "score_tiles_public.geojson"
        tile_manifest_path = root / "artifacts" / "demo_bari_tiles" / "score_tiles.manifest.json"
        junction_path = root / "layers" / "bari_signal_junctions.geojson"
        crossing_path = root / "layers" / "bari_crossings.geojson"

        _write_json(
            public_segments_path,
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[16.8, 41.1], [16.81, 41.11]],
                        },
                        "properties": {
                            "segment_score_id": "demo_bari:2021:s1",
                            "segment_id": "s1",
                            "occurred_year": 2021,
                            "public_score_index": 98.0,
                            "public_score_band": "very_high",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[16.82, 41.12], [16.83, 41.13]],
                        },
                        "properties": {
                            "segment_score_id": "demo_bari:2021:s2",
                            "segment_id": "s2",
                            "occurred_year": 2021,
                            "public_score_index": 74.0,
                            "public_score_band": "high",
                        },
                    },
                ],
            },
        )
        _write_csv(
            analyst_segments_path,
            [
                {
                    "segment_score_id": "demo_bari:2021:s1",
                    "segment_id": "s1",
                    "occurred_year": "2021",
                    "score_rank_desc": "1",
                    "public_score_index": "98.0",
                    "public_score_band": "very_high",
                    "predicted_crash_count": "5.1",
                    "observed_crash_count": "6.0",
                    "highway": "['trunk']",
                    "name": "Via Demo 1",
                },
                {
                    "segment_score_id": "demo_bari:2021:s2",
                    "segment_id": "s2",
                    "occurred_year": "2021",
                    "score_rank_desc": "2",
                    "public_score_index": "74.0",
                    "public_score_band": "high",
                    "predicted_crash_count": "3.3",
                    "observed_crash_count": "2.0",
                    "highway": "['secondary']",
                    "name": "Via Demo 2",
                },
            ],
        )
        _write_json(
            segment_manifest_path,
            {
                "contract": {
                    "resource_name": "segment_scores",
                    "public_contract_version": "segment_scores_public_v1",
                    "analyst_contract_version": "segment_scores_analyst_v1",
                },
                "outputs": {
                    "manifest_path": "artifacts/demo_bari/segment_scores.manifest.json",
                    "public_geojson_path": "artifacts/demo_bari/segment_scores_public.geojson",
                    "analyst_csv_path": "artifacts/demo_bari/segment_scores_analyst.csv",
                },
                "stats": {
                    "holdout_years": [2021],
                    "prediction_run_label": "demo_bari",
                    "prediction_task": "segment_frequency_baseline",
                    "segment_score_rows": 2,
                },
            },
        )
        _write_json(
            public_tiles_path,
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[16.8, 41.1], [16.81, 41.1], [16.81, 41.11], [16.8, 41.11], [16.8, 41.1]]
                            ],
                        },
                        "properties": {
                            "tile_score_id": "demo_bari:2021:t1",
                            "occurred_year": 2021,
                            "tile_size_m": 500.0,
                            "tile_max_public_score_index": 96.0,
                            "tile_public_score_band": "very_high",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[16.82, 41.12], [16.83, 41.12], [16.83, 41.13], [16.82, 41.13], [16.82, 41.12]]
                            ],
                        },
                        "properties": {
                            "tile_score_id": "demo_bari:2021:t2",
                            "occurred_year": 2021,
                            "tile_size_m": 500.0,
                            "tile_max_public_score_index": 72.0,
                            "tile_public_score_band": "high",
                        },
                    },
                ],
            },
        )
        _write_json(
            tile_manifest_path,
            {
                "contract": {
                    "resource_name": "segment_score_tiles",
                    "public_contract_version": "segment_score_tiles_public_v1",
                    "analyst_contract_version": None,
                },
                "outputs": {
                    "manifest_path": "artifacts/demo_bari_tiles/score_tiles.manifest.json",
                    "public_geojson_path": "artifacts/demo_bari_tiles/score_tiles_public.geojson",
                },
                "stats": {
                    "holdout_years": [2021],
                    "prediction_run_label": "demo_bari",
                    "prediction_task": "segment_frequency_baseline",
                    "tile_rows": 2,
                    "tile_size_m": 500.0,
                },
            },
        )
        _write_json(
            junction_path,
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [16.805, 41.105]},
                        "properties": {
                            "node_object_id": "signal-1",
                            "junction_id": "signal-1",
                            "occurred_year": 2025,
                            "crash_count": 9,
                            "injury_crash_count": 4,
                            "node_role": "signalized_junction",
                            "name": "Junction A",
                            # Default-deny invariant: this field is not in
                            # the node_year_metric matrix; the
                            # data_governance filter applied by
                            # _apply_node_year_metric_filter must strip
                            # it from the analyst payload.
                            "_debug_internal_leak": "should-be-stripped",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [16.825, 41.125]},
                        "properties": {
                            "node_object_id": "signal-2",
                            "junction_id": "signal-2",
                            "occurred_year": 2024,
                            "crash_count": 12,
                            "injury_crash_count": 6,
                            "node_role": "signalized_junction",
                            "name": "Junction B",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [16.826, 41.126]},
                        "properties": {
                            "node_object_id": "signal-3",
                            "junction_id": "signal-3",
                            "occurred_year": 2025,
                            "crash_count": 3,
                            "injury_crash_count": 1,
                            "node_role": "signalized_junction",
                            "name": "Junction C",
                        },
                    },
                ],
            },
        )
        _write_json(
            crossing_path,
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [16.804, 41.104]},
                        "properties": {
                            "node_object_id": "crossing-1",
                            "crossing_name": "Crossing A",
                            "pedestrian_crossing_priority_score": 88.0,
                            "public_score_index": 95.0,
                            "crossing_protection_state": "uncontrolled",
                            # Default-deny invariant: this field is not
                            # in the crossing_priority matrix; the
                            # data_governance filter applied by
                            # _apply_crossing_priority_filter must strip
                            # it from the analyst payload.
                            "_debug_crossing_internal_leak": "should-be-stripped",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [16.824, 41.124]},
                        "properties": {
                            "node_object_id": "crossing-2",
                            "crossing_name": "Crossing B",
                            "pedestrian_crossing_priority_score": 64.0,
                            "public_score_index": 71.0,
                            "crossing_protection_state": "signalized",
                        },
                    },
                ],
            },
        )
        _write_json(
            root / "data" / "dashboard" / "dashboard_summary.json",
            {
                "dashboard_summary_version": "dashboard_summary_v1",
                "generated_at_utc": "2026-05-14T10:00:00+00:00",
                "published_runs": [
                    {
                        "city_key": "bari",
                        "display_name": "Bari",
                        "occurred_years": [2021],
                        "prediction_run_label": "demo_bari",
                        "prediction_task": "segment_frequency_baseline",
                        "segment_scores": {
                            "manifest_path": "artifacts/demo_bari/segment_scores.manifest.json",
                            "public_segments_path": "artifacts/demo_bari/segment_scores_public.geojson",
                            "analyst_segments_path": "artifacts/demo_bari/segment_scores_analyst.csv",
                            "segment_score_rows": 2,
                            "predicted_crash_total": 8.4,
                            "observed_crash_total": 8.0,
                            "top_5pct_observed_crash_share": 0.5,
                        },
                        "score_tiles": {
                            "manifest_path": "artifacts/demo_bari_tiles/score_tiles.manifest.json",
                            "public_tiles_path": "artifacts/demo_bari_tiles/score_tiles_public.geojson",
                            "tile_rows": 2,
                            "tile_size_m": 500.0,
                            "tiles_high_or_very_high": 2,
                            "tiles_very_high": 1,
                        },
                    }
                ],
                "intervention_shortlists": [
                    {
                        "city_key": "bari",
                        "display_name": "Bari",
                        "top_corridors": [
                            {
                                "corridor_label": "Tangenziale Demo",
                                "predicted_crash_total": 10.2,
                                "segment_count": 3,
                                "best_rank": 1,
                            }
                        ],
                        "hotspot_tiles": [
                            {
                                "tile_score_id": "demo_bari:2021:t1",
                                "tile_public_score_band": "very_high",
                                "tile_max_public_score_index": 96.0,
                            }
                        ],
                    }
                ],
                "stats": {
                    "published_run_count": 1,
                },
            },
        )
        return ApiSettings(
            root_dir=root,
            dashboard_summary_path=Path("data/dashboard/dashboard_summary.json"),
            bari_signal_junction_metrics_path=Path("layers/bari_signal_junctions.geojson"),
            bari_crossing_priority_path=Path("layers/bari_crossings.geojson"),
        )

    def test_public_city_catalog_and_public_risk_map_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._build_sample_root(Path(temp_dir))
            client = TestClient(create_app(settings))

            catalog_response = client.get("/v1/public/cities")
            self.assertEqual(catalog_response.status_code, 200)
            catalog_payload = catalog_response.json()
            self.assertEqual(catalog_payload["cities"][0]["city_key"], "bari")
            self.assertTrue(catalog_payload["cities"][0]["supports_junction_layer"])
            self.assertEqual(catalog_payload["serving_source"], "artifact")

            map_response = client.get(
                "/v1/public/cities/bari/risk-map",
                params={"min_score_band": "very_high", "limit": 5},
            )
            self.assertEqual(map_response.status_code, 200)
            map_payload = map_response.json()
            self.assertEqual(map_payload["serving_source"], "artifact")
            self.assertEqual(map_payload["map_resource"]["view"], "public_tiles")
            self.assertEqual(map_payload["map_resource"]["stats"]["returned_features"], 1)
            self.assertEqual(map_payload["summary"]["tiles_very_high"], 1)

            interventions_response = client.get("/v1/public/cities/bari/interventions")
            self.assertEqual(interventions_response.status_code, 200)
            self.assertEqual(
                interventions_response.json()["intervention_shortlist"]["top_corridors"][0]["corridor_label"],
                "Tangenziale Demo",
            )

    def test_postgis_domain_sync_plan_counts_current_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._build_sample_root(Path(temp_dir))
            plan = build_domain_sync_plan(settings, city_key="bari")

            self.assertEqual(plan["sync_contract_version"], "postgis_domain_artifact_sync_v1")
            self.assertEqual(plan["stats"]["city_count"], 1)
            self.assertEqual(plan["stats"]["segment_features"], 2)
            self.assertEqual(plan["stats"]["public_tile_features"], 2)
            self.assertEqual(plan["cities"][0]["segment_detail_rows"], 2)

            client = TestClient(create_app(settings))
            response = client.get("/v1/admin/postgis-domain/sync-plan", params={"city_key": "bari"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["stats"]["public_tile_features"], 2)

    def test_analyst_risk_map_endpoint_supports_local_demo_when_auth_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._build_sample_root(Path(temp_dir))
            client = TestClient(create_app(settings))

            response = client.get(
                "/v1/analyst/cities/bari/risk-map",
                params={
                    "min_score_band": "high",
                    "limit": 1,
                    "junction_limit": 1,
                    "crossing_limit": 1,
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["segment_layer"]["view"], "public_segments")
            self.assertEqual(payload["segment_layer"]["stats"]["returned_features"], 1)
            self.assertEqual(payload["segment_details"]["stats"]["returned_rows"], 1)
            self.assertEqual(payload["support_layers"]["junctions"]["availability"], "available")
            self.assertEqual(payload["support_layers"]["junctions"]["stats"]["returned_features"], 1)
            self.assertEqual(payload["support_layers"]["crossings"]["stats"]["returned_features"], 1)

            # The Bari junction layer is now gated by the `node_year_metric`
            # matrix from data_governance (Issue 01 chain). The layer
            # payload must surface the redaction_policy meta block so
            # clients know which policy was applied. The matrix-tracked
            # junction fields in the fixture (junction_id, node_object_id,
            # node_role, occurred_year, crash_count, injury_crash_count,
            # name) are all 'analyst'-visible per the matrix, so they
            # flow through.
            junction_policy = payload["support_layers"]["junctions"]["redaction_policy"]
            self.assertEqual(junction_policy["record_kind"], "node_year_metric")
            self.assertEqual(junction_policy["role"], "analyst")
            junction_props = payload["support_layers"]["junctions"]["data"]["features"][0]["properties"]
            for matrix_known in ("junction_id", "node_object_id", "node_role", "occurred_year", "crash_count"):
                self.assertIn(matrix_known, junction_props)
            # Default-deny: any property not registered in the
            # node_year_metric matrix must be stripped before reaching
            # the client.
            self.assertNotIn("_debug_internal_leak", junction_props)

            # The Bari crossing layer is now also matrix-tracked
            # (record_kind='crossing_priority'). It carries the same
            # redaction_policy meta block and applies the same
            # default-deny invariant.
            crossing_policy = payload["support_layers"]["crossings"]["redaction_policy"]
            self.assertEqual(crossing_policy["record_kind"], "crossing_priority")
            self.assertEqual(crossing_policy["role"], "analyst")
            crossing_props = payload["support_layers"]["crossings"]["data"]["features"][0]["properties"]
            for matrix_known in (
                "node_object_id",
                "crossing_name",
                "pedestrian_crossing_priority_score",
                "public_score_index",
                "crossing_protection_state",
            ):
                self.assertIn(matrix_known, crossing_props)
            self.assertNotIn("_debug_crossing_internal_leak", crossing_props)

    def test_analyst_risk_map_degrades_when_optional_support_layers_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = self._build_sample_root(root)
            (root / "layers" / "bari_signal_junctions.geojson").unlink()
            (root / "layers" / "bari_crossings.geojson").unlink()
            client = TestClient(create_app(settings))

            response = client.get(
                "/v1/analyst/cities/bari/risk-map",
                params={"limit": 1, "junction_limit": 1, "crossing_limit": 1},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["segment_layer"]["stats"]["returned_features"], 1)
            self.assertEqual(payload["support_layers"]["junctions"]["availability"], "unavailable")
            self.assertEqual(payload["support_layers"]["junctions"]["stats"]["returned_features"], 0)
            self.assertEqual(payload["support_layers"]["crossings"]["availability"], "unavailable")
            self.assertEqual(payload["support_layers"]["crossings"]["stats"]["returned_features"], 0)

    def test_analyst_risk_map_requires_scope_when_auth_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._build_sample_root(Path(temp_dir))
            app = create_app(ApiSettings(**{**settings.model_dump(), "auth_enabled": True, "auth_provider": "keycloak"}))
            client = TestClient(app)

            app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                subject="viewer-1",
                assigned_roles=frozenset({"public"}),
                roles=frozenset({"public"}),
                scopes=frozenset(),
                claims={"sub": "viewer-1"},
                organization_ids=frozenset({"org-bari"}),
                municipality_ids=frozenset({"bari"}),
                is_authenticated=True,
                auth_enabled=True,
                provider="keycloak",
            )
            denied_response = client.get("/v1/analyst/cities/bari/risk-map")
            self.assertEqual(denied_response.status_code, 403)

            app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                subject="analyst-1",
                assigned_roles=frozenset({ROLE_ANALYST}),
                roles=frozenset({"public", "municipality_viewer", ROLE_ANALYST}),
                scopes=frozenset(),
                claims={"sub": "analyst-1"},
                organization_ids=frozenset({"org-bari"}),
                municipality_ids=frozenset({"bari"}),
                is_authenticated=True,
                auth_enabled=True,
                provider="keycloak",
            )
            allowed_response = client.get(
                "/v1/analyst/cities/bari/risk-map",
                params={"min_score_band": "very_high"},
            )
            self.assertEqual(allowed_response.status_code, 200)
            self.assertEqual(allowed_response.json()["city"]["city_key"], "bari")
