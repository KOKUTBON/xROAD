from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.governance_interoperability import build_governance_interoperability_bundle


class GovernanceInteroperabilityTests(unittest.TestCase):
    def test_build_governance_interoperability_bundle_writes_bundle_and_matrices(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "governance"

            result = build_governance_interoperability_bundle(output_dir)

            manifest_path = output_dir / "governance_interoperability_bundle.manifest.json"
            bundle_json_path = output_dir / "governance_interoperability_bundle.json"
            source_matrix_path = output_dir / "source_governance_matrix.csv"
            role_policy_path = output_dir / "artifact_role_policies.csv"
            datex_path = output_dir / "datex_alignment_matrix.csv"
            handoff_path = output_dir / "mobility_data_space_handoffs.csv"

            self.assertEqual(result["manifest_path"], str(manifest_path))
            self.assertTrue(manifest_path.exists())
            self.assertTrue(bundle_json_path.exists())
            self.assertTrue(source_matrix_path.exists())
            self.assertTrue(role_policy_path.exists())
            self.assertTrue(datex_path.exists())
            self.assertTrue(handoff_path.exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["contract"]["resource_name"],
                "governance_interoperability_bundle",
            )
            self.assertEqual(manifest["stats"]["source_family_count"], 9)
            self.assertEqual(manifest["stats"]["artifact_role_policy_count"], 12)

            bundle = json.loads(bundle_json_path.read_text(encoding="utf-8"))
            source_ids = {row["source_family_id"] for row in bundle["source_governance_decisions"]}
            self.assertIn("future_traffic_event_feed", source_ids)
            self.assertIn("bari_open_data_crash_feed", source_ids)

            with source_matrix_path.open(encoding="utf-8", newline="") as handle:
                source_rows = list(csv.DictReader(handle))
            self.assertEqual(len(source_rows), 9)

            with role_policy_path.open(encoding="utf-8", newline="") as handle:
                role_rows = list(csv.DictReader(handle))
            role_policy_ids = {row["role_policy_id"] for row in role_rows}
            self.assertIn("segment_scores_public_geojson__public", role_policy_ids)
            self.assertIn("signal_phase_records__public", role_policy_ids)


if __name__ == "__main__":
    unittest.main()
