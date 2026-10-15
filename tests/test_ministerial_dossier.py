"""Unit tests for Sovereign Ministerial Dossier Generator & PDF/A Renderer."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.ministerial_dossier import (
    DOSSIER_CONTRACT_VERSION,
    DOSSIER_ENGINE_VERSION,
    MinisterialDossierReport,
    compile_ministerial_dossier,
    export_ministerial_dossier_artifacts,
    render_ministerial_markdown,
    render_ministerial_pdf,
)


class TestMinisterialDossier(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_hsm = {
            "total_segments": 500,
            "fatality_rate_per_100k": 4.2,
            "disparity_coefficient": 0.25,
            "high_risk_segments_count": 25,
            "total_excess_crashes_preventable": 850.0,
        }
        self.sample_irap = {
            "total_segments": 500,
            "total_distance_km": 650.0,
            "target_4_compliance_pct": 14.5,
        }
        self.sample_telematics = {
            "mean_near_miss_rate_per_mvkt": 12.4,
        }
        self.sample_micromobility = {
            "mean_mci": 15.2,
            "total_distance_km": 650.0,
        }
        self.sample_cip = {
            "total_npv_m_eur": 1250.0,
            "benefit_cost_ratio": 45.2,
            "fatal_and_serious_injuries_prevented": 5400,
        }

    def test_compile_ministerial_dossier(self) -> None:
        """Verify compilation of executive KPIs and 6 thematic dossier chapters."""
        dossier = compile_ministerial_dossier(
            network_label="test_ministerial_puglia",
            jurisdiction_name="Regione Puglia",
            ministry_authority="Ministero delle Infrastrutture e dei Trasporti",
            hsm_data=self.sample_hsm,
            irap_data=self.sample_irap,
            telematics_data=self.sample_telematics,
            micromobility_data=self.sample_micromobility,
            cip_data=self.sample_cip,
        )

        self.assertIsInstance(dossier, MinisterialDossierReport)
        self.assertEqual(dossier.network_label, "test_ministerial_puglia")
        self.assertEqual(dossier.kpis.total_corridors_analyzed, 500)
        self.assertEqual(dossier.kpis.population_fatality_rate_per_100k, 4.2)
        self.assertEqual(dossier.kpis.irap_target_4_compliance_pct, 14.5)
        self.assertEqual(dossier.kpis.cip_5yr_fsi_prevented, 5400)
        self.assertEqual(len(dossier.sections), 6)

        d_dict = dossier.to_dict()
        self.assertEqual(d_dict["dossier_engine_version"], DOSSIER_ENGINE_VERSION)
        self.assertEqual(d_dict["contract_version"], DOSSIER_CONTRACT_VERSION)
        self.assertIn("executive_kpis", d_dict)
        self.assertIn("sections", d_dict)

    def test_render_ministerial_markdown(self) -> None:
        """Verify markdown rendering includes executive table, chapters, and sign-off."""
        dossier = compile_ministerial_dossier(
            network_label="test_md",
            hsm_data=self.sample_hsm,
        )
        md = render_ministerial_markdown(dossier)
        self.assertIn("# Sovereign Ministerial Safety Dossier", md)
        self.assertIn("Executive Summary & Strategic KPIs", md)
        self.assertIn("Macro-Infrastructure Screening", md)
        self.assertIn("Sovereign Evidentiary Statement", md)

    def test_render_ministerial_pdf_bytes(self) -> None:
        """Verify native vector PDF renderer outputs valid %PDF-1.4 bytes with header and xref table."""
        dossier = compile_ministerial_dossier(
            network_label="test_pdf",
            hsm_data=self.sample_hsm,
            irap_data=self.sample_irap,
        )
        pdf_bytes = render_ministerial_pdf(dossier)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4\n"))
        self.assertTrue(pdf_bytes.rstrip().endswith(b"%%EOF"))

    def test_export_ministerial_dossier_artifacts(self) -> None:
        """Verify export of PDF, MD, JSON bundle, and cryptographic SHA-256 manifest."""
        dossier = compile_ministerial_dossier(
            network_label="test_export",
            hsm_data=self.sample_hsm,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_files = export_ministerial_dossier_artifacts(
                dossier=dossier,
                output_dir=tmpdir,
                network_label="test_export",
            )
            for key in ["dossier_pdf", "dossier_md", "bundle_json", "manifest"]:
                self.assertIn(key, out_files)
                fpath = Path(out_files[key])
                self.assertTrue(fpath.exists())
                self.assertGreater(fpath.stat().st_size, 0)

            manifest = json.loads(Path(out_files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "sovereign_ministerial_safety_dossier")
            self.assertIn("dossier_pdf", manifest["files"])
            self.assertIn("dossier_md", manifest["files"])


if __name__ == "__main__":
    unittest.main()
