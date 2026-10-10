from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.published_refresh import build_published_refresh_bundle


class PublishedRefreshTests(unittest.TestCase):
    def test_build_published_refresh_bundle_rebuilds_outputs_and_uses_latest_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            registry_dir = data_root / "registry"
            published_index_dir = data_root / "published_index"
            dashboard_dir = data_root / "dashboard"
            refresh_dir = data_root / "reporting" / "published_refresh" / "latest"
            store_dir = data_root / "prediction_store" / "demo_run"
            tile_dir = data_root / "prediction_store" / "demo_run_tiles"
            model_dir = data_root / "models" / "demo_run"
            transferability_dir = data_root / "models" / "demo_transferability"
            benchmark_dir = data_root / "reporting" / "transferability_benchmark" / "demo"
            store_dir.mkdir(parents=True, exist_ok=True)
            tile_dir.mkdir(parents=True, exist_ok=True)
            model_dir.mkdir(parents=True, exist_ok=True)
            transferability_dir.mkdir(parents=True, exist_ok=True)
            benchmark_dir.mkdir(parents=True, exist_ok=True)

            source_metrics_path = model_dir / "frequency_baseline.metrics.json"
            source_metrics_path.write_text(
                json.dumps(
                    {
                        "training_config": {
                            "training_config_version": "training_config_v1",
                            "task": "segment_frequency_baseline",
                            "split_strategy": "temporal_holdout",
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            public_segments_path = store_dir / "segment_scores_public.geojson"
            public_segments_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [0.5, 0.5]]},
                                "properties": {
                                    "segment_score_id": "demo_run:2021:s1",
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
            analyst_csv_path = store_dir / "segment_scores_analyst.csv"
            analyst_csv_path.write_text(
                "\n".join(
                    [
                        "name,ref,highway,predicted_crash_count,observed_crash_count,public_score_index,public_score_band,score_rank_desc,score_decile,segment_length_m,occurred_year,segment_id,segment_score_id",
                        "\"['Demo Corridor']\",SS16,\"['trunk']\",2.5,3,98,very_high,1,1,200,2021,s1,demo_run:2021:s1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            segment_manifest_path = store_dir / "segment_scores.manifest.json"
            segment_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_scores",
                            "public_contract_version": "segment_scores_public_v1",
                            "analyst_contract_version": "segment_scores_analyst_v1",
                        },
                        "outputs": {
                            "public_geojson_path": str(public_segments_path),
                            "analyst_csv_path": str(analyst_csv_path),
                        },
                        "stats": {
                            "prediction_run_label": "demo_run",
                            "prediction_task": "segment_frequency_baseline",
                            "holdout_years": [2021],
                            "segment_score_rows": 1,
                            "observed_crash_total": 3,
                            "predicted_crash_total": 2.5,
                            "top_5pct_observed_crash_share": 1.0,
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "source_metrics",
                                    "path": "data/models/demo_run/frequency_baseline.metrics.json",
                                }
                            ],
                            "publishable_outputs": [],
                            "supporting_outputs": [],
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            public_tiles_path = tile_dir / "score_tiles_public.geojson"
            public_tiles_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
                                },
                                "properties": {
                                    "tile_score_id": "demo_run:2021:0:0:500m",
                                    "occurred_year": 2021,
                                    "tile_public_score_band": "very_high",
                                    "tile_max_public_score_index": 98.0,
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            tile_summary_path = tile_dir / "score_tiles_summary.csv"
            tile_summary_path.write_text(
                "\n".join(
                    [
                        "tile_score_id,tile_public_score_band,tile_max_public_score_index,tile_segment_count,tile_very_high_band_segment_count,tile_high_band_segment_count",
                        "demo_run:2021:0:0:500m,very_high,98,1,1,0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            tile_manifest_path = tile_dir / "score_tiles.manifest.json"
            tile_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_score_tiles",
                            "public_contract_version": "segment_score_tiles_public_v1",
                        },
                        "outputs": {
                            "public_geojson_path": str(public_tiles_path),
                            "summary_csv_path": str(tile_summary_path),
                        },
                        "stats": {
                            "prediction_run_label": "demo_run",
                            "prediction_task": "segment_frequency_baseline",
                            "holdout_years": [2021],
                            "tile_size_m": 500.0,
                            "tile_rows": 1,
                            "tiles_high_or_very_high": 1,
                            "tiles_very_high": 1,
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "segment_scores_manifest",
                                    "path": "data/prediction_store/demo_run/segment_scores.manifest.json",
                                }
                            ],
                            "publishable_outputs": [],
                            "supporting_outputs": [],
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            transferability_metrics_path = transferability_dir / "frequency_transferability.metrics.json"
            transferability_metrics_path.write_text(
                json.dumps(
                    {
                        "holdout_year": 2021,
                        "random_forest_n_estimators": 25,
                        "requested_modes": [
                            "within_jurisdiction_temporal",
                            "cross_jurisdiction_temporal",
                            "cross_jurisdiction_cold_start",
                            "cross_jurisdiction_history_free",
                        ],
                        "dataset_inputs": [
                            {
                                "label": "demo_run",
                                "path": "data/processed/aggregates/demo_run/segment_year_metrics.csv",
                            },
                            {
                                "label": "peer_city",
                                "path": "data/processed/aggregates/peer_city/segment_year_metrics.csv",
                            },
                        ],
                        "training_config": {
                            "training_config_version": "training_config_v1",
                            "task": "segment_frequency_transferability",
                            "split_strategy": "jurisdiction_holdout",
                        },
                        "cross_jurisdiction_temporal": {
                            "demo_run": {
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
                            "demo_run": {
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
                            "demo_run": {
                                "test_rows": 12,
                                "test_crash_total": 5,
                                "train_jurisdictions": ["peer_city"],
                                "random_forest_poisson_metrics": {
                                    "mean_poisson_deviance": 0.45,
                                    "top_5pct_crash_share": 0.3,
                                },
                            }
                        },
                        "within_jurisdiction_temporal": {
                            "demo_run": {
                                "test_rows": 12,
                                "test_crash_total": 5,
                                "train_jurisdictions": ["demo_run"],
                                "random_forest_poisson_metrics": {
                                    "mean_poisson_deviance": 0.2,
                                    "top_5pct_crash_share": 0.6,
                                },
                            }
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            benchmark_json_path = benchmark_dir / "transferability_benchmark.json"
            benchmark_json_path.write_text(
                json.dumps(
                    {
                        "benchmark_label": "Demo Benchmark",
                        "budget_profiles": [
                            {
                                "stack_key": "demo_run__peer_city",
                                "stack_display_name": "Demo Run + Peer City",
                                "dataset_labels": ["demo_run", "peer_city"],
                                "recommended_budget": 25,
                            }
                        ],
                        "runs": [
                            {
                                "stack_key": "demo_run__peer_city",
                                "stack_display_name": "Demo Run + Peer City",
                                "dataset_count": 2,
                                "random_forest_n_estimators": 25,
                                "requested_modes": [
                                    "within_jurisdiction_temporal",
                                    "cross_jurisdiction_temporal",
                                    "cross_jurisdiction_cold_start",
                                    "cross_jurisdiction_history_free",
                                ],
                                "metrics_paths": [
                                    "data/models/demo_transferability/frequency_transferability.metrics.json"
                                ],
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (benchmark_dir / "transferability_benchmark.manifest.json").write_text(
                json.dumps(
                    {
                        "outputs": {
                            "report_json_path": "data/reporting/transferability_benchmark/demo/transferability_benchmark.json",
                            "report_md_path": "data/reporting/transferability_benchmark/demo/transferability_benchmark.md",
                        },
                        "stats": {"input_run_count": 1},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (benchmark_dir / "transferability_benchmark.md").write_text(
                "# Demo Benchmark\n",
                encoding="utf-8",
            )

            manifest = build_published_refresh_bundle(
                data_root=data_root,
                registry_output_dir=registry_dir,
                published_index_output_dir=published_index_dir,
                dashboard_output_dir=dashboard_dir,
                output_dir=refresh_dir,
            )

            self.assertEqual(
                manifest["published_refresh_bundle_version"],
                "published_refresh_bundle_v1",
            )

            bundle_payload = json.loads(
                (refresh_dir / "published_refresh_bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                bundle_payload["transferability_selection"]["selection_source"],
                "latest_transferability_benchmark",
            )
            self.assertEqual(
                bundle_payload["transferability_selection"]["selected_random_forest_n_estimators"],
                25,
            )
            self.assertEqual(
                bundle_payload["transferability_selection"]["metrics_paths"],
                ["data/models/demo_transferability/frequency_transferability.metrics.json"],
            )
            self.assertEqual(bundle_payload["dashboard_summary_stats"]["published_run_count"], 1)
            self.assertEqual(bundle_payload["dashboard_summary_stats"]["transferability_file_count"], 3)
            self.assertEqual(bundle_payload["dashboard_summary_stats"]["transferability_source_file_count"], 1)
            self.assertEqual(bundle_payload["dashboard_summary_stats"]["lineage_traced_run_count"], 1)

            dashboard_payload = json.loads(
                (dashboard_dir / "dashboard_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                dashboard_payload["published_runs"][0]["segment_scores"]["lineage_trace"][
                    "source_metrics_path"
                ],
                "data/models/demo_run/frequency_baseline.metrics.json",
            )
            self.assertEqual(len(dashboard_payload["transferability_evaluations"]), 3)
