from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_support_runtime_cycle import (
    run_bari_signal_phase_support_runtime_cycle,
)


class SignalPhaseSupportRuntimeCycleTests(unittest.TestCase):
    def test_run_bari_signal_phase_support_runtime_cycle_chains_live_support_outputs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_runtime_cycle"
            support_resolution_bundle_path = root / "signal_phase_support_resolution_bundle.json"
            manual_mapping_stub_path = root / "arm_phase_mapping_sheet_mapping_stub.json"
            delivery_checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"

            support_resolution_bundle_path.write_text("{}", encoding="utf-8")
            manual_mapping_stub_path.write_text("{}", encoding="utf-8")
            delivery_checklist_path.write_text("delivery_item_id\n", encoding="utf-8")
            movement_objects_path.write_text("{}", encoding="utf-8")

            def _write_manifest(path: Path) -> str:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"manifest_path": str(path)}, indent=2), encoding="utf-8")
                return str(path)

            def _write_json(path: Path, payload: dict[str, object]) -> str:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
                return str(path)

            with (
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_writeback_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"]) / "signal_phase_support_writeback_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"]) / "signal_phase_support_writeback_bundle.json",
                                {
                                    "summary": {
                                        "support_request_count": 1,
                                        "manual_workbook_row_count": 18,
                                        "pedestrian_workbook_row_count": 8,
                                    }
                                },
                            ),
                        }
                    },
                ) as writeback_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_status_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"]) / "signal_phase_support_status_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"]) / "signal_phase_support_status_bundle.json",
                                {
                                    "summary": {
                                        "requests_pending_manual_resolution_count": 0,
                                        "requests_partially_ready_for_validation_count": 1,
                                        "requests_ready_for_validation_count": 0,
                                        "validation_ready_profile_count": 2,
                                    }
                                },
                            ),
                        }
                    },
                ) as status_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_action_queue",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"]) / "signal_phase_support_action_queue.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"]) / "signal_phase_support_action_queue.json",
                                {
                                    "summary": (
                                        {
                                            "workbook_fill_action_count": 0,
                                            "validation_action_count": 2,
                                            "validation_review_action_count": 0,
                                            "repair_action_count": 0,
                                            "apply_complete_count": 0,
                                            "apply_pending_count": 0,
                                            "internal_hold_count": 0,
                                        }
                                        if "signal_phase_support_apply_status_bundle_path"
                                        not in kwargs
                                        else {
                                            "workbook_fill_action_count": 0,
                                            "validation_action_count": 0,
                                            "validation_review_action_count": 0,
                                            "repair_action_count": 0,
                                            "apply_complete_count": 2,
                                            "apply_pending_count": 0,
                                            "internal_hold_count": 2,
                                        }
                                    )
                                },
                            ),
                            "action_execution_ready_queue_path": str(
                                Path(kwargs["output_dir"]) / "action_execution_ready_queue.csv"
                            ),
                        }
                    },
                ) as action_queue_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.run_bari_signal_phase_support_apply_cycle",
                    side_effect=lambda **kwargs: {
                        "manifest_path": _write_manifest(
                            Path(kwargs["output_dir"]) / "signal_phase_support_apply_cycle.manifest.json"
                        ),
                        "stats": {
                            "executed_validation_count": 2,
                            "accepted_for_ingestion_count": 2,
                            "accepted_support_artifact_count": 0,
                            "delivery_session_executed": True,
                            "movements_with_phase_timing": 0,
                            "movements_with_phase_mapping": 2,
                        },
                    },
                ) as apply_cycle_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_apply_status_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"]) / "signal_phase_support_apply_status_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"]) / "signal_phase_support_apply_status_bundle.json",
                                {
                                    "summary": {
                                        "profile_count": 2,
                                        "applied_profile_count": 2,
                                        "accepted_pending_apply_count": 0,
                                    }
                                },
                            ),
                        }
                    },
                ) as apply_status_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_request_state_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"]) / "signal_phase_support_request_state_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"]) / "signal_phase_support_request_state_bundle.json",
                                {
                                    "summary": {
                                        "pending_manual_resolution_count": 0,
                                        "partially_ready_for_validation_count": 0,
                                        "ready_for_validation_count": 0,
                                        "validation_review_required_count": 0,
                                        "accepted_pending_apply_count": 0,
                                        "partially_applied_count": 1,
                                        "fully_applied_count": 0,
                                    }
                                },
                            ),
                        }
                    },
                ) as request_state_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_operator_board_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"]) / "signal_phase_support_operator_board_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"]) / "signal_phase_support_operator_board_bundle.json",
                                {
                                    "summary": {
                                        "request_count": 1,
                                        "operator_ready_count": 0,
                                        "internal_hold_count": 1,
                                        "workbook_fill_request_count": 0,
                                        "validation_request_count": 0,
                                        "validation_review_request_count": 0,
                                        "repair_request_count": 0,
                                        "apply_pending_request_count": 0,
                                        "complete_request_count": 1,
                                    }
                                },
                            ),
                        }
                    },
                ) as operator_board_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_action_execution_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_action_execution_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_action_execution_bundle.json",
                                {
                                    "summary": {
                                        "request_count": 1,
                                        "execution_ready_count": 0,
                                        "internal_hold_count": 1,
                                        "workbook_fill_request_count": 0,
                                        "runtime_rerun_request_count": 0,
                                        "validation_review_request_count": 0,
                                        "repair_request_count": 0,
                                        "apply_pending_hold_count": 0,
                                        "complete_hold_count": 1,
                                    }
                                },
                            ),
                        }
                    },
                ) as action_execution_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_action_handoff_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_action_handoff_bundle.manifest.json"
                            ),
                            "bundle_json_path": _write_json(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_action_handoff_bundle.json",
                                {
                                    "summary": {
                                        "request_count": 1,
                                        "handoff_ready_count": 0,
                                        "internal_hold_count": 1,
                                        "workbook_handoff_count": 0,
                                        "runtime_rerun_handoff_count": 0,
                                        "validation_review_handoff_count": 0,
                                        "repair_handoff_count": 0,
                                        "apply_pending_hold_count": 0,
                                        "complete_hold_count": 1,
                                    }
                                },
                            ),
                        }
                    },
                ) as action_handoff_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_runtime_board_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_runtime_board_bundle.manifest.json"
                            ),
                            "bundle_json_path": _write_json(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_runtime_board_bundle.json",
                                {
                                    "summary": {
                                        "request_count": 1,
                                        "operator_ready_count": 0,
                                        "internal_hold_count": 1,
                                        "workbook_row_count": 0,
                                        "runtime_rerun_row_count": 0,
                                        "validation_review_row_count": 0,
                                        "repair_row_count": 0,
                                        "apply_pending_hold_count": 0,
                                        "complete_hold_count": 1,
                                    }
                                },
                            ),
                        }
                    },
                ) as runtime_board_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_runtime_action_queue",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_runtime_action_queue.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_runtime_action_queue.json",
                                {
                                    "summary": {
                                        "request_count": 1,
                                        "immediate_action_count": 0,
                                        "internal_hold_count": 1,
                                        "workbook_action_count": 0,
                                        "runtime_rerun_action_count": 0,
                                        "validation_review_action_count": 0,
                                        "repair_action_count": 0,
                                        "apply_pending_hold_count": 0,
                                        "complete_hold_count": 1,
                                    }
                                },
                            ),
                        }
                    },
                ) as runtime_action_queue_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_runtime_action_execution_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_runtime_action_execution_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_runtime_action_execution_bundle.json",
                                {
                                    "summary": {
                                        "request_count": 1,
                                        "execution_ready_count": 0,
                                        "internal_hold_count": 1,
                                        "workbook_fill_request_count": 0,
                                        "runtime_rerun_request_count": 0,
                                        "validation_review_request_count": 0,
                                        "repair_request_count": 0,
                                        "apply_pending_hold_count": 0,
                                        "complete_hold_count": 1,
                                    }
                                },
                            ),
                        }
                    },
                ) as runtime_action_execution_mock,
                patch(
                    "road_risk_modeling.signal_phase_support_runtime_cycle.build_bari_signal_phase_support_workbook_completion_bundle",
                    side_effect=lambda **kwargs: {
                        "outputs": {
                            "manifest_path": _write_manifest(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_workbook_completion_bundle.manifest.json"
                            ),
                            "report_json_path": _write_json(
                                Path(kwargs["output_dir"])
                                / "signal_phase_support_workbook_completion_bundle.json",
                                {
                                    "summary": {
                                        "request_count": 1,
                                        "workbook_fill_request_count": 0,
                                        "workbook_repair_request_count": 0,
                                        "completion_row_count": 0,
                                        "manual_completion_row_count": 0,
                                        "pedestrian_completion_row_count": 0,
                                        "non_workbook_execution_count": 0,
                                        "hold_request_count": 1,
                                        "total_crash_weight": 0,
                                        "top_completion_crash_total": 0,
                                    }
                                },
                            ),
                        }
                    },
                ) as workbook_completion_mock,
            ):
                result = run_bari_signal_phase_support_runtime_cycle(
                    output_dir=output_dir,
                    signal_phase_support_resolution_bundle_path=support_resolution_bundle_path,
                    manual_mapping_stub_path=manual_mapping_stub_path,
                    delivery_checklist_path=delivery_checklist_path,
                    movement_objects_path=movement_objects_path,
                    preview_limit=5,
                )

            self.assertEqual(result["stats"]["support_request_count"], 1)
            self.assertEqual(result["stats"]["validation_ready_profile_count"], 2)
            self.assertEqual(result["stats"]["pre_validation_action_count"], 2)
            self.assertEqual(result["stats"]["validation_action_count"], 0)
            self.assertEqual(result["stats"]["executed_validation_count"], 2)
            self.assertEqual(result["stats"]["accepted_for_ingestion_count"], 2)
            self.assertEqual(result["stats"]["applied_profile_count"], 2)
            self.assertEqual(result["stats"]["apply_complete_count"], 2)
            self.assertEqual(result["stats"]["final_partially_applied_count"], 1)
            self.assertEqual(result["stats"]["operator_ready_request_count"], 0)
            self.assertEqual(result["stats"]["operator_hold_request_count"], 1)
            self.assertEqual(result["stats"]["support_execution_ready_request_count"], 0)
            self.assertEqual(result["stats"]["support_execution_hold_request_count"], 1)
            self.assertEqual(result["stats"]["support_execution_complete_hold_count"], 1)
            self.assertEqual(result["stats"]["support_handoff_ready_request_count"], 0)
            self.assertEqual(result["stats"]["support_handoff_hold_request_count"], 1)
            self.assertEqual(result["stats"]["support_handoff_workbook_request_count"], 0)
            self.assertEqual(result["stats"]["support_handoff_complete_hold_count"], 1)
            self.assertEqual(result["stats"]["support_runtime_board_ready_request_count"], 0)
            self.assertEqual(result["stats"]["support_runtime_board_hold_request_count"], 1)
            self.assertEqual(result["stats"]["support_runtime_board_workbook_row_count"], 0)
            self.assertEqual(result["stats"]["support_runtime_action_queue_ready_count"], 0)
            self.assertEqual(result["stats"]["support_runtime_action_queue_hold_count"], 1)
            self.assertEqual(
                result["stats"]["support_runtime_action_queue_complete_hold_count"], 1
            )
            self.assertEqual(result["stats"]["support_runtime_execution_ready_request_count"], 0)
            self.assertEqual(result["stats"]["support_runtime_execution_hold_request_count"], 1)
            self.assertEqual(
                result["stats"]["support_runtime_execution_complete_hold_count"], 1
            )
            self.assertEqual(result["stats"]["support_workbook_completion_request_count"], 0)
            self.assertEqual(result["stats"]["support_workbook_completion_row_count"], 0)
            self.assertEqual(
                result["stats"]["support_workbook_completion_hold_request_count"], 1
            )
            self.assertEqual(
                result["stats"]["support_workbook_completion_total_crash_weight"], 0
            )
            self.assertTrue(result["stats"]["delivery_session_executed"])
            self.assertEqual(result["stats"]["movements_with_phase_mapping"], 2)

            writeback_mock.assert_called_once()
            status_mock.assert_called_once()
            self.assertEqual(action_queue_mock.call_count, 2)
            apply_cycle_mock.assert_called_once()
            apply_status_mock.assert_called_once()
            request_state_mock.assert_called_once()
            operator_board_mock.assert_called_once()
            action_execution_mock.assert_called_once()
            action_handoff_mock.assert_called_once()
            runtime_board_mock.assert_called_once()
            runtime_action_queue_mock.assert_called_once()
            runtime_action_execution_mock.assert_called_once()
            workbook_completion_mock.assert_called_once()

            status_kwargs = status_mock.call_args.kwargs
            self.assertEqual(
                Path(status_kwargs["signal_phase_support_writeback_bundle_path"]),
                output_dir / "support_writeback" / "signal_phase_support_writeback_bundle.json",
            )

            pre_action_queue_kwargs = action_queue_mock.call_args_list[0].kwargs
            self.assertEqual(
                Path(pre_action_queue_kwargs["signal_phase_support_status_bundle_path"]),
                output_dir / "support_status" / "signal_phase_support_status_bundle.json",
            )
            self.assertNotIn(
                "signal_phase_support_apply_status_bundle_path",
                pre_action_queue_kwargs,
            )

            apply_cycle_kwargs = apply_cycle_mock.call_args.kwargs
            self.assertEqual(
                Path(apply_cycle_kwargs["action_execution_ready_queue_path"]),
                output_dir / "support_action_queue_pre" / "action_execution_ready_queue.csv",
            )
            self.assertEqual(
                Path(apply_cycle_kwargs["delivery_checklist_path"]),
                delivery_checklist_path,
            )
            self.assertEqual(
                Path(apply_cycle_kwargs["movement_objects_path"]),
                movement_objects_path,
            )

            apply_status_kwargs = apply_status_mock.call_args.kwargs
            self.assertEqual(
                Path(apply_status_kwargs["signal_phase_support_status_bundle_path"]),
                output_dir / "support_status" / "signal_phase_support_status_bundle.json",
            )
            self.assertEqual(
                Path(apply_status_kwargs["signal_phase_support_apply_cycle_path"]),
                output_dir / "support_apply_cycle" / "signal_phase_support_apply_cycle.json",
            )

            request_state_kwargs = request_state_mock.call_args.kwargs
            self.assertEqual(
                Path(request_state_kwargs["signal_phase_support_status_bundle_path"]),
                output_dir / "support_status" / "signal_phase_support_status_bundle.json",
            )
            self.assertEqual(
                Path(request_state_kwargs["signal_phase_support_apply_status_bundle_path"]),
                output_dir / "support_apply_status" / "signal_phase_support_apply_status_bundle.json",
            )

            operator_board_kwargs = operator_board_mock.call_args.kwargs
            self.assertEqual(
                Path(operator_board_kwargs["signal_phase_support_request_state_bundle_path"]),
                output_dir / "support_request_state" / "signal_phase_support_request_state_bundle.json",
            )
            self.assertEqual(
                Path(operator_board_kwargs["signal_phase_support_action_queue_path"]),
                output_dir / "support_action_queue" / "signal_phase_support_action_queue.json",
            )

            action_execution_kwargs = action_execution_mock.call_args.kwargs
            self.assertEqual(
                Path(action_execution_kwargs["signal_phase_support_operator_board_bundle_path"]),
                output_dir
                / "support_operator_board"
                / "signal_phase_support_operator_board_bundle.json",
            )

            action_handoff_kwargs = action_handoff_mock.call_args.kwargs
            self.assertEqual(
                Path(
                    action_handoff_kwargs[
                        "signal_phase_support_action_execution_bundle_path"
                    ]
                ),
                output_dir
                / "support_action_execution"
                / "signal_phase_support_action_execution_bundle.json",
            )
            self.assertEqual(
                Path(action_handoff_kwargs["support_runtime_cycle_manifest_path"]),
                output_dir / "signal_phase_support_runtime_cycle.manifest.json",
            )

            runtime_board_kwargs = runtime_board_mock.call_args.kwargs
            self.assertEqual(
                Path(
                    runtime_board_kwargs[
                        "signal_phase_support_action_execution_bundle_path"
                    ]
                ),
                output_dir
                / "support_action_execution"
                / "signal_phase_support_action_execution_bundle.json",
            )
            self.assertEqual(
                Path(
                    runtime_board_kwargs[
                        "signal_phase_support_action_handoff_bundle_path"
                    ]
                ),
                output_dir
                / "support_action_handoff"
                / "signal_phase_support_action_handoff_bundle.json",
            )

            runtime_action_queue_kwargs = runtime_action_queue_mock.call_args.kwargs
            self.assertEqual(
                Path(
                    runtime_action_queue_kwargs[
                        "signal_phase_support_runtime_board_bundle_path"
                    ]
                ),
                output_dir
                / "support_runtime_board"
                / "signal_phase_support_runtime_board_bundle.json",
            )

            runtime_action_execution_kwargs = runtime_action_execution_mock.call_args.kwargs
            self.assertEqual(
                Path(
                    runtime_action_execution_kwargs[
                        "signal_phase_support_runtime_action_queue_path"
                    ]
                ),
                output_dir
                / "support_runtime_action_queue"
                / "signal_phase_support_runtime_action_queue.json",
            )

            workbook_completion_kwargs = workbook_completion_mock.call_args.kwargs
            self.assertEqual(
                Path(
                    workbook_completion_kwargs[
                        "signal_phase_support_runtime_action_execution_bundle_path"
                    ]
                ),
                output_dir
                / "support_runtime_action_execution"
                / "signal_phase_support_runtime_action_execution_bundle.json",
            )
            self.assertEqual(
                Path(
                    workbook_completion_kwargs[
                        "signal_phase_support_writeback_bundle_path"
                    ]
                ),
                output_dir
                / "support_writeback"
                / "signal_phase_support_writeback_bundle.json",
            )

            post_action_queue_kwargs = action_queue_mock.call_args_list[1].kwargs
            self.assertEqual(
                Path(post_action_queue_kwargs["signal_phase_support_apply_status_bundle_path"]),
                output_dir / "support_apply_status" / "signal_phase_support_apply_status_bundle.json",
            )

            manifest = json.loads(
                (output_dir / "signal_phase_support_runtime_cycle.manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                manifest["outputs"]["support_action_execution_manifest_path"],
                str(
                    output_dir
                    / "support_action_execution"
                    / "signal_phase_support_action_execution_bundle.manifest.json"
                ),
            )
            self.assertEqual(
                manifest["outputs"]["support_action_handoff_manifest_path"],
                str(
                    output_dir
                    / "support_action_handoff"
                    / "signal_phase_support_action_handoff_bundle.manifest.json"
                ),
            )
            self.assertEqual(
                manifest["outputs"]["support_runtime_board_manifest_path"],
                str(
                    output_dir
                    / "support_runtime_board"
                    / "signal_phase_support_runtime_board_bundle.manifest.json"
                ),
            )
            self.assertEqual(
                manifest["outputs"]["support_runtime_action_queue_manifest_path"],
                str(
                    output_dir
                    / "support_runtime_action_queue"
                    / "signal_phase_support_runtime_action_queue.manifest.json"
                ),
            )
            self.assertEqual(
                manifest["outputs"]["support_runtime_action_execution_manifest_path"],
                str(
                    output_dir
                    / "support_runtime_action_execution"
                    / "signal_phase_support_runtime_action_execution_bundle.manifest.json"
                ),
            )
            self.assertEqual(
                manifest["outputs"]["support_workbook_completion_manifest_path"],
                str(
                    output_dir
                    / "support_workbook_completion"
                    / "signal_phase_support_workbook_completion_bundle.manifest.json"
                ),
            )


if __name__ == "__main__":
    unittest.main()
