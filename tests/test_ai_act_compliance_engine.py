"""Tests for EU AI Act (Regulation 2024/1689) High-Risk Compliance & Explainable AI (XAI) Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.ai_act_compliance_engine import (
    AI_ACT_CONTRACT_VERSION,
    AI_ACT_ENGINE_VERSION,
    REGULATION_REFERENCE,
    AiActArticleComplianceStatus,
    AiActComplianceDossier,
    AlgorithmicFairnessMetrics,
    CorridorXaiExplanation,
    audit_algorithmic_fairness,
    compute_local_shap_explanations,
    export_ai_act_compliance_artifacts,
    generate_eu_ai_act_dossier,
)


class TestAiActComplianceEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_corridors = [
            {
                "segment_id": "seg-1",
                "name": "Via Gentile",
                "geographic_tier": "urban_core",
                "predicted_risk": 0.85,
                "current_speed_kmh": 35.0,
                "free_flow_speed_kmh": 70.0,
                "telematics_near_miss_rate": 14.5,
                "precipitation_mm_h": 12.0,
                "irap_star_rating": 2.0,
                "spatial_contagion_index": 0.45,
                "historical_eb_excess": 2.4,
            },
            {
                "segment_id": "seg-2",
                "name": "SS16 Tangenziale",
                "geographic_tier": "peripheral",
                "predicted_risk": 0.78,
                "current_speed_kmh": 55.0,
                "free_flow_speed_kmh": 90.0,
                "telematics_near_miss_rate": 11.2,
                "precipitation_mm_h": 10.0,
                "irap_star_rating": 3.5,
                "spatial_contagion_index": 0.38,
                "historical_eb_excess": 1.9,
            },
            {
                "segment_id": "seg-3",
                "name": "Via Sparano",
                "geographic_tier": "urban_core",
                "predicted_risk": 0.15,
                "current_speed_kmh": 15.0,
                "free_flow_speed_kmh": 30.0,
                "telematics_near_miss_rate": 0.8,
                "precipitation_mm_h": 1.0,
                "irap_star_rating": 4.5,
                "spatial_contagion_index": 0.05,
                "historical_eb_excess": 0.1,
            },
            {
                "segment_id": "seg-4",
                "name": "SP236 Raccordo",
                "geographic_tier": "peripheral",
                "predicted_risk": 0.25,
                "current_speed_kmh": 75.0,
                "free_flow_speed_kmh": 80.0,
                "telematics_near_miss_rate": 2.1,
                "precipitation_mm_h": 0.0,
                "irap_star_rating": 4.0,
                "spatial_contagion_index": 0.10,
                "historical_eb_excess": 0.3,
            },
        ]

    def test_local_shap_additivity(self) -> None:
        """Verify mathematical additivity of Shapley values: phi_0 + sum(phi_k) == predicted_risk."""
        explanations = compute_local_shap_explanations(self.sample_corridors)
        self.assertEqual(len(explanations), 4)

        for exp in explanations:
            self.assertIsInstance(exp, CorridorXaiExplanation)
            # Check exact mathematical reconstruction
            self.assertAlmostEqual(exp.reconstructed_risk, exp.predicted_risk, delta=0.001)
            self.assertAlmostEqual(
                exp.baseline_expected_risk + exp.sum_shapley_values,
                exp.predicted_risk,
                delta=0.001,
            )
            # Verify attributions list
            self.assertGreaterEqual(len(exp.attributions), 4)
            # Check top drivers
            if exp.predicted_risk > exp.baseline_expected_risk:
                self.assertGreater(len(exp.top_risk_drivers), 0)

            exp_dict = exp.to_dict()
            self.assertIn("top_risk_drivers", exp_dict)
            self.assertIn("attributions", exp_dict)

    def test_algorithmic_fairness_audit(self) -> None:
        """Verify demographic parity and disparate impact ratio (DIR) evaluation."""
        fairness = audit_algorithmic_fairness(
            corridors_data=self.sample_corridors,
            protected_attribute="geographic_tier",
            risk_threshold=0.60,
        )
        self.assertIsInstance(fairness, AlgorithmicFairnessMetrics)
        self.assertEqual(fairness.protected_attribute, "geographic_tier")
        self.assertEqual(fairness.unprivileged_group, "peripheral_or_rural")
        self.assertEqual(fairness.privileged_group, "urban_core")
        self.assertEqual(fairness.unprivileged_sample_size, 2)
        self.assertEqual(fairness.privileged_sample_size, 2)
        # Both groups have 1 out of 2 >= 0.60 risk -> rate 0.50 each -> DIR = 1.0 -> compliant
        self.assertAlmostEqual(fairness.unprivileged_high_risk_rate, 0.50, places=2)
        self.assertAlmostEqual(fairness.privileged_high_risk_rate, 0.50, places=2)
        self.assertAlmostEqual(fairness.disparate_impact_ratio, 1.0, places=2)
        self.assertAlmostEqual(fairness.demographic_parity_difference, 0.0, places=2)
        self.assertEqual(fairness.fairness_verdict, "compliant")

    def test_algorithmic_fairness_disparity_detection(self) -> None:
        """Verify that severe demographic or geographic disparity triggers non_compliant or warning."""
        skewed_corridors = [
            {"segment_id": "u1", "geographic_tier": "peripheral", "predicted_risk": 0.90},
            {"segment_id": "u2", "geographic_tier": "peripheral", "predicted_risk": 0.85},
            {"segment_id": "p1", "geographic_tier": "urban_core", "predicted_risk": 0.10},
            {"segment_id": "p2", "geographic_tier": "urban_core", "predicted_risk": 0.15},
        ]
        fairness = audit_algorithmic_fairness(skewed_corridors, risk_threshold=0.60)
        self.assertEqual(fairness.unprivileged_high_risk_rate, 1.0)
        self.assertEqual(fairness.privileged_high_risk_rate, 0.0)
        self.assertIn(fairness.fairness_verdict, {"warning", "non_compliant"})

    def test_generate_eu_ai_act_dossier(self) -> None:
        """Verify full CE-marking conformity dossier generation across Articles 9 through 15."""
        dossier = generate_eu_ai_act_dossier(
            corridors_data=self.sample_corridors,
            network_label="test_bari_network",
            accuracy_auc_roc=0.890,
            brier_score_loss=0.075,
        )
        self.assertIsInstance(dossier, AiActComplianceDossier)
        self.assertEqual(dossier.network_label, "test_bari_network")
        self.assertEqual(dossier.total_articles_evaluated, 7)
        self.assertEqual(dossier.compliant_articles_count, 7)
        self.assertEqual(dossier.overall_conformity_verdict, "CE_CONFORMITY_CERTIFIED")
        self.assertEqual(len(dossier.article_evaluations), 7)

        article_nums = [a.article_number for a in dossier.article_evaluations]
        self.assertEqual(
            article_nums,
            ["Article 9", "Article 10", "Article 11", "Article 12", "Article 13", "Article 14", "Article 15"],
        )

        dossier_dict = dossier.to_dict()
        self.assertIn("ai_act_engine_version", dossier_dict)
        self.assertIn("regulation_reference", dossier_dict)
        self.assertIn("fairness_metrics", dossier_dict)
        self.assertIn("article_evaluations", dossier_dict)

    def test_export_ai_act_compliance_artifacts(self) -> None:
        """Verify artifact bundle export: CSVs, JSON dossier, Markdown report, and SHA-256 manifest."""
        dossier = generate_eu_ai_act_dossier(
            corridors_data=self.sample_corridors,
            network_label="test_export_net",
        )
        all_explanations = compute_local_shap_explanations(self.sample_corridors)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_files = export_ai_act_compliance_artifacts(
                dossier=dossier,
                all_explanations=all_explanations,
                output_dir=tmpdir,
                network_label="test_export_net",
            )

            for key in ["xai_csv", "fairness_csv", "dossier_json", "report_md", "manifest"]:
                self.assertIn(key, out_files)
                fpath = Path(out_files[key])
                self.assertTrue(fpath.exists(), f"File {fpath} does not exist")
                self.assertGreater(fpath.stat().st_size, 0)

            # Validate Manifest
            manifest = json.loads(Path(out_files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "eu_ai_act_compliance_dossier")
            self.assertEqual(manifest["ai_act_engine_version"], AI_ACT_ENGINE_VERSION)
            self.assertIn("xai_csv", manifest["files"])
            self.assertIn("report_md", manifest["files"])

            # Validate Executive Markdown Report
            report_text = Path(out_files["report_md"]).read_text(encoding="utf-8")
            self.assertIn("EU AI Act (Regulation 2024/1689) High-Risk Compliance Dossier", report_text)
            self.assertIn("CE CONFORMITY CERTIFIED", report_text)
            self.assertIn("Article 9", report_text)
            self.assertIn("Article 15", report_text)


if __name__ == "__main__":
    unittest.main()
