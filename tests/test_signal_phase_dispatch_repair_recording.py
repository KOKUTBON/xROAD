from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_repair_recording import (
    build_bari_signal_phase_dispatch_repair_recording_bundle,
)


class SignalPhaseDispatchRepairRecordingBundleTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_repair_recording_bundle_applies_ready_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_repair_recording"
            runtime_queue_path = root / "dispatch_execution_queue_runtime.csv"
            repair_queue_path = root / "dispatch_log_repair_queue.csv"
            repair_log_path = root / "dispatch_log_repair_log.csv"

            self._write_csv(
                runtime_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "execution_status",
                    "execution_completed_at",
                    "execution_channel_used",
                    "execution_outcome",
                    "response_received",
                    "response_summary",
                    "protocol_reference",
                    "evidence_path",
                    "execution_notes",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "execution_status": "completed",
                        "execution_completed_at": "",
                        "execution_channel_used": "pec@example.com",
                        "execution_outcome": "pec_sent",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "",
                        "evidence_path": "",
                        "execution_notes": "operator entry started",
                    }
                ],
            )
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
                        "repair_summary": "Fix the log row.",
                    }
                ],
            )
            self._write_csv(
                repair_log_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "action_category",
                    "dispatch_validation_outcome",
                    "dispatch_validation_issue_codes",
                    "original_execution_status",
                    "original_execution_completed_at",
                    "original_execution_channel_used",
                    "original_execution_outcome",
                    "original_response_received",
                    "original_response_summary",
                    "original_protocol_reference",
                    "original_evidence_path",
                    "repair_status",
                    "repaired_execution_status",
                    "repaired_execution_completed_at",
                    "repaired_execution_channel_used",
                    "repaired_execution_outcome",
                    "repaired_response_received",
                    "repaired_response_summary",
                    "repaired_protocol_reference",
                    "repaired_evidence_path",
                    "repaired_execution_notes",
                    "repair_completed_at",
                    "repair_operator_notes",
                    "repair_evidence_path",
                    "repair_match_status",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "action_category": "repair_dispatch_log_now",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_codes": "missing_execution_completed_at | missing_protocol_or_evidence",
                        "original_execution_status": "completed",
                        "original_execution_completed_at": "",
                        "original_execution_channel_used": "pec@example.com",
                        "original_execution_outcome": "pec_sent",
                        "original_response_received": "no",
                        "original_response_summary": "",
                        "original_protocol_reference": "",
                        "original_evidence_path": "",
                        "repair_status": "ready_for_validation",
                        "repaired_execution_status": "completed",
                        "repaired_execution_completed_at": "2026-03-29T09:15:00+01:00",
                        "repaired_execution_channel_used": "planning@pec.example.test",
                        "repaired_execution_outcome": "pec_sent",
                        "repaired_response_received": "no",
                        "repaired_response_summary": "",
                        "repaired_protocol_reference": "PEC-123",
                        "repaired_evidence_path": "evidence/pec_123.eml",
                        "repaired_execution_notes": "receipt recovered",
                        "repair_completed_at": "2026-03-29T09:20:00+01:00",
                        "repair_operator_notes": "filled missing fields",
                        "repair_evidence_path": "evidence/pec_123.eml",
                        "repair_match_status": "matched_request_id",
                    }
                ],
            )

            result = build_bari_signal_phase_dispatch_repair_recording_bundle(
                output_dir=output_dir,
                dispatch_execution_runtime_queue_path=runtime_queue_path,
                dispatch_log_repair_queue_path=repair_queue_path,
                dispatch_log_repair_log_path=repair_log_path,
            )

            self.assertEqual(result["stats"]["runtime_row_count"], 1)
            self.assertEqual(result["stats"]["repair_request_count"], 1)
            self.assertEqual(result["stats"]["applied_repair_count"], 1)
            self.assertEqual(result["stats"]["pending_repair_count"], 0)

            with (output_dir / "dispatch_execution_queue_runtime_repaired.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["execution_completed_at"], "2026-03-29T09:15:00+01:00")
            self.assertEqual(rows[0]["protocol_reference"], "PEC-123")
            self.assertEqual(rows[0]["repair_applied"], "yes")
            self.assertEqual(rows[0]["repair_status"], "ready_for_validation")


if __name__ == "__main__":
    unittest.main()
