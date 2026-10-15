from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.published_index import build_published_resource_index


class PublishedIndexTests(unittest.TestCase):
    def test_build_published_resource_index_writes_static_latest_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_path = root / "run_registry.jsonl"
            output_dir = root / "published_index"
            data_root = root / "data"
            older_store_dir = data_root / "prediction_store" / "older_run"
            latest_store_dir = data_root / "prediction_store" / "latest_run"
            latest_tile_dir = data_root / "prediction_store" / "latest_tiles"
            model_dir = data_root / "models" / "latest_run"
            older_store_dir.mkdir(parents=True, exist_ok=True)
            latest_store_dir.mkdir(parents=True, exist_ok=True)
            latest_tile_dir.mkdir(parents=True, exist_ok=True)
            model_dir.mkdir(parents=True, exist_ok=True)

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
            (older_store_dir / "segment_scores.manifest.json").write_text(
                json.dumps(
                    {
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "source_metrics",
                                    "path": "data/models/latest_run/frequency_baseline.metrics.json",
                                }
                            ],
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (latest_store_dir / "segment_scores.manifest.json").write_text(
                json.dumps(
                    {
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "source_metrics",
                                    "path": "data/models/latest_run/frequency_baseline.metrics.json",
                                }
                            ],
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (latest_tile_dir / "score_tiles.manifest.json").write_text(
                json.dumps(
                    {
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "segment_scores_manifest",
                                    "path": "data/prediction_store/latest_run/segment_scores.manifest.json",
                                }
                            ],
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            entries = [
                {
                    "stage": "serving",
                    "artifact_kind": "prediction_store",
                    "run_label": "older_run",
                    "document_path": "data/prediction_store/older_run/segment_scores.manifest.json",
                    "document_mtime_utc": "2026-03-28T11:00:00+00:00",
                    "summary": {
                        "resource_name": "segment_scores",
                        "public_contract_version": "segment_scores_public_v1",
                        "analyst_contract_version": "segment_scores_analyst_v1",
                        "lineage_contract_version": "artifact_lineage_v1",
                        "stats": {
                            "prediction_run_label": "older_run",
                            "prediction_task": "segment_frequency_baseline",
                            "holdout_years": [2021],
                        },
                    },
                    "output_references": [
                        {
                            "field": "outputs.public_geojson_path",
                            "path": "data/prediction_store/older_run/segment_scores_public.geojson",
                        },
                        {
                            "field": "outputs.analyst_csv_path",
                            "path": "data/prediction_store/older_run/segment_scores_analyst.csv",
                        },
                    ],
                },
                {
                    "stage": "serving",
                    "artifact_kind": "prediction_store",
                    "run_label": "latest_run",
                    "document_path": "data/prediction_store/latest_run/segment_scores.manifest.json",
                    "document_mtime_utc": "2026-03-28T12:00:00+00:00",
                    "summary": {
                        "resource_name": "segment_scores",
                        "public_contract_version": "segment_scores_public_v1",
                        "analyst_contract_version": "segment_scores_analyst_v1",
                        "lineage_contract_version": "artifact_lineage_v1",
                        "stats": {
                            "prediction_run_label": "latest_run",
                            "prediction_task": "segment_frequency_baseline",
                            "holdout_years": [2021],
                        },
                    },
                    "output_references": [
                        {
                            "field": "outputs.public_geojson_path",
                            "path": "data/prediction_store/latest_run/segment_scores_public.geojson",
                        },
                        {
                            "field": "outputs.analyst_csv_path",
                            "path": "data/prediction_store/latest_run/segment_scores_analyst.csv",
                        },
                    ],
                },
                {
                    "stage": "serving",
                    "artifact_kind": "public_score_tiles",
                    "run_label": "latest_tiles",
                    "document_path": "data/prediction_store/latest_tiles/score_tiles.manifest.json",
                    "document_mtime_utc": "2026-03-28T12:30:00+00:00",
                    "summary": {
                        "resource_name": "segment_score_tiles",
                        "public_contract_version": "segment_score_tiles_public_v1",
                        "analyst_contract_version": None,
                        "lineage_contract_version": "artifact_lineage_v1",
                        "stats": {
                            "prediction_run_label": "latest_run",
                            "prediction_task": "segment_frequency_baseline",
                            "holdout_years": [2021],
                            "tile_size_m": 500.0,
                        },
                    },
                    "output_references": [
                        {
                            "field": "outputs.public_geojson_path",
                            "path": "data/prediction_store/latest_tiles/score_tiles_public.geojson",
                        }
                    ],
                },
                {
                    "stage": "serving",
                    "artifact_kind": "published_resource_index",
                    "run_label": "published_index",
                    "document_path": "data/published_index/published_resources.manifest.json",
                    "document_mtime_utc": "2026-03-28T13:00:00+00:00",
                    "summary": {
                        "resource_name": "published_resource_index",
                        "public_contract_version": "published_resource_index_public_v1",
                        "lineage_contract_version": "artifact_lineage_v1",
                        "stats": {
                            "catalog_record_count": 2,
                        },
                    },
                    "output_references": [
                        {
                            "field": "outputs.index_json_path",
                            "path": "data/published_index/published_resources.json",
                        }
                    ],
                },
            ]
            registry_path.write_text(
                "\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n",
                encoding="utf-8",
            )

            manifest = build_published_resource_index(
                registry_path=registry_path,
                output_dir=output_dir,
            )

            self.assertEqual(manifest["published_resource_index_version"], "published_resource_index_v1")
            self.assertEqual(manifest["stats"]["catalog_record_count"], 3)
            self.assertEqual(manifest["stats"]["resource_count"], 2)
            self.assertEqual(manifest["stats"]["stale_catalog_record_count"], 1)

            index_payload = json.loads((output_dir / "published_resources.json").read_text(encoding="utf-8"))
            self.assertEqual(
                index_payload["selection_policy"]["published_resource_selection_policy_version"],
                "published_resource_selection_policy_v1",
            )
            self.assertEqual(
                index_payload["latest_by_resource"]["segment_scores"]["manifest_path"],
                "data/prediction_store/latest_run/segment_scores.manifest.json",
            )
            self.assertFalse(
                index_payload["latest_by_resource_prediction_run"]["segment_scores"]["latest_run"]["selection"][
                    "is_stale_for_prediction_run"
                ]
            )
            self.assertEqual(
                index_payload["latest_by_resource_prediction_run"]["segment_scores"]["latest_run"]["views"][
                    "public_segments"
                ]["path"],
                "data/prediction_store/latest_run/segment_scores_public.geojson",
            )
            self.assertEqual(
                index_payload["latest_by_resource_prediction_run_year"]["segment_scores"]["latest_run"]["2021"][
                    "manifest_path"
                ],
                "data/prediction_store/latest_run/segment_scores.manifest.json",
            )
            self.assertEqual(
                index_payload["latest_by_resource_prediction_run_year_tile"]["segment_score_tiles"]["latest_run"][
                    "2021"
                ]["500.0"]["manifest_path"],
                "data/prediction_store/latest_tiles/score_tiles.manifest.json",
            )
            self.assertEqual(
                index_payload["latest_by_resource_prediction_run"]["segment_scores"]["latest_run"][
                    "lineage_trace"
                ]["source_metrics_path"],
                "data/models/latest_run/frequency_baseline.metrics.json",
            )
            self.assertEqual(
                index_payload["latest_by_resource_prediction_run_year_tile"]["segment_score_tiles"]["latest_run"][
                    "2021"
                ]["500.0"]["lineage_trace"]["source_metrics_path"],
                "data/models/latest_run/frequency_baseline.metrics.json",
            )
            resource_names = {record["resource_name"] for record in index_payload["catalog"]}
            self.assertEqual(resource_names, {"segment_scores", "segment_score_tiles"})
