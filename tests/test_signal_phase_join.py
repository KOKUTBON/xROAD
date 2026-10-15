from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.signal_phase_join import apply_signal_phase_to_movements


class SignalPhaseJoinTests(unittest.TestCase):
    def test_apply_signal_phase_to_movements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            movements_path = root / "road_movement_objects.geojson"
            provider_manifest_path = root / "provider.manifest.json"
            mapping_manifest_path = root / "mapping.manifest.json"
            provider_records_path = root / "provider_records.jsonl"
            mapping_records_path = root / "mapping_records.jsonl"
            output_dir = root / "output"

            movements_path.write_text(
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

            provider_records_path.write_text(
                json.dumps(
                    {
                        "signal_phase_record_id": "provider:1",
                        "record_kind": "signal_control_observation",
                        "profile_id": "signal_stage_plan_export",
                        "profile_type": "provider_feed",
                        "junction_id": "it-bari-signal-93",
                        "phase_id": "phase_01",
                        "stage_id": "stage_01",
                        "control_mode": "fixed_time",
                        "observed_end_utc": None,
                        "attributes": {
                            "cycle_length_s": 90,
                            "green_s": 32,
                            "amber_s": 4,
                            "all_red_s": 2,
                            "pedestrian_walk_s": 10,
                            "pedestrian_clearance_s": 12,
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            mapping_records_path.write_text(
                json.dumps(
                    {
                        "signal_phase_record_id": "mapping:1",
                        "record_kind": "movement_phase_mapping",
                        "profile_id": "arm_phase_mapping_sheet",
                        "profile_type": "analyst_mapping",
                        "junction_id": "it-bari-signal-93",
                        "phase_id": "phase_01",
                        "stage_id": "stage_01",
                        "incoming_arm_id": "278899643:drive:11003032474:278899643:0:end",
                        "movement_turn": "straight",
                        "outgoing_arm_id": "drive:278899643:279392520:0:start",
                        "protection_state": "protected",
                        "pedestrian_stage_flag": False,
                        "attributes": {},
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            provider_manifest_path.write_text(
                json.dumps(
                    {
                        "profile": {"profile_id": "signal_stage_plan_export", "profile_type": "provider_feed"},
                        "outputs": {"records_path": str(provider_records_path)},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            mapping_manifest_path.write_text(
                json.dumps(
                    {
                        "profile": {"profile_id": "arm_phase_mapping_sheet", "profile_type": "analyst_mapping"},
                        "outputs": {"records_path": str(mapping_records_path)},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = apply_signal_phase_to_movements(
                movements_path,
                [provider_manifest_path, mapping_manifest_path],
                output_dir,
            )

            self.assertEqual(manifest["stats"]["movement_count"], 1)
            self.assertEqual(manifest["stats"]["provider_record_count"], 1)
            self.assertEqual(manifest["stats"]["mapping_record_count"], 1)
            self.assertEqual(manifest["stats"]["movements_with_phase_mapping"], 1)
            self.assertEqual(manifest["stats"]["movements_with_phase_timing"], 1)

            enriched = json.loads((output_dir / "road_movement_objects_signal_phase.geojson").read_text(encoding="utf-8"))
            props = enriched["features"][0]["properties"]
            self.assertEqual(props["movement_phase_id_catalog"], "phase_01")
            self.assertEqual(props["movement_stage_id_catalog"], "stage_01")
            self.assertEqual(props["movement_protection_state_catalog"], "protected")
            self.assertEqual(props["movement_phase_green_s_mean"], 32.0)
            self.assertEqual(props["junction_phase_provider_available"], 1.0)

    def test_apply_signal_phase_to_movements_with_node_object_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            movements_path = root / "road_movement_objects.geojson"
            mapping_manifest_path = root / "mapping.manifest.json"
            mapping_records_path = root / "mapping_records.jsonl"
            output_dir = root / "output"

            movements_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "node_object_id": "move_ped_1",
                                    "junction_id": "it-bari-signal-93",
                                    "movement_role": "pedestrian_crossing",
                                    "movement_turn": "cross",
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

            mapping_records_path.write_text(
                json.dumps(
                    {
                        "signal_phase_record_id": "mapping:ped:1",
                        "record_kind": "movement_phase_mapping",
                        "profile_id": "pedestrian_stage_mapping_sheet",
                        "profile_type": "analyst_mapping",
                        "junction_id": "it-bari-signal-93",
                        "node_object_id": "move_ped_1",
                        "phase_id": "phase_02",
                        "stage_id": "stage_03",
                        "movement_turn": "cross",
                        "protection_state": "protected",
                        "pedestrian_stage_flag": True,
                        "attributes": {},
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            mapping_manifest_path.write_text(
                json.dumps(
                    {
                        "profile": {"profile_id": "pedestrian_stage_mapping_sheet", "profile_type": "analyst_mapping"},
                        "outputs": {"records_path": str(mapping_records_path)},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = apply_signal_phase_to_movements(
                movements_path,
                [mapping_manifest_path],
                output_dir,
            )

            self.assertEqual(manifest["stats"]["movement_count"], 1)
            self.assertEqual(manifest["stats"]["provider_record_count"], 0)
            self.assertEqual(manifest["stats"]["mapping_record_count"], 1)
            self.assertEqual(manifest["stats"]["movements_with_phase_mapping"], 1)

            enriched = json.loads((output_dir / "road_movement_objects_signal_phase.geojson").read_text(encoding="utf-8"))
            props = enriched["features"][0]["properties"]
            self.assertEqual(props["movement_phase_id_catalog"], "phase_02")
            self.assertEqual(props["movement_stage_id_catalog"], "stage_03")
            self.assertEqual(props["movement_protection_state_catalog"], "protected")
            self.assertEqual(props["movement_pedestrian_stage_flag"], 1.0)
            self.assertEqual(props["movement_phase_join_resolution"], "exact_movement_mapping")


if __name__ == "__main__":
    unittest.main()
