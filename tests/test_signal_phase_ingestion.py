from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.governance_interoperability import build_governance_interoperability_bundle
from road_risk_modeling.signal_phase_ingestion import ingest_signal_phase_extract


class SignalPhaseIngestionTests(unittest.TestCase):
    def test_ingest_provider_feed_extract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv = root / "controller_event.csv"
            mapping_stub = root / "mapping_stub.json"
            output_dir = root / "output"
            governance_dir = root / "governance"

            with input_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "junction_id",
                        "device_id",
                        "event_start_utc",
                        "event_end_utc",
                        "phase_id",
                        "stage_id",
                        "event_type",
                        "control_mode",
                        "plan_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "junction_id": "it-bari-signal-93",
                        "device_id": "ctrl_93",
                        "event_start_utc": "2025-05-06T07:00:00Z",
                        "event_end_utc": "2025-05-06T07:01:30Z",
                        "phase_id": "phase_01",
                        "stage_id": "stage_01",
                        "event_type": "stage_active",
                        "control_mode": "controller_runtime",
                        "plan_id": "weekday_am_peak",
                    }
                )

            mapping_stub.write_text(
                json.dumps(
                    {
                        "profile_id": "controller_event_log_export",
                        "profile_label": "Controller event log export",
                        "profile_type": "provider_feed",
                        "field_mappings": [
                            {"target_field": "junction_id", "source_field": "junction_id", "required": True, "type": "string"},
                            {"target_field": "device_id", "source_field": "device_id", "required": True, "type": "string"},
                            {"target_field": "event_start_utc", "source_field": "event_start_utc", "required": True, "type": "datetime"},
                            {"target_field": "event_end_utc", "source_field": "event_end_utc", "required": True, "type": "datetime"},
                            {"target_field": "phase_id", "source_field": "phase_id", "required": True, "type": "string"},
                            {"target_field": "stage_id", "source_field": "stage_id", "required": True, "type": "string"},
                            {"target_field": "event_type", "source_field": "event_type", "required": True, "type": "string"},
                            {"target_field": "control_mode", "source_field": "control_mode", "required": True, "type": "string"},
                            {"target_field": "plan_id", "source_field": "plan_id", "required": False, "type": "string"},
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
            build_governance_interoperability_bundle(governance_dir)

            manifest = ingest_signal_phase_extract(
                input_csv,
                mapping_stub,
                output_dir,
                governance_bundle_path=governance_dir / "governance_interoperability_bundle.json",
            )

            self.assertEqual(manifest["stats"]["written_rows"], 1)
            self.assertEqual(manifest["stats"]["record_kind_counts"]["signal_control_observation"], 1)
            records = [json.loads(line) for line in (output_dir / "signal_phase_records.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["record_kind"], "signal_control_observation")
            self.assertEqual(records[0]["junction_id"], "it-bari-signal-93")
            self.assertEqual(records[0]["control_mode"], "controller_runtime")
            manifest_payload = json.loads(
                (output_dir / "signal_phase_records.manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest_payload["governance"]["source_family_ids"],
                ["signal_controller_event_log_export"],
            )

    def test_ingest_mapping_extract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv = root / "mapping.csv"
            mapping_stub = root / "mapping_stub.json"
            output_dir = root / "output"

            with input_csv.open("w", encoding="utf-8", newline="") as handle:
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

            mapping_stub.write_text(
                json.dumps(
                    {
                        "profile_id": "arm_phase_mapping_sheet",
                        "profile_label": "Arm-to-phase mapping sheet",
                        "profile_type": "analyst_mapping",
                        "field_mappings": [
                            {"target_field": "junction_id", "source_field": "junction_id", "required": True, "type": "string"},
                            {"target_field": "incoming_arm_id", "source_field": "incoming_arm_id", "required": True, "type": "string"},
                            {"target_field": "movement_turn", "source_field": "movement_turn", "required": True, "type": "string"},
                            {"target_field": "phase_id", "source_field": "phase_id", "required": True, "type": "string"},
                            {"target_field": "stage_id", "source_field": "stage_id", "required": True, "type": "string"},
                            {"target_field": "protection_state", "source_field": "protection_state", "required": True, "type": "string"},
                            {"target_field": "outgoing_arm_id", "source_field": "outgoing_arm_id", "required": False, "type": "string"},
                            {"target_field": "pedestrian_stage_flag", "source_field": "pedestrian_stage_flag", "required": False, "type": "boolean"},
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

            manifest = ingest_signal_phase_extract(input_csv, mapping_stub, output_dir)

            self.assertEqual(manifest["stats"]["written_rows"], 1)
            self.assertEqual(manifest["stats"]["record_kind_counts"]["movement_phase_mapping"], 1)
            records = [json.loads(line) for line in (output_dir / "signal_phase_records.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["record_kind"], "movement_phase_mapping")
            self.assertEqual(records[0]["incoming_arm_id"], "278899643:drive:11003032474:278899643:0:end")
            self.assertFalse(records[0]["pedestrian_stage_flag"])

    def test_ingest_node_object_mapping_extract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv = root / "pedestrian_mapping.csv"
            mapping_stub = root / "mapping_stub.json"
            output_dir = root / "output"

            with input_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "junction_id",
                        "node_object_id",
                        "movement_turn",
                        "phase_id",
                        "stage_id",
                        "protection_state",
                        "pedestrian_stage_flag",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "junction_id": "it-bari-signal-93",
                        "node_object_id": "move_ped_1",
                        "movement_turn": "cross",
                        "phase_id": "phase_02",
                        "stage_id": "stage_03",
                        "protection_state": "protected",
                        "pedestrian_stage_flag": "true",
                    }
                )

            mapping_stub.write_text(
                json.dumps(
                    {
                        "profile_id": "pedestrian_stage_mapping_sheet",
                        "profile_label": "Pedestrian-stage mapping sheet",
                        "profile_type": "analyst_mapping",
                        "field_mappings": [
                            {"target_field": "junction_id", "source_field": "junction_id", "required": True, "type": "string"},
                            {"target_field": "node_object_id", "source_field": "node_object_id", "required": True, "type": "string"},
                            {"target_field": "movement_turn", "source_field": "movement_turn", "required": True, "type": "string"},
                            {"target_field": "phase_id", "source_field": "phase_id", "required": True, "type": "string"},
                            {"target_field": "stage_id", "source_field": "stage_id", "required": True, "type": "string"},
                            {"target_field": "protection_state", "source_field": "protection_state", "required": True, "type": "string"},
                            {"target_field": "pedestrian_stage_flag", "source_field": "pedestrian_stage_flag", "required": False, "type": "boolean"},
                        ],
                        "publication_policy": {},
                        "quality_gates": [],
                        "target_join_strategy": {"junction_key": "junction_id", "movement_mapping_level": "direct_node_object_to_phase"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = ingest_signal_phase_extract(input_csv, mapping_stub, output_dir)

            self.assertEqual(manifest["stats"]["written_rows"], 1)
            records = [json.loads(line) for line in (output_dir / "signal_phase_records.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["signal_phase_record_id"], "pedestrian_stage_mapping_sheet:it-bari-signal-93:move_ped_1:phase_02:stage_03")
            self.assertEqual(records[0]["node_object_id"], "move_ped_1")
            self.assertTrue(records[0]["pedestrian_stage_flag"])


if __name__ == "__main__":
    unittest.main()
