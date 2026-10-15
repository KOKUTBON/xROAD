from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_repair_execution import (
    build_bari_signal_phase_dispatch_repair_execution_bundle,
)


class SignalPhaseDispatchRepairExecutionBundleTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_repair_execution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_repair_execution"
            repair_queue_path = root / "dispatch_log_repair_queue.csv"
            repair_log_path = root / "dispatch_log_repair_log.csv"

            self._write_csv(
                repair_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "action_category",
                    "dispatch_validation_outcome",
                    "dispatch_validation_issue_count",
                    "dispatch_validation_issue_codes",
                    "repair_summary",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "action_category": "repair_dispatch_log_now",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_count": 2,
                        "dispatch_validation_issue_codes": "missing_execution_completed_at | missing_protocol_or_evidence",
                        "repair_summary": "Fill the missing send evidence.",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "action_category": "complete_dispatch_log_entry",
                        "dispatch_validation_outcome": "incomplete_operator_entry",
                        "dispatch_validation_issue_count": 1,
                        "dispatch_validation_issue_codes": "missing_execution_status",
                        "repair_summary": "Complete the operator entry.",
                    },
                ],
            )
            self._write_csv(
                repair_log_path,
                [
                    "request_id",
                    "repair_status",
                    "original_execution_status",
                    "original_execution_completed_at",
                    "original_execution_channel_used",
                    "original_execution_outcome",
                    "original_protocol_reference",
                    "original_evidence_path",
                ],
                [
                    {
                        "request_id": "req_1",
                        "repair_status": "pending_repair",
                        "original_execution_status": "completed",
                        "original_execution_completed_at": "",
                        "original_execution_channel_used": "pec@example.com",
                        "original_execution_outcome": "pec_sent",
                        "original_protocol_reference": "",
                        "original_evidence_path": "",
                    },
                    {
                        "request_id": "req_2",
                        "repair_status": "ready_for_validation",
                        "original_execution_status": "",
                        "original_execution_completed_at": "",
                        "original_execution_channel_used": "",
                        "original_execution_outcome": "",
                        "original_protocol_reference": "",
                        "original_evidence_path": "",
                    },
                ],
            )

            result = build_bari_signal_phase_dispatch_repair_execution_bundle(
                output_dir=output_dir,
                dispatch_log_repair_queue_path=repair_queue_path,
                dispatch_log_repair_log_path=repair_log_path,
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["execution_ready_count"], 1)
            self.assertEqual(result["stats"]["internal_hold_count"], 1)
            self.assertEqual(result["stats"]["ready_for_validation_count"], 1)

            with (output_dir / "dispatch_repair_execution_ready_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                ready_rows = list(csv.DictReader(handle))
            with (output_dir / "dispatch_repair_internal_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                hold_rows = list(csv.DictReader(handle))

            self.assertEqual(len(ready_rows), 1)
            self.assertEqual(ready_rows[0]["request_id"], "req_1")
            self.assertIn("set `repaired_execution_completed_at`", ready_rows[0]["field_guidance"])
            self.assertEqual(len(hold_rows), 1)
            self.assertEqual(hold_rows[0]["request_id"], "req_2")
            self.assertEqual(hold_rows[0]["repair_status"], "ready_for_validation")


if __name__ == "__main__":
    unittest.main()
