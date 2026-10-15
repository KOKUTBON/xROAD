from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from road_risk_modeling.signal_phase_request import build_bari_signal_phase_request_pack


class SignalPhaseRequestTests(unittest.TestCase):
    def test_build_bari_signal_phase_request_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "signal_phase_requests"
            intake_path = root / "signal_phase_intake_pack.json"
            intake_path.write_text(
                json.dumps(
                    {
                        "top_priority_signals": [
                            {
                                "junction_id": "it-bari-signal-93",
                                "signal_name": "VIE ESTRAMURALE CAPRUZZI - B. CROCE",
                                "signal_type": "IMP. SEMAF",
                                "priority_band": "tier_1_immediate",
                                "recommended_provider_profile": "controller_event_log_export",
                                "required_inputs": (
                                    "arm-to-phase mapping sheet | controller event log export | "
                                    "junction phase diagram or phasing sketch | pedestrian stage definition"
                                ),
                                "recommended_next_input": "controller timing plan, phase table, or stage log export",
                                "signalized_crash_total": 59,
                                "ambiguous_crash_total": 58,
                                "ambiguous_movement_count": 36,
                                "matched_crashes_at_junction_total": 59,
                                "movement_turn_catalog": "cross | left | straight | right | u_turn",
                                "movement_phase_groups_present": "signalized_pedestrian_stage",
                                "sample_movement": {
                                    "incoming_arm_id": "arm_in_01",
                                    "movement_turn": "left",
                                    "outgoing_arm_id": "arm_out_01",
                                    "movement_resolution_state": "ambiguous_target_variant",
                                },
                            },
                            {
                                "junction_id": "it-bari-signal-10",
                                "signal_name": "TEST SIGNAL",
                                "signal_type": "IMP. SEMAF",
                                "priority_band": "tier_2_next_wave",
                                "recommended_provider_profile": "signal_stage_plan_export",
                                "required_inputs": "arm-to-phase mapping sheet | signal stage plan export",
                                "recommended_next_input": "signal stage plan export",
                                "signalized_crash_total": 8,
                                "ambiguous_crash_total": 3,
                                "ambiguous_movement_count": 4,
                                "matched_crashes_at_junction_total": 8,
                                "movement_turn_catalog": "left | straight",
                                "movement_phase_groups_present": "signalized_aligned_turn_phase_unknown",
                                "sample_movement": {
                                    "incoming_arm_id": "arm_in_02",
                                    "movement_turn": "straight",
                                    "outgoing_arm_id": "arm_out_02",
                                    "movement_resolution_state": "explicit_target",
                                },
                            },
                        ]
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            def fake_fetcher(
                query: str,
                *,
                portal_base_url: str,
                timeout_s: float,
                verify_ssl: bool,
            ) -> dict[str, object]:
                dataset_map = {
                    "semafori": [
                        {
                            "name": "semafori",
                            "title": "Semafori",
                            "notes": "Elenco degli impianti semaforici mappati sul territorio comunale",
                            "resources": [
                                {
                                    "name": "Semafori",
                                    "format": "CSV",
                                    "url": "https://opendata.comune.bari.it/semafori.csv",
                                }
                            ],
                        }
                    ],
                    "mobilita": [
                        {
                            "name": "transit-mobility-feeds",
                            "title": "Transit and mobility services",
                            "notes": "Dataset containing public transit scheduling and mobility feeds.",
                            "resources": [
                                {
                                    "name": "Transit information",
                                    "format": "ZIP",
                                    "url": "https://opendata.example.org/google_transit.zip",
                                }
                            ],
                        }
                    ],
                }
                rows = dataset_map.get(query, [])
                return {
                    "result": {
                        "count": len(rows),
                        "results": rows,
                    }
                }

            manifest = build_bari_signal_phase_request_pack(
                output_dir=output_dir,
                signal_phase_intake_path=intake_path,
                fetcher=fake_fetcher,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_signal_phase_request_pack_builder")
            self.assertEqual(manifest["stats"]["public_dataset_count"], 2)
            self.assertEqual(manifest["stats"]["public_signal_phase_dataset_count"], 0)
            self.assertEqual(manifest["stats"]["request_row_count"], 2)
            self.assertEqual(manifest["stats"]["tier_1_signal_count"], 1)
            self.assertEqual(manifest["stats"]["tier_2_signal_count"], 1)
            self.assertEqual(manifest["stats"]["request_template_count"], 3)

            report_payload = json.loads((output_dir / "signal_phase_request_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(report_payload["recommended_acquisition_path"], "restricted_data_request_required")
            self.assertEqual(
                report_payload["public_dataset_rows"][0]["dataset_classification"],
                "signal_inventory_public",
            )
            self.assertEqual(
                report_payload["public_dataset_rows"][1]["dataset_classification"],
                "mobility_context_public",
            )

            with (output_dir / "priority_signal_request_matrix.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["acquisition_path"], "restricted_data_request_required")

            self.assertTrue((output_dir / "request_templates" / "controller_event_log_export_request.md").exists())
            self.assertTrue((output_dir / "request_templates" / "signal_stage_plan_export_request.md").exists())
            self.assertTrue((output_dir / "request_templates" / "arm_phase_mapping_sheet_request.md").exists())


if __name__ == "__main__":
    unittest.main()
