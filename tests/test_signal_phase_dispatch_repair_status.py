from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_repair_status import (
    build_bari_signal_phase_dispatch_repair_status_bundle,
)


class SignalPhaseDispatchRepairStatusBundleTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_repair_status_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_repair_status"
            repair_queue_path = root / "dispatch_log_repair_queue.csv"
            repair_log_path = root / "dispatch_log_repair_log.csv"
            execution_ready_path = root / "dispatch_repair_execution_ready_queue.csv"
            internal_hold_path = root / "dispatch_repair_internal_hold_queue.csv"
            validation_queue_path = root / "dispatch_execution_queue_validated.csv"

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
                    "repair_packet_md_path",
                    "repair_packet_json_path",
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
                        "repair_summary": "Fix the log row.",
                        "repair_packet_md_path": "packets/req_1.md",
                        "repair_packet_json_path": "packets/req_1.json",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "action_category": "repair_dispatch_log_now",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_count": 1,
                        "dispatch_validation_issue_codes": "missing_protocol_or_evidence",
                        "repair_summary": "Add protocol evidence.",
                        "repair_packet_md_path": "packets/req_2.md",
                        "repair_packet_json_path": "packets/req_2.json",
                    },
                    {
                        "dispatch_reference": "REF-3",
                        "request_id": "req_3",
                        "junction_id": "j-3",
                        "signal_name": "Signal Three",
                        "action_category": "repair_dispatch_log_now",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_count": 1,
                        "dispatch_validation_issue_codes": "missing_execution_status",
                        "repair_summary": "Set the status.",
                        "repair_packet_md_path": "packets/req_3.md",
                        "repair_packet_json_path": "packets/req_3.json",
                    },
                ],
            )
            self._write_csv(
                repair_log_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "repair_status",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "repair_status": "pending_repair",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "repair_status": "ready_for_validation",
                    },
                    {
                        "dispatch_reference": "REF-3",
                        "request_id": "req_3",
                        "junction_id": "j-3",
                        "signal_name": "Signal Three",
                        "repair_status": "ready_for_validation",
                    },
                ],
            )
            self._write_csv(
                execution_ready_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "repair_packet_md_path",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "repair_packet_md_path": "packets/req_1.md",
                    }
                ],
            )
            self._write_csv(
                internal_hold_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "repair_status",
                    "repair_packet_md_path",
                ],
                [
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "repair_status": "ready_for_validation",
                        "repair_packet_md_path": "packets/req_2.md",
                    }
                ],
            )
            self._write_csv(
                validation_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "dispatch_validation_outcome",
                    "dispatch_validation_issue_codes",
                    "writeback_eligible",
                    "repair_applied",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_codes": "missing_execution_completed_at | missing_protocol_or_evidence",
                        "writeback_eligible": "no",
                        "repair_applied": "no",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "dispatch_validation_outcome": "accepted_for_writeback",
                        "dispatch_validation_issue_codes": "",
                        "writeback_eligible": "yes",
                        "repair_applied": "yes",
                    },
                    {
                        "dispatch_reference": "REF-3",
                        "request_id": "req_3",
                        "junction_id": "j-3",
                        "signal_name": "Signal Three",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_codes": "missing_execution_status",
                        "writeback_eligible": "no",
                        "repair_applied": "yes",
                    },
                ],
            )

            result = build_bari_signal_phase_dispatch_repair_status_bundle(
                output_dir=output_dir,
                dispatch_log_repair_queue_path=repair_queue_path,
                dispatch_log_repair_log_path=repair_log_path,
                dispatch_repair_execution_ready_queue_path=execution_ready_path,
                dispatch_repair_internal_hold_queue_path=internal_hold_path,
                dispatch_validation_queue_path=validation_queue_path,
            )

            self.assertEqual(result["stats"]["request_count"], 3)
            self.assertEqual(result["stats"]["pending_repair_count"], 1)
            self.assertEqual(result["stats"]["ready_for_validation_count"], 0)
            self.assertEqual(result["stats"]["still_blocked_count"], 1)
            self.assertEqual(result["stats"]["cleared_for_writeback_count"], 1)
            self.assertEqual(result["stats"]["due_now_count"], 2)

            with (output_dir / "dispatch_repair_status.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = {row["request_id"]: row for row in csv.DictReader(handle)}

            self.assertEqual(rows["req_1"]["repair_status_category"], "pending_repair")
            self.assertEqual(rows["req_1"]["execution_queue_state"], "repair_execution_ready")
            self.assertEqual(rows["req_1"]["due_now"], "yes")

            self.assertEqual(rows["req_2"]["repair_status_category"], "repair_cleared_for_writeback")
            self.assertEqual(rows["req_2"]["execution_queue_state"], "internal_hold")
            self.assertEqual(rows["req_2"]["due_now"], "no")

            self.assertEqual(rows["req_3"]["repair_status_category"], "repair_still_blocked")
            self.assertEqual(rows["req_3"]["next_action"], "update_repair_log_and_rerun_validation")


if __name__ == "__main__":
    unittest.main()
