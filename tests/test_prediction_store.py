from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.governance_interoperability import build_governance_interoperability_bundle
from road_risk_modeling.prediction_store import publish_segment_scores


class PredictionStoreTests(unittest.TestCase):
    def test_publish_segment_scores_writes_public_and_analyst_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            predictions_path = root / "holdout_predictions.csv"
            segments_path = root / "road_segments_context.geojson"
            metrics_path = root / "frequency_baseline.metrics.json"
            output_dir = root / "prediction_store"
            governance_dir = root / "governance"

            with predictions_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "segment_id",
                        "occurred_year",
                        "crash_count",
                        "random_forest_poisson_prediction",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "segment_id": "seg-1",
                            "occurred_year": 2021,
                            "crash_count": 0,
                            "random_forest_poisson_prediction": 0.5,
                        },
                        {
                            "segment_id": "seg-2",
                            "occurred_year": 2021,
                            "crash_count": 1,
                            "random_forest_poisson_prediction": 2.5,
                        },
                    ]
                )

            segments_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                                "properties": {
                                    "segment_id": "seg-1",
                                    "highway": "residential",
                                    "segment_length_m": 100.0,
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
                                "properties": {
                                    "segment_id": "seg-2",
                                    "highway": "primary",
                                    "segment_length_m": 150.0,
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            metrics_path.write_text(
                json.dumps(
                    {
                        "training_config": {
                            "task": "segment_frequency_baseline",
                            "split_strategy": "temporal_holdout_year",
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [{"role": "aggregate_segment_year_metrics", "path": "data/processed/aggregates/demo.csv"}],
                            "publishable_outputs": [{"role": "holdout_segment_predictions", "path": str(predictions_path)}],
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            build_governance_interoperability_bundle(governance_dir)

            result = publish_segment_scores(
                predictions_path=predictions_path,
                segments_path=segments_path,
                metrics_path=metrics_path,
                output_dir=output_dir,
                governance_bundle_path=governance_dir / "governance_interoperability_bundle.json",
            )

            manifest_path = Path(result["manifest_path"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["prediction_store_version"], "segment_prediction_store_v1")
            self.assertEqual(manifest["stats"]["segment_score_rows"], 2)
            self.assertEqual(manifest["stats"]["top_5pct_observed_crash_share"], 1.0)
            self.assertEqual(manifest["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertEqual(len(manifest["lineage"]["publishable_outputs"]), 2)
            self.assertIn("segment_scores_public_geojson", manifest["governance"]["artifact_family_ids"])
            self.assertIn(
                "segment_scores_analyst_csv__analyst",
                manifest["governance"]["role_policy_ids"],
            )

            analyst_csv_path = output_dir / "segment_scores_analyst.csv"
            public_geojson_path = output_dir / "segment_scores_public.geojson"
            self.assertTrue(analyst_csv_path.exists())
            self.assertTrue(public_geojson_path.exists())

            with analyst_csv_path.open(encoding="utf-8", newline="") as handle:
                analyst_rows = list(csv.DictReader(handle))
            self.assertEqual(len(analyst_rows), 2)
            self.assertEqual(analyst_rows[0]["segment_id"], "seg-2")
            self.assertEqual(analyst_rows[0]["score_rank_desc"], "1")
            self.assertEqual(analyst_rows[0]["public_score_band"], "very_high")
            self.assertEqual(analyst_rows[1]["public_score_band"], "low")

            public_payload = json.loads(public_geojson_path.read_text(encoding="utf-8"))
            self.assertEqual(public_payload["type"], "FeatureCollection")
            self.assertEqual(len(public_payload["features"]), 2)
            public_props = public_payload["features"][0]["properties"]
            self.assertIn("public_score_index", public_props)
            self.assertNotIn("predicted_crash_count", public_props)
