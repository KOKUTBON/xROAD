from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_runtime_rehearsal import (
    run_bari_signal_phase_runtime_rehearsal,
)


class SignalPhaseRuntimeRehearsalTest(unittest.TestCase):
    def test_run_bari_signal_phase_runtime_rehearsal_injects_send_and_compares_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "runtime_rehearsal"
            intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_log_repair_log_path = root / "dispatch_log_repair_log.csv"

            intake_bundle_path.write_text("{}", encoding="utf-8")
            delivery_receipt_register_path.write_text("dispatch_reference\n", encoding="utf-8")
            delivery_checklist_path.write_text("delivery_item_id\n", encoding="utf-8")
            movement_objects_path.write_text("{}", encoding="utf-8")
            dispatch_execution_queue_path.write_text("request_id\n", encoding="utf-8")
            follow_up_tracker_path.write_text("request_id\n", encoding="utf-8")
            dispatch_bundle_path.write_text("{}", encoding="utf-8")
            dispatch_log_repair_queue_path.write_text("request_id\n", encoding="utf-8")
            dispatch_log_repair_log_path.write_text("request_id\n", encoding="utf-8")

            def _write_runtime_state(
                cycle_output_dir: Path,
                *,
                request_action_category: str,
                request_dispatch_status: str,
                request_response_status: str,
                operator_queue_type: str,
                operator_execution_route: str,
            ) -> None:
                action_queue_dir = cycle_output_dir / "dispatch_cycle" / "runtime_action_queue"
                action_queue_dir.mkdir(parents=True, exist_ok=True)
                action_payload = {
                    "action_queue": [
                        {
                            "request_id": "bari_signal_phase_01",
                            "signal_name": "Signal 93",
                            "priority_rank": 1,
                            "action_category": request_action_category,
                            "dispatch_status": request_dispatch_status,
                            "response_status": request_response_status,
                            "due_now": request_action_category == "dispatch_request_now",
                            "source_stage": "dispatch",
                        },
                        {
                            "request_id": "bari_signal_phase_02",
                            "signal_name": "Signal 94",
                            "priority_rank": 2,
                            "action_category": "dispatch_request_now",
                            "dispatch_status": "pending_dispatch",
                            "response_status": "awaiting_send",
                            "due_now": True,
                            "source_stage": "dispatch",
                        },
                    ]
                }
                (action_queue_dir / "signal_phase_action_queue.json").write_text(
                    json.dumps(action_payload, indent=2, sort_keys=True),
                    encoding="utf-8",
                )

                operator_dir = cycle_output_dir / "dispatch_cycle" / "runtime_operator_board"
                operator_dir.mkdir(parents=True, exist_ok=True)
                operator_ready_queue = []
                operator_hold_queue = []
                request_row = {
                    "request_id": "bari_signal_phase_01",
                    "signal_name": "Signal 93",
                    "action_category": request_action_category,
                    "handoff_target_kind": (
                        "dispatch_execution_log" if operator_queue_type == "ready" else ""
                    ),
                    "handoff_target_path": "/tmp/dispatch_execution_log.csv"
                    if operator_queue_type == "ready"
                    else "",
                    "execution_route": operator_execution_route,
                    "hold_reason": "Waiting for delivery." if operator_queue_type == "hold" else "",
                }
                if operator_queue_type == "ready":
                    operator_ready_queue.append(request_row)
                else:
                    operator_hold_queue.append(request_row)
                operator_ready_queue.append(
                    {
                        "request_id": "bari_signal_phase_02",
                        "signal_name": "Signal 94",
                        "action_category": "dispatch_request_now",
                        "handoff_target_kind": "dispatch_execution_log",
                        "handoff_target_path": "/tmp/dispatch_execution_log.csv",
                        "execution_route": "dispatch_send",
                        "hold_reason": "",
                    }
                )
                operator_payload = {
                    "operator_ready_queue": operator_ready_queue,
                    "operator_hold_queue": operator_hold_queue,
                }
                (operator_dir / "signal_phase_operator_board_bundle.json").write_text(
                    json.dumps(operator_payload, indent=2, sort_keys=True),
                    encoding="utf-8",
                )

            def _runtime_cycle_side_effect(**kwargs):
                cycle_output_dir = Path(kwargs["output_dir"])
                cycle_output_dir.mkdir(parents=True, exist_ok=True)
                manifest_path = cycle_output_dir / "signal_phase_runtime_cycle.manifest.json"
                manifest_path.write_text(
                    json.dumps({"manifest_path": str(manifest_path)}, indent=2),
                    encoding="utf-8",
                )

                dispatch_recording_dir = cycle_output_dir / "dispatch_recording"
                dispatch_recording_dir.mkdir(parents=True, exist_ok=True)
                runtime_log_path = dispatch_recording_dir / "dispatch_execution_log.csv"

                injected_log_path = kwargs.get("dispatch_execution_log_path")
                if injected_log_path is None:
                    with runtime_log_path.open("w", encoding="utf-8", newline="") as handle:
                        writer = csv.DictWriter(
                            handle,
                            fieldnames=[
                                "dispatch_reference",
                                "request_id",
                                "junction_id",
                                "signal_name",
                                "due_date",
                                "primary_channel_value",
                                "secondary_channel_value",
                                "execution_status",
                                "execution_completed_at",
                                "execution_channel_used",
                                "execution_outcome",
                                "response_received",
                                "response_summary",
                                "protocol_reference",
                                "evidence_path",
                                "execution_notes",
                                "log_match_status",
                            ],
                        )
                        writer.writeheader()
                        writer.writerow(
                            {
                                "dispatch_reference": "BARI-SPD-20260329-01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Signal 93",
                                "due_date": "2026-03-29",
                                "primary_channel_value": "urbanistica@example.com",
                                "secondary_channel_value": "archivio@example.com",
                                "execution_status": "pending_execution",
                                "execution_completed_at": "",
                                "execution_channel_used": "",
                                "execution_outcome": "",
                                "response_received": "no",
                                "response_summary": "",
                                "protocol_reference": "",
                                "evidence_path": "",
                                "execution_notes": "",
                                "log_match_status": "matched_request_id",
                            }
                        )
                    _write_runtime_state(
                        cycle_output_dir,
                        request_action_category="dispatch_request_now",
                        request_dispatch_status="pending_dispatch",
                        request_response_status="awaiting_send",
                        operator_queue_type="ready",
                        operator_execution_route="dispatch_send",
                    )
                    return {
                        "manifest_path": str(manifest_path),
                        "stats": {
                            "runtime_dispatch_action_count": 2,
                            "runtime_operator_board_ready_count": 2,
                            "dispatch_recorded_execution_count": 0,
                            "dispatch_validated_execution_count": 0,
                            "dispatch_writeback_ready_count": 0,
                            "dispatch_recording_unresolved_signalized_movement_total": 6,
                            "dispatch_recording_unresolved_signalized_crash_total": 13,
                            "dispatch_validation_unresolved_signalized_movement_total": 6,
                            "dispatch_validation_unresolved_signalized_crash_total": 13,
                            "dispatch_validation_accepted_unresolved_signalized_crash_total": 0,
                            "dispatch_validation_rejected_unresolved_signalized_crash_total": 13,
                            "dispatch_writeback_unresolved_signalized_movement_total": 6,
                            "dispatch_writeback_unresolved_signalized_crash_total": 13,
                            "dispatch_writeback_ready_unresolved_signalized_crash_total": 0,
                            "runtime_dispatch_cycle_unresolved_signalized_crash_total": 13,
                        },
                    }

                injected_rows = []
                with Path(injected_log_path).open("r", encoding="utf-8", newline="") as handle:
                    injected_rows = list(csv.DictReader(handle))
                selected_row = next(
                    row for row in injected_rows if row["request_id"] == "bari_signal_phase_01"
                )
                self.assertEqual(selected_row["execution_status"], "sent")
                self.assertEqual(selected_row["execution_channel_used"], "pec_email")
                self.assertEqual(selected_row["execution_outcome"], "request_dispatched")
                self.assertTrue(selected_row["protocol_reference"].startswith("REHEARSAL-"))
                self.assertTrue(selected_row["execution_completed_at"])

                _write_runtime_state(
                    cycle_output_dir,
                    request_action_category="await_delivery",
                    request_dispatch_status="sent_via_pec",
                    request_response_status="awaiting_delivery",
                    operator_queue_type="hold",
                    operator_execution_route="",
                )
                runtime_log_path.write_text(Path(injected_log_path).read_text(encoding="utf-8"), encoding="utf-8")
                return {
                    "manifest_path": str(manifest_path),
                    "stats": {
                        "runtime_dispatch_action_count": 1,
                        "runtime_operator_board_ready_count": 1,
                        "dispatch_recorded_execution_count": 1,
                        "dispatch_validated_execution_count": 1,
                        "dispatch_writeback_ready_count": 1,
                        "dispatch_recording_unresolved_signalized_movement_total": 6,
                        "dispatch_recording_unresolved_signalized_crash_total": 13,
                        "dispatch_validation_unresolved_signalized_movement_total": 6,
                        "dispatch_validation_unresolved_signalized_crash_total": 13,
                        "dispatch_validation_accepted_unresolved_signalized_crash_total": 13,
                        "dispatch_validation_rejected_unresolved_signalized_crash_total": 0,
                        "dispatch_writeback_unresolved_signalized_movement_total": 6,
                        "dispatch_writeback_unresolved_signalized_crash_total": 13,
                        "dispatch_writeback_ready_unresolved_signalized_crash_total": 13,
                        "runtime_dispatch_cycle_unresolved_signalized_crash_total": 13,
                    },
                }

            with patch(
                "road_risk_modeling.signal_phase_runtime_rehearsal.run_bari_signal_phase_runtime_cycle",
                side_effect=_runtime_cycle_side_effect,
            ) as runtime_cycle_mock:
                result = run_bari_signal_phase_runtime_rehearsal(
                    output_dir=output_dir,
                    request_id="bari_signal_phase_01",
                    signal_phase_delivery_intake_bundle_path=intake_bundle_path,
                    delivery_receipt_register_path=delivery_receipt_register_path,
                    delivery_checklist_path=delivery_checklist_path,
                    movement_objects_path=movement_objects_path,
                    dispatch_execution_queue_path=dispatch_execution_queue_path,
                    follow_up_tracker_path=follow_up_tracker_path,
                    signal_phase_dispatch_bundle_path=dispatch_bundle_path,
                    dispatch_log_repair_queue_path=dispatch_log_repair_queue_path,
                    dispatch_log_repair_log_path=dispatch_log_repair_log_path,
                    preview_limit=5,
                )

            self.assertEqual(runtime_cycle_mock.call_count, 2)
            self.assertEqual(result["stats"]["pre_runtime_dispatch_action_count"], 2)
            self.assertEqual(result["stats"]["post_runtime_dispatch_action_count"], 1)
            self.assertEqual(result["stats"]["selected_request_changed"], "yes")
            self.assertEqual(result["stats"]["selected_request_left_dispatch_action"], "yes")
            self.assertEqual(result["stats"]["selected_request_left_dispatch_send"], "yes")
            self.assertEqual(result["stats"]["post_recorded_execution_count"], 1)
            self.assertEqual(result["stats"]["post_validated_execution_count"], 1)
            self.assertEqual(result["stats"]["post_writeback_ready_count"], 1)
            self.assertEqual(result["stats"]["pre_recording_unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["post_recording_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["pre_validation_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["pre_validation_accepted_unresolved_signalized_crash_total"], 0)
            self.assertEqual(result["stats"]["post_validation_accepted_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["pre_validation_rejected_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["post_validation_rejected_unresolved_signalized_crash_total"], 0)
            self.assertEqual(result["stats"]["post_writeback_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["pre_writeback_ready_unresolved_signalized_crash_total"], 0)
            self.assertEqual(result["stats"]["post_writeback_ready_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["post_dispatch_cycle_unresolved_signalized_crash_total"], 13)

            with (output_dir / "request_state_comparison.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            selected_row = next(
                row for row in rows if row["request_id"] == "bari_signal_phase_01"
            )
            self.assertEqual(selected_row["pre_action_category"], "dispatch_request_now")
            self.assertEqual(selected_row["post_action_category"], "await_delivery")
            self.assertEqual(selected_row["pre_operator_queue_type"], "ready")
            self.assertEqual(selected_row["post_operator_queue_type"], "hold")
            self.assertEqual(selected_row["post_dispatch_status"], "sent_via_pec")
            self.assertEqual(selected_row["post_response_status"], "awaiting_delivery")

            rehearsal_md = (output_dir / "signal_phase_runtime_rehearsal.md").read_text(encoding="utf-8")
            self.assertIn("post dispatch-cycle unresolved signalized crashes: `13`", rehearsal_md)
            self.assertIn("post validation accepted unresolved signalized crashes: `13`", rehearsal_md)


if __name__ == "__main__":
    unittest.main()
