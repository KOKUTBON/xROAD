from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_follow_up_cycle import (
    run_bari_signal_phase_follow_up_cycle,
)


class SignalPhaseFollowUpCycleTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_run_bari_signal_phase_follow_up_cycle_promotes_to_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            synced_dispatch_path = root / "writeback" / "dispatch_execution_queue_synced.csv"
            synced_tracker_path = root / "writeback" / "follow_up_tracker_synced.csv"
            writeback_bundle_path = root / "writeback" / "signal_phase_follow_up_writeback_bundle.json"
            delivery_receipt_register_path = root / "intake" / "delivery_receipt_register.csv"
            delivery_monitor_queue_path = root / "monitor" / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation" / "validation_batch_results.csv"
            receive_cycle_path = root / "receive" / "signal_phase_receive_cycle.json"
            synced_receipt_register_path = root / "status_sync" / "delivery_receipt_register_synced.csv"
            output_dir = root / "follow_up_cycle"

            self._write_csv(
                synced_dispatch_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "priority_rank",
                    "dispatch_status",
                    "response_status",
                    "planned_dispatch_date",
                    "first_follow_up_date",
                    "escalation_date",
                    "recommended_channel",
                    "recommended_action",
                    "primary_channel_value",
                    "secondary_channel_value",
                    "phone_escalation_value",
                    "priority_band",
                    "email_subject",
                    "recommended_time_window",
                    "preferred_focus_hour_ranges",
                    "fallback_pilot_scope",
                    "notes",
                    "synced_follow_up_stage",
                    "synced_execution_status",
                    "synced_execution_completed_at",
                    "synced_execution_channel_used",
                    "synced_execution_outcome",
                    "synced_response_received",
                    "synced_response_summary",
                    "synced_protocol_reference",
                    "synced_evidence_path",
                ],
                [
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                        "priority_rank": 1,
                        "dispatch_status": "sent_via_pec",
                        "response_status": "follow_up_executed_no_response_yet",
                        "planned_dispatch_date": "2026-03-29",
                        "first_follow_up_date": "2026-04-05",
                        "escalation_date": "2026-04-12",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "Confirm receipt or routing and request acknowledgement.",
                        "primary_channel_value": "planning@pec.example.test",
                        "secondary_channel_value": "archives@pec.example.test",
                        "phone_escalation_value": "+39 080 577 1111",
                        "priority_band": "tier_1_immediate",
                        "email_subject": "Data request for signal 93 traffic-signal phase records",
                        "recommended_time_window": "weekday afternoon",
                        "preferred_focus_hour_ranges": "11:00-12:59 | 14:00-14:59",
                        "fallback_pilot_scope": "8 weeks of weekday coverage around 11:00-12:59 | 14:00-14:59",
                        "notes": "first follow-up executed",
                        "synced_follow_up_stage": "first_follow_up",
                        "synced_execution_status": "executed_via_pec",
                        "synced_execution_completed_at": "2026-04-05T09:15:00+02:00",
                        "synced_execution_channel_used": "pec",
                        "synced_execution_outcome": "reminder_sent",
                        "synced_response_received": "no",
                        "synced_response_summary": "",
                        "synced_protocol_reference": "PEC-123",
                        "synced_evidence_path": "evidence/pec-123.pdf",
                    }
                ],
            )

            self._write_csv(
                synced_tracker_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "follow_up_stage",
                    "due_date",
                    "recommended_channel",
                    "recommended_action",
                    "completion_status",
                    "completion_date",
                    "notes",
                    "synced_execution_status",
                    "synced_execution_completed_at",
                    "synced_response_received",
                    "synced_response_summary",
                    "synced_protocol_reference",
                    "synced_evidence_path",
                    "synced_execution_packet_md_path",
                ],
                [
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                        "follow_up_stage": "first_follow_up",
                        "due_date": "2026-04-05",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "Confirm receipt.",
                        "completion_status": "completed",
                        "completion_date": "2026-04-05",
                        "notes": "executed",
                        "synced_execution_status": "executed_via_pec",
                        "synced_execution_completed_at": "2026-04-05T09:15:00+02:00",
                        "synced_response_received": "no",
                        "synced_response_summary": "",
                        "synced_protocol_reference": "PEC-123",
                        "synced_evidence_path": "evidence/pec-123.pdf",
                        "synced_execution_packet_md_path": "packets/first_follow_up.md",
                    },
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                        "follow_up_stage": "escalation",
                        "due_date": "2026-04-12",
                        "recommended_channel": "+39 080 577 1111",
                        "recommended_action": "Escalate if still no delivery.",
                        "completion_status": "pending",
                        "completion_date": "",
                        "notes": "",
                        "synced_execution_status": "",
                        "synced_execution_completed_at": "",
                        "synced_response_received": "no",
                        "synced_response_summary": "",
                        "synced_protocol_reference": "",
                        "synced_evidence_path": "",
                        "synced_execution_packet_md_path": "",
                    },
                ],
            )

            self._write_csv(
                delivery_receipt_register_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "profile_id",
                    "delivery_item_id",
                    "receipt_status",
                    "received_date",
                    "received_file_path",
                    "validation_status",
                    "validation_manifest_path",
                    "notes",
                ],
                [
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                        "profile_id": "controller_event_log_export",
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                ],
            )

            self._write_csv(
                synced_receipt_register_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "profile_id",
                    "delivery_item_id",
                    "receipt_status",
                    "validation_status",
                    "validation_manifest_path",
                    "notes",
                    "synced_applied_to_movement_layer",
                    "synced_detected_file_count",
                ],
                [
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                        "profile_id": "controller_event_log_export",
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "receipt_status": "awaiting_delivery",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                        "synced_applied_to_movement_layer": "no",
                        "synced_detected_file_count": "0",
                    }
                ],
            )

            self._write_csv(
                delivery_monitor_queue_path,
                [
                    "delivery_item_id",
                    "monitor_status",
                    "detected_file_count",
                    "selected_received_file_path",
                    "validation_status",
                ],
                [
                    {
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "monitor_status": "awaiting_delivery",
                        "detected_file_count": 0,
                        "selected_received_file_path": "",
                        "validation_status": "",
                    }
                ],
            )

            self._write_csv(
                validation_batch_results_path,
                [
                    "delivery_item_id",
                    "validation_outcome",
                    "manifest_path",
                ],
                [],
            )

            receive_cycle_path.parent.mkdir(parents=True, exist_ok=True)
            receive_cycle_path.write_text(json.dumps({"outputs": {}}, indent=2), encoding="utf-8")

            writeback_bundle_path.parent.mkdir(parents=True, exist_ok=True)
            writeback_bundle_path.write_text(
                json.dumps(
                    {
                        "generated_at_utc": "2026-04-05T07:15:00+00:00",
                        "signal_phase_follow_up_writeback_bundle_version": "signal_phase_follow_up_writeback_bundle_v1",
                        "signal_phase_follow_up_writeback_bundle_contract_version": "signal_phase_follow_up_writeback_bundle_public_v1",
                        "summary": {
                            "dispatch_row_count": 1,
                            "tracker_row_count": 2,
                            "execution_queue_row_count": 1,
                            "writeback_ready_count": 1,
                            "dispatch_rows_updated_count": 1,
                            "tracker_rows_completed_count": 1,
                            "response_received_count": 0,
                        },
                        "outputs": {
                            "synced_dispatch_execution_queue_path": str(synced_dispatch_path),
                            "synced_follow_up_tracker_path": str(synced_tracker_path),
                            "writeback_ready_queue_path": str(root / "writeback" / "writeback_ready_queue.csv"),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            result = run_bari_signal_phase_follow_up_cycle(
                output_dir=output_dir,
                follow_up_writeback_bundle_path=writeback_bundle_path,
                delivery_receipt_register_path=delivery_receipt_register_path,
                delivery_monitor_queue_path=delivery_monitor_queue_path,
                validation_batch_results_path=validation_batch_results_path,
                receive_cycle_path=receive_cycle_path,
                synced_receipt_register_path=synced_receipt_register_path,
            )

            self.assertEqual(result["stats"]["writeback_ready_count"], 1)
            self.assertEqual(result["stats"]["runtime_follow_up_request_count"], 1)
            self.assertEqual(result["stats"]["runtime_execution_ready_count"], 1)

            runtime_follow_up_queue_path = output_dir / "runtime_follow_up" / "follow_up_ready_queue.csv"
            with runtime_follow_up_queue_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["next_follow_up_stage"], "escalation")

            runtime_execution_queue_path = (
                output_dir / "runtime_follow_up_execution" / "follow_up_execution_queue.csv"
            )
            with runtime_execution_queue_path.open("r", encoding="utf-8", newline="") as handle:
                execution_rows = list(csv.DictReader(handle))
            self.assertEqual(len(execution_rows), 1)
            self.assertEqual(execution_rows[0]["next_follow_up_stage"], "escalation")


if __name__ == "__main__":
    unittest.main()
