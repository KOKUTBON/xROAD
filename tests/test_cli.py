from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest.mock import patch

from road_risk_modeling.cli import main


class CliTests(unittest.TestCase):
    def test_publish_segment_scores_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            predictions_path = root / "predictions.csv"
            segments_path = root / "segments.geojson"
            metrics_path = root / "metrics.json"
            output_dir = root / "prediction_store"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.publish_segment_scores",
                return_value={
                    "prediction_store_version": "segment_prediction_store_v1",
                    "stats": {"segment_score_rows": 2},
                },
            ) as publish_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "publish-segment-scores",
                            str(predictions_path),
                            str(segments_path),
                            str(metrics_path),
                            "--output-dir",
                            str(output_dir),
                            "--prediction-column",
                            "random_forest_poisson_prediction",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            publish_mock.assert_called_once_with(
                str(predictions_path),
                str(segments_path),
                str(metrics_path),
                output_dir=str(output_dir),
                prediction_column="random_forest_poisson_prediction",
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["prediction_store_version"], "segment_prediction_store_v1")
            self.assertEqual(payload["stats"]["segment_score_rows"], 2)

    def test_aggregate_public_score_tiles_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_scores_path = root / "segment_scores_public.geojson"
            manifest_path = root / "segment_scores.manifest.json"
            output_dir = root / "tiles"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.aggregate_public_score_tiles",
                return_value={
                    "prediction_store_version": "segment_score_tiles_v1",
                    "stats": {"tile_rows": 10},
                },
            ) as tile_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "aggregate-public-score-tiles",
                            str(public_scores_path),
                            str(manifest_path),
                            "--output-dir",
                            str(output_dir),
                            "--tile-size-m",
                            "500",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            tile_mock.assert_called_once_with(
                str(public_scores_path),
                str(manifest_path),
                output_dir=str(output_dir),
                tile_size_m=500.0,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["prediction_store_version"], "segment_score_tiles_v1")
            self.assertEqual(payload["stats"]["tile_rows"], 10)

    def test_ingest_bari_open_data_crashes_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "staging"
            raw_dir = root / "raw"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.ingest_bari_open_data_crashes",
                return_value={
                    "source": {"adapter": "bari_open_data_ckan_csv"},
                    "stats": {"total_records": 12},
                },
            ) as ingest_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "ingest-bari-open-data-crashes",
                            "--output-dir",
                            str(output_dir),
                            "--raw-dir",
                            str(raw_dir),
                            "--limit",
                            "50",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            ingest_mock.assert_called_once_with(
                output_dir=str(output_dir),
                raw_dir=str(raw_dir),
                limit=50,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_open_data_ckan_csv")
            self.assertEqual(payload["stats"]["total_records"], 12)

    def test_build_bari_signal_nodes_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "nodes"
            raw_dir = root / "raw"
            segments_path = root / "segments.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_nodes",
                return_value={
                    "source": {"adapter": "bari_open_data_semafori"},
                    "stats": {"node_object_count": 3},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-nodes",
                            "--output-dir",
                            str(output_dir),
                            "--segments-path",
                            str(segments_path),
                            "--raw-dir",
                            str(raw_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                segments_path=str(segments_path),
                raw_dir=str(raw_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_open_data_semafori")
            self.assertEqual(payload["stats"]["node_object_count"], 3)

    def test_build_bari_crossing_and_approach_objects_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "objects"
            signals_path = root / "signals.geojson"
            segments_path = root / "segments.geojson"
            boundary_path = root / "boundary.geojson"
            crossings_path = root / "crossings.geojson"
            raw_dir = root / "raw"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_crossing_and_approach_objects",
                return_value={
                    "source": {"adapter": "bari_mixed_node_object_builder"},
                    "stats": {"total_node_object_count": 12},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-crossing-and-approach-objects",
                            "--output-dir",
                            str(output_dir),
                            "--signal-nodes-path",
                            str(signals_path),
                            "--segments-path",
                            str(segments_path),
                            "--boundary-path",
                            str(boundary_path),
                            "--crossings-path",
                            str(crossings_path),
                            "--raw-dir",
                            str(raw_dir),
                            "--approach-distance-m",
                            "20",
                            "--junction-buffer-m",
                            "30",
                            "--signal-link-m",
                            "45",
                            "--unsignalized-min-degree",
                            "5",
                            "--unsignalized-major-edge-min",
                            "3",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_nodes_path=str(signals_path),
                segments_path=str(segments_path),
                boundary_path=str(boundary_path),
                crossings_path=str(crossings_path),
                raw_dir=str(raw_dir),
                approach_distance_m=20.0,
                junction_buffer_m=30.0,
                signal_link_m=45.0,
                unsignalized_min_degree=5,
                unsignalized_major_edge_min=3,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_mixed_node_object_builder")
            self.assertEqual(payload["stats"]["total_node_object_count"], 12)

    def test_build_bari_conflict_zones_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "zones"
            node_objects_path = root / "node_objects.geojson"
            segments_path = root / "segments.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_conflict_zones",
                return_value={
                    "source": {"adapter": "bari_conflict_zone_builder"},
                    "stats": {"total_conflict_zone_count": 18},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-conflict-zones",
                            "--output-dir",
                            str(output_dir),
                            "--node-objects-path",
                            str(node_objects_path),
                            "--segments-path",
                            str(segments_path),
                            "--crossing-radius-m",
                            "11",
                            "--unsignalized-radius-m",
                            "19",
                            "--roundabout-fallback-radius-m",
                            "15",
                            "--junction-approach-length-m",
                            "17",
                            "--roundabout-entry-length-m",
                            "16",
                            "--default-zone-half-width-m",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                node_objects_path=str(node_objects_path),
                segments_path=str(segments_path),
                crossing_radius_m=11.0,
                unsignalized_radius_m=19.0,
                roundabout_fallback_radius_m=15.0,
                junction_approach_length_m=17.0,
                roundabout_entry_length_m=16.0,
                default_zone_half_width_m=5.0,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_conflict_zone_builder")
            self.assertEqual(payload["stats"]["total_conflict_zone_count"], 18)

    def test_build_bari_movement_objects_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "movements"
            conflict_zones_path = root / "road_conflict_zones.geojson"
            segments_path = root / "segments.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_movement_objects",
                return_value={
                    "source": {"adapter": "bari_movement_object_builder"},
                    "stats": {"movement_object_count": 21},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-movement-objects",
                            "--output-dir",
                            str(output_dir),
                            "--conflict-zones-path",
                            str(conflict_zones_path),
                            "--segments-path",
                            str(segments_path),
                            "--movement-offset-m",
                            "9",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                conflict_zones_path=str(conflict_zones_path),
                segments_path=str(segments_path),
                movement_offset_m=9.0,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_movement_object_builder")
            self.assertEqual(payload["stats"]["movement_object_count"], 21)

    def test_build_bari_movement_review_pack_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "movement_review"
            movement_objects_path = root / "road_movement_objects.geojson"
            matched_records_path = root / "matched_node_records.jsonl"
            aggregate_path = root / "node_year_metrics.csv"
            signal_nodes_path = root / "traffic_signal_nodes.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_movement_review_pack",
                return_value={
                    "source": {"adapter": "bari_movement_review_builder"},
                    "stats": {"unresolved_movement_count": 12},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-movement-review-pack",
                            "--output-dir",
                            str(output_dir),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--matched-records-path",
                            str(matched_records_path),
                            "--aggregate-path",
                            str(aggregate_path),
                            "--signal-nodes-path",
                            str(signal_nodes_path),
                            "--top-n",
                            "15",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                movement_objects_path=str(movement_objects_path),
                matched_records_path=str(matched_records_path),
                aggregate_path=str(aggregate_path),
                signal_nodes_path=str(signal_nodes_path),
                top_n=15,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_movement_review_builder")
            self.assertEqual(payload["stats"]["unresolved_movement_count"], 12)

    def test_build_bari_signal_phase_intake_pack_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_intake"
            movement_review_path = root / "movement_review_pack.json"
            signal_nodes_path = root / "traffic_signal_nodes.geojson"
            movement_objects_path = root / "road_movement_objects.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_intake_pack",
                return_value={
                    "source": {"adapter": "bari_signal_phase_intake_builder"},
                    "stats": {"priority_signal_export_count": 20},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-intake-pack",
                            "--output-dir",
                            str(output_dir),
                            "--movement-review-path",
                            str(movement_review_path),
                            "--signal-nodes-path",
                            str(signal_nodes_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--top-n",
                            "12",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                movement_review_path=str(movement_review_path),
                phase_readiness_csv_path=None,
                signal_nodes_path=str(signal_nodes_path),
                movement_objects_path=str(movement_objects_path),
                top_n=12,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_intake_builder")
            self.assertEqual(payload["stats"]["priority_signal_export_count"], 20)

    def test_build_bari_signal_phase_support_resolution_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_resolution"
            support_manifest_path = root / "support_validation.manifest.json"
            movement_review_path = root / "movement_review_pack.json"
            movement_objects_path = root / "road_movement_objects.geojson"
            aggregate_path = root / "node_year_metrics.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_resolution_bundle",
                return_value={
                    "source": {"adapter": "bari_signal_phase_support_resolution_bundle_builder"},
                    "stats": {"support_request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-resolution-bundle",
                            str(support_manifest_path),
                            "--output-dir",
                            str(output_dir),
                            "--movement-review-path",
                            str(movement_review_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--aggregate-path",
                            str(aggregate_path),
                            "--top-n",
                            "6",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                support_validation_manifest_paths=[str(support_manifest_path)],
                movement_review_path=str(movement_review_path),
                phase_readiness_csv_path=None,
                movement_objects_path=str(movement_objects_path),
                aggregate_path=str(aggregate_path),
                top_n=6,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_support_resolution_bundle_builder")
            self.assertEqual(payload["stats"]["support_request_count"], 1)

    def test_build_bari_signal_phase_support_writeback_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_writeback"
            support_resolution_bundle_path = root / "signal_phase_support_resolution_bundle.json"
            manual_mapping_stub_path = root / "arm_phase_mapping_sheet_mapping_stub.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_writeback_bundle",
                return_value={
                    "source": {"adapter": "bari_signal_phase_support_writeback_bundle_builder"},
                    "stats": {"manual_workbook_row_count": 18},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-writeback-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-resolution-bundle-path",
                            str(support_resolution_bundle_path),
                            "--manual-mapping-stub-path",
                            str(manual_mapping_stub_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_resolution_bundle_path=str(support_resolution_bundle_path),
                manual_mapping_stub_path=str(manual_mapping_stub_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_support_writeback_bundle_builder")
            self.assertEqual(payload["stats"]["manual_workbook_row_count"], 18)

    def test_build_bari_signal_phase_support_status_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_status"
            support_writeback_bundle_path = root / "signal_phase_support_writeback_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_status_bundle",
                return_value={
                    "source": {"adapter": "bari_signal_phase_support_status_bundle_builder"},
                    "stats": {"validation_ready_profile_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-status-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-writeback-bundle-path",
                            str(support_writeback_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_writeback_bundle_path=str(support_writeback_bundle_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_support_status_bundle_builder")
            self.assertEqual(payload["stats"]["validation_ready_profile_count"], 1)

    def test_build_bari_signal_phase_support_action_queue_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_action_queue"
            support_status_bundle_path = root / "signal_phase_support_status_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_action_queue",
                return_value={
                    "source": {"adapter": "bari_signal_phase_support_action_queue_builder"},
                    "stats": {"execution_ready_count": 2},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-action-queue",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-status-bundle-path",
                            str(support_status_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_status_bundle_path=str(support_status_bundle_path),
                signal_phase_support_apply_status_bundle_path=None,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_support_action_queue_builder")
            self.assertEqual(payload["stats"]["execution_ready_count"], 2)

    def test_build_bari_signal_phase_support_apply_status_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_apply_status"
            support_status_bundle_path = root / "signal_phase_support_status_bundle.json"
            support_apply_cycle_path = root / "signal_phase_support_apply_cycle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_apply_status_bundle",
                return_value={
                    "source": {"adapter": "bari_signal_phase_support_apply_status_bundle_builder"},
                    "stats": {"applied_profile_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-apply-status-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-status-bundle-path",
                            str(support_status_bundle_path),
                            "--signal-phase-support-apply-cycle-path",
                            str(support_apply_cycle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_status_bundle_path=str(support_status_bundle_path),
                signal_phase_support_apply_cycle_path=str(support_apply_cycle_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["source"]["adapter"],
                "bari_signal_phase_support_apply_status_bundle_builder",
            )
            self.assertEqual(payload["stats"]["applied_profile_count"], 1)

    def test_build_bari_signal_phase_support_request_state_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_request_state"
            support_status_bundle_path = root / "signal_phase_support_status_bundle.json"
            support_apply_status_bundle_path = root / "signal_phase_support_apply_status_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_request_state_bundle",
                return_value={
                    "source": {"adapter": "bari_signal_phase_support_request_state_bundle_builder"},
                    "stats": {"partially_applied_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-request-state-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-status-bundle-path",
                            str(support_status_bundle_path),
                            "--signal-phase-support-apply-status-bundle-path",
                            str(support_apply_status_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_status_bundle_path=str(support_status_bundle_path),
                signal_phase_support_apply_status_bundle_path=str(
                    support_apply_status_bundle_path
                ),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["source"]["adapter"],
                "bari_signal_phase_support_request_state_bundle_builder",
            )
            self.assertEqual(payload["stats"]["partially_applied_count"], 1)

    def test_build_bari_signal_phase_support_operator_board_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_operator_board"
            request_state_bundle_path = root / "signal_phase_support_request_state_bundle.json"
            support_action_queue_path = root / "signal_phase_support_action_queue.json"
            runtime_command = "make run-bari-signal-phase-support-runtime-cycle"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_operator_board_bundle",
                return_value={
                    "source": {"adapter": "bari_signal_phase_support_operator_board_builder"},
                    "stats": {"operator_ready_count": 1, "request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-operator-board-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-request-state-bundle-path",
                            str(request_state_bundle_path),
                            "--signal-phase-support-action-queue-path",
                            str(support_action_queue_path),
                            "--support-runtime-command",
                            runtime_command,
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_request_state_bundle_path=str(request_state_bundle_path),
                signal_phase_support_action_queue_path=str(support_action_queue_path),
                support_runtime_command=runtime_command,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["source"]["adapter"],
                "bari_signal_phase_support_operator_board_builder",
            )
            self.assertEqual(payload["stats"]["operator_ready_count"], 1)

    def test_build_bari_signal_phase_support_action_execution_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_action_execution"
            operator_board_bundle_path = root / "signal_phase_support_operator_board_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_action_execution_bundle",
                return_value={
                    "source": {
                        "adapter": "bari_signal_phase_support_action_execution_builder"
                    },
                    "stats": {"execution_ready_count": 1, "request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-action-execution-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-operator-board-bundle-path",
                            str(operator_board_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_operator_board_bundle_path=str(
                    operator_board_bundle_path
                ),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["source"]["adapter"],
                "bari_signal_phase_support_action_execution_builder",
            )
            self.assertEqual(payload["stats"]["execution_ready_count"], 1)

    def test_build_bari_signal_phase_support_action_handoff_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_action_handoff"
            action_execution_bundle_path = root / "signal_phase_support_action_execution_bundle.json"
            runtime_cycle_manifest_path = root / "signal_phase_support_runtime_cycle.manifest.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_action_handoff_bundle",
                return_value={
                    "signal_phase_support_action_handoff_bundle_version": "signal_phase_support_action_handoff_bundle_v1",
                    "stats": {"handoff_ready_count": 1, "request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-action-handoff-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-action-execution-bundle-path",
                            str(action_execution_bundle_path),
                            "--support-runtime-cycle-manifest-path",
                            str(runtime_cycle_manifest_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_action_execution_bundle_path=str(
                    action_execution_bundle_path
                ),
                support_runtime_cycle_manifest_path=str(runtime_cycle_manifest_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["signal_phase_support_action_handoff_bundle_version"],
                "signal_phase_support_action_handoff_bundle_v1",
            )
            self.assertEqual(payload["stats"]["handoff_ready_count"], 1)

    def test_build_bari_signal_phase_support_runtime_board_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_runtime_board"
            action_execution_bundle_path = root / "signal_phase_support_action_execution_bundle.json"
            action_handoff_bundle_path = root / "signal_phase_support_action_handoff_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_runtime_board_bundle",
                return_value={
                    "signal_phase_support_runtime_board_bundle_version": "signal_phase_support_runtime_board_bundle_v1",
                    "stats": {"operator_ready_count": 1, "request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-runtime-board-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-action-execution-bundle-path",
                            str(action_execution_bundle_path),
                            "--signal-phase-support-action-handoff-bundle-path",
                            str(action_handoff_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_action_execution_bundle_path=str(
                    action_execution_bundle_path
                ),
                signal_phase_support_action_handoff_bundle_path=str(
                    action_handoff_bundle_path
                ),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["signal_phase_support_runtime_board_bundle_version"],
                "signal_phase_support_runtime_board_bundle_v1",
            )
            self.assertEqual(payload["stats"]["operator_ready_count"], 1)

    def test_build_bari_signal_phase_support_runtime_action_queue_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_runtime_action_queue"
            runtime_board_bundle_path = root / "signal_phase_support_runtime_board_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_runtime_action_queue",
                return_value={
                    "signal_phase_support_runtime_action_queue_version": "signal_phase_support_runtime_action_queue_v1",
                    "stats": {"immediate_action_count": 1, "request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-runtime-action-queue",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-runtime-board-bundle-path",
                            str(runtime_board_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_runtime_board_bundle_path=str(
                    runtime_board_bundle_path
                ),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["signal_phase_support_runtime_action_queue_version"],
                "signal_phase_support_runtime_action_queue_v1",
            )
            self.assertEqual(payload["stats"]["immediate_action_count"], 1)

    def test_build_bari_signal_phase_support_runtime_action_execution_bundle_command(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_runtime_action_execution"
            runtime_action_queue_path = root / "signal_phase_support_runtime_action_queue.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_runtime_action_execution_bundle",
                return_value={
                    "signal_phase_support_runtime_action_execution_bundle_version": "signal_phase_support_runtime_action_execution_bundle_v1",
                    "stats": {"execution_ready_count": 1, "request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-runtime-action-execution-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-runtime-action-queue-path",
                            str(runtime_action_queue_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_runtime_action_queue_path=str(
                    runtime_action_queue_path
                ),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["signal_phase_support_runtime_action_execution_bundle_version"],
                "signal_phase_support_runtime_action_execution_bundle_v1",
            )
            self.assertEqual(payload["stats"]["execution_ready_count"], 1)

    def test_build_bari_signal_phase_support_workbook_completion_bundle_command(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_workbook_completion"
            runtime_execution_path = (
                root / "signal_phase_support_runtime_action_execution_bundle.json"
            )
            writeback_path = root / "signal_phase_support_writeback_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_support_workbook_completion_bundle",
                return_value={
                    "signal_phase_support_workbook_completion_bundle_version": "signal_phase_support_workbook_completion_bundle_v1",
                    "stats": {"completion_row_count": 2, "request_count": 1},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-support-workbook-completion-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-runtime-action-execution-bundle-path",
                            str(runtime_execution_path),
                            "--signal-phase-support-writeback-bundle-path",
                            str(writeback_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_runtime_action_execution_bundle_path=str(
                    runtime_execution_path
                ),
                signal_phase_support_writeback_bundle_path=str(writeback_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["signal_phase_support_workbook_completion_bundle_version"],
                "signal_phase_support_workbook_completion_bundle_v1",
            )
            self.assertEqual(payload["stats"]["completion_row_count"], 2)

    def test_run_bari_signal_phase_support_validation_batch_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_validation_batch"
            action_queue_path = root / "action_execution_ready_queue.csv"
            checklist_path = root / "delivery_checklist.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_support_validation_batch",
                return_value={
                    "signal_phase_support_validation_batch_version": "signal_phase_support_validation_batch_v1",
                    "stats": {"executed_validation_count": 1},
                },
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-support-validation-batch",
                            "--output-dir",
                            str(output_dir),
                            "--action-execution-ready-queue-path",
                            str(action_queue_path),
                            "--delivery-checklist-path",
                            str(checklist_path),
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                action_execution_ready_queue_path=str(action_queue_path),
                delivery_checklist_path=str(checklist_path),
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["signal_phase_support_validation_batch_version"], "signal_phase_support_validation_batch_v1")
            self.assertEqual(payload["stats"]["executed_validation_count"], 1)

    def test_run_bari_signal_phase_support_apply_cycle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_apply_cycle"
            action_queue_path = root / "action_execution_ready_queue.csv"
            checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_support_apply_cycle",
                return_value={
                    "signal_phase_support_apply_cycle_version": "signal_phase_support_apply_cycle_v1",
                    "stats": {"accepted_for_ingestion_count": 0},
                },
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-support-apply-cycle",
                            "--output-dir",
                            str(output_dir),
                            "--action-execution-ready-queue-path",
                            str(action_queue_path),
                            "--delivery-checklist-path",
                            str(checklist_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                action_execution_ready_queue_path=str(action_queue_path),
                delivery_checklist_path=str(checklist_path),
                movement_objects_path=str(movement_objects_path),
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["signal_phase_support_apply_cycle_version"], "signal_phase_support_apply_cycle_v1")
            self.assertEqual(payload["stats"]["accepted_for_ingestion_count"], 0)

    def test_run_bari_signal_phase_support_rehearsal_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_rehearsal"
            writeback_bundle_path = root / "signal_phase_support_writeback_bundle.json"
            resolution_bundle_path = root / "signal_phase_support_resolution_bundle.json"
            manual_mapping_stub_path = root / "arm_phase_mapping_sheet_mapping_stub.json"
            checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_support_rehearsal",
                return_value={
                    "signal_phase_support_rehearsal_version": "signal_phase_support_rehearsal_v1",
                    "stats": {"post_accepted_for_ingestion_count": 2},
                },
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-support-rehearsal",
                            "--output-dir",
                            str(output_dir),
                            "--request-id",
                            "bari_signal_phase_01",
                            "--signal-phase-support-writeback-bundle-path",
                            str(writeback_bundle_path),
                            "--signal-phase-support-resolution-bundle-path",
                            str(resolution_bundle_path),
                            "--manual-mapping-stub-path",
                            str(manual_mapping_stub_path),
                            "--delivery-checklist-path",
                            str(checklist_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--manual-phase-id",
                            "phase_x",
                            "--manual-stage-id",
                            "stage_x",
                            "--manual-protection-state",
                            "protected",
                            "--pedestrian-phase-id",
                            "ped_phase_x",
                            "--pedestrian-stage-id",
                            "ped_stage_x",
                            "--pedestrian-protection-state",
                            "protected",
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                request_id="bari_signal_phase_01",
                signal_phase_support_writeback_bundle_path=str(writeback_bundle_path),
                signal_phase_support_resolution_bundle_path=str(resolution_bundle_path),
                manual_mapping_stub_path=str(manual_mapping_stub_path),
                delivery_checklist_path=str(checklist_path),
                movement_objects_path=str(movement_objects_path),
                manual_phase_id="phase_x",
                manual_stage_id="stage_x",
                manual_protection_state="protected",
                pedestrian_phase_id="ped_phase_x",
                pedestrian_stage_id="ped_stage_x",
                pedestrian_protection_state="protected",
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["signal_phase_support_rehearsal_version"],
                "signal_phase_support_rehearsal_v1",
            )
            self.assertEqual(payload["stats"]["post_accepted_for_ingestion_count"], 2)

    def test_run_bari_signal_phase_support_runtime_cycle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_support_runtime_cycle"
            resolution_bundle_path = root / "signal_phase_support_resolution_bundle.json"
            manual_mapping_stub_path = root / "arm_phase_mapping_sheet_mapping_stub.json"
            checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_support_runtime_cycle",
                return_value={
                    "signal_phase_support_runtime_cycle_version": "signal_phase_support_runtime_cycle_v1",
                    "stats": {"accepted_for_ingestion_count": 2},
                },
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-support-runtime-cycle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-support-resolution-bundle-path",
                            str(resolution_bundle_path),
                            "--manual-mapping-stub-path",
                            str(manual_mapping_stub_path),
                            "--delivery-checklist-path",
                            str(checklist_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_support_resolution_bundle_path=str(resolution_bundle_path),
                manual_mapping_stub_path=str(manual_mapping_stub_path),
                delivery_checklist_path=str(checklist_path),
                movement_objects_path=str(movement_objects_path),
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["signal_phase_support_runtime_cycle_version"],
                "signal_phase_support_runtime_cycle_v1",
            )
            self.assertEqual(payload["stats"]["accepted_for_ingestion_count"], 2)

    def test_ingest_signal_phase_extract_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "signal_phase.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "signal_phase_records"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.ingest_signal_phase_extract",
                return_value={
                    "signal_phase_records_version": "signal_phase_records_v1",
                    "stats": {"written_rows": 2},
                },
            ) as ingest_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "ingest-signal-phase-extract",
                            str(input_csv_path),
                            str(mapping_stub_path),
                            "--output-dir",
                            str(output_dir),
                            "--limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            ingest_mock.assert_called_once_with(
                str(input_csv_path),
                str(mapping_stub_path),
                str(output_dir),
                limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["written_rows"], 2)

    def test_apply_signal_phase_to_movements_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            movement_objects_path = root / "movements.geojson"
            phase_manifest_path = root / "phase_records.manifest.json"
            output_dir = root / "movement_phase"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.apply_signal_phase_to_movements",
                return_value={
                    "movement_signal_phase_version": "movement_signal_phase_v1",
                    "stats": {"movements_with_phase_timing": 4},
                },
            ) as join_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "apply-signal-phase-to-movements",
                            str(movement_objects_path),
                            str(phase_manifest_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            join_mock.assert_called_once_with(
                str(movement_objects_path),
                [str(phase_manifest_path)],
                str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["movements_with_phase_timing"], 4)

    def test_build_bari_signal_phase_request_pack_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_requests"
            intake_path = root / "signal_phase_intake_pack.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_request_pack",
                return_value={
                    "source": {"adapter": "bari_signal_phase_request_pack_builder"},
                    "stats": {"public_dataset_count": 3, "request_row_count": 20},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-request-pack",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-intake-path",
                            str(intake_path),
                            "--portal-base-url",
                            "https://opendata.comune.bari.it/api/3/action/package_search",
                            "--timeout-s",
                            "12",
                            "--verify-ssl",
                            "--top-n",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_intake_path=str(intake_path),
                portal_base_url="https://opendata.comune.bari.it/api/3/action/package_search",
                timeout_s=12.0,
                verify_ssl=True,
                top_n=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_request_pack_builder")
            self.assertEqual(payload["stats"]["public_dataset_count"], 3)

    def test_build_bari_signal_phase_acquisition_plan_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_acquisition"
            request_pack_path = root / "signal_phase_request_pack.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_acquisition_plan",
                return_value={
                    "source": {"adapter": "bari_signal_phase_acquisition_plan_builder"},
                    "stats": {"request_row_count": 20, "delivery_item_count": 44},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-acquisition-plan",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-request-pack-path",
                            str(request_pack_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_request_pack_path=str(request_pack_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_acquisition_plan_builder")
            self.assertEqual(payload["stats"]["delivery_item_count"], 44)

    def test_build_bari_signal_phase_outreach_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_outreach"
            acquisition_plan_path = root / "signal_phase_acquisition_plan.json"
            request_pack_path = root / "signal_phase_request_pack.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_outreach_bundle",
                return_value={
                    "source": {"adapter": "bari_signal_phase_outreach_bundle_builder"},
                    "stats": {"target_request_count": 6, "request_packet_count": 6},
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-outreach-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--acquisition-plan-path",
                            str(acquisition_plan_path),
                            "--signal-phase-request-pack-path",
                            str(request_pack_path),
                            "--priority-band",
                            "tier_1_immediate",
                            "--max-requests",
                            "6",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                acquisition_plan_path=str(acquisition_plan_path),
                signal_phase_request_pack_path=str(request_pack_path),
                priority_band="tier_1_immediate",
                max_requests=6,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["source"]["adapter"], "bari_signal_phase_outreach_bundle_builder")
            self.assertEqual(payload["stats"]["request_packet_count"], 6)

    def test_validate_signal_phase_delivery_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "delivery.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "validation"
            checklist_path = root / "delivery_checklist.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.validate_signal_phase_delivery",
                return_value={"stats": {"validation_outcome": "accepted_for_ingestion", "accepted_rows": 1}},
            ) as validate_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "validate-signal-phase-delivery",
                            str(input_csv_path),
                            str(mapping_stub_path),
                            "--output-dir",
                            str(output_dir),
                            "--delivery-checklist-path",
                            str(checklist_path),
                            "--request-id",
                            "bari_signal_phase_01",
                            "--junction-id",
                            "it-bari-signal-93",
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            validate_mock.assert_called_once_with(
                str(input_csv_path),
                str(mapping_stub_path),
                str(output_dir),
                delivery_checklist_path=str(checklist_path),
                request_id="bari_signal_phase_01",
                junction_id="it-bari-signal-93",
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["validation_outcome"], "accepted_for_ingestion")

    def test_apply_validated_signal_phase_deliveries_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            movement_objects_path = root / "road_movement_objects.geojson"
            validation_manifest_path = root / "validation.manifest.json"
            output_dir = root / "session"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.apply_validated_signal_phase_deliveries",
                return_value={"stats": {"accepted_validation_count": 3, "movements_with_phase_timing": 4}},
            ) as apply_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "apply-validated-signal-phase-deliveries",
                            str(movement_objects_path),
                            str(validation_manifest_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            apply_mock.assert_called_once_with(
                str(movement_objects_path),
                [str(validation_manifest_path)],
                str(output_dir),
                matched_records_path="data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
                target_request_queue_path="data/planning/signal_phase_outreach/bari/target_request_queue.csv",
                baseline_movement_objects_path=None,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["accepted_validation_count"], 3)

    def test_build_bari_signal_phase_coverage_report_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_coverage"
            movement_objects_path = root / "road_movement_objects_signal_phase.geojson"
            matched_records_path = root / "matched_node_records.jsonl"
            target_request_queue_path = root / "target_request_queue.csv"
            delivery_session_manifest_path = root / "signal_phase_delivery_session.manifest.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_coverage_report",
                return_value={"stats": {"movement_count": 40718, "movements_with_phase_timing": 1}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-coverage-report",
                            "--output-dir",
                            str(output_dir),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--matched-records-path",
                            str(matched_records_path),
                            "--target-request-queue-path",
                            str(target_request_queue_path),
                            "--delivery-session-manifest-path",
                            str(delivery_session_manifest_path),
                            "--top-n",
                            "12",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                movement_objects_path=str(movement_objects_path),
                matched_records_path=str(matched_records_path),
                target_request_queue_path=str(target_request_queue_path),
                delivery_session_manifest_path=str(delivery_session_manifest_path),
                top_n=12,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["movement_count"], 40718)
            self.assertEqual(payload["stats"]["movements_with_phase_timing"], 1)

    def test_build_bari_signal_phase_target_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_targets"
            target_junction_coverage_path = root / "target_junction_coverage.csv"
            uncovered_signalized_hotspots_path = root / "uncovered_signalized_hotspots.csv"
            target_request_queue_path = root / "target_request_queue.csv"
            matched_movement_records_path = root / "matched_node_records.jsonl"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_target_bundle",
                return_value={"stats": {"target_count": 6, "packet_count": 6}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-target-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--target-junction-coverage-path",
                            str(target_junction_coverage_path),
                            "--uncovered-signalized-hotspots-path",
                            str(uncovered_signalized_hotspots_path),
                            "--target-request-queue-path",
                            str(target_request_queue_path),
                            "--matched-movement-records-path",
                            str(matched_movement_records_path),
                            "--top-hotspots-per-target",
                            "4",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                target_junction_coverage_path=str(target_junction_coverage_path),
                uncovered_signalized_hotspots_path=str(uncovered_signalized_hotspots_path),
                target_request_queue_path=str(target_request_queue_path),
                matched_movement_records_path=str(matched_movement_records_path),
                top_hotspots_per_target=4,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["target_count"], 6)
            self.assertEqual(payload["stats"]["packet_count"], 6)

    def test_build_bari_signal_phase_request_scope_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_request_scope"
            target_bundle_path = root / "signal_phase_target_bundle.json"
            delivery_checklist_path = root / "delivery_checklist.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_request_scope_bundle",
                return_value={"stats": {"target_count": 6, "delivery_scope_count": 18}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-request-scope-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-target-bundle-path",
                            str(target_bundle_path),
                            "--delivery-checklist-path",
                            str(delivery_checklist_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_target_bundle_path=str(target_bundle_path),
                delivery_checklist_path=str(delivery_checklist_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["target_count"], 6)
            self.assertEqual(payload["stats"]["delivery_scope_count"], 18)

    def test_build_bari_signal_phase_contact_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_contact"
            scope_bundle_path = root / "signal_phase_request_scope_bundle.json"
            outreach_tracker_path = root / "outreach_tracker.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_contact_bundle",
                return_value={"stats": {"target_count": 6, "draft_count": 6}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-contact-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-request-scope-bundle-path",
                            str(scope_bundle_path),
                            "--outreach-tracker-path",
                            str(outreach_tracker_path),
                            "--follow-up-days",
                            "10",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_request_scope_bundle_path=str(scope_bundle_path),
                outreach_tracker_path=str(outreach_tracker_path),
                follow_up_days=10,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["target_count"], 6)
            self.assertEqual(payload["stats"]["draft_count"], 6)

    def test_build_bari_signal_phase_contact_resolution_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_contact_resolution"
            contact_bundle_path = root / "signal_phase_contact_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_contact_resolution_bundle",
                return_value={"stats": {"target_count": 6, "official_channel_count": 5}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-contact-resolution-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-contact-bundle-path",
                            str(contact_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_contact_bundle_path=str(contact_bundle_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["target_count"], 6)
            self.assertEqual(payload["stats"]["official_channel_count"], 5)

    def test_build_bari_signal_phase_dispatch_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch"
            resolution_bundle_path = root / "signal_phase_contact_resolution_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_bundle",
                return_value={"stats": {"target_count": 6, "follow_up_item_count": 12}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-contact-resolution-bundle-path",
                            str(resolution_bundle_path),
                            "--planned-dispatch-date",
                            "2026-03-29",
                            "--follow-up-days",
                            "7",
                            "--escalation-days",
                            "14",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_contact_resolution_bundle_path=str(resolution_bundle_path),
                planned_dispatch_date="2026-03-29",
                follow_up_days=7,
                escalation_days=14,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["target_count"], 6)
            self.assertEqual(payload["stats"]["follow_up_item_count"], 12)

    def test_build_bari_signal_phase_delivery_intake_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_delivery_intake"
            dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            delivery_checklist_path = root / "delivery_checklist.csv"
            mapping_stub_dir = root / "mapping_stubs"
            validation_output_root = root / "validation"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_delivery_intake_bundle",
                return_value={"stats": {"dispatch_request_count": 6, "expected_delivery_count": 18}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-delivery-intake-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-dispatch-bundle-path",
                            str(dispatch_bundle_path),
                            "--delivery-checklist-path",
                            str(delivery_checklist_path),
                            "--mapping-stub-dir",
                            str(mapping_stub_dir),
                            "--validation-output-root",
                            str(validation_output_root),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_dispatch_bundle_path=str(dispatch_bundle_path),
                delivery_checklist_path=str(delivery_checklist_path),
                mapping_stub_dir=str(mapping_stub_dir),
                validation_output_root=str(validation_output_root),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["dispatch_request_count"], 6)
            self.assertEqual(payload["stats"]["expected_delivery_count"], 18)

    def test_build_bari_signal_phase_delivery_monitor_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_delivery_monitor"
            intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            receipt_register_path = root / "delivery_receipt_register.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_delivery_monitor_bundle",
                return_value={"stats": {"monitored_delivery_count": 18, "validation_ready_count": 0}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-delivery-monitor-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-delivery-intake-bundle-path",
                            str(intake_bundle_path),
                            "--delivery-receipt-register-path",
                            str(receipt_register_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_delivery_intake_bundle_path=str(intake_bundle_path),
                delivery_receipt_register_path=str(receipt_register_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["monitored_delivery_count"], 18)
            self.assertEqual(payload["stats"]["validation_ready_count"], 0)

    def test_run_bari_signal_phase_validation_batch_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_validation_batch"
            ready_queue_path = root / "validation_ready_queue.csv"
            receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_checklist_path = root / "delivery_checklist.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_validation_batch",
                return_value={"stats": {"ready_queue_count": 0, "executed_validation_count": 0}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-validation-batch",
                            "--output-dir",
                            str(output_dir),
                            "--validation-ready-queue-path",
                            str(ready_queue_path),
                            "--delivery-receipt-register-path",
                            str(receipt_register_path),
                            "--delivery-checklist-path",
                            str(delivery_checklist_path),
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                validation_ready_queue_path=str(ready_queue_path),
                delivery_receipt_register_path=str(receipt_register_path),
                delivery_checklist_path=str(delivery_checklist_path),
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["ready_queue_count"], 0)
            self.assertEqual(payload["stats"]["executed_validation_count"], 0)

    def test_run_bari_signal_phase_receive_cycle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_receive_cycle"
            intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_receive_cycle",
                return_value={"stats": {"validation_ready_count": 0, "delivery_session_executed": False}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-receive-cycle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-delivery-intake-bundle-path",
                            str(intake_bundle_path),
                            "--delivery-receipt-register-path",
                            str(receipt_register_path),
                            "--delivery-checklist-path",
                            str(delivery_checklist_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_delivery_intake_bundle_path=str(intake_bundle_path),
                delivery_receipt_register_path=str(receipt_register_path),
                delivery_checklist_path=str(delivery_checklist_path),
                movement_objects_path=str(movement_objects_path),
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["validation_ready_count"], 0)
            self.assertFalse(payload["stats"]["delivery_session_executed"])

    def test_build_bari_signal_phase_lifecycle_report_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_lifecycle"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            receipt_register_path = root / "delivery_receipt_register.csv"
            monitor_queue_path = root / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation_batch_results.csv"
            receive_cycle_path = root / "signal_phase_receive_cycle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_lifecycle_report",
                return_value={"stats": {"delivery_item_count": 18, "awaiting_delivery_count": 18}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-lifecycle-report",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-execution-queue-path",
                            str(dispatch_queue_path),
                            "--follow-up-tracker-path",
                            str(follow_up_tracker_path),
                            "--delivery-receipt-register-path",
                            str(receipt_register_path),
                            "--delivery-monitor-queue-path",
                            str(monitor_queue_path),
                            "--validation-batch-results-path",
                            str(validation_batch_results_path),
                            "--receive-cycle-path",
                            str(receive_cycle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_execution_queue_path=str(dispatch_queue_path),
                follow_up_tracker_path=str(follow_up_tracker_path),
                delivery_receipt_register_path=str(receipt_register_path),
                delivery_monitor_queue_path=str(monitor_queue_path),
                validation_batch_results_path=str(validation_batch_results_path),
                receive_cycle_path=str(receive_cycle_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["delivery_item_count"], 18)
            self.assertEqual(payload["stats"]["awaiting_delivery_count"], 18)

    def test_build_bari_signal_phase_status_sync_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_status_sync"
            receipt_register_path = root / "delivery_receipt_register.csv"
            monitor_queue_path = root / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation_batch_results.csv"
            checklist_path = root / "delivery_checklist.csv"
            receive_cycle_path = root / "signal_phase_receive_cycle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_status_sync_bundle",
                return_value={"stats": {"receipt_row_count": 18, "validated_count": 0}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-status-sync-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--delivery-receipt-register-path",
                            str(receipt_register_path),
                            "--delivery-monitor-queue-path",
                            str(monitor_queue_path),
                            "--validation-batch-results-path",
                            str(validation_batch_results_path),
                            "--delivery-checklist-path",
                            str(checklist_path),
                            "--receive-cycle-path",
                            str(receive_cycle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                delivery_receipt_register_path=str(receipt_register_path),
                delivery_monitor_queue_path=str(monitor_queue_path),
                validation_batch_results_path=str(validation_batch_results_path),
                delivery_checklist_path=str(checklist_path),
                receive_cycle_path=str(receive_cycle_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["receipt_row_count"], 18)
            self.assertEqual(payload["stats"]["validated_count"], 0)

    def test_build_bari_signal_phase_follow_up_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_follow_up"
            dispatch_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_agenda_path = root / "follow_up_agenda.csv"
            synced_receipt_path = root / "delivery_receipt_register_synced.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_follow_up_bundle",
                return_value={"stats": {"request_count": 6, "due_now_count": 0}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-follow-up-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-execution-queue-path",
                            str(dispatch_queue_path),
                            "--follow-up-agenda-path",
                            str(follow_up_agenda_path),
                            "--synced-receipt-register-path",
                            str(synced_receipt_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_execution_queue_path=str(dispatch_queue_path),
                follow_up_agenda_path=str(follow_up_agenda_path),
                synced_receipt_register_path=str(synced_receipt_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 6)
            self.assertEqual(payload["stats"]["due_now_count"], 0)

    def test_build_bari_signal_phase_follow_up_execution_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_follow_up_execution"
            follow_up_ready_queue_path = root / "follow_up_ready_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_follow_up_execution_bundle",
                return_value={"stats": {"execution_ready_count": 6, "internal_hold_count": 0}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-follow-up-execution-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--follow-up-ready-queue-path",
                            str(follow_up_ready_queue_path),
                            "--follow-up-tracker-path",
                            str(follow_up_tracker_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                follow_up_ready_queue_path=str(follow_up_ready_queue_path),
                follow_up_tracker_path=str(follow_up_tracker_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["execution_ready_count"], 6)
            self.assertEqual(payload["stats"]["internal_hold_count"], 0)

    def test_build_bari_signal_phase_follow_up_writeback_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_follow_up_writeback"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            follow_up_execution_queue_path = root / "follow_up_execution_queue.csv"
            follow_up_tracker_updates_path = root / "follow_up_tracker_updates.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_follow_up_writeback_bundle",
                return_value={"stats": {"writeback_ready_count": 1, "tracker_rows_completed_count": 1}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-follow-up-writeback-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-execution-queue-path",
                            str(dispatch_execution_queue_path),
                            "--follow-up-tracker-path",
                            str(follow_up_tracker_path),
                            "--follow-up-execution-queue-path",
                            str(follow_up_execution_queue_path),
                            "--follow-up-tracker-updates-path",
                            str(follow_up_tracker_updates_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_execution_queue_path=str(dispatch_execution_queue_path),
                follow_up_tracker_path=str(follow_up_tracker_path),
                follow_up_execution_queue_path=str(follow_up_execution_queue_path),
                follow_up_tracker_updates_path=str(follow_up_tracker_updates_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["writeback_ready_count"], 1)
            self.assertEqual(payload["stats"]["tracker_rows_completed_count"], 1)

    def test_run_bari_signal_phase_follow_up_cycle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_follow_up_cycle"
            follow_up_writeback_bundle_path = root / "signal_phase_follow_up_writeback_bundle.json"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_monitor_queue_path = root / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation_batch_results.csv"
            receive_cycle_path = root / "signal_phase_receive_cycle.json"
            synced_receipt_register_path = root / "delivery_receipt_register_synced.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_follow_up_cycle",
                return_value={"stats": {"runtime_execution_ready_count": 1, "writeback_ready_count": 1}},
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-follow-up-cycle",
                            "--output-dir",
                            str(output_dir),
                            "--follow-up-writeback-bundle-path",
                            str(follow_up_writeback_bundle_path),
                            "--delivery-receipt-register-path",
                            str(delivery_receipt_register_path),
                            "--delivery-monitor-queue-path",
                            str(delivery_monitor_queue_path),
                            "--validation-batch-results-path",
                            str(validation_batch_results_path),
                            "--receive-cycle-path",
                            str(receive_cycle_path),
                            "--synced-receipt-register-path",
                            str(synced_receipt_register_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                follow_up_writeback_bundle_path=str(follow_up_writeback_bundle_path),
                delivery_receipt_register_path=str(delivery_receipt_register_path),
                delivery_monitor_queue_path=str(delivery_monitor_queue_path),
                validation_batch_results_path=str(validation_batch_results_path),
                receive_cycle_path=str(receive_cycle_path),
                synced_receipt_register_path=str(synced_receipt_register_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["runtime_execution_ready_count"], 1)
            self.assertEqual(payload["stats"]["writeback_ready_count"], 1)

    def test_run_bari_signal_phase_operations_cycle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_operations_cycle"
            signal_phase_delivery_intake_bundle_path = root / "signal_phase_delivery_intake_bundle.json"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_checklist_path = root / "delivery_checklist.csv"
            movement_objects_path = root / "road_movement_objects.geojson"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_operations_cycle",
                return_value={"stats": {"receive_monitored_delivery_count": 18, "runtime_execution_ready_count": 6}},
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-operations-cycle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-delivery-intake-bundle-path",
                            str(signal_phase_delivery_intake_bundle_path),
                            "--delivery-receipt-register-path",
                            str(delivery_receipt_register_path),
                            "--delivery-checklist-path",
                            str(delivery_checklist_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--dispatch-execution-queue-path",
                            str(dispatch_execution_queue_path),
                            "--follow-up-tracker-path",
                            str(follow_up_tracker_path),
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_delivery_intake_bundle_path=str(signal_phase_delivery_intake_bundle_path),
                delivery_receipt_register_path=str(delivery_receipt_register_path),
                delivery_checklist_path=str(delivery_checklist_path),
                movement_objects_path=str(movement_objects_path),
                dispatch_execution_queue_path=str(dispatch_execution_queue_path),
                follow_up_tracker_path=str(follow_up_tracker_path),
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["receive_monitored_delivery_count"], 18)
            self.assertEqual(payload["stats"]["runtime_execution_ready_count"], 6)

    def test_build_bari_signal_phase_action_queue_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_action_queue"
            signal_phase_operations_cycle_path = root / "signal_phase_operations_cycle.json"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            signal_phase_dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            lifecycle_items_path = root / "lifecycle_items.csv"
            follow_up_execution_queue_path = root / "follow_up_execution_queue.csv"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_repair_status_path = root / "dispatch_repair_status.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_action_queue",
                return_value={"stats": {"request_count": 6, "dispatch_action_count": 6}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-action-queue",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-operations-cycle-path",
                            str(signal_phase_operations_cycle_path),
                            "--dispatch-execution-queue-path",
                            str(dispatch_execution_queue_path),
                            "--signal-phase-dispatch-bundle-path",
                            str(signal_phase_dispatch_bundle_path),
                            "--lifecycle-items-path",
                            str(lifecycle_items_path),
                            "--follow-up-execution-queue-path",
                            str(follow_up_execution_queue_path),
                            "--dispatch-log-repair-queue-path",
                            str(dispatch_log_repair_queue_path),
                            "--dispatch-repair-status-path",
                            str(dispatch_repair_status_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_operations_cycle_path=str(signal_phase_operations_cycle_path),
                dispatch_execution_queue_path=str(dispatch_execution_queue_path),
                signal_phase_dispatch_bundle_path=str(signal_phase_dispatch_bundle_path),
                lifecycle_items_path=str(lifecycle_items_path),
                follow_up_execution_queue_path=str(follow_up_execution_queue_path),
                dispatch_log_repair_queue_path=str(dispatch_log_repair_queue_path),
                dispatch_repair_status_path=str(dispatch_repair_status_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 6)
            self.assertEqual(payload["stats"]["dispatch_action_count"], 6)

    def test_build_bari_signal_phase_dispatch_execution_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_execution"
            signal_phase_action_queue_path = root / "action_queue.csv"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            dispatch_packet_dir = root / "dispatch_packets"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_execution_bundle",
                return_value={"stats": {"request_count": 6, "execution_ready_count": 6}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-execution-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-action-queue-path",
                            str(signal_phase_action_queue_path),
                            "--dispatch-execution-queue-path",
                            str(dispatch_execution_queue_path),
                            "--dispatch-packet-dir",
                            str(dispatch_packet_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_action_queue_path=str(signal_phase_action_queue_path),
                dispatch_execution_queue_path=str(dispatch_execution_queue_path),
                dispatch_packet_dir=str(dispatch_packet_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 6)
            self.assertEqual(payload["stats"]["execution_ready_count"], 6)

    def test_build_bari_signal_phase_action_execution_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_action_execution"
            signal_phase_action_queue_path = root / "action_queue.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_action_execution_bundle",
                return_value={"stats": {"request_count": 6, "execution_ready_count": 4}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-action-execution-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-action-queue-path",
                            str(signal_phase_action_queue_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_action_queue_path=str(signal_phase_action_queue_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 6)
            self.assertEqual(payload["stats"]["execution_ready_count"], 4)

    def test_build_bari_signal_phase_action_handoff_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_action_handoff"
            action_execution_bundle_path = root / "signal_phase_action_execution_bundle.json"
            dispatch_execution_log_path = root / "dispatch_execution_log.csv"
            follow_up_execution_queue_path = root / "follow_up_execution_queue.csv"
            dispatch_log_repair_log_path = root / "dispatch_log_repair_log.csv"
            delivery_monitor_queue_path = root / "delivery_monitor_queue.csv"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            runtime_cycle_manifest_path = root / "signal_phase_runtime_cycle.manifest.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_action_handoff_bundle",
                return_value={"stats": {"request_count": 6, "handoff_ready_count": 4}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-action-handoff-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-action-execution-bundle-path",
                            str(action_execution_bundle_path),
                            "--dispatch-execution-log-path",
                            str(dispatch_execution_log_path),
                            "--follow-up-execution-queue-path",
                            str(follow_up_execution_queue_path),
                            "--dispatch-log-repair-log-path",
                            str(dispatch_log_repair_log_path),
                            "--delivery-monitor-queue-path",
                            str(delivery_monitor_queue_path),
                            "--delivery-receipt-register-path",
                            str(delivery_receipt_register_path),
                            "--runtime-cycle-manifest-path",
                            str(runtime_cycle_manifest_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_action_execution_bundle_path=str(action_execution_bundle_path),
                dispatch_execution_log_path=str(dispatch_execution_log_path),
                follow_up_execution_queue_path=str(follow_up_execution_queue_path),
                dispatch_log_repair_log_path=str(dispatch_log_repair_log_path),
                delivery_monitor_queue_path=str(delivery_monitor_queue_path),
                delivery_receipt_register_path=str(delivery_receipt_register_path),
                runtime_cycle_manifest_path=str(runtime_cycle_manifest_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 6)
            self.assertEqual(payload["stats"]["handoff_ready_count"], 4)

    def test_build_bari_signal_phase_operator_board_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_operator_board"
            action_execution_bundle_path = root / "signal_phase_action_execution_bundle.json"
            action_handoff_bundle_path = root / "signal_phase_action_handoff_bundle.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_operator_board_bundle",
                return_value={"stats": {"request_count": 6, "operator_ready_count": 4}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-operator-board-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-action-execution-bundle-path",
                            str(action_execution_bundle_path),
                            "--signal-phase-action-handoff-bundle-path",
                            str(action_handoff_bundle_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_action_execution_bundle_path=str(action_execution_bundle_path),
                signal_phase_action_handoff_bundle_path=str(action_handoff_bundle_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 6)
            self.assertEqual(payload["stats"]["operator_ready_count"], 4)

    def test_build_bari_signal_phase_dispatch_writeback_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_writeback"
            dispatch_execution_queue_path = root / "dispatch_execution_queue.csv"
            follow_up_tracker_path = root / "follow_up_tracker.csv"
            dispatch_execution_ready_queue_path = root / "dispatch_execution_ready_queue.csv"
            dispatch_tracker_updates_path = root / "dispatch_tracker_updates.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_writeback_bundle",
                return_value={"stats": {"dispatch_row_count": 6, "dispatch_rows_updated_count": 0}},
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-writeback-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-execution-queue-path",
                            str(dispatch_execution_queue_path),
                            "--follow-up-tracker-path",
                            str(follow_up_tracker_path),
                            "--dispatch-execution-ready-queue-path",
                            str(dispatch_execution_ready_queue_path),
                            "--dispatch-tracker-updates-path",
                            str(dispatch_tracker_updates_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_execution_queue_path=str(dispatch_execution_queue_path),
                follow_up_tracker_path=str(follow_up_tracker_path),
                dispatch_execution_ready_queue_path=str(dispatch_execution_ready_queue_path),
                dispatch_tracker_updates_path=str(dispatch_tracker_updates_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["dispatch_row_count"], 6)
            self.assertEqual(payload["stats"]["dispatch_rows_updated_count"], 0)

    def test_run_bari_signal_phase_dispatch_cycle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_cycle"
            writeback_bundle_path = root / "signal_phase_dispatch_writeback_bundle.json"
            delivery_receipt_register_path = root / "delivery_receipt_register.csv"
            delivery_monitor_queue_path = root / "delivery_monitor_queue.csv"
            validation_batch_results_path = root / "validation_batch_results.csv"
            receive_cycle_path = root / "signal_phase_receive_cycle.json"
            synced_receipt_register_path = root / "delivery_receipt_register_synced.csv"
            operations_cycle_path = root / "signal_phase_operations_cycle.json"
            dispatch_bundle_path = root / "signal_phase_dispatch_bundle.json"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_repair_status_path = root / "dispatch_repair_status.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_dispatch_cycle",
                return_value={
                    "stats": {
                        "writeback_ready_count": 0,
                        "runtime_action_request_count": 6,
                    }
                },
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-dispatch-cycle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-dispatch-writeback-bundle-path",
                            str(writeback_bundle_path),
                            "--delivery-receipt-register-path",
                            str(delivery_receipt_register_path),
                            "--delivery-monitor-queue-path",
                            str(delivery_monitor_queue_path),
                            "--validation-batch-results-path",
                            str(validation_batch_results_path),
                            "--receive-cycle-path",
                            str(receive_cycle_path),
                            "--synced-receipt-register-path",
                            str(synced_receipt_register_path),
                            "--signal-phase-operations-cycle-path",
                            str(operations_cycle_path),
                            "--signal-phase-dispatch-bundle-path",
                            str(dispatch_bundle_path),
                            "--dispatch-log-repair-queue-path",
                            str(dispatch_log_repair_queue_path),
                            "--dispatch-repair-status-path",
                            str(dispatch_repair_status_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_dispatch_writeback_bundle_path=str(writeback_bundle_path),
                delivery_receipt_register_path=str(delivery_receipt_register_path),
                delivery_monitor_queue_path=str(delivery_monitor_queue_path),
                validation_batch_results_path=str(validation_batch_results_path),
                receive_cycle_path=str(receive_cycle_path),
                synced_receipt_register_path=str(synced_receipt_register_path),
                signal_phase_operations_cycle_path=str(operations_cycle_path),
                signal_phase_dispatch_bundle_path=str(dispatch_bundle_path),
                dispatch_log_repair_queue_path=str(dispatch_log_repair_queue_path),
                dispatch_repair_status_path=str(dispatch_repair_status_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["writeback_ready_count"], 0)
            self.assertEqual(payload["stats"]["runtime_action_request_count"], 6)

    def test_run_bari_signal_phase_runtime_cycle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_runtime_cycle"
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

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_runtime_cycle",
                return_value={
                    "stats": {
                        "receive_monitored_delivery_count": 18,
                        "runtime_dispatch_action_count": 6,
                    }
                },
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-runtime-cycle",
                            "--output-dir",
                            str(output_dir),
                            "--signal-phase-delivery-intake-bundle-path",
                            str(intake_bundle_path),
                            "--delivery-receipt-register-path",
                            str(delivery_receipt_register_path),
                            "--delivery-checklist-path",
                            str(delivery_checklist_path),
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--dispatch-execution-queue-path",
                            str(dispatch_execution_queue_path),
                            "--follow-up-tracker-path",
                            str(follow_up_tracker_path),
                            "--signal-phase-dispatch-bundle-path",
                            str(dispatch_bundle_path),
                            "--dispatch-log-repair-queue-path",
                            str(dispatch_log_repair_queue_path),
                            "--dispatch-log-repair-log-path",
                            str(dispatch_log_repair_log_path),
                            "--dispatch-execution-log-path",
                            str(dispatch_execution_log_path),
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                signal_phase_delivery_intake_bundle_path=str(intake_bundle_path),
                delivery_receipt_register_path=str(delivery_receipt_register_path),
                delivery_checklist_path=str(delivery_checklist_path),
                movement_objects_path=str(movement_objects_path),
                dispatch_execution_queue_path=str(dispatch_execution_queue_path),
                follow_up_tracker_path=str(follow_up_tracker_path),
                signal_phase_dispatch_bundle_path=str(dispatch_bundle_path),
                dispatch_log_repair_queue_path=str(dispatch_log_repair_queue_path),
                dispatch_log_repair_log_path=str(dispatch_log_repair_log_path),
                dispatch_execution_log_path=str(dispatch_execution_log_path),
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["receive_monitored_delivery_count"], 18)
            self.assertEqual(payload["stats"]["runtime_dispatch_action_count"], 6)

    def test_run_bari_signal_phase_runtime_rehearsal_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_runtime_rehearsal"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_signal_phase_runtime_rehearsal",
                return_value={
                    "stats": {
                        "changed_request_count": 1,
                        "selected_request_left_dispatch_action": "yes",
                    }
                },
            ) as run_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-signal-phase-runtime-rehearsal",
                            "--output-dir",
                            str(output_dir),
                            "--request-id",
                            "bari_signal_phase_01",
                            "--execution-channel-used",
                            "pec_email",
                            "--execution-outcome",
                            "request_dispatched",
                            "--preview-limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            run_mock.assert_called_once_with(
                output_dir=str(output_dir),
                request_id="bari_signal_phase_01",
                signal_phase_delivery_intake_bundle_path="data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
                delivery_receipt_register_path="data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
                delivery_checklist_path="data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
                movement_objects_path="data/processed/movement_objects/bari/road_movement_objects.geojson",
                dispatch_execution_queue_path="data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
                follow_up_tracker_path="data/planning/signal_phase_dispatch/bari/follow_up_tracker.csv",
                signal_phase_dispatch_bundle_path="data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
                dispatch_log_repair_queue_path="data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
                dispatch_log_repair_log_path="data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_log_repair_log.csv",
                execution_status="sent",
                execution_channel_used="pec_email",
                execution_outcome="request_dispatched",
                response_received="no",
                response_summary="",
                protocol_reference=None,
                evidence_path="",
                execution_notes="rehearsal send",
                execution_completed_at=None,
                preview_limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["changed_request_count"], 1)
            self.assertEqual(payload["stats"]["selected_request_left_dispatch_action"], "yes")

    def test_build_bari_signal_phase_dispatch_recording_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_recording"
            dispatch_execution_ready_queue_path = root / "dispatch_execution_ready_queue.csv"
            dispatch_execution_log_path = root / "dispatch_execution_log.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_recording_bundle",
                return_value={
                    "stats": {
                        "request_count": 6,
                        "applied_execution_count": 0,
                    }
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-recording-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-execution-ready-queue-path",
                            str(dispatch_execution_ready_queue_path),
                            "--dispatch-execution-log-path",
                            str(dispatch_execution_log_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_execution_ready_queue_path=str(dispatch_execution_ready_queue_path),
                dispatch_execution_log_path=str(dispatch_execution_log_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 6)
            self.assertEqual(payload["stats"]["applied_execution_count"], 0)

    def test_build_bari_signal_phase_dispatch_validation_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_validation"
            dispatch_execution_runtime_queue_path = root / "dispatch_execution_queue_runtime.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_validation_bundle",
                return_value={
                    "stats": {
                        "runtime_row_count": 6,
                        "accepted_for_writeback_count": 0,
                    }
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-validation-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-execution-runtime-queue-path",
                            str(dispatch_execution_runtime_queue_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_execution_runtime_queue_path=str(dispatch_execution_runtime_queue_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["runtime_row_count"], 6)
            self.assertEqual(payload["stats"]["accepted_for_writeback_count"], 0)

    def test_build_bari_signal_phase_dispatch_repair_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_repair"
            dispatch_validation_queue_path = root / "dispatch_execution_queue_validated.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_repair_bundle",
                return_value={
                    "stats": {
                        "validated_row_count": 6,
                        "repair_request_count": 0,
                    }
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-repair-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-validation-queue-path",
                            str(dispatch_validation_queue_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_validation_queue_path=str(dispatch_validation_queue_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["validated_row_count"], 6)
            self.assertEqual(payload["stats"]["repair_request_count"], 0)

    def test_build_bari_signal_phase_dispatch_repair_recording_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_repair_recording"
            dispatch_execution_runtime_queue_path = root / "dispatch_execution_queue_runtime.csv"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_log_repair_log_path = root / "dispatch_log_repair_log.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_repair_recording_bundle",
                return_value={
                    "stats": {
                        "runtime_row_count": 6,
                        "applied_repair_count": 1,
                    }
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-repair-recording-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-execution-runtime-queue-path",
                            str(dispatch_execution_runtime_queue_path),
                            "--dispatch-log-repair-queue-path",
                            str(dispatch_log_repair_queue_path),
                            "--dispatch-log-repair-log-path",
                            str(dispatch_log_repair_log_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_execution_runtime_queue_path=str(dispatch_execution_runtime_queue_path),
                dispatch_log_repair_queue_path=str(dispatch_log_repair_queue_path),
                dispatch_log_repair_log_path=str(dispatch_log_repair_log_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["runtime_row_count"], 6)
            self.assertEqual(payload["stats"]["applied_repair_count"], 1)

    def test_build_bari_signal_phase_dispatch_repair_execution_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_repair_execution"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_log_repair_log_path = root / "dispatch_log_repair_log.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_repair_execution_bundle",
                return_value={
                    "stats": {
                        "request_count": 2,
                        "execution_ready_count": 1,
                    }
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-repair-execution-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-log-repair-queue-path",
                            str(dispatch_log_repair_queue_path),
                            "--dispatch-log-repair-log-path",
                            str(dispatch_log_repair_log_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_log_repair_queue_path=str(dispatch_log_repair_queue_path),
                dispatch_log_repair_log_path=str(dispatch_log_repair_log_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 2)
            self.assertEqual(payload["stats"]["execution_ready_count"], 1)

    def test_build_bari_signal_phase_dispatch_repair_status_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_dispatch_repair_status"
            dispatch_log_repair_queue_path = root / "dispatch_log_repair_queue.csv"
            dispatch_log_repair_log_path = root / "dispatch_log_repair_log.csv"
            dispatch_repair_execution_ready_queue_path = root / "dispatch_repair_execution_ready_queue.csv"
            dispatch_repair_internal_hold_queue_path = root / "dispatch_repair_internal_hold_queue.csv"
            dispatch_validation_queue_path = root / "dispatch_execution_queue_validated.csv"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_bari_signal_phase_dispatch_repair_status_bundle",
                return_value={
                    "stats": {
                        "request_count": 2,
                        "pending_repair_count": 1,
                        "cleared_for_writeback_count": 1,
                    }
                },
            ) as build_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-bari-signal-phase-dispatch-repair-status-bundle",
                            "--output-dir",
                            str(output_dir),
                            "--dispatch-log-repair-queue-path",
                            str(dispatch_log_repair_queue_path),
                            "--dispatch-log-repair-log-path",
                            str(dispatch_log_repair_log_path),
                            "--dispatch-repair-execution-ready-queue-path",
                            str(dispatch_repair_execution_ready_queue_path),
                            "--dispatch-repair-internal-hold-queue-path",
                            str(dispatch_repair_internal_hold_queue_path),
                            "--dispatch-validation-queue-path",
                            str(dispatch_validation_queue_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_mock.assert_called_once_with(
                output_dir=str(output_dir),
                dispatch_log_repair_queue_path=str(dispatch_log_repair_queue_path),
                dispatch_log_repair_log_path=str(dispatch_log_repair_log_path),
                dispatch_repair_execution_ready_queue_path=str(
                    dispatch_repair_execution_ready_queue_path
                ),
                dispatch_repair_internal_hold_queue_path=str(
                    dispatch_repair_internal_hold_queue_path
                ),
                dispatch_validation_queue_path=str(dispatch_validation_queue_path),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["request_count"], 2)
            self.assertEqual(payload["stats"]["pending_repair_count"], 1)
            self.assertEqual(payload["stats"]["cleared_for_writeback_count"], 1)

    def test_match_node_objects_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records_path = root / "records.jsonl"
            nodes_path = root / "nodes.geojson"
            output_dir = root / "matches"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.match_canonical_records_to_node_objects",
                return_value={"stats": {"matched_records": 7}},
            ) as match_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "match-node-objects",
                            str(records_path),
                            str(nodes_path),
                            "--output-dir",
                            str(output_dir),
                            "--max-distance-m",
                            "25",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            match_mock.assert_called_once_with(
                str(records_path),
                str(nodes_path),
                str(output_dir),
                max_distance_m=25.0,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["matched_records"], 7)

    def test_aggregate_node_objects_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            matched_path = root / "matched.jsonl"
            nodes_path = root / "nodes.geojson"
            output_dir = root / "aggregates"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.aggregate_node_year_metrics",
                return_value={"stats": {"node_year_rows": 10}},
            ) as aggregate_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "aggregate-node-objects",
                            str(matched_path),
                            str(nodes_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            aggregate_mock.assert_called_once_with(
                str(matched_path),
                str(nodes_path),
                str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["node_year_rows"], 10)

    def test_query_published_resource_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "segment_scores.manifest.json"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.query_published_resource",
                return_value={
                    "resource_name": "segment_scores",
                    "view": "public_segments",
                    "stats": {"returned_features": 1},
                },
            ) as query_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "query-published-resource",
                            str(manifest_path),
                            "--view",
                            "public_segments",
                            "--occurred-year",
                            "2021",
                            "--min-score-band",
                            "high",
                            "--limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            query_mock.assert_called_once_with(
                str(manifest_path),
                view="public_segments",
                occurred_year=2021,
                min_score_band="high",
                limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["resource_name"], "segment_scores")
            self.assertEqual(payload["view"], "public_segments")
            self.assertEqual(payload["stats"]["returned_features"], 1)

    def test_resolve_latest_published_resource_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_path = root / "run_registry.jsonl"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.resolve_latest_published_resource",
                return_value={
                    "resource_name": "segment_score_tiles",
                    "resolved": {"resolved_view_path": "data/prediction_store/demo/score_tiles_public.geojson"},
                },
            ) as resolve_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "resolve-latest-published-resource",
                            "segment_score_tiles",
                            "--registry-path",
                            str(registry_path),
                            "--view",
                            "public_tiles",
                            "--prediction-run-label",
                            "demo_run",
                            "--occurred-year",
                            "2021",
                            "--tile-size-m",
                            "500",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            resolve_mock.assert_called_once_with(
                "segment_score_tiles",
                registry_path=str(registry_path),
                view="public_tiles",
                prediction_run_label="demo_run",
                occurred_year=2021,
                tile_size_m=500.0,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["resource_name"], "segment_score_tiles")
            self.assertEqual(
                payload["resolved"]["resolved_view_path"],
                "data/prediction_store/demo/score_tiles_public.geojson",
            )

    def test_build_published_resource_index_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry_path = root / "run_registry.jsonl"
            output_dir = root / "published_index"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_published_resource_index",
                return_value={
                    "published_resource_index_version": "published_resource_index_v1",
                    "stats": {"catalog_record_count": 2},
                },
            ) as build_index_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-published-resource-index",
                            "--registry-path",
                            str(registry_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_index_mock.assert_called_once_with(
                registry_path=str(registry_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["published_resource_index_version"], "published_resource_index_v1")
            self.assertEqual(payload["stats"]["catalog_record_count"], 2)

    def test_build_dashboard_summary_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            published_index_path = root / "published_resources.json"
            metrics_path = root / "frequency_transferability.metrics.json"
            output_dir = root / "dashboard"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_dashboard_summary",
                return_value={
                    "dashboard_summary_version": "dashboard_summary_v1",
                    "stats": {"published_run_count": 4},
                },
            ) as build_summary_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-dashboard-summary",
                            "--published-index-path",
                            str(published_index_path),
                            "--transferability",
                            str(metrics_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_summary_mock.assert_called_once_with(
                published_index_path=str(published_index_path),
                transferability_metrics_paths=[str(metrics_path)],
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["dashboard_summary_version"], "dashboard_summary_v1")
            self.assertEqual(payload["stats"]["published_run_count"], 4)

    def test_build_published_refresh_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            registry_dir = root / "registry"
            published_index_dir = root / "published_index"
            dashboard_dir = root / "dashboard"
            output_dir = root / "refresh"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_published_refresh_bundle",
                return_value={
                    "published_refresh_bundle_version": "published_refresh_bundle_v1",
                    "stats": {"latest_published_resource_count": 2},
                },
            ) as refresh_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-published-refresh-bundle",
                            "--data-root",
                            str(data_root),
                            "--registry-output-dir",
                            str(registry_dir),
                            "--published-index-output-dir",
                            str(published_index_dir),
                            "--dashboard-output-dir",
                            str(dashboard_dir),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            refresh_mock.assert_called_once_with(
                data_root=str(data_root),
                registry_output_dir=str(registry_dir),
                published_index_output_dir=str(published_index_dir),
                dashboard_output_dir=str(dashboard_dir),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["published_refresh_bundle_version"], "published_refresh_bundle_v1")
            self.assertEqual(payload["stats"]["latest_published_resource_count"], 2)

    def test_build_intervention_briefs_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_summary_path = root / "dashboard_summary.json"
            scenario_bundle_root = root / "scenario_countermeasures"
            output_dir = root / "intervention_briefs"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_intervention_briefs",
                return_value={
                    "intervention_brief_bundle_version": "intervention_brief_bundle_v1",
                    "brief_count": 2,
                },
            ) as build_briefs_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-intervention-briefs",
                            "--dashboard-summary-path",
                            str(dashboard_summary_path),
                            "--prediction-run-label",
                            "bari_frequency_baseline_context_v2",
                            "--prediction-run-label",
                            "lecce_municipality_frequency_baseline_context",
                            "--scenario-bundle-root",
                            str(scenario_bundle_root),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            build_briefs_mock.assert_called_once_with(
                dashboard_summary_path=str(dashboard_summary_path),
                prediction_run_labels=[
                    "bari_frequency_baseline_context_v2",
                    "lecce_municipality_frequency_baseline_context",
                ],
                scenario_bundle_root=str(scenario_bundle_root),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["intervention_brief_bundle_version"], "intervention_brief_bundle_v1")
            self.assertEqual(payload["brief_count"], 2)

    def test_build_scenario_countermeasure_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_summary_path = root / "dashboard_summary.json"
            signal_nodes_path = root / "traffic_signal_nodes.geojson"
            node_objects_path = root / "road_node_objects.geojson"
            output_dir = root / "scenario_countermeasures"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_scenario_countermeasure_bundle",
                return_value={
                    "scenario_countermeasure_bundle_version": "scenario_countermeasure_bundle_v1",
                    "scenario_bundle_count": 1,
                },
            ) as scenario_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-scenario-countermeasure-bundle",
                            "--dashboard-summary-path",
                            str(dashboard_summary_path),
                            "--prediction-run-label",
                            "bari_frequency_baseline_context_v2",
                            "--signal-nodes-path",
                            str(signal_nodes_path),
                            "--node-objects-path",
                            str(node_objects_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            scenario_mock.assert_called_once_with(
                dashboard_summary_path=str(dashboard_summary_path),
                prediction_run_labels=["bari_frequency_baseline_context_v2"],
                signal_nodes_path=str(signal_nodes_path),
                node_objects_path=str(node_objects_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["scenario_countermeasure_bundle_version"],
                "scenario_countermeasure_bundle_v1",
            )
            self.assertEqual(payload["scenario_bundle_count"], 1)

    def test_build_vru_intelligence_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_summary_path = root / "dashboard_summary.json"
            movement_objects_path = root / "road_movement_objects.geojson"
            output_dir = root / "vru_intelligence"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_vru_intelligence_bundle",
                return_value={
                    "vru_intelligence_bundle_version": "vru_intelligence_bundle_v1",
                    "bundle_count": 1,
                },
            ) as vru_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-vru-intelligence-bundle",
                            "--dashboard-summary-path",
                            str(dashboard_summary_path),
                            "--prediction-run-label",
                            "bari_frequency_baseline_context_v2",
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            vru_mock.assert_called_once_with(
                dashboard_summary_path=str(dashboard_summary_path),
                prediction_run_labels=["bari_frequency_baseline_context_v2"],
                movement_objects_path=str(movement_objects_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["vru_intelligence_bundle_version"], "vru_intelligence_bundle_v1")
            self.assertEqual(payload["bundle_count"], 1)

    def test_build_vru_exposure_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dashboard_summary_path = root / "dashboard_summary.json"
            movement_objects_path = root / "road_movement_objects.geojson"
            output_dir = root / "vru_exposure"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_vru_exposure_bundle",
                return_value={
                    "vru_exposure_bundle_version": "vru_exposure_bundle_v1",
                    "bundle_count": 1,
                },
            ) as vru_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-vru-exposure-bundle",
                            "--dashboard-summary-path",
                            str(dashboard_summary_path),
                            "--prediction-run-label",
                            "bari_frequency_baseline_context_v2",
                            "--movement-objects-path",
                            str(movement_objects_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            vru_mock.assert_called_once_with(
                dashboard_summary_path=str(dashboard_summary_path),
                prediction_run_labels=["bari_frequency_baseline_context_v2"],
                movement_objects_path=str(movement_objects_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["vru_exposure_bundle_version"], "vru_exposure_bundle_v1")
            self.assertEqual(payload["bundle_count"], 1)

    def test_build_exposure_readiness_report_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_path = root / "segments.geojson"
            output_dir = root / "planning"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_exposure_readiness_report",
                return_value={
                    "exposure_readiness_version": "exposure_readiness_v1",
                    "stats": {"dataset_count": 1},
                },
            ) as readiness_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-exposure-readiness-report",
                            "--dataset",
                            f"bari={dataset_path}",
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            readiness_mock.assert_called_once_with(
                datasets=[("bari", str(dataset_path))],
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["exposure_readiness_version"], "exposure_readiness_v1")
            self.assertEqual(payload["stats"]["dataset_count"], 1)

    def test_build_exposure_source_catalog_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            readiness_report_path = root / "exposure_readiness.json"
            output_dir = root / "exposure_sources"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_exposure_source_catalog",
                return_value={
                    "exposure_source_catalog_version": "exposure_source_catalog_v1",
                    "stats": {"dataset_count": 4},
                },
            ) as catalog_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-exposure-source-catalog",
                            "--readiness-report-path",
                            str(readiness_report_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            catalog_mock.assert_called_once_with(
                readiness_report_path=str(readiness_report_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["exposure_source_catalog_version"], "exposure_source_catalog_v1")
            self.assertEqual(payload["stats"]["dataset_count"], 4)

    def test_build_exposure_onboarding_plan_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_catalog_path = root / "exposure_source_catalog.json"
            output_dir = root / "exposure_onboarding"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_exposure_onboarding_plan",
                return_value={
                    "exposure_onboarding_plan_version": "exposure_onboarding_plan_v1",
                    "stats": {"work_item_count": 12},
                },
            ) as onboarding_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-exposure-onboarding-plan",
                            "--source-catalog-path",
                            str(source_catalog_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            onboarding_mock.assert_called_once_with(
                source_catalog_path=str(source_catalog_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["exposure_onboarding_plan_version"], "exposure_onboarding_plan_v1")
            self.assertEqual(payload["stats"]["work_item_count"], 12)

    def test_build_governance_interoperability_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "governance"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_governance_interoperability_bundle",
                return_value={
                    "governance_interoperability_version": "governance_interoperability_bundle_v1",
                    "stats": {"source_family_count": 9},
                },
            ) as governance_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-governance-interoperability-bundle",
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            governance_mock.assert_called_once_with(output_dir=str(output_dir))
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["governance_interoperability_version"],
                "governance_interoperability_bundle_v1",
            )
            self.assertEqual(payload["stats"]["source_family_count"], 9)

    def test_build_exposure_connector_intake_pack_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_catalog_path = root / "exposure_source_catalog.json"
            onboarding_plan_path = root / "exposure_onboarding_plan.json"
            output_dir = root / "exposure_connector_intake"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_exposure_connector_intake_pack",
                return_value={
                    "exposure_connector_intake_version": "exposure_connector_intake_v1",
                    "stats": {"phase_1_work_item_count": 8},
                },
            ) as intake_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-exposure-connector-intake-pack",
                            "--source-catalog-path",
                            str(source_catalog_path),
                            "--onboarding-plan-path",
                            str(onboarding_plan_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            intake_mock.assert_called_once_with(
                source_catalog_path=str(source_catalog_path),
                onboarding_plan_path=str(onboarding_plan_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["exposure_connector_intake_version"], "exposure_connector_intake_v1")
            self.assertEqual(payload["stats"]["phase_1_work_item_count"], 8)

    def test_ingest_exposure_connector_extract_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "connector.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "processed"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.ingest_exposure_connector_extract",
                return_value={
                    "exposure_connector_observations_version": "exposure_connector_observations_v1",
                    "stats": {"written_rows": 1},
                },
            ) as ingest_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "ingest-exposure-connector-extract",
                            str(input_csv_path),
                            str(mapping_stub_path),
                            "--output-dir",
                            str(output_dir),
                            "--limit",
                            "5",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            ingest_mock.assert_called_once_with(
                str(input_csv_path),
                str(mapping_stub_path),
                str(output_dir),
                limit=5,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["exposure_connector_observations_version"], "exposure_connector_observations_v1")
            self.assertEqual(payload["stats"]["written_rows"], 1)

    def test_normalize_exposure_provider_extract_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "provider.csv"
            output_dir = root / "normalized"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.normalize_exposure_provider_extract",
                return_value={
                    "exposure_provider_normalization_version": "exposure_provider_normalization_v1",
                    "stats": {"written_rows": 2, "rejected_rows": 0},
                },
            ) as normalize_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "normalize-exposure-provider-extract",
                            str(input_csv_path),
                            "--provider-profile-id",
                            "municipal_counter_export",
                            "--output-dir",
                            str(output_dir),
                            "--limit",
                            "10",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            normalize_mock.assert_called_once_with(
                str(input_csv_path),
                provider_profile_id="municipal_counter_export",
                mapping_stub_path=None,
                output_dir=str(output_dir),
                limit=10,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["exposure_provider_normalization_version"],
                "exposure_provider_normalization_v1",
            )
            self.assertEqual(payload["stats"]["written_rows"], 2)

    def test_normalize_exposure_provider_extract_command_with_mapping_stub(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_csv_path = root / "provider.csv"
            mapping_stub_path = root / "mapping_stub.json"
            output_dir = root / "normalized"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.normalize_exposure_provider_extract",
                return_value={
                    "exposure_provider_normalization_version": "exposure_provider_normalization_v1",
                    "provider_profile_id": "fixed_speed_counter_export",
                    "stats": {"written_rows": 1, "rejected_rows": 0},
                },
            ) as normalize_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "normalize-exposure-provider-extract",
                            str(input_csv_path),
                            "--mapping-stub-path",
                            str(mapping_stub_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            normalize_mock.assert_called_once_with(
                str(input_csv_path),
                provider_profile_id=None,
                mapping_stub_path=str(mapping_stub_path),
                output_dir=str(output_dir),
                limit=None,
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload["exposure_provider_normalization_version"],
                "exposure_provider_normalization_v1",
            )
            self.assertEqual(payload["provider_profile_id"], "fixed_speed_counter_export")

    def test_apply_connector_observations_to_segments_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            observation_manifest_path = root / "connector_observations.manifest.json"
            output_dir = root / "joined"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.apply_connector_observations_to_segments",
                return_value={
                    "segment_connector_observations_version": "segment_connector_observations_v1",
                    "stats": {"matched_segment_count": 1},
                },
            ) as join_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "apply-connector-observations-to-segments",
                            str(segments_path),
                            "--observation-manifest-path",
                            str(observation_manifest_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            join_mock.assert_called_once_with(
                str(segments_path),
                [str(observation_manifest_path)],
                str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["segment_connector_observations_version"], "segment_connector_observations_v1")
            self.assertEqual(payload["stats"]["matched_segment_count"], 1)

    def test_run_bari_phase1_exposure_pilot_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "bari_phase1_pilot"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_phase1_exposure_pilot",
                return_value={
                    "exposure_pilot_cycle_version": "exposure_pilot_cycle_v1",
                    "stats": {"joined_matched_segment_count": 1},
                },
            ) as pilot_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-phase1-exposure-pilot",
                            "--motorized-provider-profile-id",
                            "municipal_counter_export",
                            "--speed-provider-profile-id",
                            "fixed_speed_counter_export",
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            pilot_mock.assert_called_once_with(
                segments_path="data/processed/segments/bari_context_v2/road_segments_context.geojson",
                motorized_extract_path=(
                    "data/planning/exposure_connector_intake/sample_templates/"
                    "motorized_exposure_connector_v1__municipal_counter_export.csv"
                ),
                motorized_mapping_stub_path=(
                    "data/planning/exposure_connector_intake/mapping_stubs/"
                    "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
                ),
                speed_extract_path=(
                    "data/planning/exposure_connector_intake/sample_templates/"
                    "observed_speed_connector_v1__fixed_speed_counter_export.csv"
                ),
                speed_mapping_stub_path=(
                    "data/planning/exposure_connector_intake/mapping_stubs/"
                    "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
                ),
                motorized_provider_profile_id="municipal_counter_export",
                speed_provider_profile_id="fixed_speed_counter_export",
                normalize_motorized_provider_extract=False,
                normalize_speed_provider_extract=False,
                mapping_stub_root="data/planning/exposure_connector_intake/mapping_stubs",
                readiness_dataset_label="bari_pilot",
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["exposure_pilot_cycle_version"], "exposure_pilot_cycle_v1")
            self.assertEqual(payload["stats"]["joined_matched_segment_count"], 1)

    def test_run_bari_phase1_exposure_pilot_command_with_mapping_stub_normalization_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "bari_phase1_pilot"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.run_bari_phase1_exposure_pilot",
                return_value={
                    "exposure_pilot_cycle_version": "exposure_pilot_cycle_v1",
                    "stats": {"joined_matched_segment_count": 1},
                },
            ) as pilot_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "run-bari-phase1-exposure-pilot",
                            "--normalize-motorized-provider-extract",
                            "--normalize-speed-provider-extract",
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            pilot_mock.assert_called_once_with(
                segments_path="data/processed/segments/bari_context_v2/road_segments_context.geojson",
                motorized_extract_path=(
                    "data/planning/exposure_connector_intake/sample_templates/"
                    "motorized_exposure_connector_v1__municipal_counter_export.csv"
                ),
                motorized_mapping_stub_path=(
                    "data/planning/exposure_connector_intake/mapping_stubs/"
                    "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
                ),
                speed_extract_path=(
                    "data/planning/exposure_connector_intake/sample_templates/"
                    "observed_speed_connector_v1__fixed_speed_counter_export.csv"
                ),
                speed_mapping_stub_path=(
                    "data/planning/exposure_connector_intake/mapping_stubs/"
                    "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
                ),
                motorized_provider_profile_id=None,
                speed_provider_profile_id=None,
                normalize_motorized_provider_extract=True,
                normalize_speed_provider_extract=True,
                mapping_stub_root="data/planning/exposure_connector_intake/mapping_stubs",
                readiness_dataset_label="bari_pilot",
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["exposure_pilot_cycle_version"], "exposure_pilot_cycle_v1")
            self.assertEqual(payload["stats"]["joined_matched_segment_count"], 1)

    def test_serve_published_api_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            published_index_path = root / "published_resources.json"
            dashboard_dir = root / "dashboard"
            dashboard_summary_path = root / "dashboard_summary.json"

            with patch("road_risk_modeling.cli.serve_published_api") as serve_mock:
                exit_code = main(
                    [
                        "serve-published-api",
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8080",
                        "--published-index-path",
                        str(published_index_path),
                        "--root-dir",
                        str(root),
                        "--dashboard-dir",
                        str(dashboard_dir),
                        "--dashboard-summary-path",
                        str(dashboard_summary_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            serve_mock.assert_called_once_with(
                host="0.0.0.0",
                port=8080,
                published_index_path=str(published_index_path),
                root_dir=root,
                dashboard_dir=dashboard_dir,
                dashboard_summary_path=dashboard_summary_path,
            )

    def test_build_run_registry_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_run_registry",
                return_value={"registry_version": "run_registry_v1", "stats": {"entries": 1}},
            ) as registry_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-run-registry",
                            "--data-root",
                            str(data_root),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            registry_mock.assert_called_once_with(
                data_root=str(data_root),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["registry_version"], "run_registry_v1")
            self.assertEqual(payload["stats"]["entries"], 1)

    def test_extract_segments_from_boundary_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            boundary_path = root / "boundary.geojson"
            boundary_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            output_dir = root / "segments"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.extract_segments_from_boundary",
                return_value={"inputs": {"boundary_path": str(boundary_path)}, "stats": {"segment_count": 1}},
            ) as extract_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "extract-segments-from-boundary",
                            str(boundary_path),
                            "--output-dir",
                            str(output_dir),
                            "--network-type",
                            "drive",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            extract_mock.assert_called_once_with(
                str(boundary_path),
                output_dir=str(output_dir),
                network_type="drive",
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["segment_count"], 1)

    def test_evaluate_transferability_command_passes_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_path = root / "aggregate.csv"
            dataset_path.write_text("segment_id,occurred_year,crash_count\nseg-1,2021,1\n", encoding="utf-8")
            output_dir = root / "models"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.evaluate_frequency_transferability",
                return_value={"requested_modes": ["cross_jurisdiction_temporal"], "cross_jurisdiction_temporal": {}},
            ) as eval_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "evaluate-frequency-transferability",
                            "--dataset",
                            f"bari={dataset_path}",
                            "--dataset",
                            f"foggia={dataset_path}",
                            "--output-dir",
                            str(output_dir),
                            "--mode",
                            "cross_jurisdiction_temporal",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            eval_mock.assert_called_once_with(
                datasets=[("bari", str(dataset_path)), ("foggia", str(dataset_path))],
                output_dir=str(output_dir),
                holdout_year=2021,
                rf_n_estimators=300,
                modes=["cross_jurisdiction_temporal"],
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["requested_modes"], ["cross_jurisdiction_temporal"])

    def test_build_transferability_benchmark_bundle_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metrics_path = root / "frequency_transferability.metrics.json"
            metrics_path.write_text("{}", encoding="utf-8")
            output_dir = root / "reporting"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.build_transferability_benchmark_bundle",
                return_value={
                    "transferability_benchmark_version": "transferability_benchmark_v1",
                    "stats": {"input_run_count": 1},
                },
            ) as benchmark_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "build-transferability-benchmark-bundle",
                            "--transferability",
                            str(metrics_path),
                            "--benchmark-label",
                            "Demo Benchmark",
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            benchmark_mock.assert_called_once_with(
                transferability_metrics_paths=[str(metrics_path)],
                benchmark_label="Demo Benchmark",
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["transferability_benchmark_version"], "transferability_benchmark_v1")

    def test_apply_exposure_policy_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            segments_path = root / "segments.geojson"
            segments_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            output_dir = root / "policy"

            stdout = io.StringIO()
            with patch(
                "road_risk_modeling.cli.apply_exposure_policy_to_segments",
                return_value={"policy": {"exposure_policy_version": "segment_exposure_v2_static_context_built_env"}},
            ) as policy_mock:
                with redirect_stdout(stdout):
                    exit_code = main(
                        [
                            "apply-exposure-policy",
                            str(segments_path),
                            "--output-dir",
                            str(output_dir),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            policy_mock.assert_called_once_with(
                str(segments_path),
                output_dir=str(output_dir),
            )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["policy"]["exposure_policy_version"], "segment_exposure_v2_static_context_built_env")

    def test_profile_jurisdictions_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            zip_path = root / "legacy.zip"
            records_path = root / "canonical.jsonl"
            output_dir = root / "profiles"

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/INCSTRAD_Classificazione_2020_var2.html",
                    "ELENCO MODALITA'<table><tr><td>072</td><td>Bari</td><td></td><td></td></tr></table>",
                )
                archive.writestr(
                    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/INCSTRAD_Classificazione_2020_var3.html",
                    "ELENCO MODALITA'<table><tr><td>006</td><td>Bari</td><td>072</td><td></td></tr></table>",
                )

            records_path.write_text(
                json.dumps(
                    {
                        "crash_id": "x",
                        "province_code": "72",
                        "city_code": "6",
                        "fatalities": 0,
                        "injuries": 1,
                        "severity_level": "injury",
                        "latitude": 41.1,
                        "longitude": 16.8,
                        "occurred_year": 2021,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "profile-jurisdictions",
                        str(records_path),
                        "--zip-path",
                        str(zip_path),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["top_cities"][0]["city_name"], "Bari")
            self.assertTrue((output_dir / "jurisdiction_city_profile.csv").exists())

    def test_ingest_config_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            zip_path = root / "legacy.zip"
            config_path = root / "project.toml"
            output_dir = root / "staging"

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "synthetic_examples/crashes.csv",
                    "ANNO,PROV,COMUNE,LOCINC,NOMESTR,METEO,MORTI,FERITI,NREC,DESCRIZIONE1,CODICE,"
                    "YCOORD_ACI,XCOORD_ACI,ORGRIL,TIPOST,PAVIM,INTNIN,FONDOST,SEGNAL,NATINC,"
                    "TIPOVEIA,TIPOVEIB,TIPOVEIC,KM,METRI,TRONCO,MOR24H,MOR30G\n"
                    "2020,71,2,1,,1,0,1,123,Via Roma,,41.1,16.8,2,2,1,7,1,3,2,1,8.0,,0.0,0.0,12.0,0,0\n",
                )

            config_path.write_text(
                "[project]\n"
                "name = 'pilot'\n"
                "country_code = 'IT'\n"
                "timezone = 'Europe/Rome'\n"
                f"legacy_zip = '{zip_path}'\n\n"
                "[data]\n"
                "crash_csv_member = 'synthetic_examples/crashes.csv'\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "ingest-config",
                        str(config_path),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["project"]["name"], "pilot")
            self.assertEqual(payload["stats"]["total_records"], 1)

    def test_qa_canonical_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records_path = root / "canonical.jsonl"
            report_path = root / "canonical.qa.json"
            records_path.write_text(
                json.dumps(
                    {
                        "crash_id": "x",
                        "source_system": "legacy",
                        "source_record_id": "8",
                        "source_unique_key": "2020:8",
                        "province_code": "71",
                        "city_code": "2",
                        "latitude": 41.1,
                        "longitude": 16.8,
                        "roadway_type": "intersection",
                        "intersection_type": "intersection",
                        "severity_level": "injury",
                        "fatalities": 0,
                        "injuries": 1,
                        "quality_flags": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "qa-canonical",
                        str(records_path),
                        "--output-path",
                        str(report_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["total_records"], 1)
            self.assertTrue(report_path.exists())

    def test_curate_canonical_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records_path = root / "canonical.jsonl"
            curated_path = root / "canonical.curated.jsonl"
            rejected_path = root / "canonical.rejected.jsonl"
            records_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "x",
                                "source_unique_key": "2020:8",
                                "quality_flags": [],
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "y",
                                "source_unique_key": "2020:9",
                                "quality_flags": ["coordinates_outside_expected_jurisdiction_bounds"],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "curate-canonical",
                        str(records_path),
                        "--output-path",
                        str(curated_path),
                        "--rejected-path",
                        str(rejected_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["stats"]["kept_records"], 1)
            self.assertTrue(curated_path.exists())
            self.assertTrue(rejected_path.exists())

    def test_train_severity_baseline_command(self) -> None:
        try:
            import pandas  # noqa: F401
            import sklearn  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("ML stack not installed")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            matched_path = root / "matched.jsonl"
            aggregate_path = root / "aggregate.csv"
            output_dir = root / "models"

            matched_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "a",
                                "segment_id": "seg-1",
                                "occurred_year": 2020,
                                "severity_level": "fatal",
                                "fatalities": 1,
                                "injuries": 0,
                                "match_distance_m": 1.0,
                                "weather_code": "1",
                                "roadway_type": "intersection",
                                "intersection_type": "intersection",
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "b",
                                "segment_id": "seg-2",
                                "occurred_year": 2020,
                                "severity_level": "injury",
                                "fatalities": 0,
                                "injuries": 1,
                                "match_distance_m": 3.0,
                                "weather_code": "2",
                                "roadway_type": "road_segment",
                                "intersection_type": "non_intersection",
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "c",
                                "segment_id": "seg-1",
                                "occurred_year": 2021,
                                "severity_level": "fatal",
                                "fatalities": 1,
                                "injuries": 0,
                                "match_distance_m": 1.2,
                                "weather_code": "1",
                                "roadway_type": "intersection",
                                "intersection_type": "intersection",
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "d",
                                "segment_id": "seg-2",
                                "occurred_year": 2021,
                                "severity_level": "injury",
                                "fatalities": 0,
                                "injuries": 2,
                                "match_distance_m": 2.8,
                                "weather_code": "2",
                                "roadway_type": "road_segment",
                                "intersection_type": "non_intersection",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            aggregate_path.write_text(
                "segment_id,occurred_year,crash_count,fatal_crash_count,injury_crash_count,fatalities_total,injuries_total,mean_match_distance_m,segment_length_m,highway,oneway,ref,bridge,junction,access,tunnel,lanes_numeric,maxspeed_numeric,width_numeric,is_roundabout\n"
                "seg-1,2020,1,1,0,1,0,1.0,90.0,residential,False,,,,,,1,30,5,False\n"
                "seg-1,2021,1,1,0,1,0,1.0,90.0,residential,False,,,,,,1,30,5,False\n"
                "seg-2,2020,1,0,1,0,1,3.0,120.0,primary,True,SS16,,,,,2,70,7,False\n"
                "seg-2,2021,1,0,1,0,2,2.8,120.0,primary,True,SS16,,,,,2,70,7,False\n",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "train-severity-baseline",
                        str(matched_path),
                        str(aggregate_path),
                        "--output-dir",
                        str(output_dir),
                        "--holdout-year",
                        "2021",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["holdout_year"], 2021)
            self.assertIn("random_forest_classifier_metrics", payload)
