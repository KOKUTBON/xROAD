from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_recording import (
    build_bari_signal_phase_dispatch_recording_bundle,
)


class SignalPhaseDispatchRecordingBundleTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_recording_bundle_applies_logged_send(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_recording"
            execution_ready_queue_path = root / "dispatch_execution_ready_queue.csv"
            execution_log_path = root / "dispatch_execution_log.csv"

            self._write_csv(
                execution_ready_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "priority_rank",
                    "priority_band",
                    "action_category",
                    "due_date",
                    "due_now",
                    "dispatch_status",
                    "response_status",
                    "primary_channel_value",
                    "secondary_channel_value",
                    "unresolved_signalized_movement_count",
                    "unresolved_signalized_crash_count",
                    "unresolved_coverage_pct",
                    "unresolved_crash_coverage_pct",
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
                        "priority_rank": 1,
                        "priority_band": "tier_1_immediate",
                        "action_category": "dispatch_request_now",
                        "due_date": "2026-03-29",
                        "due_now": "True",
                        "dispatch_status": "pending_dispatch",
                        "response_status": "awaiting_send",
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_value": "secondary@example.com",
                        "unresolved_signalized_movement_count": 6,
                        "unresolved_signalized_crash_count": 13,
                        "unresolved_coverage_pct": 30.0,
                        "unresolved_crash_coverage_pct": 65.0,
                        "execution_status": "pending_execution",
                        "execution_completed_at": "",
                        "execution_channel_used": "",
                        "execution_outcome": "",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "",
                        "evidence_path": "",
                        "execution_notes": "",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "priority_rank": 2,
                        "priority_band": "tier_1_immediate",
                        "action_category": "dispatch_request_now",
                        "due_date": "2026-03-29",
                        "due_now": "True",
                        "dispatch_status": "pending_dispatch",
                        "response_status": "awaiting_send",
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_value": "secondary@example.com",
                        "unresolved_signalized_movement_count": 0,
                        "unresolved_signalized_crash_count": 0,
                        "unresolved_coverage_pct": 0.0,
                        "unresolved_crash_coverage_pct": 0.0,
                        "execution_status": "pending_execution",
                        "execution_completed_at": "",
                        "execution_channel_used": "",
                        "execution_outcome": "",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "",
                        "evidence_path": "",
                        "execution_notes": "",
                    },
                ],
            )

            self._write_csv(
                execution_log_path,
                [
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
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "due_date": "2026-03-29",
                        "primary_channel_value": "primary@example.com",
                        "secondary_channel_value": "secondary@example.com",
                        "execution_status": "completed",
                        "execution_completed_at": "2026-03-29T09:15:00+01:00",
                        "execution_channel_used": "primary@example.com",
                        "execution_outcome": "pec_sent",
                        "response_received": "yes",
                        "response_summary": "PEC accepted",
                        "protocol_reference": "PG-001",
                        "evidence_path": "evidence/pec-001.eml",
                        "execution_notes": "sent",
                        "log_match_status": "matched_request_id",
                    },
                    {
                        "dispatch_reference": "REF-X",
                        "request_id": "req_missing",
                        "junction_id": "j-x",
                        "signal_name": "Missing",
                        "due_date": "2026-03-29",
                        "primary_channel_value": "x@example.com",
                        "secondary_channel_value": "",
                        "execution_status": "completed",
                        "execution_completed_at": "2026-03-29T11:00:00+01:00",
                        "execution_channel_used": "x@example.com",
                        "execution_outcome": "pec_sent",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "PG-X",
                        "evidence_path": "evidence/x.eml",
                        "execution_notes": "stale",
                        "log_match_status": "matched_request_id",
                    },
                ],
            )

            result = build_bari_signal_phase_dispatch_recording_bundle(
                output_dir=output_dir,
                dispatch_execution_ready_queue_path=execution_ready_queue_path,
                dispatch_execution_log_path=execution_log_path,
            )

            self.assertEqual(result["stats"]["request_count"], 2)
            self.assertEqual(result["stats"]["applied_execution_count"], 1)
            self.assertEqual(result["stats"]["pending_execution_count"], 1)
            self.assertEqual(result["stats"]["unmatched_log_row_count"], 1)
            self.assertEqual(result["stats"]["targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["unresolved_signalized_crash_total"], 13)

            with (output_dir / "dispatch_execution_queue_runtime.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = {row["request_id"]: row for row in csv.DictReader(handle)}

            self.assertEqual(rows["req_1"]["execution_status"], "completed")
            self.assertEqual(rows["req_1"]["protocol_reference"], "PG-001")
            self.assertEqual(rows["req_1"]["recording_status"], "execution_logged")
            self.assertEqual(rows["req_1"]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(rows["req_1"]["unresolved_signalized_crash_count"], "13")
            self.assertEqual(rows["req_2"]["execution_status"], "pending_execution")
            self.assertEqual(rows["req_2"]["recording_status"], "awaiting_operator_entry")

            with (output_dir / "dispatch_execution_log.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                log_rows = {row["request_id"]: row for row in csv.DictReader(handle)}

            self.assertEqual(log_rows["req_1"]["unresolved_signalized_movement_count"], "6")
            self.assertEqual(log_rows["req_1"]["unresolved_signalized_crash_count"], "13")

            bundle_md = (output_dir / "signal_phase_dispatch_recording_bundle.md").read_text(encoding="utf-8")
            self.assertIn("targets with unresolved movements: `1`", bundle_md)


if __name__ == "__main__":
    unittest.main()
