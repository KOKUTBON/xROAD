from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.registry import build_run_registry


class RegistryTests(unittest.TestCase):
    def test_build_run_registry_writes_registry_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = data_root / "processed" / "segments" / "demo_context" / "road_segments_context.manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "inputs": {
                            "segments_path": "data/processed/segments/demo/road_segments_enriched.geojson",
                            "boundary_path": "data/processed/segments/demo/boundary.geojson",
                        },
                        "outputs": {
                            "context_path": "data/processed/segments/demo_context/road_segments_context.geojson",
                            "manifest_path": str(manifest_path),
                        },
                        "policy": {
                            "exposure_policy_version": "segment_exposure_v2_static_context_built_env",
                        },
                        "stats": {
                            "segment_count": 3,
                            "segments_with_any_built_environment": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            frequency_metrics_path = data_root / "models" / "demo_frequency" / "frequency_baseline.metrics.json"
            frequency_metrics_path.parent.mkdir(parents=True, exist_ok=True)
            frequency_metrics_path.write_text(
                json.dumps(
                    {
                        "input_path": "data/processed/aggregates/demo/segment_year_metrics.csv",
                        "holdout_year": 2021,
                        "training_config": {
                            "training_config_version": "training_config_v1",
                            "task": "segment_frequency_baseline",
                            "split_strategy": "temporal_holdout_year",
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "aggregate_segment_year_metrics",
                                    "path": "data/processed/aggregates/demo/segment_year_metrics.csv",
                                }
                            ],
                            "publishable_outputs": [
                                {
                                    "role": "holdout_segment_predictions",
                                    "path": "data/models/demo_frequency/holdout_predictions.csv",
                                }
                            ],
                        },
                        "train_rows": 10,
                        "test_rows": 5,
                        "train_crash_total": 12,
                        "test_crash_total": 3,
                        "random_forest_poisson_metrics": {
                            "mean_poisson_deviance": 0.25,
                            "rmse": 0.4,
                            "top_5pct_crash_share": 0.5,
                        },
                        "outputs": {
                            "model_path": "data/models/demo_frequency/frequency_baseline.joblib",
                            "predictions_path": "data/models/demo_frequency/holdout_predictions.csv",
                            "metrics_path": str(frequency_metrics_path),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            transfer_metrics_path = (
                data_root
                / "models"
                / "demo_transferability"
                / "frequency_transferability.metrics.json"
            )
            transfer_metrics_path.parent.mkdir(parents=True, exist_ok=True)
            transfer_metrics_path.write_text(
                json.dumps(
                    {
                        "holdout_year": 2021,
                        "random_forest_n_estimators": 25,
                        "requested_modes": ["cross_jurisdiction_temporal"],
                        "training_config": {
                            "training_config_version": "training_config_v1",
                            "task": "frequency_transferability_evaluation",
                            "split_strategy": "leave_one_jurisdiction_out_temporal_holdout",
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {"role": "aggregate_segment_year_metrics:a", "path": "data/processed/aggregates/a.csv"},
                                {"role": "aggregate_segment_year_metrics:b", "path": "data/processed/aggregates/b.csv"},
                            ],
                            "publishable_outputs": [
                                {
                                    "role": "transferability_predictions",
                                    "path": "data/models/demo_transferability/frequency_transferability_predictions.csv",
                                }
                            ],
                        },
                        "dataset_inputs": [
                            {"label": "a", "path": "data/processed/aggregates/a.csv", "sha256": "x", "rows": 1, "crash_total": 1},
                            {"label": "b", "path": "data/processed/aggregates/b.csv", "sha256": "y", "rows": 1, "crash_total": 1},
                        ],
                        "cross_jurisdiction_temporal": {
                            "a": {
                                "train_jurisdictions": ["b"],
                                "random_forest_poisson_metrics": {
                                    "mean_poisson_deviance": 0.3,
                                    "top_5pct_crash_share": 0.4,
                                },
                            }
                        },
                        "outputs": {
                            "metrics_path": str(transfer_metrics_path),
                            "predictions_path": "data/models/demo_transferability/frequency_transferability_predictions.csv",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            onboarding_manifest_path = (
                data_root
                / "planning"
                / "exposure_onboarding"
                / "exposure_onboarding_plan.manifest.json"
            )
            onboarding_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            onboarding_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "exposure_onboarding_plan",
                            "public_contract_version": "exposure_onboarding_plan_public_v1",
                        },
                        "stats": {
                            "dataset_count": 4,
                            "work_item_count": 12,
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "exposure_source_catalog_json",
                                    "path": "data/planning/exposure_sources/exposure_source_catalog.json",
                                }
                            ],
                            "publishable_outputs": [
                                {
                                    "role": "exposure_onboarding_plan_json",
                                    "path": "data/planning/exposure_onboarding/exposure_onboarding_plan.json",
                                }
                            ],
                        },
                        "outputs": {
                            "plan_json_path": "data/planning/exposure_onboarding/exposure_onboarding_plan.json",
                            "plan_markdown_path": "data/planning/exposure_onboarding/exposure_onboarding_plan.md",
                            "matrix_csv_path": "data/planning/exposure_onboarding/connector_onboarding_matrix.csv",
                            "manifest_path": str(onboarding_manifest_path),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            intake_manifest_path = (
                data_root
                / "planning"
                / "exposure_connector_intake"
                / "connector_intake_pack.manifest.json"
            )
            intake_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            intake_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "exposure_connector_intake_pack",
                            "public_contract_version": "exposure_connector_intake_public_v1",
                        },
                        "stats": {
                            "municipality_count": 4,
                            "phase_1_work_item_count": 8,
                            "template_count": 4,
                            "mapping_stub_count": 16,
                            "rights_matrix_row_count": 16,
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {
                                    "role": "exposure_source_catalog_json",
                                    "path": "data/planning/exposure_sources/exposure_source_catalog.json",
                                },
                                {
                                    "role": "exposure_onboarding_plan_json",
                                    "path": "data/planning/exposure_onboarding/exposure_onboarding_plan.json",
                                },
                            ],
                            "publishable_outputs": [
                                {
                                    "role": "connector_intake_pack_json",
                                    "path": "data/planning/exposure_connector_intake/connector_intake_pack.json",
                                }
                            ],
                        },
                        "outputs": {
                            "pack_json_path": "data/planning/exposure_connector_intake/connector_intake_pack.json",
                            "pack_markdown_path": "data/planning/exposure_connector_intake/connector_intake_pack.md",
                            "rights_matrix_path": "data/planning/exposure_connector_intake/source_rights_matrix.csv",
                            "manifest_path": str(intake_manifest_path),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            connector_observations_manifest_path = (
                data_root
                / "processed"
                / "exposure_connector_observations"
                / "demo_motorized"
                / "connector_observations.manifest.json"
            )
            connector_observations_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            connector_observations_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "exposure_connector_observations",
                            "public_contract_version": "exposure_connector_observations_public_v1",
                        },
                        "connector": {
                            "municipality_label": "bari",
                            "work_item_id": "bari_01_motorized_exposure_municipal",
                            "capability_code": "motorized_exposure",
                            "provider_profile_id": "municipal_counter_export",
                        },
                        "stats": {
                            "total_rows": 1,
                            "written_rows": 1,
                            "rejected_rows": 0,
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {"role": "connector_input_csv", "path": "data/planning/exposure_connector_intake/sample_templates/demo.csv"},
                                {"role": "connector_mapping_stub_json", "path": "data/planning/exposure_connector_intake/mapping_stubs/demo.json"},
                            ],
                            "publishable_outputs": [
                                {"role": "connector_observations_jsonl", "path": "data/processed/exposure_connector_observations/demo_motorized/connector_observations.jsonl"},
                            ],
                        },
                        "outputs": {
                            "observations_path": "data/processed/exposure_connector_observations/demo_motorized/connector_observations.jsonl",
                            "rejected_rows_path": "data/processed/exposure_connector_observations/demo_motorized/connector_rejected_rows.jsonl",
                            "manifest_path": str(connector_observations_manifest_path),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            segment_connector_manifest_path = (
                data_root
                / "processed"
                / "segments"
                / "demo_connector_join"
                / "road_segments_connector_observations.manifest.json"
            )
            segment_connector_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            segment_connector_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_connector_observations",
                            "public_contract_version": "segment_connector_observations_public_v1",
                        },
                        "stats": {
                            "segment_count": 2,
                            "matched_observations": 2,
                            "matched_segment_count": 1,
                        },
                        "lineage": {
                            "lineage_contract_version": "artifact_lineage_v1",
                            "upstream_inputs": [
                                {"role": "segments_geojson", "path": "data/processed/segments/demo/road_segments_context.geojson"},
                                {"role": "connector_observations_manifest", "path": "data/processed/exposure_connector_observations/demo_motorized/connector_observations.manifest.json"},
                            ],
                            "publishable_outputs": [
                                {"role": "segment_connector_observations_geojson", "path": "data/processed/segments/demo_connector_join/road_segments_connector_observations.geojson"},
                            ],
                        },
                        "outputs": {
                            "connector_segments_path": "data/processed/segments/demo_connector_join/road_segments_connector_observations.geojson",
                            "manifest_path": str(segment_connector_manifest_path),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["registry_version"], "run_registry_v1")
            self.assertEqual(manifest["stats"]["entries"], 7)
            self.assertEqual(manifest["stats"]["stage_counts"]["enrichment"], 2)
            self.assertEqual(manifest["stats"]["stage_counts"]["evaluation"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["ingestion"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["modeling"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 2)
            self.assertEqual(manifest["inputs"]["excluded_output_dir"], str(output_dir))

            jsonl_path = output_dir / "run_registry.jsonl"
            csv_path = output_dir / "run_registry.csv"
            self.assertTrue(jsonl_path.exists())
            self.assertTrue(csv_path.exists())

            entries = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(entries), 7)

            frequency_entry = next(entry for entry in entries if entry["artifact_kind"] == "frequency_model")
            self.assertEqual(frequency_entry["stage"], "modeling")
            self.assertEqual(frequency_entry["summary"]["holdout_year"], 2021)
            self.assertEqual(
                frequency_entry["summary"]["random_forest_poisson_metrics"]["mean_poisson_deviance"],
                0.25,
            )
            self.assertEqual(
                frequency_entry["input_references"][0]["path"],
                "data/processed/aggregates/demo/segment_year_metrics.csv",
            )
            self.assertEqual(frequency_entry["summary"]["training_task"], "segment_frequency_baseline")
            self.assertEqual(frequency_entry["summary"]["lineage_contract_version"], "artifact_lineage_v1")

            transfer_entry = next(entry for entry in entries if entry["artifact_kind"] == "transferability")
            self.assertEqual(transfer_entry["stage"], "evaluation")
            self.assertEqual(transfer_entry["summary"]["random_forest_n_estimators"], 25)
            self.assertEqual(transfer_entry["summary"]["dataset_labels"], ["a", "b"])
            self.assertEqual(transfer_entry["summary"]["training_task"], "frequency_transferability_evaluation")
            self.assertEqual(transfer_entry["summary"]["upstream_input_count"], 2)

            onboarding_entry = next(entry for entry in entries if entry["artifact_kind"] == "exposure_onboarding_plan")
            self.assertEqual(onboarding_entry["stage"], "reporting")
            self.assertEqual(onboarding_entry["summary"]["resource_name"], "exposure_onboarding_plan")
            self.assertEqual(onboarding_entry["summary"]["upstream_input_count"], 1)

            intake_entry = next(entry for entry in entries if entry["artifact_kind"] == "exposure_connector_intake_pack")
            self.assertEqual(intake_entry["stage"], "reporting")
            self.assertEqual(intake_entry["summary"]["resource_name"], "exposure_connector_intake_pack")
            self.assertEqual(intake_entry["summary"]["upstream_input_count"], 2)

            connector_observations_entry = next(entry for entry in entries if entry["artifact_kind"] == "exposure_connector_observations")
            self.assertEqual(connector_observations_entry["stage"], "ingestion")
            self.assertEqual(connector_observations_entry["summary"]["resource_name"], "exposure_connector_observations")
            self.assertEqual(connector_observations_entry["summary"]["upstream_input_count"], 2)

            segment_connector_entry = next(entry for entry in entries if entry["artifact_kind"] == "segment_connector_observations")
            self.assertEqual(segment_connector_entry["stage"], "enrichment")
            self.assertEqual(segment_connector_entry["summary"]["resource_name"], "segment_connector_observations")
            self.assertEqual(segment_connector_entry["summary"]["upstream_input_count"], 2)

            with csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 7)
            self.assertIn("frequency_deviance", rows[0])
            self.assertIn("training_task", rows[0])
            self.assertIn("lineage_contract_version", rows[0])

    def test_build_run_registry_classifies_conflict_zone_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "conflict_zones"
                / "demo"
                / "road_conflict_zones.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_conflict_zone_builder",
                        },
                        "inputs": {
                            "node_objects_path": "data/processed/node_objects/demo/road_node_objects.geojson",
                            "segments_path": "data/processed/segments/demo/road_segments.geojson",
                        },
                        "outputs": {
                            "geojson_path": "data/processed/conflict_zones/demo/road_conflict_zones.geojson",
                            "manifest_path": str(manifest_path),
                        },
                        "stats": {
                            "total_conflict_zone_count": 7,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["object_modeling"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["conflict_zone_layer"], 1)

    def test_build_run_registry_classifies_movement_object_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "movement_objects"
                / "demo"
                / "road_movement_objects.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_movement_object_builder",
                        },
                        "inputs": {
                            "conflict_zones_path": "data/processed/conflict_zones/demo/road_conflict_zones.geojson",
                            "segments_path": "data/processed/segments/demo/road_segments.geojson",
                        },
                        "outputs": {
                            "geojson_path": "data/processed/movement_objects/demo/road_movement_objects.geojson",
                            "manifest_path": str(manifest_path),
                        },
                        "stats": {
                            "movement_object_count": 21,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["object_modeling"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["movement_object_layer"], 1)

    def test_build_run_registry_classifies_movement_review_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "movement_review"
                / "bari"
                / "movement_review_pack.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_movement_review_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/movement_review/bari/movement_review_pack.json",
                            "report_md_path": "data/reporting/movement_review/bari/movement_review_pack.md",
                            "phase_readiness_path": "data/reporting/movement_review/bari/signal_phase_readiness.csv",
                        },
                        "stats": {
                            "movement_object_count": 40,
                            "unresolved_movement_count": 10,
                            "heuristic_resolved_movement_count": 2,
                            "signal_phase_review_row_count": 5,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["movement_review_pack"], 1)

    def test_build_run_registry_classifies_signal_phase_intake_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_intake"
                / "bari"
                / "signal_phase_intake_pack.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_intake_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/planning/signal_phase_intake/bari/signal_phase_intake_pack.json",
                            "report_md_path": "data/planning/signal_phase_intake/bari/signal_phase_intake_pack.md",
                            "priority_signals_csv_path": "data/planning/signal_phase_intake/bari/priority_signals.csv",
                        },
                        "stats": {
                            "signal_phase_review_row_count": 426,
                            "priority_signal_export_count": 20,
                            "provider_profile_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_intake_pack"], 1)

    def test_build_run_registry_classifies_signal_phase_support_resolution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_resolution"
                / "bari"
                / "signal_phase_support_resolution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_resolution_bundle_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.json",
                            "report_md_path": "data/reporting/signal_phase_support_resolution/bari/signal_phase_support_resolution_bundle.md",
                            "support_resolution_queue_path": "data/reporting/signal_phase_support_resolution/bari/support_resolution_queue.csv",
                        },
                        "stats": {
                            "support_request_count": 1,
                            "manual_arm_phase_review_row_count": 18,
                            "pedestrian_stage_review_row_count": 8,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_support_resolution_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_support_writeback_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_writeback"
                / "bari"
                / "signal_phase_support_writeback_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_writeback_bundle_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.json",
                            "report_md_path": "data/reporting/signal_phase_support_writeback/bari/signal_phase_support_writeback_bundle.md",
                            "manual_workbook_path": "data/reporting/signal_phase_support_writeback/bari/workbooks/arm_phase_mapping_sheet_workbook.csv",
                            "pedestrian_workbook_path": "data/reporting/signal_phase_support_writeback/bari/workbooks/pedestrian_stage_mapping_sheet_workbook.csv",
                        },
                        "stats": {
                            "support_request_count": 1,
                            "manual_workbook_row_count": 18,
                            "pedestrian_workbook_row_count": 8,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_support_writeback_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_support_status_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_status"
                / "bari"
                / "signal_phase_support_status_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_status_bundle_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.json",
                            "report_md_path": "data/reporting/signal_phase_support_status/bari/signal_phase_support_status_bundle.md",
                            "request_support_status_path": "data/reporting/signal_phase_support_status/bari/request_support_status.csv",
                        },
                        "stats": {
                            "support_request_count": 1,
                            "validation_ready_profile_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_support_status_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_support_action_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_action_queue"
                / "bari"
                / "signal_phase_support_action_queue.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_action_queue_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_support_action_queue/bari/signal_phase_support_action_queue.json",
                            "report_md_path": "data/reporting/signal_phase_support_action_queue/bari/signal_phase_support_action_queue.md",
                            "action_execution_ready_queue_path": "data/reporting/signal_phase_support_action_queue/bari/action_execution_ready_queue.csv",
                        },
                        "stats": {
                            "profile_count": 2,
                            "execution_ready_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_support_action_queue"], 1)

    def test_build_run_registry_classifies_signal_phase_support_apply_status_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_apply_status"
                / "bari"
                / "signal_phase_support_apply_status_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_apply_status_bundle_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_support_apply_status/bari/signal_phase_support_apply_status_bundle.json",
                            "report_md_path": "data/reporting/signal_phase_support_apply_status/bari/signal_phase_support_apply_status_bundle.md",
                            "support_apply_status_path": "data/reporting/signal_phase_support_apply_status/bari/support_apply_status.csv",
                        },
                        "stats": {
                            "profile_count": 2,
                            "applied_profile_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_apply_status_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_request_state_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_request_state"
                / "bari"
                / "signal_phase_support_request_state_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_request_state_bundle_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_support_request_state/bari/signal_phase_support_request_state_bundle.json",
                            "report_md_path": "data/reporting/signal_phase_support_request_state/bari/signal_phase_support_request_state_bundle.md",
                            "request_support_runtime_state_path": "data/reporting/signal_phase_support_request_state/bari/request_support_runtime_state.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "partially_applied_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_request_state_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_operator_board_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_operator_board"
                / "bari"
                / "signal_phase_support_operator_board_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_support_operator_board_bundle",
                            "public_contract_version": "signal_phase_support_operator_board_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_support_operator_board_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "operator_ready_queue_path": "data/reporting/signal_phase_support_operator_board/bari/operator_ready_queue.csv",
                            "operator_hold_queue_path": "data/reporting/signal_phase_support_operator_board/bari/operator_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "operator_ready_count": 1,
                            "internal_hold_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_operator_board_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_action_execution_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_action_execution"
                / "bari"
                / "signal_phase_support_action_execution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_support_action_execution_bundle",
                            "public_contract_version": "signal_phase_support_action_execution_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_support_action_execution_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "execution_ready_queue_path": "data/reporting/signal_phase_support_action_execution/bari/action_execution_ready_queue.csv",
                            "internal_hold_queue_path": "data/reporting/signal_phase_support_action_execution/bari/action_internal_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "execution_ready_count": 1,
                            "internal_hold_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_action_execution_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_action_handoff_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_action_handoff"
                / "bari"
                / "signal_phase_support_action_handoff_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_support_action_handoff_bundle",
                            "public_contract_version": "signal_phase_support_action_handoff_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_support_action_handoff_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "action_handoff_queue_path": "data/reporting/signal_phase_support_action_handoff/bari/action_handoff_queue.csv",
                            "action_handoff_hold_queue_path": "data/reporting/signal_phase_support_action_handoff/bari/action_handoff_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "handoff_ready_count": 1,
                            "internal_hold_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_action_handoff_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_runtime_board_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_runtime_board"
                / "bari"
                / "signal_phase_support_runtime_board_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_support_runtime_board_bundle",
                            "public_contract_version": "signal_phase_support_runtime_board_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_support_runtime_board_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "operator_ready_queue_path": "data/reporting/signal_phase_support_runtime_board/bari/operator_ready_queue.csv",
                            "operator_hold_queue_path": "data/reporting/signal_phase_support_runtime_board/bari/operator_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "operator_ready_count": 1,
                            "internal_hold_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_runtime_board_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_runtime_action_queue(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_runtime_action_queue"
                / "bari"
                / "signal_phase_support_runtime_action_queue.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_support_runtime_action_queue",
                            "public_contract_version": "signal_phase_support_runtime_action_queue_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_support_runtime_action_queue_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "action_queue_path": "data/reporting/signal_phase_support_runtime_action_queue/bari/action_queue.csv",
                            "action_hold_queue_path": "data/reporting/signal_phase_support_runtime_action_queue/bari/action_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "immediate_action_count": 1,
                            "internal_hold_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_runtime_action_queue"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_runtime_action_execution_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_runtime_action_execution"
                / "bari"
                / "signal_phase_support_runtime_action_execution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_support_runtime_action_execution_bundle",
                            "public_contract_version": "signal_phase_support_runtime_action_execution_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_support_runtime_action_execution_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "execution_ready_queue_path": "data/reporting/signal_phase_support_runtime_action_execution/bari/action_execution_ready_queue.csv",
                            "internal_hold_queue_path": "data/reporting/signal_phase_support_runtime_action_execution/bari/action_internal_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "execution_ready_count": 1,
                            "internal_hold_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_runtime_action_execution_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_workbook_completion_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_workbook_completion"
                / "bari"
                / "signal_phase_support_workbook_completion_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_support_workbook_completion_bundle",
                            "public_contract_version": "signal_phase_support_workbook_completion_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_support_workbook_completion_builder",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "workbook_completion_queue_path": "data/reporting/signal_phase_support_workbook_completion/bari/workbook_completion_queue.csv",
                            "non_workbook_execution_queue_path": "data/reporting/signal_phase_support_workbook_completion/bari/non_workbook_execution_queue.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "workbook_fill_request_count": 1,
                            "completion_row_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_workbook_completion_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_validation_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "quality"
                / "signal_phase_support_validation_batches"
                / "bari"
                / "signal_phase_support_validation_batch.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_validation_batch_runner",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "batch_json_path": "data/quality/signal_phase_support_validation_batches/bari/signal_phase_support_validation_batch.json",
                            "batch_md_path": "data/quality/signal_phase_support_validation_batches/bari/signal_phase_support_validation_batch.md",
                            "result_rows_path": "data/quality/signal_phase_support_validation_batches/bari/support_validation_batch_results.csv",
                        },
                        "stats": {
                            "action_queue_count": 2,
                            "executed_validation_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["quality"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_support_validation_batch"], 1)

    def test_build_run_registry_classifies_signal_phase_support_apply_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_support_apply_cycles"
                / "bari"
                / "signal_phase_support_apply_cycle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_apply_cycle_runner",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "cycle_json_path": "data/processed/signal_phase_support_apply_cycles/bari/signal_phase_support_apply_cycle.json",
                            "cycle_md_path": "data/processed/signal_phase_support_apply_cycles/bari/signal_phase_support_apply_cycle.md",
                            "support_validation_batch_manifest_path": "data/quality/signal_phase_support_validation_batches/bari/signal_phase_support_validation_batch.manifest.json",
                        },
                        "stats": {
                            "action_queue_count": 2,
                            "accepted_for_ingestion_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["quality"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_support_apply_cycle"], 1)

    def test_build_run_registry_classifies_signal_phase_support_rehearsal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_support_rehearsal"
                / "bari"
                / "signal_phase_support_rehearsal.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_rehearsal_runner",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "rehearsal_json_path": "data/reporting/signal_phase_support_rehearsal/bari/signal_phase_support_rehearsal.json",
                            "rehearsal_md_path": "data/reporting/signal_phase_support_rehearsal/bari/signal_phase_support_rehearsal.md",
                            "request_state_comparison_path": "data/reporting/signal_phase_support_rehearsal/bari/request_state_comparison.csv",
                            "profile_state_comparison_path": "data/reporting/signal_phase_support_rehearsal/bari/profile_state_comparison.csv",
                        },
                        "stats": {
                            "request_count": 1,
                            "changed_request_count": 1,
                            "post_accepted_for_ingestion_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_rehearsal"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_support_runtime_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_support_runtime_cycles"
                / "bari"
                / "signal_phase_support_runtime_cycle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {
                            "adapter": "bari_signal_phase_support_runtime_cycle_runner",
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "cycle_json_path": "data/processed/signal_phase_support_runtime_cycles/bari/signal_phase_support_runtime_cycle.json",
                            "cycle_md_path": "data/processed/signal_phase_support_runtime_cycles/bari/signal_phase_support_runtime_cycle.md",
                            "support_writeback_manifest_path": "data/processed/signal_phase_support_runtime_cycles/bari/support_writeback/signal_phase_support_writeback_bundle.manifest.json",
                            "support_status_manifest_path": "data/processed/signal_phase_support_runtime_cycles/bari/support_status/signal_phase_support_status_bundle.manifest.json",
                            "support_action_queue_manifest_path": "data/processed/signal_phase_support_runtime_cycles/bari/support_action_queue/signal_phase_support_action_queue.manifest.json",
                            "support_runtime_board_manifest_path": "data/processed/signal_phase_support_runtime_cycles/bari/support_runtime_board/signal_phase_support_runtime_board_bundle.manifest.json",
                            "support_runtime_action_queue_manifest_path": "data/processed/signal_phase_support_runtime_cycles/bari/support_runtime_action_queue/signal_phase_support_runtime_action_queue.manifest.json",
                            "support_apply_cycle_manifest_path": "data/processed/signal_phase_support_runtime_cycles/bari/support_apply_cycle/signal_phase_support_apply_cycle.manifest.json",
                        },
                        "stats": {
                            "support_request_count": 1,
                            "accepted_for_ingestion_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_support_runtime_cycle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = data_root / "processed" / "signal_phase_records" / "demo" / "signal_phase_records.manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "profile": {"profile_id": "controller_event_log_export", "profile_type": "provider_feed"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "records_path": "data/processed/signal_phase_records/demo/signal_phase_records.jsonl",
                        },
                        "stats": {"written_rows": 2},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["ingestion"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_records"], 1)

    def test_build_run_registry_classifies_signal_phase_request_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_requests"
                / "bari"
                / "signal_phase_request_pack.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {"adapter": "bari_signal_phase_request_pack_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/planning/signal_phase_requests/bari/signal_phase_request_pack.json",
                        },
                        "stats": {
                            "public_dataset_count": 3,
                            "public_signal_phase_dataset_count": 0,
                            "request_row_count": 20,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_request_pack"], 1)

    def test_build_run_registry_classifies_signal_phase_acquisition_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_acquisition"
                / "bari"
                / "signal_phase_acquisition_plan.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {"adapter": "bari_signal_phase_acquisition_plan_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "plan_json_path": "data/planning/signal_phase_acquisition/bari/signal_phase_acquisition_plan.json",
                        },
                        "stats": {
                            "request_row_count": 20,
                            "tier_1_signal_count": 6,
                            "delivery_item_count": 44,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_acquisition_plan"], 1)

    def test_build_run_registry_classifies_signal_phase_outreach_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_outreach"
                / "bari"
                / "signal_phase_outreach_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {"adapter": "bari_signal_phase_outreach_bundle_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/planning/signal_phase_outreach/bari/signal_phase_outreach_bundle.json",
                        },
                        "stats": {
                            "target_request_count": 6,
                            "target_delivery_item_count": 18,
                            "request_packet_count": 6,
                            "profile_packet_count": 3,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_outreach_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_delivery_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "quality"
                / "signal_phase_delivery_validation"
                / "bari_controller_event_sample"
                / "signal_phase_delivery_validation.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {"adapter": "signal_phase_delivery_validator"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/quality/signal_phase_delivery_validation/bari_controller_event_sample/signal_phase_delivery_validation.json",
                        },
                        "stats": {
                            "validation_outcome": "accepted_for_ingestion",
                            "accepted_rows": 1,
                            "rejected_rows": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["quality"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_delivery_validation"], 1)

    def test_build_run_registry_classifies_signal_phase_delivery_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_delivery_sessions"
                / "bari_sample"
                / "signal_phase_delivery_session.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": {"adapter": "validated_signal_phase_delivery_session_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "session_json_path": "data/processed/signal_phase_delivery_sessions/bari_sample/signal_phase_delivery_session.json",
                        },
                        "stats": {
                            "accepted_validation_count": 3,
                            "ingested_manifest_count": 3,
                            "movement_count": 40718,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["enrichment"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_delivery_session"], 1)

    def test_build_run_registry_classifies_signal_phase_coverage_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_coverage"
                / "bari_sample"
                / "signal_phase_coverage.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_coverage_report",
                            "public_contract_version": "signal_phase_coverage_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_coverage_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_coverage/bari_sample/signal_phase_coverage.json",
                            "coverage_by_role_path": "data/reporting/signal_phase_coverage/bari_sample/coverage_by_role.csv",
                        },
                        "stats": {
                            "movement_count": 40718,
                            "signalized_movement_count": 6815,
                            "matched_crash_count": 7020,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_coverage_report"], 1)

    def test_build_run_registry_classifies_signal_phase_target_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_targets"
                / "bari"
                / "signal_phase_target_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_target_bundle",
                            "public_contract_version": "signal_phase_target_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_target_bundle_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/reporting/signal_phase_targets/bari/signal_phase_target_bundle.json",
                            "target_priority_matrix_path": "data/reporting/signal_phase_targets/bari/target_priority_matrix.csv",
                        },
                        "stats": {
                            "target_count": 6,
                            "packet_count": 6,
                            "targets_with_provider_data": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_target_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_request_scope_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_request_scope"
                / "bari"
                / "signal_phase_request_scope_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_request_scope_bundle",
                            "public_contract_version": "signal_phase_request_scope_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_request_scope_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/reporting/signal_phase_request_scope/bari/signal_phase_request_scope_bundle.json",
                            "target_collection_windows_path": "data/reporting/signal_phase_request_scope/bari/target_collection_windows.csv",
                        },
                        "stats": {
                            "target_count": 6,
                            "delivery_scope_count": 18,
                            "controller_event_scope_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_request_scope_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_contact_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_contact"
                / "bari"
                / "signal_phase_contact_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_contact_bundle",
                            "public_contract_version": "signal_phase_contact_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_contact_bundle_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/planning/signal_phase_contact/bari/signal_phase_contact_bundle.json",
                            "contact_send_queue_path": "data/planning/signal_phase_contact/bari/contact_send_queue.csv",
                        },
                        "stats": {
                            "target_count": 6,
                            "draft_count": 6,
                            "ready_to_send_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_contact_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_contact_resolution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_contact_resolution"
                / "bari"
                / "signal_phase_contact_resolution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_contact_resolution_bundle",
                            "public_contract_version": "signal_phase_contact_resolution_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_contact_resolution_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/planning/signal_phase_contact_resolution/bari/signal_phase_contact_resolution_bundle.json",
                            "contact_resolution_queue_path": "data/planning/signal_phase_contact_resolution/bari/contact_resolution_queue.csv",
                        },
                        "stats": {
                            "target_count": 6,
                            "direct_contact_count": 0,
                            "routable_via_official_channels_count": 6,
                            "official_channel_count": 5,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_contact_resolution_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_dispatch"
                / "bari"
                / "signal_phase_dispatch_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_bundle",
                            "public_contract_version": "signal_phase_dispatch_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_dispatch_bundle_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
                            "dispatch_queue_path": "data/planning/signal_phase_dispatch/bari/dispatch_execution_queue.csv",
                        },
                        "stats": {
                            "target_count": 6,
                            "dispatch_queue_count": 6,
                            "follow_up_item_count": 12,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_dispatch_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_delivery_intake_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "planning"
                / "signal_phase_delivery_intake"
                / "bari"
                / "signal_phase_delivery_intake_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_delivery_intake_bundle",
                            "public_contract_version": "signal_phase_delivery_intake_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_delivery_intake_bundle_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/planning/signal_phase_delivery_intake/bari/signal_phase_delivery_intake_bundle.json",
                            "receipt_register_path": "data/planning/signal_phase_delivery_intake/bari/delivery_receipt_register.csv",
                        },
                        "stats": {
                            "dispatch_request_count": 6,
                            "expected_delivery_count": 18,
                            "packet_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_delivery_intake_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_delivery_monitor_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_delivery_monitor"
                / "bari"
                / "signal_phase_delivery_monitor_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_delivery_monitor_bundle",
                            "public_contract_version": "signal_phase_delivery_monitor_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_delivery_monitor_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "bundle_json_path": "data/reporting/signal_phase_delivery_monitor/bari/signal_phase_delivery_monitor_bundle.json",
                            "validation_ready_queue_path": "data/reporting/signal_phase_delivery_monitor/bari/validation_ready_queue.csv",
                        },
                        "stats": {
                            "monitored_delivery_count": 18,
                            "detected_file_count": 0,
                            "validation_ready_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_delivery_monitor_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_validation_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "quality"
                / "signal_phase_validation_batches"
                / "bari"
                / "signal_phase_validation_batch.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_validation_batch",
                            "public_contract_version": "signal_phase_validation_batch_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_validation_batch_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "batch_json_path": "data/quality/signal_phase_validation_batches/bari/signal_phase_validation_batch.json",
                            "result_rows_path": "data/quality/signal_phase_validation_batches/bari/validation_batch_results.csv",
                        },
                        "stats": {
                            "ready_queue_count": 0,
                            "executed_validation_count": 0,
                            "accepted_for_ingestion_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["quality"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_validation_batch"], 1)

    def test_build_run_registry_classifies_signal_phase_receive_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_receive_cycles"
                / "bari"
                / "signal_phase_receive_cycle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_receive_cycle",
                            "public_contract_version": "signal_phase_receive_cycle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_receive_cycle_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "cycle_json_path": "data/processed/signal_phase_receive_cycles/bari/signal_phase_receive_cycle.json",
                            "monitor_manifest_path": "data/processed/signal_phase_receive_cycles/bari/monitor/signal_phase_delivery_monitor_bundle.manifest.json",
                            "validation_batch_manifest_path": "data/processed/signal_phase_receive_cycles/bari/validation_batch/signal_phase_validation_batch.manifest.json",
                        },
                        "stats": {
                            "monitored_delivery_count": 18,
                            "validation_ready_count": 0,
                            "executed_validation_count": 0,
                            "delivery_session_executed": False,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["quality"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_receive_cycle"], 1)

    def test_build_run_registry_classifies_signal_phase_lifecycle_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_lifecycle"
                / "bari"
                / "signal_phase_lifecycle_report.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_lifecycle_report",
                            "public_contract_version": "signal_phase_lifecycle_report_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_lifecycle_report_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "report_json_path": "data/reporting/signal_phase_lifecycle/bari/signal_phase_lifecycle_report.json",
                            "lifecycle_items_path": "data/reporting/signal_phase_lifecycle/bari/lifecycle_items.csv",
                        },
                        "stats": {
                            "delivery_item_count": 18,
                            "awaiting_delivery_count": 18,
                            "applied_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_lifecycle_report"], 1)

    def test_build_run_registry_classifies_signal_phase_status_sync_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_status_sync"
                / "bari"
                / "signal_phase_status_sync_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_status_sync_bundle",
                            "public_contract_version": "signal_phase_status_sync_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_status_sync_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "synced_receipt_path": "data/reporting/signal_phase_status_sync/bari/delivery_receipt_register_synced.csv",
                            "synced_checklist_path": "data/reporting/signal_phase_status_sync/bari/delivery_checklist_synced.csv",
                        },
                        "stats": {
                            "receipt_row_count": 18,
                            "validated_count": 0,
                            "mapped_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_status_sync_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_follow_up_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_follow_up"
                / "bari"
                / "signal_phase_follow_up_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_follow_up_bundle",
                            "public_contract_version": "signal_phase_follow_up_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_follow_up_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "follow_up_ready_queue_path": "data/reporting/signal_phase_follow_up/bari/follow_up_ready_queue.csv",
                        },
                        "stats": {
                            "request_count": 6,
                            "due_now_count": 0,
                            "open_delivery_item_count": 18,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["signal_phase_follow_up_bundle"], 1)

    def test_build_run_registry_classifies_signal_phase_follow_up_execution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_follow_up_execution"
                / "bari"
                / "signal_phase_follow_up_execution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_follow_up_execution_bundle",
                            "public_contract_version": "signal_phase_follow_up_execution_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_follow_up_execution_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "follow_up_execution_queue_path": "data/reporting/signal_phase_follow_up_execution/bari/follow_up_execution_queue.csv",
                        },
                        "stats": {
                            "execution_ready_count": 6,
                            "internal_hold_count": 0,
                            "tracker_update_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_follow_up_execution_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_follow_up_writeback_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_follow_up_writeback"
                / "bari"
                / "signal_phase_follow_up_writeback_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_follow_up_writeback_bundle",
                            "public_contract_version": "signal_phase_follow_up_writeback_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_follow_up_writeback_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "writeback_ready_queue_path": "data/reporting/signal_phase_follow_up_writeback/bari/writeback_ready_queue.csv",
                        },
                        "stats": {
                            "writeback_ready_count": 1,
                            "dispatch_rows_updated_count": 1,
                            "tracker_rows_completed_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_follow_up_writeback_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_follow_up_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_follow_up_cycles"
                / "bari"
                / "signal_phase_follow_up_cycle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_follow_up_cycle",
                            "public_contract_version": "signal_phase_follow_up_cycle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_follow_up_cycle_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "runtime_follow_up_execution_manifest_path": "data/processed/signal_phase_follow_up_cycles/bari/runtime_follow_up_execution/signal_phase_follow_up_execution_bundle.manifest.json",
                        },
                        "stats": {
                            "writeback_ready_count": 1,
                            "runtime_follow_up_request_count": 1,
                            "runtime_execution_ready_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_follow_up_cycle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_operations_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_operations_cycles"
                / "bari"
                / "signal_phase_operations_cycle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_operations_cycle",
                            "public_contract_version": "signal_phase_operations_cycle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_operations_cycle_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "follow_up_cycle_manifest_path": "data/processed/signal_phase_operations_cycles/bari/follow_up_cycle/signal_phase_follow_up_cycle.manifest.json",
                        },
                        "stats": {
                            "receive_monitored_delivery_count": 18,
                            "follow_up_execution_ready_count": 6,
                            "runtime_execution_ready_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_operations_cycle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_action_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_action_queue"
                / "bari"
                / "signal_phase_action_queue.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_action_queue",
                            "public_contract_version": "signal_phase_action_queue_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_action_queue_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "action_queue_path": "data/reporting/signal_phase_action_queue/bari/action_queue.csv",
                        },
                        "stats": {
                            "request_count": 6,
                            "dispatch_action_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_action_queue"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_execution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_dispatch_execution"
                / "bari"
                / "signal_phase_dispatch_execution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_execution_bundle",
                            "public_contract_version": "signal_phase_dispatch_execution_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_dispatch_execution_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "dispatch_execution_ready_queue_path": "data/reporting/signal_phase_dispatch_execution/bari/dispatch_execution_ready_queue.csv",
                        },
                        "stats": {
                            "request_count": 6,
                            "execution_ready_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_dispatch_execution_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_action_execution_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_action_execution"
                / "bari"
                / "signal_phase_action_execution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_action_execution_bundle",
                            "public_contract_version": "signal_phase_action_execution_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_action_execution_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "action_execution_ready_queue_path": "data/reporting/signal_phase_action_execution/bari/action_execution_ready_queue.csv",
                            "action_internal_hold_queue_path": "data/reporting/signal_phase_action_execution/bari/action_internal_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 6,
                            "execution_ready_count": 4,
                            "internal_hold_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_action_execution_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_action_handoff_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_action_handoff"
                / "bari"
                / "signal_phase_action_handoff_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_action_handoff_bundle",
                            "public_contract_version": "signal_phase_action_handoff_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_action_handoff_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "action_handoff_queue_path": "data/reporting/signal_phase_action_handoff/bari/action_handoff_queue.csv",
                            "action_handoff_hold_queue_path": "data/reporting/signal_phase_action_handoff/bari/action_handoff_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 6,
                            "handoff_ready_count": 4,
                            "internal_hold_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_action_handoff_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_operator_board_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_operator_board"
                / "bari"
                / "signal_phase_operator_board_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_operator_board_bundle",
                            "public_contract_version": "signal_phase_operator_board_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_operator_board_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "operator_ready_queue_path": "data/reporting/signal_phase_operator_board/bari/operator_ready_queue.csv",
                            "operator_hold_queue_path": "data/reporting/signal_phase_operator_board/bari/operator_hold_queue.csv",
                        },
                        "stats": {
                            "request_count": 6,
                            "operator_ready_count": 4,
                            "internal_hold_count": 2,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_operator_board_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_writeback_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_dispatch_writeback"
                / "bari"
                / "signal_phase_dispatch_writeback_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_writeback_bundle",
                            "public_contract_version": "signal_phase_dispatch_writeback_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_dispatch_writeback_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "synced_dispatch_execution_queue_path": "data/reporting/signal_phase_dispatch_writeback/bari/dispatch_execution_queue_synced.csv",
                        },
                        "stats": {
                            "dispatch_row_count": 6,
                            "dispatch_rows_updated_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_dispatch_writeback_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_dispatch_cycles"
                / "bari"
                / "signal_phase_dispatch_cycle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_cycle",
                            "public_contract_version": "signal_phase_dispatch_cycle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_dispatch_cycle_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "runtime_action_queue_manifest_path": "data/processed/signal_phase_dispatch_cycles/bari/runtime_action_queue/signal_phase_action_queue.manifest.json",
                        },
                        "stats": {
                            "writeback_ready_count": 0,
                            "runtime_action_request_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_dispatch_cycle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_runtime_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "processed"
                / "signal_phase_runtime_cycles"
                / "bari"
                / "signal_phase_runtime_cycle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_runtime_cycle",
                            "public_contract_version": "signal_phase_runtime_cycle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_runtime_cycle_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "dispatch_cycle_manifest_path": "data/processed/signal_phase_runtime_cycles/bari/dispatch_cycle/signal_phase_dispatch_cycle.manifest.json",
                        },
                        "stats": {
                            "receive_monitored_delivery_count": 18,
                            "runtime_dispatch_action_count": 6,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_runtime_cycle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_runtime_rehearsal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_runtime_rehearsal"
                / "bari"
                / "signal_phase_runtime_rehearsal.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_runtime_rehearsal",
                            "public_contract_version": "signal_phase_runtime_rehearsal_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_runtime_rehearsal_runner"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "rehearsal_json_path": "data/reporting/signal_phase_runtime_rehearsal/bari/signal_phase_runtime_rehearsal.json",
                            "rehearsal_md_path": "data/reporting/signal_phase_runtime_rehearsal/bari/signal_phase_runtime_rehearsal.md",
                            "pre_runtime_cycle_manifest_path": "data/reporting/signal_phase_runtime_rehearsal/bari/pre_runtime_cycle/signal_phase_runtime_cycle.manifest.json",
                            "post_runtime_cycle_manifest_path": "data/reporting/signal_phase_runtime_rehearsal/bari/post_runtime_cycle/signal_phase_runtime_cycle.manifest.json",
                        },
                        "stats": {
                            "request_count": 6,
                            "changed_request_count": 1,
                            "selected_request_left_dispatch_action": "yes",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_runtime_rehearsal"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_recording_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_dispatch_recording"
                / "bari"
                / "signal_phase_dispatch_recording_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_recording_bundle",
                            "public_contract_version": "signal_phase_dispatch_recording_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_dispatch_recording_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "dispatch_execution_queue_runtime_path": "data/reporting/signal_phase_dispatch_recording/bari/dispatch_execution_queue_runtime.csv",
                        },
                        "stats": {
                            "request_count": 6,
                            "applied_execution_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_dispatch_recording_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_validation_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "quality"
                / "signal_phase_dispatch_validation"
                / "bari"
                / "signal_phase_dispatch_validation_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_validation_bundle",
                            "public_contract_version": "signal_phase_dispatch_validation_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_dispatch_validation_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "validated_queue_path": "data/quality/signal_phase_dispatch_validation/bari/dispatch_execution_queue_validated.csv",
                        },
                        "stats": {
                            "runtime_row_count": 6,
                            "accepted_for_writeback_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["quality"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_dispatch_validation_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_repair_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_dispatch_repair"
                / "bari"
                / "signal_phase_dispatch_repair_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_repair_bundle",
                            "public_contract_version": "signal_phase_dispatch_repair_bundle_public_v1",
                        },
                        "source": {"adapter": "bari_signal_phase_dispatch_repair_builder"},
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "repair_queue_path": "data/reporting/signal_phase_dispatch_repair/bari/dispatch_log_repair_queue.csv",
                        },
                        "stats": {
                            "validated_row_count": 6,
                            "repair_request_count": 0,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["signal_phase_dispatch_repair_bundle"],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_repair_recording_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_dispatch_repair_recording"
                / "bari"
                / "signal_phase_dispatch_repair_recording_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_repair_recording_bundle",
                            "public_contract_version": "signal_phase_dispatch_repair_recording_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_dispatch_repair_recording_builder"
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "dispatch_execution_queue_runtime_repaired_path": "data/reporting/signal_phase_dispatch_repair_recording/bari/dispatch_execution_queue_runtime_repaired.csv",
                        },
                        "stats": {
                            "runtime_row_count": 6,
                            "repair_request_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"][
                    "signal_phase_dispatch_repair_recording_bundle"
                ],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_repair_execution_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_dispatch_repair_execution"
                / "bari"
                / "signal_phase_dispatch_repair_execution_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_repair_execution_bundle",
                            "public_contract_version": "signal_phase_dispatch_repair_execution_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_dispatch_repair_execution_builder"
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "dispatch_repair_execution_ready_queue_path": "data/reporting/signal_phase_dispatch_repair_execution/bari/dispatch_repair_execution_ready_queue.csv",
                        },
                        "stats": {
                            "request_count": 2,
                            "execution_ready_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"][
                    "signal_phase_dispatch_repair_execution_bundle"
                ],
                1,
            )

    def test_build_run_registry_classifies_signal_phase_dispatch_repair_status_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root
                / "reporting"
                / "signal_phase_dispatch_repair_status"
                / "bari"
                / "signal_phase_dispatch_repair_status_bundle.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "signal_phase_dispatch_repair_status_bundle",
                            "public_contract_version": "signal_phase_dispatch_repair_status_bundle_public_v1",
                        },
                        "source": {
                            "adapter": "bari_signal_phase_dispatch_repair_status_builder"
                        },
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "status_queue_path": "data/reporting/signal_phase_dispatch_repair_status/bari/dispatch_repair_status.csv",
                        },
                        "stats": {
                            "request_count": 2,
                            "pending_repair_count": 1,
                            "cleared_for_writeback_count": 1,
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"][
                    "signal_phase_dispatch_repair_status_bundle"
                ],
                1,
            )

    def test_build_run_registry_classifies_movement_signal_phase_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"

            manifest_path = (
                data_root / "processed" / "movement_objects" / "bari_signal_phase" / "road_movement_objects_signal_phase.manifest.json"
            )
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "manifest_path": str(manifest_path),
                            "geojson_path": "data/processed/movement_objects/bari_signal_phase/road_movement_objects_signal_phase.geojson",
                        },
                        "stats": {"movements_with_phase_timing": 4},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["enrichment"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["movement_signal_phase_layer"], 1)

    def test_build_run_registry_excludes_existing_registry_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = data_root / "registry"
            output_dir.mkdir(parents=True, exist_ok=True)

            existing_registry_manifest = output_dir / "run_registry.manifest.json"
            existing_registry_manifest.write_text(
                json.dumps(
                    {
                        "registry_version": "run_registry_v1",
                        "stats": {"entries": 99},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            frequency_metrics_path = data_root / "models" / "demo_frequency" / "frequency_baseline.metrics.json"
            frequency_metrics_path.parent.mkdir(parents=True, exist_ok=True)
            frequency_metrics_path.write_text(
                json.dumps(
                    {
                        "input_path": "data/processed/aggregates/demo/segment_year_metrics.csv",
                        "holdout_year": 2021,
                        "random_forest_poisson_metrics": {
                            "mean_poisson_deviance": 0.25,
                            "top_5pct_crash_share": 0.5,
                        },
                        "outputs": {
                            "metrics_path": str(frequency_metrics_path),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["inputs"]["documents_scanned"], 1)

    def test_build_run_registry_classifies_serving_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            tile_manifest_path = data_root / "prediction_store" / "demo_tiles" / "score_tiles.manifest.json"
            tile_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            tile_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "segment_score_tiles",
                            "public_contract_version": "segment_score_tiles_public_v1",
                        },
                        "stats": {
                            "tile_rows": 4,
                        },
                        "outputs": {
                            "manifest_path": str(tile_manifest_path),
                            "public_geojson_path": "data/prediction_store/demo_tiles/score_tiles_public.geojson",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            index_manifest_path = data_root / "published_index" / "published_resources.manifest.json"
            index_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            index_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "published_resource_index",
                            "public_contract_version": "published_resource_index_public_v1",
                        },
                        "stats": {
                            "catalog_record_count": 2,
                        },
                        "outputs": {
                            "manifest_path": str(index_manifest_path),
                            "index_json_path": "data/published_index/published_resources.json",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            dashboard_summary_manifest_path = data_root / "dashboard" / "dashboard_summary.manifest.json"
            dashboard_summary_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            dashboard_summary_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "dashboard_summary",
                            "public_contract_version": "dashboard_summary_public_v1",
                        },
                        "stats": {
                            "published_run_count": 4,
                        },
                        "outputs": {
                            "manifest_path": str(dashboard_summary_manifest_path),
                            "summary_json_path": "data/dashboard/dashboard_summary.json",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 3)
            self.assertEqual(manifest["stats"]["stage_counts"]["serving"], 3)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["dashboard_summary"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["published_resource_index"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["public_score_tiles"], 1)

    def test_build_run_registry_classifies_reporting_intervention_briefs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            brief_manifest_path = (
                data_root / "intervention_briefs" / "demo_city" / "intervention_brief.manifest.json"
            )
            brief_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            brief_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "intervention_brief",
                            "public_contract_version": "intervention_brief_public_v1",
                        },
                        "stats": {
                            "prediction_run_label": "demo_city",
                            "recommended_action_count": 4,
                        },
                        "outputs": {
                            "manifest_path": str(brief_manifest_path),
                            "brief_json_path": "data/intervention_briefs/demo_city/intervention_brief.json",
                            "brief_markdown_path": "data/intervention_briefs/demo_city/intervention_brief.md",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["intervention_brief"], 1)

    def test_build_run_registry_classifies_reporting_scenario_countermeasure_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            scenario_manifest_path = (
                data_root
                / "planning"
                / "scenario_countermeasures"
                / "demo_city"
                / "scenario_bundle.manifest.json"
            )
            scenario_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            scenario_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "scenario_countermeasure_bundle",
                            "public_contract_version": "scenario_countermeasure_bundle_public_v1",
                        },
                        "stats": {
                            "scenario_count": 6,
                            "portfolio_count": 4,
                        },
                        "outputs": {
                            "manifest_path": str(scenario_manifest_path),
                            "scenario_bundle_path": (
                                "data/planning/scenario_countermeasures/demo_city/scenario_bundle.json"
                            ),
                            "scenario_spec_path": (
                                "data/planning/scenario_countermeasures/demo_city/scenario_spec.json"
                            ),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(
                manifest["stats"]["artifact_kind_counts"]["scenario_countermeasure_bundle"],
                1,
            )

    def test_build_run_registry_classifies_reporting_vru_intelligence_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            vru_manifest_path = (
                data_root
                / "planning"
                / "vru_intelligence"
                / "demo_city"
                / "vru_intelligence_bundle.manifest.json"
            )
            vru_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            vru_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "vru_intelligence_bundle",
                            "public_contract_version": "vru_intelligence_bundle_public_v1",
                        },
                        "stats": {
                            "segment_count": 44,
                            "crossing_profile_count": 10,
                        },
                        "outputs": {
                            "manifest_path": str(vru_manifest_path),
                            "bundle_path": "data/planning/vru_intelligence/demo_city/vru_intelligence_bundle.json",
                            "segment_scores_path": "data/planning/vru_intelligence/demo_city/segment_vru_scores.csv",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["vru_intelligence_bundle"], 1)

    def test_build_run_registry_classifies_reporting_vru_exposure_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            vru_manifest_path = (
                data_root
                / "planning"
                / "vru_exposure"
                / "demo_city"
                / "vru_exposure_bundle.manifest.json"
            )
            vru_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            vru_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "vru_exposure_bundle",
                            "public_contract_version": "vru_exposure_bundle_public_v1",
                        },
                        "stats": {
                            "segment_feature_count": 44,
                            "crossing_feature_count": 10,
                        },
                        "outputs": {
                            "manifest_path": str(vru_manifest_path),
                            "bundle_path": "data/planning/vru_exposure/demo_city/vru_exposure_bundle.json",
                            "segment_geojson_path": (
                                "data/planning/vru_exposure/demo_city/segment_vru_exposure.geojson"
                            ),
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["vru_exposure_bundle"], 1)

    def test_build_run_registry_classifies_transferability_benchmark_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            benchmark_manifest_path = (
                data_root
                / "reporting"
                / "transferability_benchmark"
                / "transferability_benchmark.manifest.json"
            )
            benchmark_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            benchmark_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "transferability_benchmark",
                            "public_contract_version": "transferability_benchmark_public_v1",
                        },
                        "stats": {
                            "input_run_count": 3,
                            "stack_count": 2,
                        },
                        "outputs": {
                            "manifest_path": str(benchmark_manifest_path),
                            "report_json_path": "data/reporting/transferability_benchmark/transferability_benchmark.json",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            build_run_registry(data_root=data_root, output_dir=output_dir)

            entries = [
                json.loads(line)
                for line in (output_dir / "run_registry.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            entry = next(entry for entry in entries if entry["artifact_kind"] == "transferability_benchmark")
            self.assertEqual(entry["stage"], "reporting")
            self.assertEqual(entry["summary"]["resource_name"], "transferability_benchmark")

    def test_build_run_registry_classifies_published_refresh_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            refresh_manifest_path = (
                data_root
                / "reporting"
                / "published_refresh"
                / "latest"
                / "published_refresh_bundle.manifest.json"
            )
            refresh_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            refresh_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "published_refresh_bundle",
                            "public_contract_version": "published_refresh_bundle_public_v1",
                        },
                        "stats": {
                            "latest_published_resource_count": 2,
                            "selected_transferability_input_count": 1,
                        },
                        "outputs": {
                            "manifest_path": str(refresh_manifest_path),
                            "bundle_json_path": "data/reporting/published_refresh/latest/published_refresh_bundle.json",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            build_run_registry(data_root=data_root, output_dir=output_dir)

            entries = [
                json.loads(line)
                for line in (output_dir / "run_registry.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            entry = next(entry for entry in entries if entry["artifact_kind"] == "published_refresh_bundle")
            self.assertEqual(entry["stage"], "reporting")
            self.assertEqual(entry["summary"]["resource_name"], "published_refresh_bundle")

    def test_build_run_registry_classifies_exposure_readiness_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            readiness_manifest_path = (
                data_root / "planning" / "exposure_readiness" / "exposure_readiness.manifest.json"
            )
            readiness_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            readiness_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "exposure_readiness",
                            "public_contract_version": "exposure_readiness_public_v1",
                        },
                        "stats": {
                            "dataset_count": 4,
                            "highest_priority_missing_count": 8,
                        },
                        "outputs": {
                            "manifest_path": str(readiness_manifest_path),
                            "report_json_path": "data/planning/exposure_readiness/exposure_readiness.json",
                            "report_markdown_path": "data/planning/exposure_readiness/exposure_readiness.md",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["exposure_readiness"], 1)

    def test_build_run_registry_classifies_exposure_source_catalogs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            output_dir = root / "registry"

            catalog_manifest_path = (
                data_root / "planning" / "exposure_sources" / "exposure_source_catalog.manifest.json"
            )
            catalog_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_manifest_path.write_text(
                json.dumps(
                    {
                        "contract": {
                            "resource_name": "exposure_source_catalog",
                            "public_contract_version": "exposure_source_catalog_public_v1",
                        },
                        "stats": {
                            "dataset_count": 4,
                            "connector_contract_count": 3,
                        },
                        "outputs": {
                            "manifest_path": str(catalog_manifest_path),
                            "catalog_json_path": "data/planning/exposure_sources/exposure_source_catalog.json",
                            "catalog_markdown_path": "data/planning/exposure_sources/exposure_source_catalog.md",
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            manifest = build_run_registry(data_root=data_root, output_dir=output_dir)

            self.assertEqual(manifest["stats"]["entries"], 1)
            self.assertEqual(manifest["stats"]["stage_counts"]["reporting"], 1)
            self.assertEqual(manifest["stats"]["artifact_kind_counts"]["exposure_source_catalog"], 1)
