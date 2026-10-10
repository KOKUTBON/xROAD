from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.governance_interoperability import build_governance_interoperability_bundle
from road_risk_modeling.signal_phase_intake import build_bari_signal_phase_intake_pack


class SignalPhaseIntakeTests(unittest.TestCase):
    def test_build_bari_signal_phase_intake_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_intake"
            movement_review_path = root / "movement_review_pack.json"
            signal_nodes_path = root / "traffic_signal_nodes.geojson"
            movement_objects_path = root / "road_movement_objects.geojson"
            governance_dir = root / "governance"

            movement_review_path.write_text(
                json.dumps(
                    {
                        "signal_phase_readiness": [
                            {
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                                "signal_type": "IMP. SEMAF",
                                "signalized_movement_count": 44,
                                "ambiguous_movement_count": 36,
                                "heuristic_resolved_movement_count": 0,
                                "signalized_crash_total": 59,
                                "ambiguous_crash_total": 58,
                                "heuristic_resolved_crash_total": 0,
                                "matched_crashes_at_junction_total": 59,
                                "phase_priority_groups_present": (
                                    "signalized_aligned_turn_phase_unknown | "
                                    "signalized_crossing_turn_phase_unknown | signalized_pedestrian_stage"
                                ),
                                "recommended_next_input": "controller timing plan, phase table, or stage log export",
                                "timing_data_status": "missing_from_current_sources",
                                "review_priority_score": 7104,
                            },
                            {
                                "junction_id": "it-bari-signal-10",
                                "signal_name": "TEST SIGNAL",
                                "signal_type": "IMP. SEMAF",
                                "signalized_movement_count": 10,
                                "ambiguous_movement_count": 4,
                                "heuristic_resolved_movement_count": 2,
                                "signalized_crash_total": 8,
                                "ambiguous_crash_total": 3,
                                "heuristic_resolved_crash_total": 1,
                                "matched_crashes_at_junction_total": 8,
                                "phase_priority_groups_present": "signalized_aligned_turn_phase_unknown",
                                "recommended_next_input": "controller timing plan, phase table, or stage log export",
                                "timing_data_status": "missing_from_current_sources",
                                "review_priority_score": 820,
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            signal_nodes_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "it-bari-signal-93",
                                    "name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                                    "signal_type": "IMP. SEMAF",
                                    "asset_code": "93",
                                    "source_record_id": "signal_93",
                                },
                                "geometry": {"type": "Point", "coordinates": [16.86, 41.12]},
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "it-bari-signal-10",
                                    "name": "TEST SIGNAL",
                                    "signal_type": "IMP. SEMAF",
                                    "asset_code": "10",
                                    "source_record_id": "signal_10",
                                },
                                "geometry": {"type": "Point", "coordinates": [16.81, 41.10]},
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            movement_objects_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "junction_id": "it-bari-signal-93",
                                    "movement_role": "signalized_turn_movement",
                                    "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                                    "movement_turn": "straight",
                                    "approach_arm_id": "approach_arm_01",
                                    "movement_resolution_state": "ambiguous_target_variant",
                                },
                                "geometry": {"type": "Point", "coordinates": [16.86, 41.12]},
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "junction_id": "it-bari-signal-93",
                                    "movement_role": "signalized_turn_movement",
                                    "phase_priority_group": "signalized_crossing_turn_phase_unknown",
                                    "movement_turn": "u_turn",
                                    "approach_arm_id": "approach_arm_02",
                                    "movement_resolution_state": "explicit_target",
                                },
                                "geometry": {"type": "Point", "coordinates": [16.8601, 41.1201]},
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "junction_id": "it-bari-signal-93",
                                    "movement_role": "pedestrian_crossing_movement",
                                    "phase_priority_group": "signalized_pedestrian_stage",
                                    "movement_turn": "cross",
                                    "approach_arm_id": "approach_arm_03",
                                    "movement_resolution_state": "explicit_target",
                                },
                                "geometry": {"type": "Point", "coordinates": [16.8602, 41.1202]},
                            },
                            {
                                "type": "Feature",
                                "properties": {
                                    "junction_id": "it-bari-signal-10",
                                    "movement_role": "signalized_turn_movement",
                                    "phase_priority_group": "signalized_aligned_turn_phase_unknown",
                                    "movement_turn": "left",
                                    "approach_arm_id": "approach_arm_01",
                                    "movement_resolution_state": "heuristic_target_resolution",
                                },
                                "geometry": {"type": "Point", "coordinates": [16.81, 41.10]},
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            build_governance_interoperability_bundle(governance_dir)

            manifest = build_bari_signal_phase_intake_pack(
                output_dir=output_dir,
                movement_review_path=movement_review_path,
                signal_nodes_path=signal_nodes_path,
                movement_objects_path=movement_objects_path,
                top_n=1,
                governance_bundle_path=governance_dir / "governance_interoperability_bundle.json",
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_intake_builder")
            self.assertEqual(manifest["stats"]["signal_phase_review_row_count"], 2)
            self.assertEqual(manifest["stats"]["priority_signal_export_count"], 1)
            self.assertEqual(manifest["stats"]["provider_profile_count"], 2)
            self.assertEqual(manifest["stats"]["template_count"], 4)
            self.assertEqual(manifest["stats"]["mapping_stub_count"], 4)

            report_payload = json.loads((output_dir / "signal_phase_intake_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(report_payload["top_priority_signals"][0]["junction_id"], "it-bari-signal-93")
            self.assertEqual(
                report_payload["top_priority_signals"][0]["recommended_provider_profile"],
                "controller_event_log_export",
            )

            with (output_dir / "priority_signals.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["priority_band"], "tier_1_immediate")
            self.assertIn("arm-to-phase mapping sheet", rows[0]["required_inputs"])

            self.assertTrue((output_dir / "sample_templates" / "signal_stage_plan_export_template.csv").exists())
            self.assertTrue((output_dir / "mapping_stubs" / "controller_event_log_export_mapping_stub.json").exists())
            self.assertTrue((output_dir / "sample_templates" / "junction_phase_diagram_support_template.pdf").exists())
            self.assertTrue((output_dir / "mapping_stubs" / "junction_phase_diagram_support_mapping_stub.json").exists())
            mapping_stub = json.loads(
                (output_dir / "mapping_stubs" / "controller_event_log_export_mapping_stub.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                mapping_stub["governance"]["source_family_ids"],
                ["signal_controller_event_log_export"],
            )
            self.assertIn("signal_phase_intake_pack", manifest["governance"]["artifact_family_ids"])


if __name__ == "__main__":
    unittest.main()
