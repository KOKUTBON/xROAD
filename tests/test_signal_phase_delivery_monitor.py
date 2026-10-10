from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_delivery_monitor import build_bari_signal_phase_delivery_monitor_bundle


class SignalPhaseDeliveryMonitorTests(unittest.TestCase):
    def test_build_bari_signal_phase_delivery_monitor_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_delivery_monitor"
            intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            receipt_register_path = root / "delivery_receipt_register.csv"

            intake_bundle_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "dispatch_request_count": 2,
                            "expected_delivery_count": 3,
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            ready_dropzone = root / "incoming" / "bari_signal_phase_01" / "controller_event_log_export"
            ready_dropzone.mkdir(parents=True, exist_ok=True)
            ready_file = ready_dropzone / "controller_event_log_001.csv"
            ready_file.write_text("timestamp,event\n", encoding="utf-8")

            manual_dropzone = root / "incoming" / "bari_signal_phase_01" / "arm_phase_mapping_sheet"
            manual_dropzone.mkdir(parents=True, exist_ok=True)
            (manual_dropzone / "arm_phase_mapping_a.csv").write_text("a", encoding="utf-8")
            (manual_dropzone / "arm_phase_mapping_b.csv").write_text("b", encoding="utf-8")

            empty_dropzone = root / "incoming" / "bari_signal_phase_02" / "controller_event_log_export"
            empty_dropzone.mkdir(parents=True, exist_ok=True)

            with receipt_register_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "profile_id",
                        "delivery_item_id",
                        "delivery_format",
                        "requested_window",
                        "acceptance_gate",
                        "expected_filename_hint",
                        "incoming_dropzone_path",
                        "mapping_stub_path",
                        "validation_output_dir",
                        "validation_command",
                        "receipt_status",
                        "received_date",
                        "received_file_path",
                        "validation_status",
                        "validation_manifest_path",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "profile_id": "controller_event_log_export",
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months",
                        "acceptance_gate": "events complete",
                        "expected_filename_hint": "controller_event_log_*.csv",
                        "incoming_dropzone_path": str(ready_dropzone),
                        "mapping_stub_path": "mapping.json",
                        "validation_output_dir": "validation/out",
                        "validation_command": "validate-signal-phase-delivery <received_file_path> mapping.json",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "profile_id": "arm_phase_mapping_sheet",
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "delivery_format": "CSV",
                        "requested_window": "current_layout",
                        "acceptance_gate": "mapping complete",
                        "expected_filename_hint": "arm_phase_mapping_*.csv",
                        "incoming_dropzone_path": str(manual_dropzone),
                        "mapping_stub_path": "mapping_sheet.json",
                        "validation_output_dir": "validation/map",
                        "validation_command": "validate-signal-phase-delivery <received_file_path> mapping_sheet.json",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-02",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "profile_id": "controller_event_log_export",
                        "delivery_item_id": "bari_signal_phase_02__controller_event_log_export",
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months",
                        "acceptance_gate": "events complete",
                        "expected_filename_hint": "controller_event_log_*.csv",
                        "incoming_dropzone_path": str(empty_dropzone),
                        "mapping_stub_path": "mapping.json",
                        "validation_output_dir": "validation/out_b",
                        "validation_command": "validate-signal-phase-delivery <received_file_path> mapping.json",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )

            result = build_bari_signal_phase_delivery_monitor_bundle(
                output_dir=output_dir,
                signal_phase_delivery_intake_bundle_path=intake_bundle_path,
                delivery_receipt_register_path=receipt_register_path,
            )

            self.assertEqual(result["stats"]["monitored_delivery_count"], 3)
            self.assertEqual(result["stats"]["detected_file_count"], 3)
            self.assertEqual(result["stats"]["validation_ready_count"], 1)
            self.assertEqual(result["stats"]["awaiting_delivery_count"], 1)
            self.assertEqual(result["stats"]["manual_review_count"], 1)

            payload = json.loads((output_dir / "signal_phase_delivery_monitor_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["monitor_queue"]), 3)
            ready_rows = payload["validation_ready_queue"]
            self.assertEqual(len(ready_rows), 1)
            self.assertIn(str(ready_file), ready_rows[0]["validation_command_ready"])

            with (output_dir / "delivery_monitor_queue.csv").open(encoding="utf-8", newline="") as handle:
                monitor_rows = list(csv.DictReader(handle))
            rows_by_key = {(row["request_id"], row["profile_id"]): row for row in monitor_rows}
            self.assertEqual(
                rows_by_key[("bari_signal_phase_01", "controller_event_log_export")]["monitor_status"],
                "ready_for_validation",
            )
            self.assertEqual(
                rows_by_key[("bari_signal_phase_01", "arm_phase_mapping_sheet")]["monitor_status"],
                "multiple_files_manual_review",
            )
            self.assertEqual(
                rows_by_key[("bari_signal_phase_02", "controller_event_log_export")]["monitor_status"],
                "awaiting_delivery",
            )

            with (output_dir / "validation_ready_queue.csv").open(encoding="utf-8", newline="") as handle:
                ready_queue_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_queue_rows), 1)
            self.assertEqual(ready_queue_rows[0]["monitor_status"], "ready_for_validation")


if __name__ == "__main__":
    unittest.main()
