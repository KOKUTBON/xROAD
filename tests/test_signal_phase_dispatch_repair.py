from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_dispatch_repair import (
    build_bari_signal_phase_dispatch_repair_bundle,
)


class SignalPhaseDispatchRepairBundleTest(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_dispatch_repair_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_repair"
            validation_queue_path = root / "dispatch_execution_queue_validated.csv"

            self._write_csv(
                validation_queue_path,
                [
                    "dispatch_reference",
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "dispatch_validation_outcome",
                    "dispatch_validation_issue_count",
                    "dispatch_validation_issue_codes",
                    "execution_status",
                    "execution_completed_at",
                    "execution_channel_used",
                    "execution_outcome",
                    "response_received",
                    "response_summary",
                    "protocol_reference",
                    "evidence_path",
                    "execution_packet_md_path",
                ],
                [
                    {
                        "dispatch_reference": "REF-1",
                        "request_id": "req_1",
                        "junction_id": "j-1",
                        "signal_name": "Signal One",
                        "dispatch_validation_outcome": "rejected_for_writeback",
                        "dispatch_validation_issue_count": 2,
                        "dispatch_validation_issue_codes": "missing_execution_completed_at | missing_protocol_or_evidence",
                        "execution_status": "completed",
                        "execution_completed_at": "",
                        "execution_channel_used": "pec@example.com",
                        "execution_outcome": "pec_sent",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "",
                        "evidence_path": "",
                        "execution_packet_md_path": "packets/req_1.md",
                    },
                    {
                        "dispatch_reference": "REF-2",
                        "request_id": "req_2",
                        "junction_id": "j-2",
                        "signal_name": "Signal Two",
                        "dispatch_validation_outcome": "accepted_for_writeback",
                        "dispatch_validation_issue_count": 0,
                        "dispatch_validation_issue_codes": "",
                        "execution_status": "completed",
                        "execution_completed_at": "2026-03-29T10:00:00+01:00",
                        "execution_channel_used": "pec@example.com",
                        "execution_outcome": "pec_sent",
                        "response_received": "no",
                        "response_summary": "",
                        "protocol_reference": "PG-1",
                        "evidence_path": "evidence/req_2.eml",
                        "execution_packet_md_path": "packets/req_2.md",
                    },
                ],
            )

            result = build_bari_signal_phase_dispatch_repair_bundle(
                output_dir=output_dir,
                dispatch_validation_queue_path=validation_queue_path,
            )

            self.assertEqual(result["stats"]["validated_row_count"], 2)
            self.assertEqual(result["stats"]["repair_request_count"], 1)
            self.assertEqual(result["stats"]["blocked_execution_count"], 1)

            with (output_dir / "dispatch_log_repair_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["request_id"], "req_1")
            self.assertEqual(rows[0]["action_category"], "repair_dispatch_log_now")


if __name__ == "__main__":
    unittest.main()
