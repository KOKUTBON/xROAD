from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.signal_phase_support_apply_status import (
    build_bari_signal_phase_support_apply_status_bundle,
)


class SignalPhaseSupportApplyStatusTests(unittest.TestCase):
    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_build_bari_signal_phase_support_apply_status_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_apply_status"
            status_bundle_path = root / "signal_phase_support_status_bundle.json"
            apply_cycle_path = root / "signal_phase_support_apply_cycle.json"
            validation_ready_queue_path = root / "validation_ready_queue.csv"
            validation_hold_queue_path = root / "validation_hold_queue.csv"
            validation_batch_manifest_path = root / "support_validation_batch.manifest.json"
            validation_batch_json_path = root / "support_validation_batch.json"
            validation_manifest_path = root / "validation_outputs" / "arm_phase" / "signal_phase_delivery_validation.manifest.json"
            delivery_session_manifest_path = root / "signal_phase_delivery_session.manifest.json"
            delivery_session_json_path = root / "signal_phase_delivery_session.json"

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
                        "validation_command": "validate arm",
                        "ready_row_count": 4,
                        "pending_row_count": 0,
                        "total_row_count": 4,
                        "validation_state_category": "ready_for_validation",
                        "next_action": "Run validation",
                    }
                ],
            )
            self._write_csv(
                validation_hold_queue_path,
                fieldnames,
                [
                    {
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "Via A",
                        "profile_id": "pedestrian_stage_mapping_sheet",
                        "workbook_path": "/tmp/ped_workbook.csv",
                        "delivery_csv_path": "/tmp/by_request/bari_signal_phase_01/pedestrian_stage_mapping_sheet_delivery.csv",
                        "mapping_stub_path": "/tmp/ped_stub.json",
                        "validation_command": "validate ped",
                        "ready_row_count": 0,
                        "pending_row_count": 8,
                        "total_row_count": 8,
                        "validation_state_category": "waiting_for_analyst_resolution",
                        "next_action": "Fill workbook",
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

            validation_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            validation_manifest_path.write_text(
                json.dumps(
                    {
                        "inputs": {"request_id": "bari_signal_phase_01"},
                        "profile": {"profile_id": "arm_phase_mapping_sheet"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            validation_batch_json_path.write_text(
                json.dumps(
                    {
                        "validation_results": [
                            {
                                "request_id": "bari_signal_phase_01",
                                "profile_id": "arm_phase_mapping_sheet",
                                "validation_outcome": "accepted_for_ingestion",
                                "batch_outcome": "validated",
                                "manifest_path": str(validation_manifest_path),
                            },
                            {
                                "request_id": "bari_signal_phase_01",
                                "profile_id": "pedestrian_stage_mapping_sheet",
                                "validation_outcome": "provider_fix_required",
                                "batch_outcome": "validated",
                                "manifest_path": str(root / "validation_outputs" / "pedestrian" / "signal_phase_delivery_validation.manifest.json"),
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            validation_batch_manifest_path.write_text(
                json.dumps(
                    {"outputs": {"batch_json_path": str(validation_batch_json_path)}},
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            delivery_session_json_path.write_text(
                json.dumps(
                    {
                        "accepted_deliveries": [
                            {
                                "validation_manifest_path": str(validation_manifest_path),
                                "ingested_manifest_path": str(root / "ingested_records.manifest.json"),
                            }
                        ],
                        "outputs": {
                            "movement_signal_phase_manifest_path": str(
                                root / "road_movement_objects_signal_phase.manifest.json"
                            )
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            delivery_session_manifest_path.write_text(
                json.dumps(
                    {"outputs": {"session_json_path": str(delivery_session_json_path)}},
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            apply_cycle_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "support_validation_batch_manifest_path": str(validation_batch_manifest_path),
                            "delivery_session_manifest_path": str(delivery_session_manifest_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_bari_signal_phase_support_apply_status_bundle(
                output_dir=output_dir,
                signal_phase_support_status_bundle_path=status_bundle_path,
                signal_phase_support_apply_cycle_path=apply_cycle_path,
            )

            self.assertEqual(
                manifest["source"]["adapter"],
                "bari_signal_phase_support_apply_status_bundle_builder",
            )
            self.assertEqual(manifest["stats"]["profile_count"], 2)
            self.assertEqual(manifest["stats"]["applied_profile_count"], 1)
            self.assertEqual(manifest["stats"]["validation_failed_count"], 1)

            with (output_dir / "support_apply_status.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

            category_by_profile = {
                row["profile_id"]: row["apply_status_category"] for row in rows
            }
            self.assertEqual(
                category_by_profile["arm_phase_mapping_sheet"], "applied_to_movement_layer"
            )
            self.assertEqual(
                category_by_profile["pedestrian_stage_mapping_sheet"], "validation_failed"
            )


if __name__ == "__main__":
    unittest.main()
