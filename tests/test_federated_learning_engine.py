"""Tests for Privacy-Preserving Federated Learning Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.federated_learning_engine import (
    FL_CONTRACT_VERSION,
    FL_ENGINE_VERSION,
    MODEL_FEATURES,
    DifferentialPrivacyConfig,
    FederatedClientNode,
    FederatedClientUpdate,
    FederatedRoundConfig,
    FederatedRoundResult,
    FederatedTrainingConvergenceReport,
    aggregate_federated_round,
    export_federated_learning_artifacts,
    run_federated_training_pipeline,
    simulate_local_node_update,
)


class TestFederatedLearningEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_nodes = [
            FederatedClientNode(
                node_id="node-aspi",
                concessionaire_name="ASPI Motorways",
                jurisdiction="IT-MOTORWAY",
                sample_size=300,
                local_features=[
                    {
                        "telematics_near_miss_rate": 12.0,
                        "speed_drop_ratio": 0.30,
                        "precipitation_mm_h": 5.0,
                        "irap_deficit_score": 2.0,
                        "spatial_contagion_index": 0.35,
                        "historical_eb_excess": 1.8,
                        "aadt_exposure_k": 40.0,
                        "observed_crash": 1,
                    },
                    {
                        "telematics_near_miss_rate": 2.5,
                        "speed_drop_ratio": 0.05,
                        "precipitation_mm_h": 0.0,
                        "irap_deficit_score": 1.0,
                        "spatial_contagion_index": 0.10,
                        "historical_eb_excess": 0.3,
                        "aadt_exposure_k": 30.0,
                        "observed_crash": 0,
                    },
                ],
            ),
            FederatedClientNode(
                node_id="node-anas",
                concessionaire_name="ANAS State Roads",
                jurisdiction="IT-STATE",
                sample_size=400,
                local_features=[
                    {
                        "telematics_near_miss_rate": 15.0,
                        "speed_drop_ratio": 0.40,
                        "precipitation_mm_h": 8.0,
                        "irap_deficit_score": 3.0,
                        "spatial_contagion_index": 0.40,
                        "historical_eb_excess": 2.2,
                        "aadt_exposure_k": 25.0,
                        "observed_crash": 1,
                    },
                    {
                        "telematics_near_miss_rate": 3.0,
                        "speed_drop_ratio": 0.08,
                        "precipitation_mm_h": 1.0,
                        "irap_deficit_score": 2.0,
                        "spatial_contagion_index": 0.15,
                        "historical_eb_excess": 0.5,
                        "aadt_exposure_k": 20.0,
                        "observed_crash": 0,
                    },
                ],
            ),
        ]
        self.initial_weights = {feat: 0.10 for feat in MODEL_FEATURES}
        self.initial_weights["bias"] = -0.50

    def test_simulate_local_node_update(self) -> None:
        """Verify local gradient descent update and differential privacy clipping."""
        round_cfg = FederatedRoundConfig(
            round_id=1,
            local_epochs=2,
            learning_rate=0.05,
            dp_config=DifferentialPrivacyConfig(clip_norm=1.0, enable_dp=True),
        )
        update = simulate_local_node_update(
            node=self.sample_nodes[0],
            global_weights=self.initial_weights,
            round_cfg=round_cfg,
            random_seed=42,
        )
        self.assertIsInstance(update, FederatedClientUpdate)
        self.assertEqual(update.node_id, "node-aspi")
        self.assertEqual(update.sample_size, 300)
        self.assertGreater(update.gradient_norm, 0.0)
        self.assertGreater(update.local_auc, 0.5)
        self.assertGreater(update.local_loss, 0.0)
        self.assertGreater(update.epsilon_spent, 0.0)

        # Check weights updated
        self.assertIn("telematics_near_miss_rate", update.updated_weights)
        self.assertIn("bias", update.updated_weights)

    def test_aggregate_federated_round_methods(self) -> None:
        """Verify FedAvg, Trimmed-Mean, and Median aggregation algorithms."""
        u1 = FederatedClientUpdate(
            node_id="n1",
            sample_size=300,
            updated_weights={"bias": -0.40, "telematics_near_miss_rate": 0.15},
            local_loss=0.55,
            local_auc=0.75,
            gradient_norm=0.8,
            epsilon_spent=1.0,
        )
        u2 = FederatedClientUpdate(
            node_id="n2",
            sample_size=700,
            updated_weights={"bias": -0.60, "telematics_near_miss_rate": 0.25},
            local_loss=0.45,
            local_auc=0.82,
            gradient_norm=0.7,
            epsilon_spent=1.0,
        )

        # 1. FedAvg (weighted average: 0.3 * -0.4 + 0.7 * -0.6 = -0.54)
        cfg_avg = FederatedRoundConfig(round_id=1, aggregation_method="fedavg")
        res_avg = aggregate_federated_round([u1, u2], cfg_avg, self.initial_weights)
        self.assertAlmostEqual(res_avg.global_weights["bias"], -0.54, places=2)
        self.assertAlmostEqual(res_avg.global_weights["telematics_near_miss_rate"], 0.22, places=2)
        self.assertEqual(res_avg.total_samples, 1000)
        self.assertEqual(res_avg.participant_count, 2)

        # 2. Median aggregation
        cfg_med = FederatedRoundConfig(round_id=1, aggregation_method="median")
        res_med = aggregate_federated_round([u1, u2], cfg_med, self.initial_weights)
        self.assertAlmostEqual(res_med.global_weights["bias"], -0.50, places=2)

        # 3. Trimmed-Mean aggregation
        cfg_trim = FederatedRoundConfig(round_id=1, aggregation_method="trimmed_mean", trimmed_fraction=0.1)
        res_trim = aggregate_federated_round([u1, u2], cfg_trim, self.initial_weights)
        self.assertIsInstance(res_trim, FederatedRoundResult)

    def test_run_federated_training_pipeline_convergence(self) -> None:
        """Verify multi-round federated training convergence and generalization."""
        nodes_input = [
            {
                "node_id": "ASPI-1",
                "concessionaire_name": "Autostrade per l'Italia",
                "sample_size": 250,
            },
            {
                "node_id": "ANAS-1",
                "concessionaire_name": "ANAS Compartimento Puglia",
                "sample_size": 350,
            },
        ]
        report = run_federated_training_pipeline(
            nodes_data=nodes_input,
            rounds_count=3,
            aggregation_method="fedavg",
            enable_dp=True,
            target_epsilon=2.0,
            network_label="test_fl_net",
        )
        self.assertIsInstance(report, FederatedTrainingConvergenceReport)
        self.assertEqual(report.total_rounds, 3)
        self.assertEqual(len(report.rounds_history), 3)
        self.assertGreaterEqual(report.final_auc, report.initial_auc)
        self.assertLessEqual(report.final_loss, report.initial_loss)
        self.assertGreater(report.total_privacy_budget_spent, 0.0)

        report_dict = report.to_dict()
        self.assertIn("sovereign_framework_standard", report_dict)
        self.assertIn("participating_nodes", report_dict)
        self.assertIn("final_global_weights", report_dict)

    def test_export_federated_learning_artifacts(self) -> None:
        """Verify export of convergence history CSV, bundle JSON, report MD, and SHA-256 manifest."""
        nodes_input = [
            {"node_id": "n1", "concessionaire_name": "Operator 1", "sample_size": 200},
            {"node_id": "n2", "concessionaire_name": "Operator 2", "sample_size": 300},
        ]
        report = run_federated_training_pipeline(
            nodes_data=nodes_input,
            rounds_count=2,
            network_label="test_export_fl",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_files = export_federated_learning_artifacts(
                report=report,
                output_dir=tmpdir,
                network_label="test_export_fl",
            )

            for key in ["convergence_csv", "bundle_json", "report_md", "manifest"]:
                self.assertIn(key, out_files)
                fpath = Path(out_files[key])
                self.assertTrue(fpath.exists(), f"File {fpath} does not exist")
                self.assertGreater(fpath.stat().st_size, 0)

            # Validate Manifest
            manifest = json.loads(Path(out_files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "federated_learning_convergence_dossier")
            self.assertEqual(manifest["fl_engine_version"], FL_ENGINE_VERSION)
            self.assertIn("convergence_csv", manifest["files"])
            self.assertIn("report_md", manifest["files"])

            # Validate Markdown Report
            md_text = Path(out_files["report_md"]).read_text(encoding="utf-8")
            self.assertIn("Privacy-Preserving Federated Learning Report", md_text)
            self.assertIn("Zero Raw Telematics Ingestion", md_text)
            self.assertIn("Differential Privacy", md_text)


if __name__ == "__main__":
    unittest.main()
