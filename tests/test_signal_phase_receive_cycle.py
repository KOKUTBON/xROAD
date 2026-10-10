from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from road_risk_modeling.signal_phase_receive_cycle import run_bari_signal_phase_receive_cycle


class SignalPhaseReceiveCycleTests(unittest.TestCase):
    def test_run_bari_signal_phase_receive_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "receive_cycle"
            intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            receipt_register_path = root / "delivery_receipt_register.csv"
            checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            mapping_stub_path = root / "arm_phase_mapping_stub.json"
            support_mapping_stub_path = root / "support_mapping_stub.json"

            dropzone = root / "incoming" / "bari_signal_phase_01" / "arm_phase_mapping_sheet"
            dropzone.mkdir(parents=True, exist_ok=True)
            input_csv_path = dropzone / "arm_phase_mapping_001.csv"
            support_dropzone = root / "incoming" / "bari_signal_phase_01" / "junction_phase_diagram_support"
            support_dropzone.mkdir(parents=True, exist_ok=True)
            support_file_path = support_dropzone / "junction_phase_diagram_001.pdf"

            intake_bundle_path.write_text(
                json.dumps({"summary": {"dispatch_request_count": 1, "expected_delivery_count": 1}}, indent=2),
                encoding="utf-8",
            )
            movement_objects_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "move_1",
                                    "junction_id": "it-bari-signal-93",
                                    "movement_role": "signalized_turn_movement",
                                    "movement_turn": "straight",
                                    "incoming_arm_id": "278899643:drive:11003032474:278899643:0:end",
                                    "outgoing_arm_id": "drive:278899643:279392520:0:start",
                                },
                                "geometry": {"type": "Point", "coordinates": [16.86, 41.12]},
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            mapping_stub_path.write_text(
                json.dumps(
                    {
                        "profile_id": "arm_phase_mapping_sheet",
                        "profile_label": "Arm-to-phase mapping sheet",
                        "profile_type": "analyst_mapping",
                        "field_mappings": [
                            {
                                "target_field": "junction_id",
                                "source_field": "junction_id",
                                "required": True,
                                "type": "string",
                            },
                            {
                                "target_field": "incoming_arm_id",
                                "source_field": "incoming_arm_id",
                                "required": True,
                                "type": "string",
                            },
                            {
                                "target_field": "movement_turn",
                                "source_field": "movement_turn",
                                "required": True,
                                "type": "string",
                            },
                            {
                                "target_field": "phase_id",
                                "source_field": "phase_id",
                                "required": True,
                                "type": "string",
                            },
                            {
                                "target_field": "stage_id",
                                "source_field": "stage_id",
                                "required": True,
                                "type": "string",
                            },
                            {
                                "target_field": "protection_state",
                                "source_field": "protection_state",
                                "required": True,
                                "type": "string",
                            },
                            {
                                "target_field": "outgoing_arm_id",
                                "source_field": "outgoing_arm_id",
                                "required": False,
                                "type": "string",
                            },
                            {
                                "target_field": "pedestrian_stage_flag",
                                "source_field": "pedestrian_stage_flag",
                                "required": False,
                                "type": "boolean",
                            },
                        ],
                        "publication_policy": {},
                        "quality_gates": [],
                        "target_join_strategy": {"junction_key": "junction_id"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            support_mapping_stub_path.write_text(
                json.dumps(
                    {
                        "profile_id": "junction_phase_diagram_support",
                        "profile_label": "Junction phase diagram support",
                        "profile_type": "support_artifact",
                        "field_mappings": [],
                        "support_validation": {
                            "validation_mode": "file_presence_and_extension",
                            "allowed_extensions": [".pdf", ".png"],
                            "minimum_file_size_bytes": 16,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            with input_csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "junction_id",
                        "incoming_arm_id",
                        "movement_turn",
                        "phase_id",
                        "stage_id",
                        "protection_state",
                        "outgoing_arm_id",
                        "pedestrian_stage_flag",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "junction_id": "it-bari-signal-93",
                        "incoming_arm_id": "278899643:drive:11003032474:278899643:0:end",
                        "movement_turn": "straight",
                        "phase_id": "phase_01",
                        "stage_id": "stage_01",
                        "protection_state": "protected",
                        "outgoing_arm_id": "drive:278899643:279392520:0:start",
                        "pedestrian_stage_flag": "false",
                    }
                )
            support_file_path.write_text("%PDF-1.4\nsupport sample\n", encoding="utf-8")

            with checklist_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "delivery_item_id",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "priority_band",
                        "profile_id",
                        "owner_team",
                        "delivery_format",
                        "requested_window",
                        "acceptance_gate",
                        "delivery_status",
                        "received_date",
                        "validated_date",
                        "mapped_to_movements",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "arm_phase_mapping_sheet",
                        "owner_team": "traffic control center",
                        "delivery_format": "CSV export",
                        "requested_window": "current_layout",
                        "acceptance_gate": "mapping complete",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "primary",
                    }
                )
                writer.writerow(
                    {
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "priority_band": "tier_1_immediate",
                        "profile_id": "junction_phase_diagram_support",
                        "owner_team": "traffic control center",
                        "delivery_format": "PDF support diagram",
                        "requested_window": "current_layout",
                        "acceptance_gate": "diagram identifies stages",
                        "delivery_status": "awaiting_request",
                        "received_date": "",
                        "validated_date": "",
                        "mapped_to_movements": "no",
                        "notes": "support",
                    }
                )

            with receipt_register_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "dispatch_reference",
                        "request_id",
                        "junction_id",
                        "signal_name",
                        "profile_id",
                        "delivery_item_id",
                        "delivery_format",
                        "requested_window",
                        "acceptance_gate",
                        "expected_filename_hint",
                        "incoming_dropzone_path",
                        "mapping_stub_path",
                        "validation_output_dir",
                        "validation_command",
                        "receipt_status",
                        "received_date",
                        "received_file_path",
                        "validation_status",
                        "validation_manifest_path",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "arm_phase_mapping_sheet",
                        "delivery_item_id": "bari_signal_phase_01__arm_phase_mapping_sheet",
                        "delivery_format": "CSV export",
                        "requested_window": "current_layout",
                        "acceptance_gate": "mapping complete",
                        "expected_filename_hint": "arm_phase_mapping_*.csv",
                        "incoming_dropzone_path": str(dropzone),
                        "mapping_stub_path": str(mapping_stub_path),
                        "validation_output_dir": str(root / "validated" / "mapping"),
                        "validation_command": "validate-signal-phase-delivery <received_file_path> mapping.json",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )
                writer.writerow(
                    {
                        "dispatch_reference": "BARI-SPD-20260329-01",
                        "request_id": "bari_signal_phase_01",
                        "junction_id": "it-bari-signal-93",
                        "signal_name": "CAPRUZZI - B. CROCE",
                        "profile_id": "junction_phase_diagram_support",
                        "delivery_item_id": "bari_signal_phase_01__junction_phase_diagram_support",
                        "delivery_format": "PDF support diagram",
                        "requested_window": "current_layout",
                        "acceptance_gate": "diagram identifies stages",
                        "expected_filename_hint": "junction_phase_diagram_*",
                        "incoming_dropzone_path": str(support_dropzone),
                        "mapping_stub_path": str(support_mapping_stub_path),
                        "validation_output_dir": str(root / "validated" / "support"),
                        "validation_command": "validate-signal-phase-delivery <received_file_path> support_mapping.json",
                        "receipt_status": "awaiting_delivery",
                        "received_date": "",
                        "received_file_path": "",
                        "validation_status": "not_started",
                        "validation_manifest_path": "",
                        "notes": "",
                    }
                )

            support_resolution_manifest = output_dir / "support_resolution" / "signal_phase_support_resolution_bundle.manifest.json"
            support_resolution_manifest.parent.mkdir(parents=True, exist_ok=True)
            support_resolution_manifest.write_text("{}", encoding="utf-8")
            support_resolution_json = output_dir / "support_resolution" / "signal_phase_support_resolution_bundle.json"
            support_resolution_json.write_text(
                json.dumps(
                    {
                        "summary": {
                            "support_request_count": 1,
                            "manual_arm_phase_review_row_count": 2,
                            "pedestrian_stage_review_row_count": 1,
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            support_runtime_manifest = output_dir / "support_runtime_cycle" / "signal_phase_support_runtime_cycle.manifest.json"
            support_runtime_manifest.parent.mkdir(parents=True, exist_ok=True)
            support_runtime_manifest.write_text("{}", encoding="utf-8")

            with patch(
                "road_risk_modeling.signal_phase_receive_cycle.build_bari_signal_phase_support_resolution_bundle",
                return_value={"manifest_path": str(support_resolution_manifest)},
            ) as support_resolution_mock, patch(
                "road_risk_modeling.signal_phase_receive_cycle.run_bari_signal_phase_support_runtime_cycle",
                return_value={
                    "manifest_path": str(support_runtime_manifest),
                    "stats": {"delivery_session_executed": False, "applied_profile_count": 0},
                },
            ) as support_runtime_mock:
                result = run_bari_signal_phase_receive_cycle(
                    output_dir=output_dir,
                    signal_phase_delivery_intake_bundle_path=intake_bundle_path,
                    delivery_receipt_register_path=receipt_register_path,
                    delivery_checklist_path=checklist_path,
                    movement_objects_path=movement_objects_path,
                    matched_records_path=None,
                    target_request_queue_path=None,
                    preview_limit=5,
                )

            self.assertEqual(result["stats"]["monitored_delivery_count"], 2)
            self.assertEqual(result["stats"]["validation_ready_count"], 2)
            self.assertEqual(result["stats"]["executed_validation_count"], 2)
            self.assertEqual(result["stats"]["accepted_for_ingestion_count"], 1)
            self.assertEqual(result["stats"]["accepted_support_artifact_count"], 1)
            self.assertTrue(result["stats"]["delivery_session_executed"])
            self.assertEqual(result["stats"]["movements_with_phase_mapping"], 1)
            self.assertEqual(result["stats"]["support_resolution_request_count"], 1)
            self.assertTrue(result["stats"]["support_runtime_cycle_executed"])
            support_resolution_mock.assert_called_once()
            support_runtime_mock.assert_called_once()
            support_runtime_kwargs = support_runtime_mock.call_args.kwargs
            self.assertEqual(
                Path(support_runtime_kwargs["movement_objects_path"]).name,
                "road_movement_objects_signal_phase.geojson",
            )

            payload = json.loads((output_dir / "signal_phase_receive_cycle.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["stats"]["delivery_session_executed"])
            self.assertIsNotNone(payload["outputs"]["delivery_session_manifest_path"])
            self.assertEqual(
                payload["outputs"]["support_resolution_manifest_path"],
                str(support_resolution_manifest),
            )
            self.assertEqual(
                payload["outputs"]["support_runtime_cycle_manifest_path"],
                str(support_runtime_manifest),
            )


if __name__ == "__main__":
    unittest.main()
