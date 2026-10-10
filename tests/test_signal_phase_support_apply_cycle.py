from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_support_apply_cycle import run_bari_signal_phase_support_apply_cycle


class SignalPhaseSupportApplyCycleTests(unittest.TestCase):
    def test_run_bari_signal_phase_support_apply_cycle_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_apply_cycle"
            action_queue_path = root / "action_execution_ready_queue.csv"
            checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            batch_manifest_path = output_dir / "support_validation_batch" / "signal_phase_support_validation_batch.manifest.json"
            batch_json_path = output_dir / "support_validation_batch" / "signal_phase_support_validation_batch.json"

            action_queue_path.write_text("support_action_reference\n", encoding="utf-8")
            checklist_path.write_text("delivery_item_id\n", encoding="utf-8")
            movement_objects_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            batch_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            batch_json_path.write_text(
                json.dumps(
                    {
                        "validation_results": [
                            {
                                "support_action_reference": "bari_signal_phase_01:arm_phase_mapping_sheet",
                                "batch_outcome": "skipped_non_validation_action",
                                "validation_outcome": "",
                                "manifest_path": "",
                            }
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            batch_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "batch_json_path": str(batch_json_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with patch(
                "road_risk_modeling.signal_phase_support_apply_cycle.run_bari_signal_phase_support_validation_batch",
                return_value={
                    "manifest_path": str(batch_manifest_path),
                    "stats": {
                        "action_queue_count": 2,
                        "validation_candidate_count": 0,
                        "executed_validation_count": 0,
                        "accepted_for_ingestion_count": 0,
                        "accepted_support_artifact_count": 0,
                        "partial_review_count": 0,
                        "provider_fix_required_count": 0,
                        "skipped_non_validation_action_count": 2,
                        "skipped_missing_validation_inputs_count": 0,
                    },
                },
            ) as batch_mock, patch(
                "road_risk_modeling.signal_phase_support_apply_cycle.apply_validated_signal_phase_deliveries",
            ) as apply_mock:
                result = run_bari_signal_phase_support_apply_cycle(
                    output_dir=output_dir,
                    action_execution_ready_queue_path=action_queue_path,
                    delivery_checklist_path=checklist_path,
                    movement_objects_path=movement_objects_path,
                )

            self.assertEqual(result["stats"]["action_queue_count"], 2)
            self.assertEqual(result["stats"]["accepted_for_ingestion_count"], 0)
            self.assertFalse(result["stats"]["delivery_session_executed"])
            batch_mock.assert_called_once()
            apply_mock.assert_not_called()

            payload = json.loads((output_dir / "signal_phase_support_apply_cycle.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["stats"]["skipped_non_validation_action_count"], 2)
            self.assertIsNone(payload["outputs"]["delivery_session_manifest_path"])

    def test_run_bari_signal_phase_support_apply_cycle_executes_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "support_apply_cycle"
            action_queue_path = root / "action_execution_ready_queue.csv"
            checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            batch_manifest_path = output_dir / "support_validation_batch" / "signal_phase_support_validation_batch.manifest.json"
            batch_json_path = output_dir / "support_validation_batch" / "signal_phase_support_validation_batch.json"
            accepted_validation_manifest = root / "accepted_validation.manifest.json"
            delivery_session_manifest = output_dir / "delivery_session" / "signal_phase_delivery_session.manifest.json"

            action_queue_path.write_text("support_action_reference\n", encoding="utf-8")
            checklist_path.write_text("delivery_item_id\n", encoding="utf-8")
            movement_objects_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            accepted_validation_manifest.write_text("{}", encoding="utf-8")
            delivery_session_manifest.parent.mkdir(parents=True, exist_ok=True)
            delivery_session_manifest.write_text("{}", encoding="utf-8")
            batch_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            batch_json_path.write_text(
                json.dumps(
                    {
                        "validation_results": [
                            {
                                "support_action_reference": "bari_signal_phase_01:arm_phase_mapping_sheet",
                                "batch_outcome": "executed_validation",
                                "validation_outcome": "accepted_for_ingestion",
                                "manifest_path": str(accepted_validation_manifest),
                            }
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            batch_manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "batch_json_path": str(batch_json_path),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with patch(
                "road_risk_modeling.signal_phase_support_apply_cycle.run_bari_signal_phase_support_validation_batch",
                return_value={
                    "manifest_path": str(batch_manifest_path),
                    "stats": {
                        "action_queue_count": 1,
                        "validation_candidate_count": 1,
                        "executed_validation_count": 1,
                        "accepted_for_ingestion_count": 1,
                        "accepted_support_artifact_count": 0,
                        "partial_review_count": 0,
                        "provider_fix_required_count": 0,
                        "skipped_non_validation_action_count": 0,
                        "skipped_missing_validation_inputs_count": 0,
                    },
                },
            ) as batch_mock, patch(
                "road_risk_modeling.signal_phase_support_apply_cycle.apply_validated_signal_phase_deliveries",
                return_value={
                    "manifest_path": str(delivery_session_manifest),
                    "stats": {
                        "movement_count": 1,
                        "movements_with_phase_timing": 1,
                        "movements_with_phase_mapping": 1,
                    },
                },
            ) as apply_mock:
                result = run_bari_signal_phase_support_apply_cycle(
                    output_dir=output_dir,
                    action_execution_ready_queue_path=action_queue_path,
                    delivery_checklist_path=checklist_path,
                    movement_objects_path=movement_objects_path,
                )

            self.assertEqual(result["stats"]["accepted_for_ingestion_count"], 1)
            self.assertTrue(result["stats"]["delivery_session_executed"])
            batch_mock.assert_called_once()
            apply_mock.assert_called_once_with(
                movement_objects_path,
                [str(accepted_validation_manifest)],
                output_dir / "delivery_session",
                matched_records_path="data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
                target_request_queue_path="data/planning/signal_phase_outreach/bari/target_request_queue.csv",
                baseline_movement_objects_path=movement_objects_path,
            )

            payload = json.loads((output_dir / "signal_phase_support_apply_cycle.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["stats"]["movement_count"], 1)
            self.assertEqual(payload["outputs"]["delivery_session_manifest_path"], str(delivery_session_manifest))


if __name__ == "__main__":
    unittest.main()
