from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_operations_cycle import (
    run_bari_signal_phase_operations_cycle,
)


class SignalPhaseOperationsCycleTest(unittest.TestCase):
    def test_run_bari_signal_phase_operations_cycle_chains_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "operations_cycle"
            intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"

            intake_bundle_path.write_text("{}", encoding="utf-8")
            delivery_receipt_register_path.write_text("dispatch_reference\n", encoding="utf-8")
            delivery_checklist_path.write_text("delivery_item_id\n", encoding="utf-8")
            movement_objects_path.write_text("{}", encoding="utf-8")
            dispatch_execution_queue_path.write_text("request_id\n", encoding="utf-8")
            follow_up_tracker_path.write_text("request_id\n", encoding="utf-8")

            def _write_manifest(path: Path) -> str:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"manifest_path": str(path)}, indent=2), encoding="utf-8")
                return str(path)

            with (
                patch(
                    "road_risk_modeling.signal_phase_operations_cycle.run_bari_signal_phase_receive_cycle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_receive_cycle.manifest.json"
                        ),
                        "stats": {
                            "monitored_delivery_count": 18,
                            "validation_ready_count": 0,
                            "accepted_for_ingestion_count": 0,
                        },
                    },
                ) as receive_mock,
                patch(
                    "road_risk_modeling.signal_phase_operations_cycle.build_bari_signal_phase_status_sync_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_status_sync_bundle.manifest.json"
                        ),
                        "stats": {"validated_count": 0},
                    },
                ) as status_sync_mock,
                patch(
                    "road_risk_modeling.signal_phase_operations_cycle.build_bari_signal_phase_lifecycle_report",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_lifecycle_report.manifest.json"
                        ),
                        "stats": {
                            "delivery_item_count": 18,
                            "pending_follow_up_count": 36,
                        },
                    },
                ) as lifecycle_mock,
                patch(
                    "road_risk_modeling.signal_phase_operations_cycle.build_bari_signal_phase_follow_up_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_follow_up_bundle.manifest.json"
                        ),
                        "stats": {"request_count": 6},
                    },
                ) as follow_up_mock,
                patch(
                    "road_risk_modeling.signal_phase_operations_cycle.build_bari_signal_phase_follow_up_execution_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_follow_up_execution_bundle.manifest.json"
                        ),
                        "stats": {"execution_ready_count": 6},
                    },
                ) as execution_mock,
                patch(
                    "road_risk_modeling.signal_phase_operations_cycle.build_bari_signal_phase_follow_up_writeback_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_follow_up_writeback_bundle.manifest.json"
                        ),
                        "stats": {"writeback_ready_count": 0},
                    },
                ) as writeback_mock,
                patch(
                    "road_risk_modeling.signal_phase_operations_cycle.run_bari_signal_phase_follow_up_cycle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_follow_up_cycle.manifest.json"
                        ),
                        "stats": {"runtime_execution_ready_count": 6},
                    },
                ) as follow_up_cycle_mock,
            ):
                result = run_bari_signal_phase_operations_cycle(
                    output_dir=output_dir,
                    signal_phase_delivery_intake_bundle_path=intake_bundle_path,
                    delivery_receipt_register_path=delivery_receipt_register_path,
                    delivery_checklist_path=delivery_checklist_path,
                    movement_objects_path=movement_objects_path,
                    dispatch_execution_queue_path=dispatch_execution_queue_path,
                    follow_up_tracker_path=follow_up_tracker_path,
                    preview_limit=5,
                )

            self.assertEqual(result["stats"]["receive_monitored_delivery_count"], 18)
            self.assertEqual(result["stats"]["follow_up_execution_ready_count"], 6)
            self.assertEqual(result["stats"]["runtime_execution_ready_count"], 6)

            receive_mock.assert_called_once()
            status_sync_mock.assert_called_once()
            lifecycle_mock.assert_called_once()
            follow_up_mock.assert_called_once()
            execution_mock.assert_called_once()
            writeback_mock.assert_called_once()
            follow_up_cycle_mock.assert_called_once()

            status_sync_kwargs = status_sync_mock.call_args.kwargs
            self.assertEqual(
                Path(status_sync_kwargs["delivery_monitor_queue_path"]),
                output_dir / "receive_cycle" / "monitor" / "delivery_monitor_queue.csv",
            )
            self.assertEqual(
                Path(status_sync_kwargs["validation_batch_results_path"]),
                output_dir / "receive_cycle" / "validation_batch" / "validation_batch_results.csv",
            )

            follow_up_kwargs = follow_up_mock.call_args.kwargs
            self.assertEqual(
                Path(follow_up_kwargs["follow_up_agenda_path"]),
                output_dir / "lifecycle" / "follow_up_agenda.csv",
            )
            self.assertEqual(
                Path(follow_up_kwargs["synced_receipt_register_path"]),
                output_dir / "status_sync" / "delivery_receipt_register_synced.csv",
            )

            cycle_kwargs = follow_up_cycle_mock.call_args.kwargs
            self.assertEqual(
                Path(cycle_kwargs["follow_up_writeback_bundle_path"]),
                output_dir / "follow_up_writeback" / "signal_phase_follow_up_writeback_bundle.json",
            )


if __name__ == "__main__":
    unittest.main()
