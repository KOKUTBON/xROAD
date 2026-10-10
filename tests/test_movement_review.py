from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.movement_review import build_bari_movement_review_pack


class MovementReviewTests(unittest.TestCase):
    def test_build_bari_movement_review_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import Point  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            movement_objects_path = root / "road_movement_objects.geojson"
            matched_records_path = root / "matched_node_records.jsonl"
            aggregate_path = root / "node_year_metrics.csv"
            signal_nodes_path = root / "traffic_signal_nodes.geojson"
            output_dir = root / "movement_review"

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "m-amb-signal",
                        "junction_id": "sig-1",
                        "name": "Via A [straight]",
                        "movement_role": "signalized_turn_movement",
                        "movement_turn": "straight",
                        "movement_resolution_state": "ambiguous_target_variant",
                        "movement_resolution_method": "bearing_and_continuity_unresolved",
                        "candidate_target_arm_count": 2,
                        "candidate_target_arm_catalog": "seg-a:end@E | seg-b:end@E",
                        "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                        "signal_priority_variant": "signal_phase_unknown",
                        "control_state": "signalized",
                        "segment_name": "Via A",
                        "segment_ref": "SS16",
                        "geometry": Point(16.87, 41.11),
                    },
                    {
                        "node_object_id": "m-heur",
                        "junction_id": "j-1",
                        "name": "Via B [left]",
                        "movement_role": "unsignalized_turn_movement",
                        "movement_turn": "left",
                        "movement_resolution_state": "heuristic_target_resolution",
                        "movement_resolution_method": "bearing_and_continuity_rank",
                        "candidate_target_arm_count": 2,
                        "candidate_target_arm_catalog": "seg-c:end@N | seg-d:end@NW",
                        "movement_target_rank": 1,
                        "movement_target_score": 55.0,
                        "movement_target_heading_delta_deg": 4.0,
                        "movement_target_continuity_flags": "shared_ref | shared_name",
                        "phase_priority_group": "major_minor_priority_crossing_turn",
                        "signal_priority_variant": "major_minor_priority",
                        "control_state": "unsignalized_multi_arm",
                        "segment_name": "Via B",
                        "segment_ref": "",
                        "geometry": Point(16.871, 41.111),
                    },
                    {
                        "node_object_id": "m-cross",
                        "junction_id": "sig-1",
                        "name": "Crossing A",
                        "movement_role": "pedestrian_crossing",
                        "movement_turn": "cross",
                        "movement_resolution_state": "crossing_zone_equivalent",
                        "movement_resolution_method": "crossing_zone_center",
                        "candidate_target_arm_count": 0,
                        "candidate_target_arm_catalog": None,
                        "phase_priority_group": "signalized_pedestrian_stage",
                        "signal_priority_variant": "pedestrian_signalized",
                        "control_state": "signalized",
                        "segment_name": "Via A",
                        "segment_ref": "SS16",
                        "geometry": Point(16.872, 41.112),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(movement_objects_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "sig-1",
                        "name": "Via A - Via B",
                        "signal_type": "ITS",
                        "geometry": Point(16.87, 41.11),
                    }
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(signal_nodes_path, driver="GeoJSON")

            with aggregate_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["node_object_id", "occurred_year", "crash_count", "injuries_total"],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"node_object_id": "m-amb-signal", "occurred_year": 2024, "crash_count": 4, "injuries_total": 2},
                        {"node_object_id": "m-amb-signal", "occurred_year": 2023, "crash_count": 1, "injuries_total": 1},
                        {"node_object_id": "m-heur", "occurred_year": 2024, "crash_count": 2, "injuries_total": 1},
                        {"node_object_id": "m-cross", "occurred_year": 2024, "crash_count": 3, "injuries_total": 1},
                    ]
                )

            with matched_records_path.open("w", encoding="utf-8") as handle:
                for movement_id, junction_id, repeats in [
                    ("m-amb-signal", "sig-1", 5),
                    ("m-heur", "j-1", 2),
                    ("m-cross", "sig-1", 3),
                ]:
                    for index in range(repeats):
                        handle.write(
                            json.dumps(
                                {
                                    "crash_id": f"{movement_id}-{index}",
                                    "node_object_id": movement_id,
                                    "junction_id": junction_id,
                                }
                            )
                            + "\n"
                        )

            manifest = build_bari_movement_review_pack(
                output_dir=output_dir,
                movement_objects_path=movement_objects_path,
                matched_records_path=matched_records_path,
                aggregate_path=aggregate_path,
                signal_nodes_path=signal_nodes_path,
                top_n=5,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_movement_review_builder")
            self.assertEqual(manifest["stats"]["movement_object_count"], 3)
            self.assertEqual(manifest["stats"]["unresolved_movement_count"], 1)
            self.assertEqual(manifest["stats"]["heuristic_resolved_movement_count"], 1)
            self.assertEqual(manifest["stats"]["signal_phase_review_row_count"], 1)

            with (output_dir / "unresolved_target_review.csv").open(encoding="utf-8") as handle:
                unresolved_rows = list(csv.DictReader(handle))
            self.assertEqual(len(unresolved_rows), 1)
            self.assertEqual(unresolved_rows[0]["node_object_id"], "m-amb-signal")
            self.assertEqual(int(unresolved_rows[0]["total_crashes"]), 5)

            with (output_dir / "heuristic_target_review.csv").open(encoding="utf-8") as handle:
                heuristic_rows = list(csv.DictReader(handle))
            self.assertEqual(len(heuristic_rows), 1)
            self.assertEqual(heuristic_rows[0]["node_object_id"], "m-heur")
            self.assertEqual(heuristic_rows[0]["movement_resolution_method"], "bearing_and_continuity_rank")

            with (output_dir / "signal_phase_readiness.csv").open(encoding="utf-8") as handle:
                phase_rows = list(csv.DictReader(handle))
            self.assertEqual(len(phase_rows), 1)
            self.assertEqual(phase_rows[0]["junction_id"], "sig-1")
            self.assertEqual(int(phase_rows[0]["signalized_movement_count"]), 2)
            self.assertEqual(int(phase_rows[0]["signalized_crash_total"]), 8)
            self.assertEqual(phase_rows[0]["timing_data_status"], "missing_from_current_sources")

            review_payload = json.loads((output_dir / "movement_review_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(review_payload["summary"]["unresolved_crash_total"], 5)
            self.assertEqual(review_payload["top_unresolved_movements"][0]["node_object_id"], "m-amb-signal")
            self.assertEqual(review_payload["signal_phase_readiness"][0]["signal_name"], "Via A - Via B")
