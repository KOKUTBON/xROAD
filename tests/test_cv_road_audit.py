"""Unit tests for Computer Vision Road Safety Auditing & iRAP Feature Extraction Engine."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.cv_road_audit import (
    CV_CONTRACT_VERSION,
    CV_ENGINE_VERSION,
    AuditedSegmentFeatures,
    FrameSafetyObservation,
    RoadAssetDetection,
    aggregate_frame_detections_to_segments,
    export_cv_audit_artifacts,
    parse_frame_observations,
)


class TestCvRoadAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_frames = [
            {
                "frame_id": "frame-001",
                "segment_id": "seg-safe-01",
                "timestamp": "2026-05-10T14:30:00Z",
                "latitude": 41.1171,
                "longitude": 16.8719,
                "heading_deg": 180.0,
                "speed_kmh": 45.0,
                "detections": [
                    {
                        "detection_id": "d-001",
                        "asset_class": "median_barrier_concrete",
                        "confidence": 0.94,
                        "relative_position": "left",
                        "estimated_distance_m": 4.5,
                        "bbox": [0.4, 0.05, 0.8, 0.2],
                    },
                    {
                        "detection_id": "d-002",
                        "asset_class": "guardrail_w_beam",
                        "confidence": 0.91,
                        "relative_position": "roadside_right",
                        "estimated_distance_m": 5.0,
                    },
                    {
                        "detection_id": "d-003",
                        "asset_class": "paved_sidewalk",
                        "confidence": 0.88,
                        "relative_position": "right",
                        "estimated_distance_m": 6.0,
                    },
                    {
                        "detection_id": "d-004",
                        "asset_class": "crosswalk_zebra",
                        "confidence": 0.95,
                        "relative_position": "center",
                    },
                    {
                        "detection_id": "d-005",
                        "asset_class": "segregated_cycleway",
                        "confidence": 0.92,
                        "relative_position": "right",
                    },
                    {
                        "detection_id": "d-006",
                        "asset_class": "street_light",
                        "confidence": 0.89,
                        "relative_position": "roadside_right",
                    },
                    {
                        "detection_id": "d-007",
                        "asset_class": "crisp_marking",
                        "confidence": 0.96,
                    },
                ],
            },
            {
                "frame_id": "frame-002",
                "segment_id": "seg-hazardous-02",
                "timestamp": "2026-05-10T14:32:00Z",
                "latitude": 41.1250,
                "longitude": 16.8650,
                "detections": [
                    {
                        "detection_id": "d-010",
                        "asset_class": "rigid_pole",
                        "confidence": 0.92,
                        "relative_position": "roadside_right",
                        "estimated_distance_m": 2.0,
                    },
                    {
                        "detection_id": "d-011",
                        "asset_class": "tree_unshielded",
                        "confidence": 0.94,
                        "relative_position": "roadside_right",
                        "estimated_distance_m": 1.5,
                    },
                    {
                        "detection_id": "d-012",
                        "asset_class": "pothole",
                        "confidence": 0.87,
                        "relative_position": "center",
                        "estimated_distance_m": 3.0,
                    },
                    {
                        "detection_id": "d-013",
                        "asset_class": "pothole",
                        "confidence": 0.85,
                        "relative_position": "right",
                        "estimated_distance_m": 4.0,
                    },
                    {
                        "detection_id": "d-014",
                        "asset_class": "faded_marking",
                        "confidence": 0.90,
                    },
                ],
            },
        ]

        self.sample_segments = [
            {
                "segment_id": "seg-safe-01",
                "length_km": 0.5,
                "aadt": 8000.0,
                "operating_speed_kmh": 50.0,
                "lanes_numeric": 2,
                "width_numeric": 7.5,
            },
            {
                "segment_id": "seg-hazardous-02",
                "length_km": 0.4,
                "aadt": 12000.0,
                "operating_speed_kmh": 80.0,
                "lanes_numeric": 2,
                "width_numeric": 6.5,
            },
            {
                "segment_id": "seg-uninspected-03",
                "length_km": 0.8,
                "aadt": 3000.0,
                "operating_speed_kmh": 50.0,
                "has_sidewalk": True,
                "has_median_barrier": False,
            },
        ]

    def test_parse_frame_observations(self) -> None:
        obs = parse_frame_observations(self.sample_frames)
        self.assertEqual(len(obs), 2)
        self.assertIsInstance(obs[0], FrameSafetyObservation)
        self.assertEqual(obs[0].frame_id, "frame-001")
        self.assertEqual(obs[0].segment_id, "seg-safe-01")
        self.assertEqual(len(obs[0].detections), 7)

        d1 = obs[0].detections[0]
        self.assertIsInstance(d1, RoadAssetDetection)
        self.assertEqual(d1.asset_class, "median_barrier_concrete")
        self.assertAlmostEqual(d1.confidence, 0.94, places=2)
        self.assertEqual(d1.relative_position, "left")
        self.assertAlmostEqual(d1.estimated_distance_m, 4.5, places=1)
        self.assertEqual(d1.bbox, [0.4, 0.05, 0.8, 0.2])

    def test_aggregate_frame_detections_safe_corridor(self) -> None:
        obs = parse_frame_observations(self.sample_frames)
        audited = aggregate_frame_detections_to_segments(self.sample_segments, obs)
        self.assertEqual(len(audited), 3)

        safe_seg = next(s for s in audited if s.segment_id == "seg-safe-01")
        self.assertTrue(safe_seg.has_median_barrier)
        self.assertTrue(safe_seg.is_divided)
        self.assertTrue(safe_seg.has_roadside_barrier)
        self.assertTrue(safe_seg.has_sidewalk)
        self.assertTrue(safe_seg.has_pedestrian_crossing)
        self.assertTrue(safe_seg.has_segregated_cycle_facility)
        self.assertTrue(safe_seg.street_lighting_detected)
        self.assertAlmostEqual(safe_seg.roadside_hazard_severity, 0.2, places=2)
        self.assertAlmostEqual(safe_seg.marking_quality_score, 1.0, places=2)
        self.assertEqual(safe_seg.pothole_count_total, 0)
        self.assertEqual(safe_seg.total_frames_analyzed, 1)

        # Automated iRAP rating evaluation
        irap = safe_seg.irap_star_ratings
        self.assertIn("vehicle_occupant", irap)
        self.assertIn("pedestrian", irap)
        self.assertGreaterEqual(irap["vehicle_occupant"]["star_rating"], 3)
        self.assertGreaterEqual(irap["pedestrian"]["star_rating"], 3)
        self.assertTrue(irap["meets_un_target_4"])

    def test_aggregate_frame_detections_hazardous_corridor(self) -> None:
        obs = parse_frame_observations(self.sample_frames)
        audited = aggregate_frame_detections_to_segments(self.sample_segments, obs)

        haz_seg = next(s for s in audited if s.segment_id == "seg-hazardous-02")
        self.assertFalse(haz_seg.has_median_barrier)
        self.assertFalse(haz_seg.has_roadside_barrier)
        self.assertFalse(haz_seg.has_sidewalk)
        self.assertFalse(haz_seg.has_pedestrian_crossing)
        self.assertFalse(haz_seg.has_segregated_cycle_facility)
        # 2 rigid hazards detected without guardrails -> severity 0.85
        self.assertAlmostEqual(haz_seg.roadside_hazard_severity, 0.85, places=2)
        self.assertEqual(haz_seg.pothole_count_total, 2)
        self.assertAlmostEqual(haz_seg.pothole_density_per_km, 5.0, places=2)  # 2 / 0.4 km = 5.0
        self.assertAlmostEqual(haz_seg.marking_quality_score, 0.0, places=2)  # faded markings only

        # High speed + roadside hazards + no pedestrian protection -> fails UN target 4
        irap = haz_seg.irap_star_ratings
        self.assertFalse(irap["meets_un_target_4"])
        self.assertLessEqual(irap["pedestrian"]["star_rating"], 2)

    def test_uninspected_segment_metadata_fallback(self) -> None:
        obs = parse_frame_observations(self.sample_frames)
        audited = aggregate_frame_detections_to_segments(self.sample_segments, obs)

        uninspected = next(s for s in audited if s.segment_id == "seg-uninspected-03")
        self.assertEqual(uninspected.total_frames_analyzed, 0)
        self.assertTrue(uninspected.has_sidewalk)
        self.assertFalse(uninspected.has_median_barrier)
        self.assertEqual(uninspected.pothole_count_total, 0)

    def test_export_cv_audit_artifacts(self) -> None:
        obs = parse_frame_observations(self.sample_frames)
        audited = aggregate_frame_detections_to_segments(self.sample_segments, obs)

        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = Path(temp_dir)
            files = export_cv_audit_artifacts(
                audited_segments=audited,
                raw_observations=obs,
                output_dir=out_path,
                network_label="test_network",
            )

            for key in ["segments_csv", "assets_csv", "bundle_json", "report_md", "manifest"]:
                self.assertIn(key, files)
                p = Path(files[key])
                self.assertTrue(p.exists(), f"File {files[key]} should exist")
                self.assertGreater(p.stat().st_size, 0)

            # Validate Bundle JSON content
            bundle = json.loads(Path(files["bundle_json"]).read_text(encoding="utf-8"))
            self.assertEqual(bundle["cv_engine_version"], CV_ENGINE_VERSION)
            self.assertEqual(bundle["contract_version"], CV_CONTRACT_VERSION)
            self.assertEqual(bundle["network_label"], "test_network")
            self.assertEqual(bundle["summary"]["total_segments_audited"], 3)
            self.assertEqual(bundle["summary"]["total_inspection_frames"], 2)
            self.assertEqual(bundle["summary"]["total_assets_detected"], 12)
            self.assertEqual(bundle["summary"]["total_potholes_detected"], 2)

            # Validate Manifest
            manifest = json.loads(Path(files["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_family"], "computer_vision_road_audit")
            self.assertIn("files", manifest)
            self.assertIn("segments_csv", manifest["files"])
            self.assertIn("sha256", manifest["files"]["segments_csv"])


if __name__ == "__main__":
    unittest.main()
