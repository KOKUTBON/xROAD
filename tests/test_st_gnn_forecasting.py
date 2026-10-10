"""Unit tests for Spatio-Temporal Graph Neural Network (ST-GNN) Crash Risk Forecasting Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.st_gnn_forecasting import (
    ST_GNN_CONTRACT_VERSION,
    ST_GNN_ENGINE_VERSION,
    GraphEdge,
    HighRiskCorridorAlert,
    RoadGraphNode,
    SegmentRiskForecast,
    SpatioTemporalFeatureFrame,
    build_network_graph_adjacency,
    execute_st_gnn_forecast,
    export_st_gnn_artifacts,
)


class TestStGnnForecasting(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_nodes = [
            RoadGraphNode(
                segment_id="seg-1",
                length_km=0.5,
                free_flow_speed_kmh=50.0,
                functional_class="urban_arterial",
                latitude=41.1171,
                longitude=16.8719,
            ),
            RoadGraphNode(
                segment_id="seg-2",
                length_km=0.4,
                free_flow_speed_kmh=50.0,
                functional_class="urban_arterial",
                latitude=41.1150,
                longitude=16.8710,
            ),
            RoadGraphNode(
                segment_id="seg-3",
                length_km=0.6,
                free_flow_speed_kmh=60.0,
                functional_class="urban_collector",
                latitude=41.1120,
                longitude=16.8700,
            ),
        ]

        self.sample_edges = [
            GraphEdge(from_segment_id="seg-1", to_segment_id="seg-2", distance_m=200.0, weight=1.0),
            GraphEdge(from_segment_id="seg-2", to_segment_id="seg-3", distance_m=350.0, weight=0.9),
        ]

        # Scenario: seg-2 has severe storm and high near misses; seg-3 is dry
        self.sample_frames = [
            SpatioTemporalFeatureFrame(
                segment_id="seg-1",
                timestamp="2026-05-18T12:00:00Z",
                historical_crash_count=2.0,
                telematics_near_miss_rate=40.0,
                current_speed_kmh=45.0,
                speed_ratio=0.90,
                precipitation_mm_h=2.0,
                surface_condition="wet",
            ),
            SpatioTemporalFeatureFrame(
                segment_id="seg-2",
                timestamp="2026-05-18T12:00:00Z",
                historical_crash_count=5.0,
                telematics_near_miss_rate=180.0,
                current_speed_kmh=20.0,
                speed_ratio=0.40,
                precipitation_mm_h=15.0,
                surface_condition="wet",
                is_peak_hour=True,
            ),
            SpatioTemporalFeatureFrame(
                segment_id="seg-3",
                timestamp="2026-05-18T12:00:00Z",
                historical_crash_count=0.5,
                telematics_near_miss_rate=10.0,
                current_speed_kmh=58.0,
                speed_ratio=0.97,
                precipitation_mm_h=0.0,
                surface_condition="dry",
            ),
        ]

    def test_build_network_graph_adjacency(self) -> None:
        node_index, P, A_adp = build_network_graph_adjacency(self.sample_nodes, self.sample_edges)
        self.assertEqual(len(node_index), 3)
        self.assertIn("seg-1", node_index)
        self.assertIn("seg-2", node_index)
        self.assertIn("seg-3", node_index)

        # Transition matrix row-sum normalization
        for i in range(3):
            row_sum = sum(P[i])
            self.assertAlmostEqual(row_sum, 1.0, places=3)
            adp_row_sum = sum(A_adp[i])
            self.assertAlmostEqual(adp_row_sum, 1.0, places=3)

    def test_execute_st_gnn_forecast(self) -> None:
        forecasts, alerts = execute_st_gnn_forecast(
            nodes=self.sample_nodes,
            time_series_frames=self.sample_frames,
            edges=self.sample_edges,
            horizons=[1, 6, 24],
        )

        # 3 nodes * 3 horizons = 9 forecasts
        self.assertEqual(len(forecasts), 9)

        # Check forecasts for seg-2 (severe shock) vs seg-3 (nominal)
        seg2_h1 = next(f for f in forecasts if f.segment_id == "seg-2" and f.horizon_hours == 1)
        seg3_h1 = next(f for f in forecasts if f.segment_id == "seg-3" and f.horizon_hours == 1)

        self.assertGreater(seg2_h1.crash_probability, 0.70)
        self.assertEqual(seg2_h1.alert_tier, "critical")
        self.assertIn("severe_weather_low_friction", seg2_h1.contributing_factors)
        self.assertIn("high_kinematic_near_miss_density", seg2_h1.contributing_factors)

        self.assertLess(seg3_h1.crash_probability, seg2_h1.crash_probability)

        # Check multi-horizon persistence
        seg2_h6 = next(f for f in forecasts if f.segment_id == "seg-2" and f.horizon_hours == 6)
        seg2_h24 = next(f for f in forecasts if f.segment_id == "seg-2" and f.horizon_hours == 24)
        self.assertGreater(seg2_h6.crash_probability, 0.50)
        self.assertGreater(seg2_h24.crash_probability, 0.40)

        # Check alerts generated
        self.assertGreater(len(alerts), 0)
        top_alert = alerts[0]
        self.assertIn(top_alert.alert_tier, {"critical", "high"})
        self.assertGreater(top_alert.crash_probability, 0.50)

    def test_export_st_gnn_artifacts(self) -> None:
        forecasts, alerts = execute_st_gnn_forecast(
            nodes=self.sample_nodes,
            time_series_frames=self.sample_frames,
            edges=self.sample_edges,
            horizons=[1, 6],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            files = export_st_gnn_artifacts(
                forecasts=forecasts,
                alerts=alerts,
                output_dir=out_dir,
                network_label="test_st_gnn",
            )

            for key in ["forecasts_csv", "alerts_csv", "bundle_json", "bulletin_md", "manifest"]:
                self.assertIn(key, files)
                p = Path(files[key])
                self.assertTrue(p.exists(), f"{key} should exist")
                self.assertGreater(p.stat().st_size, 0)

            # Validate Bundle JSON
            bundle = json.loads(Path(files["bundle_json"]).read_text(encoding="utf-8"))
            self.assertEqual(bundle["st_gnn_engine_version"], ST_GNN_ENGINE_VERSION)
            self.assertEqual(bundle["contract_version"], ST_GNN_CONTRACT_VERSION)
            self.assertEqual(bundle["network_label"], "test_st_gnn")
            self.assertEqual(bundle["summary"]["total_segments_forecasted"], 3)
            self.assertEqual(bundle["summary"]["total_predictions_generated"], 6)

            # Validate Manifest
            manifest = json.loads(Path(files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "spatio_temporal_graph_risk_forecasting")
            self.assertIn("forecasts_csv", manifest["files"])
            self.assertIn("sha256", manifest["files"]["forecasts_csv"])


if __name__ == "__main__":
    unittest.main()
