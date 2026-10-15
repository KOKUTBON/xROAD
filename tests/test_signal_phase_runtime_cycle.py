from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_runtime_cycle import (
    run_bari_signal_phase_runtime_cycle,
)


class SignalPhaseRuntimeCycleTest(unittest.TestCase):
    def test_run_bari_signal_phase_runtime_cycle_chains_dispatch_and_receive_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "runtime_cycle"
            intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_log_repair_log_path = root / "dispatch_log_repair_log.csv"
            dispatch_execution_log_path = root / "dispatch_execution_log.csv"

            intake_bundle_path.write_text("{}", encoding="utf-8")
            delivery_receipt_register_path.write_text("dispatch_reference\n", encoding="utf-8")
            delivery_checklist_path.write_text("delivery_item_id\n", encoding="utf-8")
            movement_objects_path.write_text("{}", encoding="utf-8")
            dispatch_execution_queue_path.write_text("request_id\n", encoding="utf-8")
            follow_up_tracker_path.write_text("request_id\n", encoding="utf-8")
            dispatch_bundle_path.write_text("{}", encoding="utf-8")
            dispatch_log_repair_queue_path.write_text("request_id\n", encoding="utf-8")
            dispatch_log_repair_log_path.write_text("request_id\n", encoding="utf-8")
            dispatch_execution_log_path.write_text("request_id\n", encoding="utf-8")

            def _write_manifest(path: Path) -> str:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"manifest_path": str(path)}, indent=2), encoding="utf-8")
                return str(path)

            with (
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.run_bari_signal_phase_operations_cycle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_operations_cycle.manifest.json"
                        ),
                        "stats": {
                            "receive_monitored_delivery_count": 18,
                            "lifecycle_delivery_item_count": 18,
                        },
                    },
                ) as operations_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_action_queue",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_action_queue.manifest.json"
                        ),
                        "stats": {"dispatch_action_count": 6},
                    },
                ) as action_queue_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_execution_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_execution_bundle.manifest.json"
                        ),
                        "stats": {"execution_ready_count": 6},
                    },
                ) as execution_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_recording_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_recording_bundle.manifest.json"
                        ),
                        "stats": {
                            "applied_execution_count": 0,
                            "unresolved_signalized_movement_total": 6,
                            "unresolved_signalized_crash_total": 13,
                        },
                    },
                ) as recording_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_repair_recording_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_repair_recording_bundle.manifest.json"
                        ),
                        "stats": {"applied_repair_count": 0},
                    },
                ) as repair_recording_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_validation_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_validation_bundle.manifest.json"
                        ),
                        "stats": {
                            "accepted_for_writeback_count": 0,
                            "rejected_for_writeback_count": 0,
                            "unresolved_signalized_movement_total": 6,
                            "unresolved_signalized_crash_total": 13,
                            "accepted_unresolved_signalized_crash_total": 13,
                            "rejected_unresolved_signalized_crash_total": 0,
                        },
                    },
                ) as validation_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_repair_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_repair_bundle.manifest.json"
                        ),
                        "stats": {"repair_request_count": 0},
                    },
                ) as repair_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_repair_execution_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_repair_execution_bundle.manifest.json"
                        ),
                        "stats": {"execution_ready_count": 0},
                    },
                ) as repair_execution_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_repair_status_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_repair_status_bundle.manifest.json"
                        ),
                        "stats": {
                            "pending_repair_count": 0,
                            "ready_for_validation_count": 0,
                            "still_blocked_count": 0,
                            "cleared_for_writeback_count": 0,
                        },
                    },
                ) as repair_status_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.build_bari_signal_phase_dispatch_writeback_bundle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_writeback_bundle.manifest.json"
                        ),
                        "stats": {
                            "writeback_ready_count": 0,
                            "unresolved_signalized_movement_total": 6,
                            "unresolved_signalized_crash_total": 13,
                            "writeback_ready_unresolved_signalized_crash_total": 13,
                        },
                    },
                ) as writeback_mock,
                patch(
                    "road_risk_modeling.signal_phase_runtime_cycle.run_bari_signal_phase_dispatch_cycle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_dispatch_cycle.manifest.json"
                        ),
                        "stats": {
                            "runtime_action_request_count": 6,
                            "runtime_action_execution_ready_count": 4,
                            "runtime_action_internal_hold_count": 2,
                            "runtime_action_handoff_ready_count": 4,
                            "runtime_operator_board_ready_count": 4,
                            "runtime_dispatch_action_count": 6,
                            "runtime_follow_up_action_count": 0,
                            "writeback_unresolved_signalized_crash_total": 13,
                        },
                    },
                ) as dispatch_cycle_mock,
            ):
                result = run_bari_signal_phase_runtime_cycle(
                    output_dir=output_dir,
                    signal_phase_delivery_intake_bundle_path=intake_bundle_path,
                    delivery_receipt_register_path=delivery_receipt_register_path,
                    delivery_checklist_path=delivery_checklist_path,
                    movement_objects_path=movement_objects_path,
                    dispatch_execution_queue_path=dispatch_execution_queue_path,
                    follow_up_tracker_path=follow_up_tracker_path,
                    signal_phase_dispatch_bundle_path=dispatch_bundle_path,
                    dispatch_log_repair_queue_path=dispatch_log_repair_queue_path,
                    dispatch_log_repair_log_path=dispatch_log_repair_log_path,
                    dispatch_execution_log_path=dispatch_execution_log_path,
                    preview_limit=5,
                )

            self.assertEqual(result["stats"]["receive_monitored_delivery_count"], 18)
            self.assertEqual(result["stats"]["dispatch_action_count"], 6)
            self.assertEqual(result["stats"]["runtime_action_execution_ready_count"], 4)
            self.assertEqual(result["stats"]["runtime_action_handoff_ready_count"], 4)
            self.assertEqual(result["stats"]["runtime_operator_board_ready_count"], 4)
            self.assertEqual(result["stats"]["runtime_dispatch_action_count"], 6)
            self.assertEqual(result["stats"]["dispatch_recording_unresolved_signalized_movement_total"], 6)
            self.assertEqual(result["stats"]["dispatch_validation_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["dispatch_writeback_unresolved_signalized_crash_total"], 13)
            self.assertEqual(result["stats"]["runtime_dispatch_cycle_unresolved_signalized_crash_total"], 13)

            operations_mock.assert_called_once()
            action_queue_mock.assert_called_once()
            execution_mock.assert_called_once()
            recording_mock.assert_called_once()
            repair_recording_mock.assert_called_once()
            validation_mock.assert_called_once()
            repair_mock.assert_called_once()
            repair_execution_mock.assert_called_once()
            repair_status_mock.assert_called_once()
            writeback_mock.assert_called_once()
            dispatch_cycle_mock.assert_called_once()

            action_kwargs = action_queue_mock.call_args.kwargs
            self.assertEqual(
                Path(action_kwargs["signal_phase_operations_cycle_path"]),
                output_dir / "operations_cycle" / "signal_phase_operations_cycle.json",
            )
            self.assertEqual(
                Path(action_kwargs["signal_phase_dispatch_bundle_path"]),
                dispatch_bundle_path,
            )

            recording_kwargs = recording_mock.call_args.kwargs
            self.assertEqual(
                Path(recording_kwargs["dispatch_execution_ready_queue_path"]),
                output_dir / "dispatch_execution" / "dispatch_execution_ready_queue.csv",
            )
            self.assertEqual(
                Path(recording_kwargs["dispatch_execution_log_path"]),
                dispatch_execution_log_path,
            )

            validation_kwargs = validation_mock.call_args.kwargs
            self.assertEqual(
                Path(validation_kwargs["dispatch_execution_runtime_queue_path"]),
                output_dir
                / "dispatch_repair_recording"
                / "dispatch_execution_queue_runtime_repaired.csv",
            )

            repair_recording_kwargs = repair_recording_mock.call_args.kwargs
            self.assertEqual(
                Path(repair_recording_kwargs["dispatch_execution_runtime_queue_path"]),
                output_dir / "dispatch_recording" / "dispatch_execution_queue_runtime.csv",
            )
            self.assertEqual(
                Path(repair_recording_kwargs["dispatch_log_repair_queue_path"]),
                dispatch_log_repair_queue_path,
            )
            self.assertEqual(
                Path(repair_recording_kwargs["dispatch_log_repair_log_path"]),
                dispatch_log_repair_log_path,
            )

            repair_kwargs = repair_mock.call_args.kwargs
            self.assertEqual(
                Path(repair_kwargs["dispatch_validation_queue_path"]),
                output_dir / "dispatch_validation" / "dispatch_execution_queue_validated.csv",
            )

            repair_execution_kwargs = repair_execution_mock.call_args.kwargs
            self.assertEqual(
                Path(repair_execution_kwargs["dispatch_log_repair_queue_path"]),
                output_dir / "dispatch_repair" / "dispatch_log_repair_queue.csv",
            )
            self.assertEqual(
                Path(repair_execution_kwargs["dispatch_log_repair_log_path"]),
                dispatch_log_repair_log_path,
            )

            repair_status_kwargs = repair_status_mock.call_args.kwargs
            self.assertEqual(
                Path(repair_status_kwargs["dispatch_log_repair_queue_path"]),
                output_dir / "dispatch_repair" / "dispatch_log_repair_queue.csv",
            )
            self.assertEqual(
                Path(repair_status_kwargs["dispatch_log_repair_log_path"]),
                dispatch_log_repair_log_path,
            )
            self.assertEqual(
                Path(repair_status_kwargs["dispatch_repair_execution_ready_queue_path"]),
                output_dir / "dispatch_repair_execution" / "dispatch_repair_execution_ready_queue.csv",
            )
            self.assertEqual(
                Path(repair_status_kwargs["dispatch_repair_internal_hold_queue_path"]),
                output_dir / "dispatch_repair_execution" / "dispatch_repair_internal_hold_queue.csv",
            )
            self.assertEqual(
                Path(repair_status_kwargs["dispatch_validation_queue_path"]),
                output_dir / "dispatch_validation" / "dispatch_execution_queue_validated.csv",
            )

            writeback_kwargs = writeback_mock.call_args.kwargs
            self.assertEqual(
                Path(writeback_kwargs["dispatch_execution_ready_queue_path"]),
                output_dir / "dispatch_validation" / "dispatch_execution_queue_validated.csv",
            )

            dispatch_cycle_kwargs = dispatch_cycle_mock.call_args.kwargs
            self.assertEqual(
                Path(dispatch_cycle_kwargs["signal_phase_dispatch_writeback_bundle_path"]),
                output_dir / "dispatch_writeback" / "signal_phase_dispatch_writeback_bundle.json",
            )
            self.assertEqual(
                Path(dispatch_cycle_kwargs["signal_phase_operations_cycle_path"]),
                output_dir / "operations_cycle" / "signal_phase_operations_cycle.json",
            )
            self.assertEqual(
                Path(dispatch_cycle_kwargs["dispatch_log_repair_queue_path"]),
                output_dir / "dispatch_repair" / "dispatch_log_repair_queue.csv",
            )
            self.assertEqual(
                Path(dispatch_cycle_kwargs["dispatch_repair_status_path"]),
                output_dir / "dispatch_repair_status" / "dispatch_repair_status.csv",
            )
            self.assertEqual(
                Path(dispatch_cycle_kwargs["delivery_monitor_queue_path"]),
                output_dir / "operations_cycle" / "receive_cycle" / "monitor" / "delivery_monitor_queue.csv",
            )

            cycle_md = (output_dir / "signal_phase_runtime_cycle.md").read_text(encoding="utf-8")
            self.assertIn("dispatch-cycle carried unresolved signalized crashes: `13`", cycle_md)


if __name__ == "__main__":
    unittest.main()
