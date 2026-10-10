from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_runtime_action_execution import (
    build_bari_signal_phase_support_runtime_action_execution_bundle,
)


class SignalPhaseSupportRuntimeActionExecutionTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_runtime_action_execution_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_runtime_action_execution"
            runtime_action_queue_path = root / "signal_phase_support_runtime_action_queue.json"

            runtime_action_queue_path.write_text(
                json.dumps(
                    {
                        "action_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "request_runtime_category": "pending_manual_resolution",
                                "action_category": "fill_support_workbook_now",
                                "final_action_category": "support_fill_workbook_now",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_route": "support_workbook_fill",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": "/tmp/arm.csv",
                                "request_packet_md_path": "/tmp/request_01.md",
                                "packet_md_path": "/tmp/packet_01.md",
                                "handoff_target_kind": "support_workbook_csv",
                                "handoff_target_path": "/tmp/arm.csv",
                                "handoff_command": "validate arm workbook",
                                "handoff_instructions": "Fill workbook rows.",
                                "action_summary": "Fill workbook rows.",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_02",
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Signal 94",
                                "request_runtime_category": "ready_for_validation",
                                "action_category": "validate_support_delivery_now",
                                "final_action_category": "support_runtime_rerun_now",
                                "due_now": "yes",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "execution_route": "support_runtime_rerun",
                                "execution_target_kind": "support_runtime_cycle_command",
                                "execution_target": "run support runtime",
                                "request_packet_md_path": "/tmp/request_02.md",
                                "packet_md_path": "/tmp/packet_02.md",
                                "handoff_target_kind": "support_runtime_cycle_command",
                                "handoff_target_path": "/tmp/runtime.manifest.json",
                                "handoff_command": "run support runtime",
                                "handoff_instructions": "Rerun support runtime.",
                                "action_summary": "Rerun support runtime.",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_03",
                                "request_id": "bari_signal_phase_03",
                                "junction_id": "it-bari-signal-84",
                                "signal_name": "Signal 84",
                                "request_runtime_category": "validation_review_required",
                                "action_category": "review_support_validation_results",
                                "final_action_category": "support_validation_review_now",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_route": "support_validation_review",
                                "execution_target_kind": "support_request_packet",
                                "execution_target": "/tmp/request_03.md",
                                "request_packet_md_path": "/tmp/request_03.md",
                                "packet_md_path": "/tmp/packet_03.md",
                                "handoff_target_kind": "support_request_packet",
                                "handoff_target_path": "/tmp/request_03.md",
                                "handoff_command": "run support runtime",
                                "handoff_instructions": "Review packet.",
                                "action_summary": "Review validation packet.",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_04",
                                "request_id": "bari_signal_phase_04",
                                "junction_id": "it-bari-signal-67",
                                "signal_name": "Signal 67",
                                "request_runtime_category": "validation_review_required",
                                "action_category": "repair_support_delivery",
                                "final_action_category": "support_repair_workbook_now",
                                "due_now": "yes",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "execution_route": "support_workbook_repair",
                                "execution_target_kind": "support_workbook_csv",
                                "execution_target": "/tmp/repair.csv",
                                "request_packet_md_path": "/tmp/request_04.md",
                                "packet_md_path": "/tmp/packet_04.md",
                                "handoff_target_kind": "support_workbook_csv",
                                "handoff_target_path": "/tmp/repair.csv",
                                "handoff_command": "validate repair workbook",
                                "handoff_instructions": "Repair workbook.",
                                "action_summary": "Repair workbook rows.",
                            },
                        ],
                        "action_hold_queue": [
                            {
                                "support_request_reference": "bari_signal_phase_05",
                                "request_id": "bari_signal_phase_05",
                                "junction_id": "it-bari-signal-57",
                                "signal_name": "Signal 57",
                                "request_runtime_category": "accepted_pending_apply",
                                "action_category": "support_apply_pending_refresh",
                                "final_action_category": "support_apply_pending_refresh",
                                "due_now": "no",
                                "dominant_profile_id": "arm_phase_mapping_sheet",
                                "request_packet_md_path": "/tmp/request_05.md",
                                "packet_md_path": "/tmp/packet_05.md",
                                "action_summary": "Waiting for apply refresh.",
                            },
                            {
                                "support_request_reference": "bari_signal_phase_06",
                                "request_id": "bari_signal_phase_06",
                                "junction_id": "it-bari-signal-27",
                                "signal_name": "Signal 27",
                                "request_runtime_category": "fully_applied_to_movement_layer",
                                "action_category": "support_request_complete",
                                "final_action_category": "support_request_complete",
                                "due_now": "no",
                                "dominant_profile_id": "pedestrian_stage_mapping_sheet",
                                "request_packet_md_path": "/tmp/request_06.md",
                                "packet_md_path": "/tmp/packet_06.md",
                                "action_summary": "Already complete.",
                            },
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_runtime_action_execution_bundle(
                output_dir=output_dir,
                signal_phase_support_runtime_action_queue_path=runtime_action_queue_path,
            )

            self.assertEqual(
                manifest["source"]["adapter"],
                "bari_signal_phase_support_runtime_action_execution_builder",
            )
            self.assertEqual(manifest["stats"]["request_count"], 6)
            self.assertEqual(manifest["stats"]["execution_ready_count"], 4)
            self.assertEqual(manifest["stats"]["internal_hold_count"], 2)
            self.assertEqual(manifest["stats"]["workbook_fill_request_count"], 1)
            self.assertEqual(manifest["stats"]["runtime_rerun_request_count"], 1)
            self.assertEqual(manifest["stats"]["validation_review_request_count"], 1)
            self.assertEqual(manifest["stats"]["repair_request_count"], 1)
            self.assertEqual(manifest["stats"]["apply_pending_hold_count"], 1)
            self.assertEqual(manifest["stats"]["complete_hold_count"], 1)

            with (output_dir / "action_execution_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_rows), 4)
            self.assertEqual(ready_rows[0]["request_id"], "bari_signal_phase_04")
            by_request = {row["request_id"]: row for row in ready_rows}
            self.assertEqual(
                by_request["bari_signal_phase_01"]["execution_route"],
                "support_workbook_fill",
            )
            self.assertEqual(
                by_request["bari_signal_phase_02"]["execution_route"],
                "support_runtime_rerun",
            )
            self.assertEqual(
                by_request["bari_signal_phase_03"]["execution_route"],
                "support_validation_review",
            )
            self.assertEqual(
                by_request["bari_signal_phase_04"]["execution_route"],
                "support_workbook_repair",
            )

            with (output_dir / "action_internal_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))
            hold_by_request = {row["request_id"]: row for row in hold_rows}
            self.assertEqual(
                hold_by_request["bari_signal_phase_05"]["final_action_category"],
                "support_apply_pending_refresh",
            )
            self.assertEqual(
                hold_by_request["bari_signal_phase_06"]["final_action_category"],
                "support_request_complete",
            )


if __name__ == "__main__":
    unittest.main()
