from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_validation import (
    build_bari_signal_phase_dispatch_validation_bundle,
)


class SignalPhaseDispatchValidationBundleTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_validation_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_validation"
            runtime_queue_path = root / "dispatch_execution_queue_runtime.csv"

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
                    "recording_status",
                    "unresolved_signalized_movement_count",
                    "unresolved_signalized_crash_count",
                    "unresolved_coverage_pct",
                    "unresolved_crash_coverage_pct",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "execution_status": "completed",
                        "execution_completed_at": "2026-03-29T09:15:00+01:00",
                        "execution_channel_used": "urbanistica@pec.example.com",
                        "execution_outcome": "pec_sent",
                        "response_received": "yes",
                        "response_summary": "PEC accepted",
                        "protocol_reference": "PG-001",
                        "evidence_path": "evidence/pec-001.eml",
                        "recording_status": "execution_logged",
                        "unresolved_signalized_movement_count": 6,
                        "unresolved_signalized_crash_count": 13,
                        "unresolved_coverage_pct": 30.0,
                        "unresolved_crash_coverage_pct": 65.0,
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "execution_status": "completed",
                        "execution_completed_at": "",
                        "execution_channel_used": "",
                        "execution_outcome": "",
                        "response_received": "yes",
                        "response_summary": "",
                        "protocol_reference": "",
                        "evidence_path": "",
                        "recording_status": "execution_logged",
                        "unresolved_signalized_movement_count": 4,
                        "unresolved_signalized_crash_count": 7,
                        "unresolved_coverage_pct": 20.0,
                        "unresolved_crash_coverage_pct": 35.0,
                    },
                    {
                        "dispatch_reference": "REF-3",
                        "request_id": "req_3",
                        "junction_id": "j-3",
                        "signal_name": "Signal Three",
                        "execution_status": "pending_execution",
                        "execution_completed_at": "",
                        "execution_channel_used": "",
                        "execution_outcome": "",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "",
                        "evidence_path": "",
                        "recording_status": "awaiting_operator_entry",
                        "unresolved_signalized_movement_count": 0,
                        "unresolved_signalized_crash_count": 0,
                        "unresolved_coverage_pct": 0.0,
                        "unresolved_crash_coverage_pct": 0.0,
                    },
                ],
            )

            result = build_bari_signal_phase_dispatch_validation_bundle(
                output_dir=output_dir,
                dispatch_execution_runtime_queue_path=runtime_queue_path,
            )

            self.assertEqual(result["stats"]["runtime_row_count"], 3)
            self.assertEqual(result["stats"]["accepted_for_writeback_count"], 1)
            self.assertEqual(result["stats"]["rejected_for_writeback_count"], 1)
            self.assertEqual(result["stats"]["pending_operator_entry_count"], 1)
            self.assertGreaterEqual(result["stats"]["issue_count"], 5)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 2)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 10)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 20)
            self.assertEqual(result["stats"]["accepted_unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["accepted_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["rejected_unresolved_signalized_movement_total"], 4)
            self.assertEqual(result["stats"]["rejected_unresolved_signalized_crash_total"], 7)

            with (output_dir / "dispatch_execution_queue_validated.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = {row["request_id"]: row for row in csv.DictReader(handle)}

            self.assertEqual(rows["req_1"]["dispatch_validation_outcome"], "accepted_for_writeback")
            self.assertEqual(rows["req_1"]["writeback_eligible"], "yes")
            self.assertEqual(rows["req_2"]["dispatch_validation_outcome"], "rejected_for_writeback")
            self.assertEqual(rows["req_2"]["writeback_eligible"], "no")
            self.assertEqual(rows["req_3"]["dispatch_validation_outcome"], "pending_operator_entry")
            self.assertEqual(rows["req_3"]["writeback_eligible"], "no")
            self.assertEqual(rows["req_1"]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(rows["req_2"]["unresolved_signalized_crash_count"], "7")

            with (output_dir / "dispatch_validation_issues.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                issue_codes = {row["issue_code"] for row in csv.DictReader(handle)}

            self.assertIn("missing_execution_completed_at", issue_codes)
            self.assertIn("missing_execution_channel_used", issue_codes)
            self.assertIn("missing_protocol_or_evidence", issue_codes)

            bundle_md = (output_dir / "signal_phase_dispatch_validation_bundle.md").read_text(encoding="utf-8")
            self.assertIn("unresolved signalized crashes across runtime rows: `20`", bundle_md)


if __name__ == "__main__":
    unittest.main()
