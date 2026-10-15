from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.governance_interoperability import build_governance_interoperability_bundle
from road_risk_modeling.public_score_tiles import aggregate_public_score_tiles


class PublicScoreTilesTests(unittest.TestCase):
    def test_aggregate_public_score_tiles_writes_public_tile_outputs(self) -> None:
        try:
            import geopandas  # noqa: F401
            import shapely  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("Geospatial stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_scores_path = root / "segment_scores_public.geojson"
            store_manifest_path = root / "segment_scores.manifest.json"
            output_dir = root / "tiles"
            governance_dir = root / "governance"

            public_scores_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[16.85, 41.11], [16.851, 41.111]]},
                                "properties": {
                                    "segment_score_id": "run:2021:seg-1",
                                    "segment_id": "seg-1",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 96.0,
                                    "public_score_band": "very_high",
                                    "score_decile": 1,
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[16.8512, 41.1112], [16.8522, 41.1122]]},
                                "properties": {
                                    "segment_score_id": "run:2021:seg-2",
                                    "segment_id": "seg-2",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 82.0,
                                    "public_score_band": "high",
                                    "score_decile": 2,
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "LineString", "coordinates": [[16.87, 41.13], [16.871, 41.131]]},
                                "properties": {
                                    "segment_score_id": "run:2021:seg-3",
                                    "segment_id": "seg-3",
                                    "occurred_year": 2021,
                                    "prediction_run_label": "demo_run",
                                    "prediction_task": "segment_frequency_baseline",
                                    "public_score_index": 48.0,
                                    "public_score_band": "low",
                                    "score_decile": 6,
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            store_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "public_contract_version": "segment_scores_public_v1",
                        },
                        "stats": {
                            "segment_score_rows": 3,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            build_governance_interoperability_bundle(governance_dir)

            result = aggregate_public_score_tiles(
                public_scores_path=public_scores_path,
                prediction_store_manifest_path=store_manifest_path,
                output_dir=output_dir,
                tile_size_m=500.0,
                governance_bundle_path=governance_dir / "governance_interoperability_bundle.json",
            )

            manifest_path = Path(result["manifest_path"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["prediction_store_version"], "segment_score_tiles_v1")
            self.assertEqual(manifest["stats"]["tile_rows"], 2)
            self.assertEqual(manifest["stats"]["tiles_high_or_very_high"], 1)
            self.assertEqual(manifest["contract"]["public_contract_version"], "segment_score_tiles_public_v1")
            self.assertEqual(manifest["lineage"]["lineage_contract_version"], "artifact_lineage_v1")
            self.assertIn("segment_score_tiles_public_geojson", manifest["governance"]["artifact_family_ids"])

            summary_path = output_dir / "score_tiles_summary.csv"
            public_geojson_path = output_dir / "score_tiles_public.geojson"
            self.assertTrue(summary_path.exists())
            self.assertTrue(public_geojson_path.exists())

            with summary_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["tile_segment_count"], "2")
            self.assertEqual(rows[0]["tile_public_score_band"], "very_high")

            public_payload = json.loads(public_geojson_path.read_text(encoding="utf-8"))
            self.assertEqual(public_payload["type"], "FeatureCollection")
            self.assertEqual(len(public_payload["features"]), 2)
            props = public_payload["features"][0]["properties"]
            self.assertIn("tile_max_public_score_index", props)
            self.assertNotIn("tile_col", props)
