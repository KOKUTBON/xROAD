from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_action_handoff import (
    build_bari_signal_phase_support_action_handoff_bundle,
)


class SignalPhaseSupportActionHandoffTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_action_handoff_bundle_routes_ready_actions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_action_handoff"
            action_execution_bundle_path = root / "signal_phase_support_action_execution_bundle.json"
            runtime_cycle_manifest_path = root / "signal_phase_support_runtime_cycle.manifest.json"
            runtime_cycle_manifest_path.write_text("{}", encoding="utf-8")

            action_execution_bundle_path.write_text(
                json.dumps(
                    {
                        "execution_ready_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "request_runtime_category": "pending_manual_resolution",
                                "action_category": "fill_support_workbook_now",
                                "execution_route": "support_workbook_fill",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "dominant_workbook_path": "/tmp/arm_workbook.csv",
                                "dominant_delivery_csv_path": "/tmp/arm_delivery.csv",
                                "dominant_validation_command": "validate arm",
                                "request_packet_md_path": "/tmp/request_01.md",
                                "runtime_command": "make run-bari-signal-phase-support-runtime-cycle",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": "/tmp/arm_workbook.csv",
                                "execution_summary": "Complete the workbook.",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_02",
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "request_runtime_category": "ready_for_validation",
                                "action_category": "validate_support_delivery_now",
                                "execution_route": "support_runtime_rerun",
                                "due_now": "yes",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "dominant_workbook_path": "/tmp/ped_workbook.csv",
                                "dominant_delivery_csv_path": "/tmp/ped_delivery.csv",
                                "dominant_validation_command": "validate ped",
                                "request_packet_md_path": "/tmp/request_02.md",
                                "runtime_command": "make run-bari-signal-phase-support-runtime-cycle",
                                "execution_target_kind": "support_runtime_command",
                                "execution_target": "make run-bari-signal-phase-support-runtime-cycle",
                                "execution_summary": "Rerun support runtime.",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_03",
                                "request_id": "bari_signal_phase_03",
                                "junction_id": "it-bari-signal-84",
                                "signal_name": "Signal 84",
                                "request_runtime_category": "validation_review_required",
                                "action_category": "review_support_validation_results",
                                "execution_route": "support_validation_review",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "dominant_workbook_path": "/tmp/review_workbook.csv",
                                "dominant_delivery_csv_path": "/tmp/review_delivery.csv",
                                "dominant_validation_command": "validate review",
                                "request_packet_md_path": "/tmp/request_03.md",
                                "runtime_command": "make run-bari-signal-phase-support-runtime-cycle",
                                "execution_summary": "Review validation output.",
                            },
                        ],
                        "internal_hold_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_04",
                                "request_id": "bari_signal_phase_04",
                                "junction_id": "it-bari-signal-67",
                                "signal_name": "Signal 67",
                                "request_runtime_category": "fully_applied_to_movement_layer",
                                "action_category": "support_request_complete",
                                "execution_route": "",
                                "due_now": "no",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "hold_reason": "The support request is already fully applied to the movement layer.",
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = build_bari_signal_phase_support_action_handoff_bundle(
                output_dir=output_dir,
                signal_phase_support_action_execution_bundle_path=action_execution_bundle_path,
                support_runtime_cycle_manifest_path=runtime_cycle_manifest_path,
            )

            self.assertEqual(result["stats"]["request_count"], 4)
            self.assertEqual(result["stats"]["handoff_ready_count"], 3)
            self.assertEqual(result["stats"]["internal_hold_count"], 1)
            self.assertEqual(result["stats"]["workbook_handoff_count"], 1)
            self.assertEqual(result["stats"]["runtime_rerun_handoff_count"], 1)
            self.assertEqual(result["stats"]["validation_review_handoff_count"], 1)
            self.assertEqual(result["stats"]["complete_hold_count"], 1)

            with (output_dir / "action_handoff_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            by_request = {row["request_id"]: row for row in ready_rows}
            self.assertEqual(
                by_request["bari_signal_phase_01"]["handoff_target_kind"],
                "support_workbook_csv",
            )
            self.assertEqual(
                by_request["bari_signal_phase_02"]["handoff_target_kind"],
                "support_runtime_cycle_command",
            )
            self.assertEqual(
                Path(by_request["bari_signal_phase_02"]["handoff_target_path"]),
                runtime_cycle_manifest_path,
            )
            self.assertEqual(
                by_request["bari_signal_phase_03"]["handoff_target_kind"],
                "support_request_packet",
            )

            with (output_dir / "action_handoff_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            self.assertEqual(hold_rows[0]["action_category"], "support_request_complete")


if __name__ == "__main__":
    unittest.main()
