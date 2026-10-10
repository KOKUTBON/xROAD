from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_workbook_completion import (
    build_bari_signal_phase_support_workbook_completion_bundle,
)


class SignalPhaseSupportWorkbookCompletionTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_workbook_completion_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_workbook_completion"
            runtime_execution_path = (
                root / "signal_phase_support_runtime_action_execution_bundle.json"
            )
            writeback_path = root / "signal_phase_support_writeback_bundle.json"
            manual_workbook_path = root / "arm_phase_mapping_sheet_workbook.csv"
            pedestrian_workbook_path = root / "pedestrian_stage_mapping_sheet_workbook.csv"
            manual_delivery_path = root / "arm_phase_mapping_sheet_delivery.csv"
            pedestrian_delivery_path = root / "pedestrian_stage_mapping_sheet_delivery.csv"

            runtime_execution_path.write_text(
                json.dumps(
                    {
                        "execution_ready_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "final_action_category": "support_fill_workbook_now",
                                "execution_route": "support_workbook_fill",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": str(manual_workbook_path),
                                "execution_summary": "Complete workbook rows.",
                                "execution_packet_md_path": "/tmp/request_01.md",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_02",
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "final_action_category": "support_runtime_rerun_now",
                                "execution_route": "support_runtime_rerun",
                                "execution_target_kind": "support_runtime_cycle_command",
                                "execution_target": "run support runtime",
                                "execution_summary": "Rerun support runtime.",
                                "execution_packet_md_path": "/tmp/request_02.md",
                            },
                        ],
                        "internal_hold_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_03",
                                "request_id": "bari_signal_phase_03",
                                "junction_id": "it-bari-signal-95",
                                "signal_name": "Signal 95",
                                "final_action_category": "support_request_complete",
                                "hold_reason": "Already complete.",
                                "execution_packet_md_path": "/tmp/request_03.md",
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            writeback_path.write_text(
                json.dumps(
                    {
                        "manual_mapping_workbook_path": str(manual_workbook_path),
                        "pedestrian_mapping_workbook_path": str(pedestrian_workbook_path),
                        "manual_delivery_path": str(manual_delivery_path),
                        "pedestrian_delivery_path": str(pedestrian_delivery_path),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manual_fields = [
                "request_id",
                "junction_id",
                "signal_name",
                "signal_type",
                "incoming_arm_id",
                "movement_turn",
                "phase_id",
                "stage_id",
                "protection_state",
                "outgoing_arm_id",
                "pedestrian_stage_flag",
                "source_crash_total",
                "source_injury_total",
                "source_peak_year",
                "source_peak_year_crash_count",
                "source_candidate_target_arm_catalog",
                "support_artifact_path",
                "validation_manifest_path",
                "manual_mapping_hint",
            ]
            with manual_workbook_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=manual_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Signal 93",
                        "signal_type": "traffic_signal",
                        "incoming_arm_id": "arm-a",
                        "movement_turn": "left",
                        "source_crash_total": "50",
                        "source_injury_total": "24",
                        "source_peak_year": "2024",
                        "source_peak_year_crash_count": "18",
                        "source_candidate_target_arm_catalog": "arm-b|arm-c",
                        "support_artifact_path": "/tmp/support.pdf",
                        "validation_manifest_path": "/tmp/validation.manifest.json",
                        "manual_mapping_hint": "Use stage plan.",
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Signal 93",
                        "signal_type": "traffic_signal",
                        "incoming_arm_id": "arm-ready",
                        "movement_turn": "right",
                        "phase_id": "P2",
                        "stage_id": "S2",
                        "protection_state": "protected",
                        "source_crash_total": "10",
                    }
                )
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_99",
                        "junction_id": "it-bari-signal-99",
                        "signal_name": "Signal 99",
                        "signal_type": "traffic_signal",
                        "incoming_arm_id": "arm-other",
                        "movement_turn": "through",
                        "source_crash_total": "100",
                    }
                )

            pedestrian_fields = [
                "request_id",
                "junction_id",
                "signal_name",
                "signal_type",
                "node_object_id",
                "movement_turn",
                "phase_id",
                "stage_id",
                "protection_state",
                "pedestrian_stage_flag",
                "source_crash_total",
                "source_injury_total",
                "source_peak_year",
                "source_peak_year_crash_count",
                "support_artifact_path",
                "validation_manifest_path",
                "manual_mapping_hint",
            ]
            with pedestrian_workbook_path.open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=pedestrian_fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Signal 93",
                        "signal_type": "traffic_signal",
                        "node_object_id": "crossing-a",
                        "movement_turn": "cross",
                        "pedestrian_stage_flag": "true",
                        "source_crash_total": "1",
                        "source_injury_total": "1",
                        "source_peak_year": "2024",
                        "source_peak_year_crash_count": "1",
                    }
                )

            manual_delivery_path.write_text(
                "junction_id,incoming_arm_id,movement_turn,phase_id,stage_id,protection_state\n",
                encoding="utf-8",
            )
            pedestrian_delivery_path.write_text(
                "junction_id,node_object_id,movement_turn,phase_id,stage_id,protection_state\n",
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_workbook_completion_bundle(
                output_dir=output_dir,
                signal_phase_support_runtime_action_execution_bundle_path=runtime_execution_path,
                signal_phase_support_writeback_bundle_path=writeback_path,
            )

            self.assertEqual(
                manifest["source"]["adapter"],
                "bari_signal_phase_support_workbook_completion_builder",
            )
            self.assertEqual(manifest["stats"]["request_count"], 3)
            self.assertEqual(manifest["stats"]["workbook_fill_request_count"], 1)
            self.assertEqual(manifest["stats"]["completion_row_count"], 2)
            self.assertEqual(manifest["stats"]["manual_completion_row_count"], 1)
            self.assertEqual(manifest["stats"]["pedestrian_completion_row_count"], 1)
            self.assertEqual(manifest["stats"]["non_workbook_execution_count"], 1)
            self.assertEqual(manifest["stats"]["hold_request_count"], 1)
            self.assertEqual(manifest["stats"]["total_crash_weight"], 51)
            self.assertEqual(manifest["stats"]["top_completion_crash_total"], 50)

            with (output_dir / "workbook_completion_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                completion_rows = list(csv.DictReader(handle))
            self.assertEqual(len(completion_rows), 2)
            self.assertEqual(completion_rows[0]["profile_id"], "arm_phase_mapping_sheet")
            self.assertEqual(completion_rows[0]["row_number"], "1")
            self.assertEqual(completion_rows[0]["completion_priority_rank"], "1")
            self.assertEqual(
                completion_rows[0]["required_fields_missing"],
                "phase_id|stage_id|protection_state",
            )
            self.assertEqual(
                completion_rows[0]["recommended_fields_missing"],
                "outgoing_arm_id",
            )
            self.assertEqual(
                completion_rows[1]["profile_id"],
                "pedestrian_stage_mapping_sheet",
            )

            with (output_dir / "non_workbook_execution_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                non_workbook_rows = list(csv.DictReader(handle))
            self.assertEqual(non_workbook_rows[0]["request_id"], "bari_signal_phase_02")
            self.assertEqual(
                non_workbook_rows[0]["execution_route"], "support_runtime_rerun"
            )

            with (output_dir / "workbook_completion_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(hold_rows[0]["request_id"], "bari_signal_phase_03")


if __name__ == "__main__":
    unittest.main()
