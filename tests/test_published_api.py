from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.published_api import handle_published_api_request, resolve_dashboard_asset_response


class PublishedApiTests(unittest.TestCase):
    def test_handle_published_api_request_serves_index_and_queries_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            store_dir = data_root / "prediction_store" / "demo_run"
            index_dir = data_root / "published_index"
            store_dir.mkdir(parents=True, exist_ok=True)
            index_dir.mkdir(parents=True, exist_ok=True)

            public_geojson_path = store_dir / "segment_scores_public.geojson"
            public_geojson_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[16.8, 41.1], [16.81, 41.11]]},
                                "properties": {
                                    "segment_score_id": "demo:2021:s1",
                                    "segment_id": "s1",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 98.0,
                                    "public_score_band": "very_high",
                                    "score_decile": 1,
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest_path = store_dir / "segment_scores.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_scores",
                            "public_contract_version": "segment_scores_public_v1",
                            "analyst_contract_version": "segment_scores_analyst_v1",
                        },
                        "outputs": {
                            "manifest_path": "data/prediction_store/demo_run/segment_scores.manifest.json",
                            "public_geojson_path": "data/prediction_store/demo_run/segment_scores_public.geojson",
                            "analyst_csv_path": "data/prediction_store/demo_run/segment_scores_analyst.csv",
                        },
                        "stats": {
                            "holdout_years": [2021],
                            "prediction_run_label": "demo_run",
                            "prediction_task": "segment_frequency_baseline",
                            "segment_score_rows": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            published_index_path = index_dir / "published_resources.json"
            published_index_path.write_text(
                json.dumps(
                    {
                        "published_resource_index_version": "published_resource_index_v1",
                        "selection_policy": {
                            "published_resource_selection_policy_version": "published_resource_selection_policy_v1"
                        },
                        "catalog": [
                            {
                                "resource_name": "segment_scores",
                                "artifact_kind": "prediction_store",
                                "run_label": "demo_run",
                                "prediction_run_label": "demo_run",
                                "prediction_task": "segment_frequency_baseline",
                                "occurred_years": [2021],
                                "tile_size_m": None,
                                "document_mtime_utc": "2026-03-28T13:30:00+00:00",
                                "manifest_path": "data/prediction_store/demo_run/segment_scores.manifest.json",
                                "contract_versions": {
                                    "public_contract_version": "segment_scores_public_v1",
                                    "analyst_contract_version": "segment_scores_analyst_v1",
                                    "lineage_contract_version": "artifact_lineage_v1",
                                },
                                "selection": {
                                    "is_latest_for_prediction_run": True,
                                    "published_resource_selection_policy_version": "published_resource_selection_policy_v1",
                                },
                                "lineage_trace": {
                                    "source_metrics_path": "data/models/demo_run/frequency_baseline.metrics.json",
                                    "trace_status": "resolved",
                                },
                                "views": {
                                    "public_segments": {
                                        "path": "data/prediction_store/demo_run/segment_scores_public.geojson",
                                        "contract_version": "segment_scores_public_v1",
                                    }
                                },
                                "stats": {
                                    "holdout_years": [2021],
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "segment_score_rows": 1,
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            status, health_payload = handle_published_api_request(
                "GET",
                "/v1/healthz",
                published_index_path=published_index_path,
                root_dir=root,
            )
            self.assertEqual(status, 200)
            self.assertEqual(health_payload["status"], "ok")

            status, latest_payload = handle_published_api_request(
                "GET",
                "/v1/published-resource/latest?resource_name=segment_scores&prediction_run_label=demo_run&occurred_year=2021",
                published_index_path=published_index_path,
                root_dir=root,
            )
            self.assertEqual(status, 200)
            self.assertEqual(
                latest_payload["selection_policy"]["published_resource_selection_policy_version"],
                "published_resource_selection_policy_v1",
            )
            self.assertEqual(latest_payload["resolved"]["resolved_view"], "public_segments")
            self.assertEqual(
                latest_payload["resolved"]["manifest_path"],
                "data/prediction_store/demo_run/segment_scores.manifest.json",
            )
            self.assertEqual(
                latest_payload["resolved"]["lineage_trace"]["source_metrics_path"],
                "data/models/demo_run/frequency_baseline.metrics.json",
            )

            status, query_payload = handle_published_api_request(
                "GET",
                "/v1/published-resource/query?resource_name=segment_scores&prediction_run_label=demo_run&occurred_year=2021&min_score_band=high&limit=1",
                published_index_path=published_index_path,
                root_dir=root,
            )
            self.assertEqual(status, 200)
            self.assertEqual(query_payload["resource"]["resource_name"], "segment_scores")
            self.assertEqual(query_payload["resource"]["stats"]["returned_features"], 1)
            self.assertEqual(query_payload["resolution"]["resolved_view"], "public_segments")

    def test_handle_published_api_request_returns_400_for_missing_resource_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_dir = root / "data" / "published_index"
            index_dir.mkdir(parents=True, exist_ok=True)
            published_index_path = index_dir / "published_resources.json"
            published_index_path.write_text(
                json.dumps({"published_resource_index_version": "published_resource_index_v1", "catalog": []}),
                encoding="utf-8",
            )

            status, payload = handle_published_api_request(
                "GET",
                "/v1/published-resource/latest",
                published_index_path=published_index_path,
                root_dir=root,
            )
            self.assertEqual(status, 400)
            self.assertEqual(payload["error"]["code"], "bad_request")

    def test_handle_published_api_request_returns_404_for_unknown_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_dir = root / "data" / "published_index"
            index_dir.mkdir(parents=True, exist_ok=True)
            published_index_path = index_dir / "published_resources.json"
            published_index_path.write_text(
                json.dumps({"published_resource_index_version": "published_resource_index_v1", "catalog": []}),
                encoding="utf-8",
            )

            status, payload = handle_published_api_request(
                "GET",
                "/v1/unknown",
                published_index_path=published_index_path,
                root_dir=root,
            )
            self.assertEqual(status, 404)
            self.assertEqual(payload["error"]["code"], "not_found")

    def test_resolve_dashboard_asset_response_serves_index_html_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_dir = root / "dashboard"
            dashboard_dir.mkdir(parents=True, exist_ok=True)
            (dashboard_dir / "index.html").write_text("<html><body>demo dashboard</body></html>", encoding="utf-8")
            (dashboard_dir / "app.js").write_text("console.log('demo');", encoding="utf-8")

            index_response = resolve_dashboard_asset_response(
                "/dashboard/",
                dashboard_dir=dashboard_dir,
                root_dir=root,
            )
            self.assertIsNotNone(index_response)
            index_status, index_content_type, index_body = index_response
            self.assertEqual(index_status, 200)
            self.assertEqual(index_content_type, "text/html; charset=utf-8")
            self.assertIn(b"demo dashboard", index_body)

            asset_response = resolve_dashboard_asset_response(
                "/dashboard/app.js",
                dashboard_dir=dashboard_dir,
                root_dir=root,
            )
            self.assertIsNotNone(asset_response)
            asset_status, asset_content_type, asset_body = asset_response
            self.assertEqual(asset_status, 200)
            self.assertEqual(asset_content_type, "application/javascript; charset=utf-8")
            self.assertIn(b"console.log", asset_body)

    def test_handle_published_api_request_serves_dashboard_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_dir = root / "data" / "published_index"
            dashboard_dir = root / "data" / "dashboard"
            index_dir.mkdir(parents=True, exist_ok=True)
            dashboard_dir.mkdir(parents=True, exist_ok=True)

            published_index_path = index_dir / "published_resources.json"
            published_index_path.write_text(
                json.dumps({"published_resource_index_version": "published_resource_index_v1", "catalog": []}),
                encoding="utf-8",
            )
            dashboard_summary_path = dashboard_dir / "dashboard_summary.json"
            dashboard_summary_path.write_text(
                json.dumps(
                    {
                        "dashboard_summary_version": "dashboard_summary_v1",
                        "published_runs": [{"prediction_run_label": "demo_run"}],
                        "transferability_matrix": [],
                    }
                ),
                encoding="utf-8",
            )

            status, payload = handle_published_api_request(
                "GET",
                "/v1/dashboard-summary",
                published_index_path=published_index_path,
                dashboard_summary_path=dashboard_summary_path,
                root_dir=root,
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["summary"]["dashboard_summary_version"], "dashboard_summary_v1")
            self.assertEqual(payload["summary"]["published_runs"][0]["prediction_run_label"], "demo_run")
