from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_delivery_intake import build_bari_signal_phase_delivery_intake_bundle


class SignalPhaseDeliveryIntakeTests(unittest.TestCase):
    def test_build_bari_signal_phase_delivery_intake_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_delivery_intake"
            dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            delivery_checklist_path = root / "delivery_checklist.csv"
            mapping_stub_dir = root / "mapping_stubs"
            mapping_stub_dir.mkdir(parents=True, exist_ok=True)

            for profile_id in ["controller_event_log_export", "arm_phase_mapping_sheet"]:
                (mapping_stub_dir / f"{profile_id}_mapping_stub.json").write_text("{}", encoding="utf-8")

            dispatch_bundle_path.write_text(
                json.dumps(
                    {
                        "dispatch_queue": [
                            {
                                "dispatch_reference": "BARI-SPD-20260329-01",
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Via A Junction",
                                "priority_rank": 1,
                                "planned_dispatch_date": "2026-03-29",
                                "first_follow_up_date": "2026-04-05",
                                "escalation_date": "2026-04-12",
                            },
                            {
                                "dispatch_reference": "BARI-SPD-20260329-02",
                                "request_id": "bari_signal_phase_02",
                                "junction_id": "it-bari-signal-94",
                                "signal_name": "Via B Junction",
                                "priority_rank": 2,
                                "planned_dispatch_date": "2026-03-29",
                                "first_follow_up_date": "2026-04-05",
                                "escalation_date": "2026-04-12",
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with delivery_checklist_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "delivery_item_id",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_band",
                        "profile_id",
                        "owner_team",
                        "delivery_format",
                        "requested_window",
                        "acceptance_gate",
                        "delivery_status",
                        "received_date",
                        "validated_date",
                        "mapped_to_movements",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__controller_event_log_export",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "controller_event_log_export",
                        "owner_team": "ITS",
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months_plus_current_control_state",
                        "acceptance_gate": "events complete",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A Junction",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "arm_phase_mapping_sheet",
                        "owner_team": "ITS",
                        "delivery_format": "CSV",
                        "requested_window": "current_junction_geometry_revision",
                        "acceptance_gate": "mapping complete",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_02__controller_event_log_export",
                        "request_id": "bari_signal_phase_02",
                        "junction_id": "it-bari-signal-94",
                        "signal_name": "Via B Junction",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "controller_event_log_export",
                        "owner_team": "ITS",
                        "delivery_format": "CSV",
                        "requested_window": "last_12_months_plus_current_control_state",
                        "acceptance_gate": "events complete",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "",
                    }
                )

            result = build_bari_signal_phase_delivery_intake_bundle(
                output_dir=output_dir,
                signal_phase_dispatch_bundle_path=dispatch_bundle_path,
                delivery_checklist_path=delivery_checklist_path,
                mapping_stub_dir=mapping_stub_dir,
                validation_output_root=root / "validation",
            )

            self.assertEqual(result["stats"]["dispatch_request_count"], 2)
            self.assertEqual(result["stats"]["expected_delivery_count"], 3)
            self.assertEqual(result["stats"]["distinct_profile_count"], 2)
            self.assertEqual(result["stats"]["packet_count"], 2)

            payload = json.loads((output_dir / "signal_phase_delivery_intake_bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["dispatch_requests"]), 2)
            self.assertEqual(payload["dispatch_requests"][0]["expected_delivery_count"], 2)

            with (output_dir / "expected_deliveries.csv").open(encoding="utf-8", newline="") as handle:
                expected_rows = list(csv.DictReader(handle))
            self.assertEqual(len(expected_rows), 3)
            self.assertIn("validate-signal-phase-delivery", expected_rows[0]["validation_command"])

            with (output_dir / "delivery_receipt_register.csv").open(encoding="utf-8", newline="") as handle:
                receipt_rows = list(csv.DictReader(handle))
            self.assertEqual(len(receipt_rows), 3)
            self.assertEqual(receipt_rows[0]["receipt_status"], "awaiting_delivery")

            packet_md = (output_dir / "intake_packets" / "bari_signal_phase_01.md").read_text(encoding="utf-8")
            self.assertIn("incoming drop zone", packet_md)
            self.assertIn("validation command", packet_md)


if __name__ == "__main__":
    unittest.main()
