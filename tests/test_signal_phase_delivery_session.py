from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from road_risk_modeling.signal_phase_delivery_session import apply_validated_signal_phase_deliveries


class SignalPhaseDeliverySessionTests(unittest.TestCase):
    def test_apply_validated_signal_phase_deliveries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "session"
            movement_objects_path = root / "road_movement_objects.geojson"
            matched_records_path = root / "matched_node_records.jsonl"
            target_request_queue_path = root / "target_request_queue.csv"
            input_csv_path = root / "controller_event_log.csv"
            mapping_stub_path = root / "mapping_stub.json"
            accepted_validation_manifest = root / "accepted.manifest.json"
            skipped_validation_manifest = root / "skipped.manifest.json"

            movement_objects_path.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {"node_object_id": "move_1"},
                                "geometry": {"type": "Point", "coordinates": [16.86, 41.12]},
                            }
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            matched_records_path.write_text(
                json.dumps({"node_object_id": "move_1"}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            target_request_queue_path.write_text(
                "request_id,junction_id,signal_name,priority_rank,priority_band,recommended_provider_profile,acquisition_status,required_profiles\n"
                "bari_signal_phase_01,it-bari-signal-93,Signal 93,1,tier_1_immediate,controller_event_log_export,pending_outreach,controller_event_log_export\n",
                encoding="utf-8",
            )
            input_csv_path.write_text("junction_id,device_id\nit-bari-signal-93,bari_ctrl_001\n", encoding="utf-8")
            mapping_stub_path.write_text(json.dumps({"profile_id": "controller_event_log_export"}, indent=2), encoding="utf-8")

            accepted_validation_manifest.write_text(
                json.dumps(
                    {
                        "profile": {"profile_id": "controller_event_log_export"},
                        "inputs": {
                            "input_csv_path": {"path": str(input_csv_path)},
                            "mapping_stub_path": {"path": str(mapping_stub_path)},
                        },
                        "stats": {"validation_outcome": "accepted_for_ingestion"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            skipped_validation_manifest.write_text(
                json.dumps(
                    {
                        "profile": {"profile_id": "signal_stage_plan_export"},
                        "inputs": {
                            "input_csv_path": {"path": str(input_csv_path)},
                            "mapping_stub_path": {"path": str(mapping_stub_path)},
                        },
                        "stats": {"validation_outcome": "provider_fix_required"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            fake_ingest_manifest = root / "ingested" / "signal_phase_records.manifest.json"
            fake_ingest_manifest.parent.mkdir(parents=True, exist_ok=True)
            fake_ingest_manifest.write_text("{}", encoding="utf-8")
            fake_join_manifest = root / "joined" / "road_movement_objects_signal_phase.manifest.json"
            fake_join_manifest.parent.mkdir(parents=True, exist_ok=True)
            fake_join_geojson = root / "joined" / "road_movement_objects_signal_phase.geojson"
            fake_join_geojson.write_text(
                movement_objects_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            fake_join_manifest.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "geojson_path": str(fake_join_geojson),
                            "manifest_path": str(fake_join_manifest),
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            fake_uplift_manifest = root / "uplift" / "signal_phase_delivery_uplift.manifest.json"
            fake_uplift_manifest.parent.mkdir(parents=True, exist_ok=True)
            fake_uplift_manifest.write_text(
                json.dumps(
                    {
                        "stats": {
                            "movements_with_phase_timing_before": 0,
                            "movements_with_phase_timing_after": 1,
                            "movements_with_phase_mapping_before": 0,
                            "movements_with_phase_mapping_after": 1,
                            "matched_signalized_crashes_on_timed_movements_before": 0,
                            "matched_signalized_crashes_on_timed_movements_after": 1,
                            "matched_signalized_crashes_on_mapped_movements_before": 0,
                            "matched_signalized_crashes_on_mapped_movements_after": 1,
                        }
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            with patch(
                "road_risk_modeling.signal_phase_delivery_session.ingest_signal_phase_extract",
                return_value={"manifest_path": str(fake_ingest_manifest)},
            ) as ingest_mock, patch(
                "road_risk_modeling.signal_phase_delivery_session.apply_signal_phase_to_movements",
                return_value={
                    "manifest_path": str(fake_join_manifest),
                    "stats": {
                        "movement_count": 1,
                        "movements_with_phase_timing": 1,
                        "movements_with_phase_mapping": 1,
                        "provider_record_count": 1,
                        "mapping_record_count": 1,
                    },
                },
            ) as join_mock:
                with patch(
                    "road_risk_modeling.signal_phase_delivery_session.build_bari_signal_phase_delivery_uplift_report",
                    return_value={"manifest_path": str(fake_uplift_manifest)},
                ) as uplift_mock:
                    result = apply_validated_signal_phase_deliveries(
                        movement_objects_path,
                        [accepted_validation_manifest, skipped_validation_manifest],
                        output_dir,
                        matched_records_path=matched_records_path,
                        target_request_queue_path=target_request_queue_path,
                    )

            self.assertEqual(result["stats"]["validation_manifest_count"], 2)
            self.assertEqual(result["stats"]["accepted_validation_count"], 1)
            self.assertEqual(result["stats"]["skipped_validation_count"], 1)
            self.assertEqual(result["stats"]["ingested_manifest_count"], 1)
            self.assertTrue(result["stats"]["delivery_uplift_report_generated"])
            self.assertEqual(result["stats"]["uplift_movements_with_phase_timing"], 1)
            self.assertEqual(result["stats"]["uplift_movements_with_phase_mapping"], 1)
            ingest_mock.assert_called_once()
            join_mock.assert_called_once_with(
                movement_objects_path,
                [str(fake_ingest_manifest)],
                output_dir / "movement_layer",
            )
            uplift_mock.assert_called_once()
            self.assertEqual(
                result["outputs"]["movement_signal_phase_geojson_path"],
                str(fake_join_geojson),
            )
            self.assertEqual(
                result["outputs"]["delivery_uplift_manifest_path"],
                str(fake_uplift_manifest),
            )

            payload = json.loads((output_dir / "signal_phase_delivery_session.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["accepted_deliveries"]), 1)
            self.assertEqual(len(payload["skipped_deliveries"]), 1)
            self.assertEqual(payload["outputs"]["delivery_uplift_manifest_path"], str(fake_uplift_manifest))


if __name__ == "__main__":
    unittest.main()
