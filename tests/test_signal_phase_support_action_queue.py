from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_action_queue import (
    build_bari_signal_phase_support_action_queue,
)


class SignalPhaseSupportActionQueueTests(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_support_action_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_action_queue"
            status_bundle_path = root / "signal_phase_support_status_bundle.json"
            validation_ready_queue_path = root / "validation_ready_queue.csv"
            validation_hold_queue_path = root / "validation_hold_queue.csv"

            self._write_csv(
                validation_ready_queue_path,
                [
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "profile_id",
                    "workbook_path",
                    "delivery_csv_path",
                    "mapping_stub_path",
                    "validation_command",
                    "ready_row_count",
                    "pending_row_count",
                    "total_row_count",
                    "validation_state_category",
                    "next_action",
                ],
                [
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "profile_id": "arm_phase_mapping_sheet",
                        "workbook_path": "/tmp/manual_workbook.csv",
                        "delivery_csv_path": "/tmp/by_request/bari_signal_phase_01/arm_phase_mapping_sheet_delivery.csv",
                        "mapping_stub_path": "/tmp/manual_stub.json",
                        "validation_command": "validate manual",
                        "ready_row_count": 4,
                        "pending_row_count": 0,
                        "total_row_count": 4,
                        "validation_state_category": "ready_for_validation",
                        "next_action": "Run validation.",
                    }
                ],
            )
            self._write_csv(
                validation_hold_queue_path,
                [
                    "request_id",
                    "junction_id",
                    "signal_name",
                    "profile_id",
                    "workbook_path",
                    "delivery_csv_path",
                    "mapping_stub_path",
                    "validation_command",
                    "ready_row_count",
                    "pending_row_count",
                    "total_row_count",
                    "validation_state_category",
                    "next_action",
                ],
                [
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "profile_id": "pedestrian_stage_mapping_sheet",
                        "workbook_path": "/tmp/ped_workbook.csv",
                        "delivery_csv_path": "/tmp/by_request/bari_signal_phase_01/pedestrian_stage_mapping_sheet_delivery.csv",
                        "mapping_stub_path": "/tmp/ped_stub.json",
                        "validation_command": "validate pedestrian",
                        "ready_row_count": 0,
                        "pending_row_count": 8,
                        "total_row_count": 8,
                        "validation_state_category": "waiting_for_analyst_resolution",
                        "next_action": "Finish workbook rows.",
                    }
                ],
            )

            status_bundle_path.write_text(
                json.dumps(
                    {
                        "validation_ready_queue_path": str(validation_ready_queue_path),
                        "validation_hold_queue_path": str(validation_hold_queue_path),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_action_queue(
                output_dir=output_dir,
                signal_phase_support_status_bundle_path=status_bundle_path,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_support_action_queue_builder")
            self.assertEqual(manifest["stats"]["profile_count"], 2)
            self.assertEqual(manifest["stats"]["execution_ready_count"], 2)
            self.assertEqual(manifest["stats"]["workbook_fill_action_count"], 1)
            self.assertEqual(manifest["stats"]["validation_action_count"], 1)
            self.assertEqual(manifest["stats"]["internal_hold_count"], 0)

            with (output_dir / "action_execution_ready_queue.csv").open("r", encoding="utf-8", newline="") as handle:
                ready_rows = list(csv.DictReader(handle))
            self.assertEqual(len(ready_rows), 2)
            self.assertEqual(
                {row["action_category"] for row in ready_rows},
                {"fill_support_workbook_now", "validate_support_delivery_now"},
            )
            self.assertEqual(
                {row["delivery_csv_path"] for row in ready_rows},
                {
                    "/tmp/by_request/bari_signal_phase_01/arm_phase_mapping_sheet_delivery.csv",
                    "/tmp/by_request/bari_signal_phase_01/pedestrian_stage_mapping_sheet_delivery.csv",
                },
            )
            self.assertEqual(
                {row["execution_route"] for row in ready_rows},
                {"analyst_workbook_fill", "validate_delivery"},
            )

            packet_path = output_dir / "action_packets" / "bari_signal_phase_01__arm_phase_mapping_sheet.md"
            self.assertTrue(packet_path.exists())

            payload = json.loads((output_dir / "signal_phase_support_action_queue.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["execution_ready_count"], 2)

    def test_build_bari_signal_phase_support_action_queue_applies_apply_status_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_action_queue"
            status_bundle_path = root / "signal_phase_support_status_bundle.json"
            apply_status_bundle_path = root / "signal_phase_support_apply_status_bundle.json"
            validation_ready_queue_path = root / "validation_ready_queue.csv"
            validation_hold_queue_path = root / "validation_hold_queue.csv"
            support_apply_status_path = root / "support_apply_status.csv"

            fieldnames = [
                "request_id",
                "junction_id",
                "signal_name",
                "profile_id",
                "workbook_path",
                "delivery_csv_path",
                "mapping_stub_path",
                "validation_command",
                "ready_row_count",
                "pending_row_count",
                "total_row_count",
                "validation_state_category",
                "next_action",
            ]
            self._write_csv(
                validation_ready_queue_path,
                fieldnames,
                [
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "profile_id": "arm_phase_mapping_sheet",
                        "workbook_path": "/tmp/manual_workbook.csv",
                        "delivery_csv_path": "/tmp/by_request/bari_signal_phase_01/arm_phase_mapping_sheet_delivery.csv",
                        "mapping_stub_path": "/tmp/manual_stub.json",
                        "validation_command": "validate manual",
                        "ready_row_count": 4,
                        "pending_row_count": 0,
                        "total_row_count": 4,
                        "validation_state_category": "ready_for_validation",
                        "next_action": "Run validation",
                    }
                ],
            )
            self._write_csv(validation_hold_queue_path, fieldnames, [])
            status_bundle_path.write_text(
                json.dumps(
                    {
                        "validation_ready_queue_path": str(validation_ready_queue_path),
                        "validation_hold_queue_path": str(validation_hold_queue_path),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            self._write_csv(
                support_apply_status_path,
                [
                    "request_id",
                    "profile_id",
                    "apply_status_category",
                    "action_summary",
                    "next_action",
                    "validation_outcome",
                    "validation_manifest_path",
                    "delivery_session_manifest_path",
                    "movement_signal_phase_manifest_path",
                    "ingested_manifest_path",
                ],
                [
                    {
                        "request_id": "bari_signal_phase_01",
                        "profile_id": "arm_phase_mapping_sheet",
                        "apply_status_category": "applied_to_movement_layer",
                        "action_summary": "Already applied.",
                        "next_action": "Do not rerun.",
                        "validation_outcome": "accepted_for_ingestion",
                        "validation_manifest_path": "/tmp/validation.manifest.json",
                        "delivery_session_manifest_path": "/tmp/delivery_session.manifest.json",
                        "movement_signal_phase_manifest_path": "/tmp/movement.manifest.json",
                        "ingested_manifest_path": "/tmp/ingested.manifest.json",
                    }
                ],
            )
            apply_status_bundle_path.write_text(
                json.dumps(
                    {"support_apply_status_path": str(support_apply_status_path)},
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_action_queue(
                output_dir=output_dir,
                signal_phase_support_status_bundle_path=status_bundle_path,
                signal_phase_support_apply_status_bundle_path=apply_status_bundle_path,
            )

            self.assertEqual(manifest["stats"]["execution_ready_count"], 0)
            self.assertEqual(manifest["stats"]["apply_complete_count"], 1)

            with (output_dir / "action_internal_hold_queue.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["action_category"], "support_apply_complete")
            self.assertEqual(rows[0]["due_now"], "no")


if __name__ == "__main__":
    unittest.main()
