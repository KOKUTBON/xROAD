from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_request_state import (
    build_bari_signal_phase_support_request_state_bundle,
)


class SignalPhaseSupportRequestStateTests(unittest.TestCase):
    def test_build_bari_signal_phase_support_request_state_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_request_state"
            status_bundle_path = root / "signal_phase_support_status_bundle.json"
            apply_status_bundle_path = root / "signal_phase_support_apply_status_bundle.json"

            status_bundle_path.write_text(
                json.dumps(
                    {
                        "request_support_status": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "Via A",
                                "request_status_category": "partially_ready_for_validation",
                                "manual_workbook_row_count": 18,
                                "manual_ready_count": 1,
                                "manual_pending_count": 17,
                                "pedestrian_workbook_row_count": 8,
                                "pedestrian_ready_count": 1,
                                "pedestrian_pending_count": 7,
                                "validation_ready_profile_count": 2,
                                "signalized_movement_count": 3,
                                "matched_crashes_at_junction_total": 8,
                                "unresolved_signalized_movement_count": 1,
                                "unresolved_signalized_crash_total": 4,
                                "manual_workbook_path": "/tmp/manual.csv",
                                "pedestrian_workbook_path": "/tmp/ped.csv",
                                "manual_delivery_path": "/tmp/manual_delivery.csv",
                                "pedestrian_delivery_path": "/tmp/ped_delivery.csv",
                                "recommended_next_action": "Finish mappings",
                                "next_action": "Run validation",
                            }
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            apply_status_bundle_path.write_text(
                json.dumps(
                    {
                        "status_rows": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "profile_id": "arm_phase_mapping_sheet",
                                "apply_status_category": "applied_to_movement_layer",
                            },
                            {
                                "request_id": "bari_signal_phase_01",
                                "profile_id": "pedestrian_stage_mapping_sheet",
                                "apply_status_category": "waiting_for_analyst_resolution",
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_request_state_bundle(
                output_dir=output_dir,
                signal_phase_support_status_bundle_path=status_bundle_path,
                signal_phase_support_apply_status_bundle_path=apply_status_bundle_path,
            )

            self.assertEqual(
                manifest["source"]["adapter"],
                "bari_signal_phase_support_request_state_bundle_builder",
            )
            self.assertEqual(manifest["stats"]["request_count"], 1)
            self.assertEqual(manifest["stats"]["partially_applied_count"], 1)
            self.assertEqual(manifest["stats"]["active_request_count"], 1)
            self.assertEqual(manifest["stats"]["hold_request_count"], 0)
            self.assertEqual(
                manifest["stats"]["requests_with_unresolved_signalized_movements_count"],
                1,
            )
            self.assertEqual(manifest["stats"]["unresolved_signalized_movement_count_total"], 1)
            self.assertEqual(manifest["stats"]["unresolved_signalized_crash_total"], 4)

            with (output_dir / "request_support_runtime_state.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                state_rows = list(csv.DictReader(handle))
            self.assertEqual(len(state_rows), 1)
            self.assertEqual(state_rows[0]["unresolved_signalized_movement_count"], "1")
            self.assertEqual(state_rows[0]["unresolved_signalized_crash_total"], "4")

            payload = json.loads(
                (output_dir / "signal_phase_support_request_state_bundle.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["summary"]["unresolved_signalized_crash_total"], 4)
            request_row = payload["request_support_runtime_state"][0]
            self.assertEqual(
                request_row["request_runtime_category"],
                "partially_applied_manual_resolution",
            )
            self.assertEqual(request_row["applied_profile_count"], 1)
            self.assertEqual(request_row["unresolved_signalized_movement_count"], 1)

            report_md = (output_dir / "signal_phase_support_request_state_bundle.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("requests with unresolved signalized movements: `1`", report_md)
            self.assertIn("unresolved signalized crashes: `4`", report_md)

            packet_md = (output_dir / "request_packets" / "bari_signal_phase_01.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("unresolved signalized movements: `1`", packet_md)
            self.assertIn("unresolved signalized crashes: `4`", packet_md)


if __name__ == "__main__":
    unittest.main()
