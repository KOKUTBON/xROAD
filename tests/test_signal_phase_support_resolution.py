from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_resolution import (
    build_bari_signal_phase_support_resolution_bundle,
)


class SignalPhaseSupportResolutionTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_resolution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_resolution"
            movement_review_path = root / "movement_review_pack.json"
            phase_readiness_path = root / "signal_phase_readiness.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            aggregate_path = root / "node_year_metrics.csv"
            support_file_path = root / "junction_phase_diagram.pdf"
            support_manifest_path = root / "support_validation.manifest.json"
            nonsupport_manifest_path = root / "controller_validation.manifest.json"

            movement_review_path.write_text(
                json.dumps(
                    {
                        "signal_phase_readiness": [],
                        "summary": {"signal_phase_review_row_count": 1},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            with phase_readiness_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "junction_id",
                        "signal_name",
                        "signal_type",
                        "signalized_movement_count",
                        "signalized_crash_total",
                        "matched_crashes_at_junction_total",
                        "ambiguous_movement_count",
                        "phase_priority_groups_present",
                        "review_priority_score",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "junction_id": "sig-1",
                        "signal_name": "Via A - Via B",
                        "signal_type": "ITS",
                        "signalized_movement_count": 3,
                        "signalized_crash_total": 6,
                        "matched_crashes_at_junction_total": 8,
                        "ambiguous_movement_count": 2,
                        "phase_priority_groups_present": "signalized_aligned_turn_phase_unknown | signalized_pedestrian_stage",
                        "review_priority_score": 700,
                    }
                )

            movement_objects_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "m-left-a",
                                    "junction_id": "sig-1",
                                    "name": "Via A [left]",
                                    "movement_role": "signalized_turn_movement",
                                    "movement_turn": "left",
                                    "movement_resolution_state": "ambiguous_target_variant",
                                    "movement_resolution_method": "bearing_and_continuity_unresolved",
                                    "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                                    "incoming_arm_id": "arm_a",
                                    "outgoing_arm_id": "out_1",
                                    "candidate_target_arm_count": 2,
                                    "candidate_target_arm_catalog": "out_1 | out_2",
                                    "control_state": "signalized",
                                },
                                "geometry": None,
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "m-left-b",
                                    "junction_id": "sig-1",
                                    "name": "Via A [left]",
                                    "movement_role": "signalized_turn_movement",
                                    "movement_turn": "left",
                                    "movement_resolution_state": "ambiguous_target_variant",
                                    "movement_resolution_method": "bearing_and_continuity_unresolved",
                                    "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                                    "incoming_arm_id": "arm_a",
                                    "outgoing_arm_id": "out_2",
                                    "candidate_target_arm_count": 2,
                                    "candidate_target_arm_catalog": "out_1 | out_2",
                                    "control_state": "signalized",
                                },
                                "geometry": None,
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "m-ped-1",
                                    "junction_id": "sig-1",
                                    "name": "Crossing A",
                                    "movement_role": "pedestrian_crossing",
                                    "movement_turn": "cross",
                                    "movement_resolution_state": "crossing_zone_equivalent",
                                    "phase_priority_group": "signalized_pedestrian_stage",
                                    "control_state": "signalized",
                                },
                                "geometry": None,
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with aggregate_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["node_object_id", "occurred_year", "crash_count", "injuries_total"],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"node_object_id": "m-left-a", "occurred_year": 2024, "crash_count": 3, "injuries_total": 1},
                        {"node_object_id": "m-left-b", "occurred_year": 2024, "crash_count": 1, "injuries_total": 0},
                        {"node_object_id": "m-ped-1", "occurred_year": 2024, "crash_count": 2, "injuries_total": 1},
                    ]
                )

            support_file_path.write_text("support diagram placeholder\n", encoding="utf-8")
            support_manifest_path.write_text(
                json.dumps(
                    {
                        "profile": {
                            "profile_id": "junction_phase_diagram_support",
                            "profile_type": "support_artifact",
                            "profile_label": "Junction phase diagram support",
                        },
                        "inputs": {
                            "request_id": "bari_signal_phase_01",
                            "junction_id": "sig-1",
                            "input_csv_path": {"path": str(support_file_path)},
                            "mapping_stub_path": {"path": str(root / "mapping_stub.json")},
                        },
                        "outputs": {
                            "report_json_path": str(root / "support_validation.json"),
                        },
                        "stats": {
                            "validation_outcome": "accepted_support_artifact",
                            "support_file_size_bytes": 24,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            nonsupport_manifest_path.write_text(
                json.dumps(
                    {
                        "profile": {
                            "profile_id": "controller_event_log_export",
                            "profile_type": "provider_feed",
                        },
                        "stats": {
                            "validation_outcome": "accepted_for_ingestion",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_resolution_bundle(
                output_dir=output_dir,
                support_validation_manifest_paths=[support_manifest_path, nonsupport_manifest_path],
                movement_review_path=movement_review_path,
                phase_readiness_csv_path=phase_readiness_path,
                movement_objects_path=movement_objects_path,
                aggregate_path=aggregate_path,
                top_n=5,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_support_resolution_bundle_builder")
            self.assertEqual(manifest["stats"]["validation_manifest_count"], 2)
            self.assertEqual(manifest["stats"]["accepted_support_artifact_count"], 1)
            self.assertEqual(manifest["stats"]["support_request_count"], 1)
            self.assertEqual(manifest["stats"]["manual_arm_phase_review_row_count"], 1)
            self.assertEqual(manifest["stats"]["pedestrian_stage_review_row_count"], 1)
            self.assertEqual(
                manifest["stats"]["requests_with_unresolved_signalized_movements_count"],
                1,
            )
            self.assertEqual(
                manifest["stats"]["unresolved_signalized_movement_count_total"],
                1,
            )
            self.assertEqual(manifest["stats"]["unresolved_signalized_crash_total"], 4)

            with (output_dir / "support_resolution_queue.csv").open(encoding="utf-8", newline="") as handle:
                queue_rows = list(csv.DictReader(handle))
            self.assertEqual(len(queue_rows), 1)
            self.assertEqual(queue_rows[0]["request_id"], "bari_signal_phase_01")
            self.assertEqual(queue_rows[0]["support_resolution_scope"], "arm_phase_and_pedestrian_stage_resolution")
            self.assertEqual(int(queue_rows[0]["manual_arm_phase_crash_total"]), 4)
            self.assertEqual(int(queue_rows[0]["pedestrian_stage_crash_total"]), 2)
            self.assertEqual(int(queue_rows[0]["unresolved_signalized_movement_count"]), 1)
            self.assertEqual(int(queue_rows[0]["unresolved_signalized_crash_total"]), 4)

            with (output_dir / "manual_arm_phase_review.csv").open(encoding="utf-8", newline="") as handle:
                manual_rows = list(csv.DictReader(handle))
            self.assertEqual(len(manual_rows), 1)
            self.assertEqual(manual_rows[0]["incoming_arm_id"], "arm_a")
            self.assertEqual(manual_rows[0]["movement_turn"], "left")
            self.assertEqual(int(manual_rows[0]["movement_variant_count"]), 2)
            self.assertEqual(int(manual_rows[0]["crash_total"]), 4)

            with (output_dir / "pedestrian_stage_review.csv").open(encoding="utf-8", newline="") as handle:
                pedestrian_rows = list(csv.DictReader(handle))
            self.assertEqual(len(pedestrian_rows), 1)
            self.assertEqual(pedestrian_rows[0]["node_object_id"], "m-ped-1")
            self.assertEqual(int(pedestrian_rows[0]["crash_total"]), 2)

            packet_path = output_dir / "analyst_packets" / "bari_signal_phase_01.md"
            self.assertTrue(packet_path.exists())

            payload = json.loads((output_dir / "signal_phase_support_resolution_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["support_request_count"], 1)
            self.assertEqual(payload["summary"]["unresolved_signalized_movement_count_total"], 1)
            self.assertEqual(payload["summary"]["unresolved_signalized_crash_total"], 4)
            self.assertEqual(payload["support_resolution_requests"][0]["signal_name"], "Via A - Via B")

            report_md = (output_dir / "signal_phase_support_resolution_bundle.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("unresolved signalized crashes: `4`", report_md)
