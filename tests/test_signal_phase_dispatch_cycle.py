from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_dispatch_cycle import (
    run_bari_signal_phase_dispatch_cycle,
)


class SignalPhaseDispatchCycleTest(unittest.TestCase):
    def test_run_bari_signal_phase_dispatch_cycle_rebuilds_runtime_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "dispatch_cycle"
            synced_dispatch_path = root / "writeback" / "dispatch_execution_queue_synced.csv"
            synced_tracker_path = root / "writeback" / "follow_up_tracker_synced.csv"
            writeback_bundle_path = root / "writeback" / "signal_phase_dispatch_writeback_bundle.json"
            delivery_receipt_register_path = root / "intake" / "delivery_receipt_register.csv"
            delivery_monitor_queue_path = root / "monitor" / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation" / "validation_batch_results.csv"
            receive_cycle_path = root / "receive" / "signal_phase_receive_cycle.json"
            synced_receipt_register_path = root / "status_sync" / "delivery_receipt_register_synced.csv"
            operations_cycle_path = root / "operations" / "signal_phase_operations_cycle.json"
            dispatch_bundle_path = root / "dispatch" / "signal_phase_dispatch_bundle.json"
            dispatch_log_repair_queue_path = root / "repair" / "dispatch_log_repair_queue.csv"
            dispatch_repair_status_path = root / "repair_status" / "dispatch_repair_status.csv"

            synced_dispatch_path.parent.mkdir(parents=True, exist_ok=True)
            synced_dispatch_path.write_text("request_id\n", encoding="utf-8")
            synced_tracker_path.write_text("request_id\n", encoding="utf-8")
            writeback_bundle_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "writeback_ready_count": 1,
                            "dispatch_rows_updated_count": 1,
                            "tracker_rows_retimed_count": 1,
                            "targets_with_unresolved_movements": 1,
                            "unresolved_signalized_movement_total": 6,
                            "unresolved_signalized_crash_total": 13,
                            "writeback_ready_unresolved_signalized_movement_total": 6,
                            "writeback_ready_unresolved_signalized_crash_total": 13,
                        },
                        "outputs": {
                            "synced_dispatch_execution_queue_path": str(synced_dispatch_path),
                            "synced_follow_up_tracker_path": str(synced_tracker_path),
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            delivery_receipt_register_path.parent.mkdir(parents=True, exist_ok=True)
            delivery_receipt_register_path.write_text("dispatch_reference\n", encoding="utf-8")
            delivery_monitor_queue_path.parent.mkdir(parents=True, exist_ok=True)
            delivery_monitor_queue_path.write_text("delivery_item_id\n", encoding="utf-8")
            validation_batch_results_path.parent.mkdir(parents=True, exist_ok=True)
            validation_batch_results_path.write_text("delivery_item_id\n", encoding="utf-8")
            receive_cycle_path.parent.mkdir(parents=True, exist_ok=True)
            receive_cycle_path.write_text("{}", encoding="utf-8")
            synced_receipt_register_path.parent.mkdir(parents=True, exist_ok=True)
            synced_receipt_register_path.write_text("dispatch_reference\n", encoding="utf-8")
            operations_cycle_path.parent.mkdir(parents=True, exist_ok=True)
            operations_cycle_path.write_text("{}", encoding="utf-8")
            dispatch_bundle_path.parent.mkdir(parents=True, exist_ok=True)
            dispatch_bundle_path.write_text("{}", encoding="utf-8")
            dispatch_log_repair_queue_path.parent.mkdir(parents=True, exist_ok=True)
            dispatch_log_repair_queue_path.write_text("request_id\n", encoding="utf-8")
            dispatch_repair_status_path.parent.mkdir(parents=True, exist_ok=True)
            dispatch_repair_status_path.write_text("request_id\n", encoding="utf-8")

            def _write_manifest(path: Path) -> str:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"manifest_path": str(path)}, indent=2), encoding="utf-8")
                return str(path)

            with (
                patch(
                    "road_risk_modeling.signal_phase_dispatch_cycle.build_bari_signal_phase_lifecycle_report",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_lifecycle_report.manifest.json"
                        ),
                        "stats": {
                            "delivery_item_count": 18,
                            "pending_follow_up_count": 12,
                            "due_follow_up_count": 6,
                        },
                    },
                ) as lifecycle_mock,
                patch(
                    "road_risk_modeling.signal_phase_dispatch_cycle.build_bari_signal_phase_follow_up_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_follow_up_bundle.manifest.json"
                        ),
                        "stats": {"request_count": 6, "due_now_count": 2},
                    },
                ) as follow_up_mock,
                patch(
                    "road_risk_modeling.signal_phase_dispatch_cycle.build_bari_signal_phase_follow_up_execution_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_follow_up_execution_bundle.manifest.json"
                        ),
                        "stats": {"execution_ready_count": 2, "internal_hold_count": 1},
                    },
                ) as execution_mock,
                patch(
                    "road_risk_modeling.signal_phase_dispatch_cycle.build_bari_signal_phase_action_queue",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_action_queue.manifest.json"
                        ),
                        "stats": {
                            "request_count": 6,
                            "immediate_action_count": 2,
                            "dispatch_action_count": 1,
                            "dispatch_log_fix_action_count": 0,
                            "follow_up_action_count": 1,
                        },
                    },
                ) as action_queue_mock,
                patch(
                    "road_risk_modeling.signal_phase_dispatch_cycle.build_bari_signal_phase_action_execution_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"])
                            / "signal_phase_action_execution_bundle.manifest.json"
                        ),
                        "stats": {
                            "execution_ready_count": 3,
                            "internal_hold_count": 3,
                        },
                    },
                ) as action_execution_mock,
                patch(
                    "road_risk_modeling.signal_phase_dispatch_cycle.build_bari_signal_phase_action_handoff_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"])
                            / "signal_phase_action_handoff_bundle.manifest.json"
                        ),
                        "stats": {
                            "handoff_ready_count": 3,
                            "internal_hold_count": 3,
                        },
                    },
                ) as action_handoff_mock,
                patch(
                    "road_risk_modeling.signal_phase_dispatch_cycle.build_bari_signal_phase_operator_board_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"])
                            / "signal_phase_operator_board_bundle.manifest.json"
                        ),
                        "stats": {
                            "operator_ready_count": 3,
                            "internal_hold_count": 3,
                        },
                    },
                ) as operator_board_mock,
            ):
                result = run_bari_signal_phase_dispatch_cycle(
                    output_dir=output_dir,
                    signal_phase_dispatch_writeback_bundle_path=writeback_bundle_path,
                    delivery_receipt_register_path=delivery_receipt_register_path,
                    delivery_monitor_queue_path=delivery_monitor_queue_path,
                    validation_batch_results_path=validation_batch_results_path,
                    receive_cycle_path=receive_cycle_path,
                    synced_receipt_register_path=synced_receipt_register_path,
                    signal_phase_operations_cycle_path=operations_cycle_path,
                    signal_phase_dispatch_bundle_path=dispatch_bundle_path,
                    dispatch_log_repair_queue_path=dispatch_log_repair_queue_path,
                    dispatch_repair_status_path=dispatch_repair_status_path,
                )

            self.assertEqual(result["stats"]["writeback_ready_count"], 1)
            self.assertEqual(result["stats"]["runtime_lifecycle_delivery_item_count"], 18)
            self.assertEqual(result["stats"]["runtime_action_request_count"], 6)
            self.assertEqual(result["stats"]["runtime_action_execution_ready_count"], 3)
            self.assertEqual(result["stats"]["runtime_action_handoff_ready_count"], 3)
            self.assertEqual(result["stats"]["runtime_operator_board_ready_count"], 3)
            self.assertEqual(result["stats"]["runtime_dispatch_action_count"], 1)
            self.assertEqual(result["stats"]["writeback_targets_with_unresolved_movements"], 1)
            self.assertEqual(result["stats"]["writeback_unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["writeback_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["writeback_ready_unresolved_signalized_crash_total"], 13)

            lifecycle_mock.assert_called_once()
            follow_up_mock.assert_called_once()
            execution_mock.assert_called_once()
            action_queue_mock.assert_called_once()
            action_execution_mock.assert_called_once()
            action_handoff_mock.assert_called_once()
            operator_board_mock.assert_called_once()

            lifecycle_kwargs = lifecycle_mock.call_args.kwargs
            self.assertEqual(
                Path(lifecycle_kwargs["dispatch_execution_queue_path"]),
                synced_dispatch_path,
            )
            self.assertEqual(
                Path(lifecycle_kwargs["follow_up_tracker_path"]),
                synced_tracker_path,
            )

            action_kwargs = action_queue_mock.call_args.kwargs
            self.assertEqual(
                Path(action_kwargs["dispatch_execution_queue_path"]),
                synced_dispatch_path,
            )
            self.assertEqual(
                Path(action_kwargs["signal_phase_operations_cycle_path"]),
                operations_cycle_path,
            )
            self.assertEqual(
                Path(action_kwargs["signal_phase_dispatch_bundle_path"]),
                dispatch_bundle_path,
            )
            self.assertEqual(
                Path(action_kwargs["lifecycle_items_path"]),
                output_dir / "runtime_lifecycle" / "lifecycle_items.csv",
            )
            self.assertEqual(
                Path(action_kwargs["follow_up_execution_queue_path"]),
                output_dir / "runtime_follow_up_execution" / "follow_up_execution_queue.csv",
            )
            self.assertEqual(
                Path(action_kwargs["dispatch_log_repair_queue_path"]),
                dispatch_log_repair_queue_path,
            )
            self.assertEqual(
                Path(action_kwargs["dispatch_repair_status_path"]),
                dispatch_repair_status_path,
            )

            action_execution_kwargs = action_execution_mock.call_args.kwargs
            self.assertEqual(
                Path(action_execution_kwargs["signal_phase_action_queue_path"]),
                output_dir / "runtime_action_queue" / "action_queue.csv",
            )

            action_handoff_kwargs = action_handoff_mock.call_args.kwargs
            self.assertEqual(
                Path(action_handoff_kwargs["signal_phase_action_execution_bundle_path"]),
                output_dir
                / "runtime_action_execution"
                / "signal_phase_action_execution_bundle.json",
            )

            operator_board_kwargs = operator_board_mock.call_args.kwargs
            self.assertEqual(
                Path(operator_board_kwargs["signal_phase_action_execution_bundle_path"]),
                output_dir
                / "runtime_action_execution"
                / "signal_phase_action_execution_bundle.json",
            )
            self.assertEqual(
                Path(operator_board_kwargs["signal_phase_action_handoff_bundle_path"]),
                output_dir
                / "runtime_action_handoff"
                / "signal_phase_action_handoff_bundle.json",
            )

            cycle_md = (output_dir / "signal_phase_dispatch_cycle.md").read_text(encoding="utf-8")
            self.assertIn("writeback unresolved signalized crashes: `13`", cycle_md)


if __name__ == "__main__":
    unittest.main()
