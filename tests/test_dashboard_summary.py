from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.dashboard_summary import build_dashboard_summary


class DashboardSummaryTests(unittest.TestCase):
    def test_build_dashboard_summary_writes_published_and_transferability_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            published_index_path = root / "published_resources.json"
            output_dir = root / "dashboard"
            metrics_path = root / "frequency_transferability.metrics.json"
            prediction_store_dir = root / "prediction_store" / "demo_city"
            tile_store_dir = root / "prediction_store" / "demo_city_tiles"
            prediction_store_dir.mkdir(parents=True, exist_ok=True)
            tile_store_dir.mkdir(parents=True, exist_ok=True)

            analyst_csv_path = prediction_store_dir / "segment_scores_analyst.csv"
            analyst_csv_path.write_text(
                "\n".join(
                    [
                        "name,ref,highway,predicted_crash_count,observed_crash_count,public_score_index,public_score_band,score_rank_desc,score_decile,segment_length_m,segment_id,segment_score_id",
                        "\"['Tangenziale di Demo']\",SS16,\"['trunk']\",3.2,4,100,very_high,1,1,250,seg-1,demo_city:2021:seg-1",
                        "\"['Tangenziale di Demo']\",SS16,\"['trunk']\",2.1,3,96,very_high,2,1,240,seg-2,demo_city:2021:seg-2",
                        "\"['Via Porto']\",,\"['secondary']\",1.0,1,85,high,4,2,180,seg-3,demo_city:2021:seg-3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            public_segments_path = prediction_store_dir / "segment_scores_public.geojson"
            public_segments_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {"segment_score_id": "demo_city:2021:seg-1"},
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.0, 0.0], [0.8, 0.8]],
                                },
                            },
                            {
                                "type": "Feature",
                                "properties": {"segment_score_id": "demo_city:2021:seg-2"},
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.2, 0.8], [0.8, 0.2]],
                                },
                            },
                            {
                                "type": "Feature",
                                "properties": {"segment_score_id": "demo_city:2021:seg-3"},
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[1.2, 1.2], [1.8, 1.8]],
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            segment_manifest_path = prediction_store_dir / "segment_scores.manifest.json"
            segment_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "analyst_csv_path": str(analyst_csv_path),
                            "public_geojson_path": str(public_segments_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            tile_summary_csv_path = tile_store_dir / "score_tiles_summary.csv"
            tile_summary_csv_path.write_text(
                "\n".join(
                    [
                        "tile_score_id,tile_public_score_band,tile_max_public_score_index,tile_segment_count,tile_very_high_band_segment_count,tile_high_band_segment_count",
                        "demo_city:2021:0:0:500m,very_high,100,4,2,2",
                        "demo_city:2021:0:1:500m,very_high,98,3,1,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            public_tiles_path = tile_store_dir / "score_tiles_public.geojson"
            public_tiles_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {"tile_score_id": "demo_city:2021:0:0:500m"},
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
                                },
                            },
                            {
                                "type": "Feature",
                                "properties": {"tile_score_id": "demo_city:2021:0:1:500m"},
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0], [1.0, 1.0]]],
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            tile_manifest_path = tile_store_dir / "score_tiles.manifest.json"
            tile_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "summary_csv_path": str(tile_summary_csv_path),
                            "public_geojson_path": str(public_tiles_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            published_index_path.write_text(
                json.dumps(
                    {
                        "catalog": [],
                        "selection_policy": {
                            "published_resource_selection_policy_version": "published_resource_selection_policy_v1"
                        },
                        "stats": {"catalog_record_count": 4},
                        "latest_by_resource_prediction_run": {
                            "segment_scores": {
                                "demo_city": {
                                    "city_key": "demo_city",
                                    "prediction_run_label": "demo_city",
                                    "prediction_task": "segment_frequency_baseline",
                                    "occurred_years": [2021],
                                    "manifest_path": str(segment_manifest_path),
                                    "contract_versions": {
                                        "public_contract_version": "segment_scores_public_v1",
                                        "analyst_contract_version": "segment_scores_analyst_v1",
                                        "lineage_contract_version": "artifact_lineage_v1",
                                    },
                                    "views": {
                                        "public_segments": {"path": str(public_segments_path)},
                                        "analyst_segments": {"path": str(analyst_csv_path)},
                                    },
                                    "selection": {
                                        "is_latest_for_prediction_run": True,
                                        "published_resource_selection_policy_version": "published_resource_selection_policy_v1",
                                    },
                                    "lineage_trace": {
                                        "source_metrics_path": "data/models/demo_city/frequency_baseline.metrics.json",
                                        "trace_status": "resolved",
                                    },
                                    "stats": {
                                        "segment_score_rows": 42,
                                        "observed_crash_total": 10,
                                        "predicted_crash_total": 9.5,
                                        "top_5pct_observed_crash_share": 0.4,
                                    },
                                }
                            },
                            "segment_score_tiles": {
                                "demo_city": {
                                    "city_key": "demo_city",
                                    "prediction_run_label": "demo_city",
                                    "prediction_task": "segment_frequency_baseline",
                                    "occurred_years": [2021],
                                    "manifest_path": str(tile_manifest_path),
                                    "contract_versions": {
                                        "public_contract_version": "segment_score_tiles_public_v1",
                                        "lineage_contract_version": "artifact_lineage_v1",
                                    },
                                    "views": {
                                        "public_tiles": {"path": str(public_tiles_path)},
                                    },
                                    "selection": {
                                        "is_latest_for_prediction_run": True,
                                        "published_resource_selection_policy_version": "published_resource_selection_policy_v1",
                                    },
                                    "lineage_trace": {
                                        "source_metrics_path": "data/models/demo_city/frequency_baseline.metrics.json",
                                        "trace_status": "resolved",
                                    },
                                    "stats": {
                                        "tile_rows": 7,
                                        "tile_size_m": 500.0,
                                        "tiles_high_or_very_high": 3,
                                        "tiles_very_high": 2,
                                    },
                                }
                            },
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            metrics_path.write_text(
                json.dumps(
                    {
                        "holdout_year": 2021,
                        "random_forest_n_estimators": 25,
                        "requested_modes": [
                            "cross_jurisdiction_temporal",
                            "cross_jurisdiction_cold_start",
                            "cross_jurisdiction_history_free",
                        ],
                        "cross_jurisdiction_temporal": {
                            "demo_city": {
                                "test_rows": 12,
                                "test_crash_total": 5,
                                "train_jurisdictions": ["peer_city"],
                                "random_forest_poisson_metrics": {
                                    "mean_poisson_deviance": 0.25,
                                    "top_5pct_crash_share": 0.5,
                                },
                            }
                        },
                        "cross_jurisdiction_cold_start": {
                            "demo_city": {
                                "test_rows": 12,
                                "test_crash_total": 5,
                                "train_jurisdictions": ["peer_city"],
                                "random_forest_poisson_metrics": {
                                    "mean_poisson_deviance": 0.35,
                                    "top_5pct_crash_share": 0.4,
                                },
                            }
                        },
                        "cross_jurisdiction_history_free": {
                            "demo_city": {
                                "test_rows": 12,
                                "test_crash_total": 5,
                                "train_jurisdictions": ["peer_city"],
                                "random_forest_poisson_metrics": {
                                    "mean_poisson_deviance": 0.45,
                                    "top_5pct_crash_share": 0.3,
                                },
                            }
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_dashboard_summary(
                published_index_path=published_index_path,
                transferability_metrics_paths=[metrics_path],
                output_dir=output_dir,
            )

            self.assertEqual(manifest["dashboard_summary_version"], "dashboard_summary_v1")
            self.assertEqual(manifest["stats"]["published_run_count"], 1)
            self.assertEqual(manifest["stats"]["transferability_file_count"], 3)
            self.assertEqual(manifest["stats"]["transferability_source_file_count"], 1)
            self.assertEqual(manifest["stats"]["lineage_traced_run_count"], 1)

            summary_payload = json.loads((output_dir / "dashboard_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                summary_payload["published_resource_selection_policy"][
                    "published_resource_selection_policy_version"
                ],
                "published_resource_selection_policy_v1",
            )
            self.assertEqual(summary_payload["published_runs"][0]["display_name"], "Demo City")
            self.assertEqual(summary_payload["published_runs"][0]["city_key"], "demo_city")
            self.assertEqual(summary_payload["published_runs"][0]["score_tiles"]["tile_rows"], 7)
            self.assertEqual(
                summary_payload["published_runs"][0]["segment_scores"]["public_segments_path"],
                str(public_segments_path),
            )
            self.assertEqual(
                summary_payload["published_runs"][0]["segment_scores"]["lineage_trace"]["trace_status"],
                "resolved",
            )
            self.assertEqual(summary_payload["transferability_evaluations"][0]["mode"], "cross_jurisdiction_temporal")
            self.assertEqual(summary_payload["transferability_evaluations"][1]["mode"], "cross_jurisdiction_cold_start")
            self.assertEqual(summary_payload["transferability_evaluations"][2]["mode"], "cross_jurisdiction_history_free")
            self.assertEqual(
                summary_payload["transferability_matrix"][0]["metrics_by_mode"]["cross_jurisdiction_temporal"][
                    "mean_poisson_deviance"
                ],
                0.25,
            )
            self.assertEqual(
                summary_payload["transferability_matrix"][0]["metrics_by_mode"]["cross_jurisdiction_cold_start"][
                    "mean_poisson_deviance"
                ],
                0.35,
            )
            self.assertEqual(
                summary_payload["transferability_matrix"][0]["metrics_by_mode"]["cross_jurisdiction_history_free"][
                    "mean_poisson_deviance"
                ],
                0.45,
            )
            self.assertEqual(summary_payload["intervention_priority"][0]["very_high_tiles_rank"], 1)
            self.assertEqual(summary_payload["intervention_priority"][0]["top_5_share_rank"], 1)
            self.assertEqual(summary_payload["intervention_shortlists"][0]["top_corridors"][0]["corridor_label"], "Tangenziale di Demo")
            self.assertEqual(summary_payload["intervention_shortlists"][0]["hotspot_tiles"][0]["tile_score_id"], "demo_city:2021:0:0:500m")
            self.assertEqual(
                summary_payload["intervention_shortlists"][0]["top_corridors"][0]["focus_segment_score_ids"],
                ["demo_city:2021:seg-1", "demo_city:2021:seg-2"],
            )
            self.assertEqual(
                summary_payload["intervention_shortlists"][0]["top_corridors"][0]["top_segments"][0]["segment_score_id"],
                "demo_city:2021:seg-1",
            )
            self.assertEqual(
                summary_payload["intervention_shortlists"][0]["hotspot_tiles"][0]["intersection_segment_count"],
                2,
            )
            self.assertEqual(
                summary_payload["intervention_shortlists"][0]["hotspot_tiles"][0]["top_segments"][0]["segment_score_id"],
                "demo_city:2021:seg-1",
            )
