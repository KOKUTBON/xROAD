from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.scenario_countermeasures import build_scenario_countermeasure_bundle


class ScenarioCountermeasureTests(unittest.TestCase):
    def test_build_scenario_countermeasure_bundle_writes_ranked_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_summary_path = root / "dashboard_summary.json"
            output_dir = root / "scenario_countermeasures"
            run_dir = root / "prediction_store" / "demo_bari_run"
            run_dir.mkdir(parents=True, exist_ok=True)

            analyst_csv_path = run_dir / "segment_scores_analyst.csv"
            with analyst_csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "segment_score_id",
                        "segment_id",
                        "name",
                        "highway",
                        "maxspeed",
                        "lanes",
                        "segment_length_m",
                        "public_score_band",
                        "public_score_index",
                        "predicted_crash_count",
                    ],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "segment_score_id": "demo_bari_run:2021:seg-1",
                            "segment_id": "drive:1:2:0",
                            "name": "['Tangenziale Demo']",
                            "highway": "['trunk']",
                            "maxspeed": "['70']",
                            "lanes": "['3']",
                            "segment_length_m": "260",
                            "public_score_band": "very_high",
                            "public_score_index": "100",
                            "predicted_crash_count": "4.0",
                        },
                        {
                            "segment_score_id": "demo_bari_run:2021:seg-2",
                            "segment_id": "drive:2:3:0",
                            "name": "['Tangenziale Demo']",
                            "highway": "['primary']",
                            "maxspeed": "['60']",
                            "lanes": "['2']",
                            "segment_length_m": "180",
                            "public_score_band": "very_high",
                            "public_score_index": "96",
                            "predicted_crash_count": "3.2",
                        },
                        {
                            "segment_score_id": "demo_bari_run:2021:seg-3",
                            "segment_id": "drive:3:4:0",
                            "name": "['Via Demo']",
                            "highway": "['secondary']",
                            "maxspeed": "['50']",
                            "lanes": "['2']",
                            "segment_length_m": "120",
                            "public_score_band": "high",
                            "public_score_index": "88",
                            "predicted_crash_count": "1.5",
                        },
                    ]
                )

            public_geojson_path = run_dir / "segment_scores_public.geojson"
            public_geojson_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.0, 0.0], [1.0, 0.0]],
                                },
                                "properties": {
                                    "segment_score_id": "demo_bari_run:2021:seg-1",
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[1.0, 0.0], [2.0, 0.0]],
                                },
                                "properties": {
                                    "segment_score_id": "demo_bari_run:2021:seg-2",
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[0.0, 0.5], [1.0, 0.5]],
                                },
                                "properties": {
                                    "segment_score_id": "demo_bari_run:2021:seg-3",
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            segment_manifest_path = run_dir / "segment_scores.manifest.json"
            segment_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "analyst_csv_path": str(analyst_csv_path),
                            "public_geojson_path": str(public_geojson_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            signal_nodes_path = root / "traffic_signal_nodes.geojson"
            signal_nodes_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [1.0, 0.05]},
                                "properties": {
                                    "node_object_id": "it-bari-signal-1",
                                    "junction_id": "it-bari-signal-1",
                                    "object_type": "traffic_signal",
                                    "node_role": "signalized_junction",
                                    "name": "Signal Demo",
                                    "segment_id": "drive:2:3:0",
                                    "signal_type": "controller",
                                },
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            node_objects_path = root / "road_node_objects.geojson"
            node_objects_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [0.2, 0.0]},
                                "properties": {
                                    "node_object_id": "it-bari-crossing-1",
                                    "junction_id": "it-bari-crossing-1",
                                    "object_type": "crossing",
                                    "node_role": "pedestrian_crossing",
                                    "name": "Crossing Demo",
                                    "segment_id": "drive:1:2:0",
                                    "crossing_type": "uncontrolled",
                                    "crossing_markings": "yes",
                                    "crossing_signals": None,
                                },
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [1.1, 0.0]},
                                "properties": {
                                    "node_object_id": "it-bari-junction-1",
                                    "junction_id": "it-bari-junction-1",
                                    "object_type": "unsignalized_junction",
                                    "node_role": "unsignalized_junction",
                                    "name": "Junction Demo",
                                    "segment_id": "drive:2:3:0",
                                },
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            dashboard_summary_path.write_text(
                json.dumps(
                    {
                        "published_runs": [
                            {
                                "city_key": "bari",
                                "display_name": "Demo Bari",
                                "prediction_run_label": "demo_bari_run",
                                "segment_scores": {
                                    "manifest_path": str(segment_manifest_path),
                                },
                                "score_tiles": {},
                            }
                        ],
                        "intervention_shortlists": [
                            {
                                "city_key": "bari",
                                "display_name": "Demo Bari",
                                "prediction_run_label": "demo_bari_run",
                                "top_corridors": [
                                    {
                                        "corridor_label": "Tangenziale Demo",
                                        "focus_segment_score_ids": [
                                            "demo_bari_run:2021:seg-1",
                                            "demo_bari_run:2021:seg-2",
                                        ],
                                    }
                                ],
                                "hotspot_tiles": [
                                    {
                                        "tile_score_id": "demo_bari_run:2021:tile-1",
                                        "focus_segment_score_ids": [
                                            "demo_bari_run:2021:seg-2",
                                            "demo_bari_run:2021:seg-3",
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            payload = build_scenario_countermeasure_bundle(
                dashboard_summary_path=dashboard_summary_path,
                output_dir=output_dir,
                prediction_run_labels=["demo_bari_run"],
                signal_nodes_path=signal_nodes_path,
                node_objects_path=node_objects_path,
            )

            self.assertEqual(
                payload["scenario_countermeasure_bundle_version"],
                "scenario_countermeasure_bundle_v1",
            )
            self.assertEqual(payload["scenario_bundle_count"], 1)
            library_path = output_dir / "intervention_library.json"
            index_path = output_dir / "scenario_countermeasure_index.json"
            bundle_dir = output_dir / "demo_bari_run"
            spec_path = bundle_dir / "scenario_spec.json"
            bundle_path = bundle_dir / "scenario_bundle.json"
            markdown_path = bundle_dir / "scenario_bundle.md"
            delta_csv_path = bundle_dir / "scenario_segment_deltas.csv"
            self.assertTrue(library_path.exists())
            self.assertTrue(index_path.exists())
            self.assertTrue(spec_path.exists())
            self.assertTrue(bundle_path.exists())
            self.assertTrue(markdown_path.exists())
            self.assertTrue(delta_csv_path.exists())

            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            self.assertEqual(spec["scenario_spec_version"], "scenario_spec_v1")
            asset_types = {
                asset["asset_type"]
                for scenario in spec["scenarios"]
                for asset in scenario["target_assets"]
            }
            self.assertTrue({"segment", "signal", "crossing", "junction"}.issubset(asset_types))

            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(bundle["stats"]["scenario_count"], 6)
            self.assertGreaterEqual(bundle["stats"]["portfolio_count"], 1)
            self.assertTrue(bundle["planning_brief_summary"]["recommended_scenario"]["scenario_id"])
            self.assertTrue(bundle["planning_brief_summary"]["recommended_portfolio"]["title"])

            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# Demo Bari Scenario Countermeasure Bundle", markdown)
            self.assertIn("Top Portfolios", markdown)
