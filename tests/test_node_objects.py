from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.node_objects import (
    build_bari_conflict_zones,
    build_bari_crossing_and_approach_objects,
    build_bari_movement_objects,
    build_bari_signal_nodes,
)


class NodeObjectTests(unittest.TestCase):
    def test_build_bari_signal_nodes_writes_geojson_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import LineString  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            source_path = root / "signals.tsv"
            segments_path = root / "segments.geojson"
            output_dir = root / "nodes"
            raw_dir = root / "raw"

            source_path.write_text(
                '"id"\t"name"\t"folders"\t"description"\t"altitude"\t"alt_mode"\t"time_begin"\t"time_end"\t"time_when"\t"Codice"\t"LATITUDINE"\t"LONGITUDINE"\t"TIPO"\n'
                '1\tVIA A - VIA B\tBari_coordinate.xlsx\tDescrizione\t0.0\t\t\t\t\tABC01\t41.1100\t16.8700\tITS 2 MONKEY IMP. SEMAF.\n'
                '2\tVIA C - VIA D\tBari_coordinate.xlsx\tDescrizione\t0.0\t\t\t\t\tABC02\t41.1110\t16.8710\tITS 2 MONKEY IMP. SEMAF.\n',
                encoding="utf-8",
            )

            gpd.GeoDataFrame(
                [
                    {
                        "segment_id": "seg-1",
                        "highway": "primary",
                        "ref": "SS16",
                        "junction": "",
                        "geometry": LineString([(16.8695, 41.1095), (16.8715, 41.1115)]),
                    }
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(segments_path, driver="GeoJSON")

            manifest = build_bari_signal_nodes(
                output_dir=output_dir,
                segments_path=segments_path,
                source_url=source_path,
                raw_dir=raw_dir,
            )

            self.assertEqual(manifest["stats"]["node_object_count"], 2)
            self.assertEqual(manifest["stats"]["snapped_node_count"], 2)
            self.assertTrue((output_dir / "traffic_signal_nodes.geojson").exists())
            self.assertTrue((output_dir / "traffic_signal_nodes.manifest.json").exists())
            self.assertTrue((raw_dir / "bari_semafori.csv").exists())

    def test_build_bari_crossing_and_approach_objects_writes_combined_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import LineString, Point, Polygon  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            signals_path = root / "signals.geojson"
            segments_path = root / "segments.geojson"
            boundary_path = root / "boundary.geojson"
            crossings_path = root / "crossings.geojson"
            output_dir = root / "objects"

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "it-bari-signal-1",
                        "junction_id": "it-bari-signal-1",
                        "object_type": "traffic_signal",
                        "node_role": "signalized_junction",
                        "name": "VIA A - VIA B",
                        "signal_type": "IMP. SEMAF",
                        "asset_code": "ABC01",
                        "geometry": Point(16.87, 41.11),
                    }
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(signals_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [
                    {
                        "u": "n1",
                        "v": "n2",
                        "segment_id": "seg-1",
                        "highway": "primary",
                        "name": "Via A",
                        "ref": "SS16",
                        "junction": "",
                        "segment_length_m": 150.0,
                        "geometry": LineString([(16.87, 41.11), (16.872, 41.11)]),
                    },
                    {
                        "u": "n3",
                        "v": "n4",
                        "segment_id": "seg-2",
                        "highway": "secondary",
                        "name": "Via B",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 150.0,
                        "geometry": LineString([(16.87, 41.11), (16.87, 41.112)]),
                    },
                    {
                        "u": "n5",
                        "v": "n6",
                        "segment_id": "seg-3",
                        "highway": "tertiary",
                        "name": "Via C",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 150.0,
                        "geometry": LineString([(16.87, 41.11), (16.868, 41.11)]),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(segments_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [{"geometry": Polygon([(16.865, 41.105), (16.875, 41.105), (16.875, 41.115), (16.865, 41.115)])}],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(boundary_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [
                    {
                        "element": "node",
                        "osmid": "123",
                        "highway": "crossing",
                        "crossing": "traffic_signals",
                        "crossing:markings": "zebra",
                        "geometry": Point(16.8702, 41.1102),
                    }
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(crossings_path, driver="GeoJSON")

            manifest = build_bari_crossing_and_approach_objects(
                output_dir=output_dir,
                signal_nodes_path=signals_path,
                segments_path=segments_path,
                boundary_path=boundary_path,
                crossings_path=crossings_path,
                raw_dir=None,
                approach_distance_m=20.0,
                junction_buffer_m=30.0,
                signal_link_m=40.0,
            )

            self.assertEqual(manifest["stats"]["signal_anchor_count"], 1)
            self.assertEqual(manifest["stats"]["junction_approach_count"], 3)
            self.assertEqual(manifest["stats"]["crossing_object_count"], 1)
            self.assertEqual(manifest["stats"]["unsignalized_junction_count"], 0)
            self.assertEqual(manifest["stats"]["roundabout_object_count"], 0)
            self.assertEqual(manifest["stats"]["total_node_object_count"], 4)
            self.assertTrue((output_dir / "road_node_objects.geojson").exists())
            self.assertTrue((output_dir / "road_node_objects.manifest.json").exists())

    def test_build_bari_crossing_and_approach_objects_adds_unsignalized_and_roundabout_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import LineString, Point, Polygon  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            signals_path = root / "signals.geojson"
            segments_path = root / "segments.geojson"
            boundary_path = root / "boundary.geojson"
            crossings_path = root / "crossings.geojson"
            output_dir = root / "objects"

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "it-bari-signal-1",
                        "junction_id": "it-bari-signal-1",
                        "object_type": "traffic_signal",
                        "node_role": "signalized_junction",
                        "name": "FAR SIGNAL",
                        "signal_type": "IMP. SEMAF",
                        "asset_code": "ABC01",
                        "geometry": Point(16.90, 41.14),
                    }
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(signals_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [
                    {
                        "u": "j1",
                        "v": "a1",
                        "segment_id": "seg-1",
                        "highway": "primary",
                        "name": "Via Nord",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.87, 41.11), (16.87, 41.111)]),
                    },
                    {
                        "u": "j1",
                        "v": "a2",
                        "segment_id": "seg-2",
                        "highway": "secondary",
                        "name": "Via Sud",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.87, 41.11), (16.87, 41.109)]),
                    },
                    {
                        "u": "j1",
                        "v": "a3",
                        "segment_id": "seg-3",
                        "highway": "tertiary",
                        "name": "Via Est",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.87, 41.11), (16.871, 41.11)]),
                    },
                    {
                        "u": "j1",
                        "v": "a4",
                        "segment_id": "seg-4",
                        "highway": "tertiary",
                        "name": "Via Ovest",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 100.0,
                        "geometry": LineString([(16.87, 41.11), (16.869, 41.11)]),
                    },
                    {
                        "u": "r1",
                        "v": "r2",
                        "segment_id": "seg-5",
                        "highway": "primary",
                        "name": "Rotatoria A",
                        "ref": "",
                        "junction": "roundabout",
                        "segment_length_m": 80.0,
                        "geometry": LineString([(16.875, 41.115), (16.8755, 41.1155)]),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(segments_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [{"geometry": Polygon([(16.865, 41.105), (16.885, 41.105), (16.885, 41.125), (16.865, 41.125)])}],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(boundary_path, driver="GeoJSON")

            gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326").to_file(
                crossings_path,
                driver="GeoJSON",
            )

            manifest = build_bari_crossing_and_approach_objects(
                output_dir=output_dir,
                signal_nodes_path=signals_path,
                segments_path=segments_path,
                boundary_path=boundary_path,
                crossings_path=crossings_path,
                raw_dir=None,
                approach_distance_m=20.0,
                junction_buffer_m=30.0,
                signal_link_m=40.0,
                unsignalized_min_degree=4,
                unsignalized_major_edge_min=2,
            )

            self.assertEqual(manifest["stats"]["junction_approach_count"], 0)
            self.assertEqual(manifest["stats"]["crossing_object_count"], 0)
            self.assertEqual(manifest["stats"]["unsignalized_junction_count"], 1)
            self.assertEqual(manifest["stats"]["roundabout_object_count"], 2)
            self.assertEqual(manifest["stats"]["total_node_object_count"], 3)

    def test_build_bari_conflict_zones_writes_zone_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import LineString, Point, Polygon  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            node_objects_path = root / "node_objects.geojson"
            segments_path = root / "segments.geojson"
            output_dir = root / "zones"

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "cross-1",
                        "junction_id": "cross-1",
                        "source_system": "osm_crossing_features",
                        "object_type": "crossing",
                        "node_role": "pedestrian_crossing",
                        "name": "Crossing A",
                        "crossing_type": "traffic_signals",
                        "segment_id": "seg-1",
                        "segment_highway": "primary",
                        "segment_name": "Via A",
                        "segment_ref": "SS16",
                        "segment_junction": "",
                        "geometry": Point(16.8702, 41.1102),
                    },
                    {
                        "node_object_id": "approach-1",
                        "junction_id": "signal-1",
                        "source_system": "bari_signal_network_approach_builder",
                        "object_type": "junction_approach",
                        "node_role": "junction_approach",
                        "name": "Via A",
                        "signal_type": "IMP. SEMAF",
                        "segment_id": "seg-1",
                        "segment_highway": "primary",
                        "segment_name": "Via A",
                        "segment_ref": "SS16",
                        "segment_junction": "",
                        "approach_endpoint_role": "start",
                        "approach_distance_m": 20.0,
                        "geometry": Point(16.8701, 41.1100),
                    },
                    {
                        "node_object_id": "junction-1",
                        "junction_id": "junction-1",
                        "source_system": "bari_network_junction_builder",
                        "object_type": "unsignalized_junction",
                        "node_role": "unsignalized_junction",
                        "name": "Via A | Via B",
                        "segment_id": "seg-2",
                        "segment_highway": "secondary",
                        "segment_name": "Via B",
                        "segment_ref": "",
                        "segment_junction": "",
                        "network_node_ref": "j1",
                        "incident_edge_count": 4,
                        "major_edge_count": 2,
                        "roundabout_edge_count": 0,
                        "geometry": Point(16.8720, 41.1120),
                    },
                    {
                        "node_object_id": "round-1",
                        "junction_id": "round-1",
                        "source_system": "bari_network_roundabout_builder",
                        "object_type": "roundabout",
                        "node_role": "roundabout_junction",
                        "name": "Roundabout A",
                        "segment_id": "seg-rb",
                        "segment_highway": "primary",
                        "segment_name": "Rotatoria A",
                        "segment_ref": "",
                        "segment_junction": "roundabout",
                        "network_node_ref": "r1",
                        "incident_edge_count": 3,
                        "major_edge_count": 2,
                        "roundabout_edge_count": 1,
                        "geometry": Point(16.8750, 41.1150),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(node_objects_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [
                    {
                        "u": "s1",
                        "v": "s2",
                        "segment_id": "seg-1",
                        "highway": "primary",
                        "name": "Via A",
                        "ref": "SS16",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8700, 41.1100), (16.8720, 41.1100)]),
                    },
                    {
                        "u": "s1",
                        "v": "s3",
                        "segment_id": "seg-1-west",
                        "highway": "primary",
                        "name": "Via Ovest",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8700, 41.1100), (16.8690, 41.1100)]),
                    },
                    {
                        "u": "s1",
                        "v": "s4",
                        "segment_id": "seg-1-north",
                        "highway": "secondary",
                        "name": "Via Nord",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8700, 41.1100), (16.8700, 41.1110)]),
                    },
                    {
                        "u": "j1",
                        "v": "b2",
                        "segment_id": "seg-2",
                        "highway": "secondary",
                        "name": "Via B",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8730, 41.1120)]),
                    },
                    {
                        "u": "j1",
                        "v": "b3",
                        "segment_id": "seg-2-west",
                        "highway": "secondary",
                        "name": "Via B Ovest",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8710, 41.1120)]),
                    },
                    {
                        "u": "j1",
                        "v": "b4",
                        "segment_id": "seg-2-north",
                        "highway": "tertiary",
                        "name": "Via B Nord",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8720, 41.1130)]),
                    },
                    {
                        "u": "j1",
                        "v": "b5",
                        "segment_id": "seg-2-south",
                        "highway": "tertiary",
                        "name": "Via B Sud",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8720, 41.1110)]),
                    },
                    {
                        "u": "r1",
                        "v": "r2",
                        "segment_id": "seg-rb",
                        "highway": "primary",
                        "name": "Rotatoria A",
                        "ref": "",
                        "junction": "roundabout",
                        "segment_length_m": 90.0,
                        "geometry": LineString([(16.8750, 41.1150), (16.8755, 41.1155)]),
                    },
                    {
                        "u": "r1",
                        "v": "r3",
                        "segment_id": "seg-entry",
                        "highway": "secondary",
                        "name": "Via ingresso",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 110.0,
                        "geometry": LineString([(16.8750, 41.1150), (16.8760, 41.1150)]),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(segments_path, driver="GeoJSON")

            manifest = build_bari_conflict_zones(
                output_dir=output_dir,
                node_objects_path=node_objects_path,
                segments_path=segments_path,
                crossing_radius_m=10.0,
                unsignalized_radius_m=18.0,
                roundabout_fallback_radius_m=14.0,
                junction_approach_length_m=15.0,
                roundabout_entry_length_m=16.0,
                default_zone_half_width_m=5.0,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_conflict_zone_builder")
            self.assertEqual(manifest["stats"]["crossing_conflict_zone_count"], 1)
            self.assertEqual(manifest["stats"]["junction_approach_conflict_zone_count"], 1)
            self.assertEqual(manifest["stats"]["unsignalized_junction_conflict_zone_count"], 1)
            self.assertEqual(manifest["stats"]["roundabout_entry_conflict_zone_count"], 1)
            self.assertEqual(manifest["stats"]["roundabout_fallback_conflict_zone_count"], 0)
            self.assertEqual(manifest["stats"]["total_conflict_zone_count"], 4)
            self.assertEqual(
                manifest["stats"]["movement_family_counts"],
                {
                    "approach": 1,
                    "crossing": 1,
                    "junction_area": 1,
                    "roundabout_entry": 1,
                },
            )
            self.assertEqual(
                manifest["stats"]["control_state_counts"],
                {
                    "signalized": 2,
                    "unsignalized_multi_arm": 1,
                    "yield_controlled": 1,
                },
            )
            self.assertEqual(
                manifest["stats"]["turn_option_catalog_counts"],
                {
                    "left | straight | right": 1,
                    "pedestrian_crossing": 1,
                    "right": 1,
                    "straight | right": 1,
                },
            )
            self.assertEqual(
                manifest["stats"]["maneuver_complexity_counts"],
                {
                    "crossing_only": 1,
                    "limited_choice": 1,
                    "multi_choice": 1,
                    "single_choice": 1,
                },
            )
            self.assertTrue((output_dir / "road_conflict_zones.geojson").exists())
            self.assertTrue((output_dir / "road_conflict_zones.manifest.json").exists())

            zones = gpd.read_file(output_dir / "road_conflict_zones.geojson")
            self.assertEqual(len(zones), 4)

            crossing_zone = zones.loc[zones["zone_type"] == "crossing_conflict_zone"].iloc[0]
            self.assertEqual(crossing_zone["movement_family"], "crossing")
            self.assertEqual(crossing_zone["control_state"], "signalized")
            self.assertEqual(crossing_zone["crossing_protection_state"], "signalized")
            self.assertEqual(crossing_zone["turn_path_class"], "pedestrian_crossing")
            self.assertEqual(crossing_zone["priority_rule"], "controlled")

            approach_zone = zones.loc[zones["zone_type"] == "junction_approach_conflict_zone"].iloc[0]
            self.assertEqual(approach_zone["movement_family"], "approach")
            self.assertEqual(approach_zone["control_state"], "signalized")
            self.assertEqual(approach_zone["turn_path_class"], "approach_to_signal")
            self.assertEqual(approach_zone["priority_rule"], "signal_controlled")
            self.assertEqual(approach_zone["approach_node_ref"], "s1")
            self.assertEqual(approach_zone["approach_compass"], "E")
            self.assertEqual(approach_zone["connected_arm_count"], 3)
            self.assertEqual(approach_zone["turn_option_catalog"], "straight | right")
            self.assertEqual(approach_zone["turn_option_count"], 2)
            self.assertEqual(approach_zone["maneuver_complexity"], "limited_choice")

            junction_zone = zones.loc[zones["zone_type"] == "unsignalized_junction_conflict_zone"].iloc[0]
            self.assertEqual(junction_zone["movement_family"], "junction_area")
            self.assertEqual(junction_zone["control_state"], "unsignalized_multi_arm")
            self.assertEqual(junction_zone["turn_path_class"], "multi_arm_intersection")
            self.assertEqual(junction_zone["movement_arm_count"], 4)
            self.assertEqual(junction_zone["priority_rule"], "major_minor_priority")
            self.assertEqual(junction_zone["approach_node_ref"], "j1")
            self.assertEqual(junction_zone["connected_arm_count"], 4)
            self.assertEqual(junction_zone["arm_compass_catalog"], "E | N | S | W")
            self.assertEqual(junction_zone["turn_option_catalog"], "left | straight | right")
            self.assertEqual(junction_zone["turn_option_count"], 3)
            self.assertEqual(junction_zone["maneuver_complexity"], "multi_choice")

            roundabout_zone = zones.loc[zones["zone_type"] == "roundabout_entry_conflict_zone"].iloc[0]
            self.assertEqual(roundabout_zone["movement_family"], "roundabout_entry")
            self.assertEqual(roundabout_zone["control_state"], "yield_controlled")
            self.assertEqual(roundabout_zone["turn_path_class"], "roundabout_entry_merge")
            self.assertEqual(roundabout_zone["priority_rule"], "yield_to_circulating")
            self.assertEqual(roundabout_zone["approach_node_ref"], "r1")
            self.assertEqual(roundabout_zone["approach_compass"], "E")
            self.assertEqual(roundabout_zone["turn_option_catalog"], "right")
            self.assertEqual(roundabout_zone["turn_option_count"], 1)
            self.assertEqual(roundabout_zone["roundabout_component_role"], "entry")

    def test_build_bari_movement_objects_writes_explicit_turn_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import LineString, Point  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            conflict_zones_path = root / "road_conflict_zones.geojson"
            segments_path = root / "segments.geojson"
            output_dir = root / "movements"

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "cross-zone",
                        "junction_id": "cross-zone",
                        "object_type": "conflict_zone",
                        "node_role": "conflict_zone",
                        "zone_type": "crossing_conflict_zone",
                        "parent_object_id": "cross-1",
                        "parent_object_type": "crossing",
                        "name": "Crossing A",
                        "movement_family": "crossing",
                        "control_state": "signalized",
                        "crossing_protection_state": "signalized",
                        "turn_path_class": "pedestrian_crossing",
                        "movement_arm_count": 2,
                        "priority_rule": "controlled",
                        "control_detail": "traffic_signals",
                        "segment_id": "seg-1",
                        "segment_highway": "primary",
                        "segment_name": "Via A",
                        "segment_ref": "SS16",
                        "segment_junction": "",
                        "geometry": Point(16.8702, 41.1102),
                    },
                    {
                        "node_object_id": "approach-zone",
                        "junction_id": "signal-1",
                        "object_type": "conflict_zone",
                        "node_role": "conflict_zone",
                        "zone_type": "junction_approach_conflict_zone",
                        "parent_object_id": "approach-1",
                        "parent_object_type": "junction_approach",
                        "name": "Via A",
                        "movement_family": "approach",
                        "control_state": "signalized",
                        "turn_path_class": "approach_to_signal",
                        "priority_rule": "signal_controlled",
                        "control_detail": "IMP. SEMAF",
                        "approach_node_ref": "s1",
                        "approach_arm_id": "seg-1:start",
                        "approach_bearing_deg": 90.0,
                        "approach_compass": "E",
                        "turn_option_catalog": "straight | right",
                        "maneuver_complexity": "limited_choice",
                        "segment_id": "seg-1",
                        "segment_highway": "primary",
                        "segment_name": "Via A",
                        "segment_ref": "SS16",
                        "segment_junction": "",
                        "geometry": Point(16.8700, 41.1100),
                    },
                    {
                        "node_object_id": "junction-zone",
                        "junction_id": "junction-1",
                        "object_type": "conflict_zone",
                        "node_role": "conflict_zone",
                        "zone_type": "unsignalized_junction_conflict_zone",
                        "parent_object_id": "junction-1",
                        "parent_object_type": "unsignalized_junction",
                        "name": "Via A | Via B",
                        "movement_family": "junction_area",
                        "control_state": "unsignalized_multi_arm",
                        "turn_path_class": "multi_arm_intersection",
                        "movement_arm_count": 4,
                        "priority_rule": "major_minor_priority",
                        "control_detail": "incident_edges=4;major_edges=2",
                        "approach_node_ref": "j1",
                        "network_node_ref": "j1",
                        "turn_option_catalog": "left | straight | right",
                        "maneuver_complexity": "multi_choice",
                        "segment_id": "seg-2",
                        "segment_highway": "secondary",
                        "segment_name": "Via B",
                        "segment_ref": "",
                        "segment_junction": "",
                        "geometry": Point(16.8720, 41.1120),
                    },
                    {
                        "node_object_id": "round-zone",
                        "junction_id": "round-1",
                        "object_type": "conflict_zone",
                        "node_role": "conflict_zone",
                        "zone_type": "roundabout_entry_conflict_zone",
                        "parent_object_id": "round-1",
                        "parent_object_type": "roundabout",
                        "name": "Roundabout A",
                        "movement_family": "roundabout_entry",
                        "control_state": "yield_controlled",
                        "turn_path_class": "roundabout_entry_merge",
                        "movement_arm_count": 3,
                        "priority_rule": "yield_to_circulating",
                        "control_detail": "secondary",
                        "approach_node_ref": "r1",
                        "approach_arm_id": "seg-entry:start",
                        "approach_bearing_deg": 90.0,
                        "approach_compass": "E",
                        "turn_option_catalog": "right",
                        "maneuver_complexity": "single_choice",
                        "roundabout_component_role": "entry",
                        "segment_id": "seg-entry",
                        "segment_highway": "secondary",
                        "segment_name": "Via ingresso",
                        "segment_ref": "",
                        "segment_junction": "",
                        "geometry": Point(16.8750, 41.1150),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(conflict_zones_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [
                    {
                        "u": "s1",
                        "v": "s2",
                        "segment_id": "seg-1",
                        "highway": "primary",
                        "name": "Via A",
                        "ref": "SS16",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8700, 41.1100), (16.8720, 41.1100)]),
                    },
                    {
                        "u": "s1",
                        "v": "s3",
                        "segment_id": "seg-1-west",
                        "highway": "primary",
                        "name": "Via Ovest",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8700, 41.1100), (16.8690, 41.1100)]),
                    },
                    {
                        "u": "s1",
                        "v": "s4",
                        "segment_id": "seg-1-north",
                        "highway": "secondary",
                        "name": "Via Nord",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8700, 41.1100), (16.8700, 41.1110)]),
                    },
                    {
                        "u": "j1",
                        "v": "b2",
                        "segment_id": "seg-2",
                        "highway": "secondary",
                        "name": "Via B",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8730, 41.1120)]),
                    },
                    {
                        "u": "j1",
                        "v": "b3",
                        "segment_id": "seg-2-west",
                        "highway": "secondary",
                        "name": "Via B Ovest",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8710, 41.1120)]),
                    },
                    {
                        "u": "j1",
                        "v": "b4",
                        "segment_id": "seg-2-north",
                        "highway": "tertiary",
                        "name": "Via B Nord",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8720, 41.1130)]),
                    },
                    {
                        "u": "j1",
                        "v": "b5",
                        "segment_id": "seg-2-south",
                        "highway": "tertiary",
                        "name": "Via B Sud",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.8720, 41.1120), (16.8720, 41.1110)]),
                    },
                    {
                        "u": "r1",
                        "v": "r2",
                        "segment_id": "seg-rb",
                        "highway": "primary",
                        "name": "Rotatoria A",
                        "ref": "",
                        "junction": "roundabout",
                        "segment_length_m": 90.0,
                        "geometry": LineString([(16.8750, 41.1150), (16.8755, 41.1155)]),
                    },
                    {
                        "u": "r1",
                        "v": "r3",
                        "segment_id": "seg-entry",
                        "highway": "secondary",
                        "name": "Via ingresso",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 110.0,
                        "geometry": LineString([(16.8750, 41.1150), (16.8760, 41.1150)]),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(segments_path, driver="GeoJSON")

            manifest = build_bari_movement_objects(
                output_dir=output_dir,
                conflict_zones_path=conflict_zones_path,
                segments_path=segments_path,
                movement_offset_m=8.0,
            )

            self.assertEqual(manifest["source"]["adapter"], "bari_movement_object_builder")
            self.assertEqual(manifest["stats"]["source_conflict_zone_count"], 4)
            self.assertEqual(manifest["stats"]["movement_object_count"], 16)
            self.assertEqual(
                manifest["stats"]["movement_role_counts"],
                {
                    "pedestrian_crossing": 1,
                    "roundabout_entry_movement": 1,
                    "signalized_turn_movement": 2,
                    "unsignalized_turn_movement": 12,
                },
            )
            self.assertEqual(
                manifest["stats"]["movement_turn_counts"],
                {"cross": 1, "left": 4, "right": 6, "straight": 5},
            )
            self.assertEqual(
                manifest["stats"]["movement_resolution_method_counts"],
                {
                    "crossing_zone_center": 1,
                    "single_candidate_turn_match": 15,
                },
            )
            self.assertTrue((output_dir / "road_movement_objects.geojson").exists())
            self.assertTrue((output_dir / "road_movement_objects.manifest.json").exists())

            movements = gpd.read_file(output_dir / "road_movement_objects.geojson")
            self.assertEqual(len(movements), 16)

            approach_straight = movements.loc[
                movements["node_object_id"] == "approach-zone::movement::seg_1_start::straight::seg_1_west_start"
            ].iloc[0]
            self.assertEqual(approach_straight["movement_turn"], "straight")
            self.assertEqual(approach_straight["incoming_arm_id"], "seg-1:start")
            self.assertEqual(approach_straight["outgoing_arm_id"], "seg-1-west:start")
            self.assertEqual(approach_straight["outgoing_compass"], "W")
            self.assertEqual(approach_straight["candidate_target_arm_count"], 1)
            self.assertIn("seg-1-west:start@W", approach_straight["candidate_target_arm_catalog"])
            self.assertEqual(approach_straight["movement_resolution_state"], "explicit_target")
            self.assertEqual(approach_straight["movement_resolution_method"], "single_candidate_turn_match")
            self.assertEqual(approach_straight["signal_priority_variant"], "signal_phase_unknown")
            self.assertEqual(approach_straight["phase_priority_group"], "signalized_aligned_turn_phase_unknown")

            junction_left = movements.loc[
                movements["node_object_id"] == "junction-zone::movement::seg_2_start::left::seg_2_south_start"
            ].iloc[0]
            self.assertEqual(junction_left["movement_role"], "unsignalized_turn_movement")
            self.assertEqual(junction_left["incoming_compass"], "E")
            self.assertEqual(junction_left["outgoing_arm_id"], "seg-2-south:start")
            self.assertEqual(junction_left["outgoing_compass"], "S")
            self.assertEqual(junction_left["candidate_target_arm_count"], 1)
            self.assertIn("seg-2-south:start@S", junction_left["candidate_target_arm_catalog"])
            self.assertEqual(junction_left["movement_resolution_state"], "explicit_target")
            self.assertEqual(junction_left["movement_resolution_method"], "single_candidate_turn_match")
            self.assertEqual(junction_left["signal_priority_variant"], "major_minor_priority")
            self.assertEqual(junction_left["phase_priority_group"], "major_minor_priority_crossing_turn")

            roundabout_right = movements.loc[
                movements["node_object_id"] == "round-zone::movement::seg_entry_start::right::seg_rb_start"
            ].iloc[0]
            self.assertEqual(roundabout_right["movement_role"], "roundabout_entry_movement")
            self.assertEqual(roundabout_right["roundabout_component_role"], "entry")
            self.assertEqual(roundabout_right["candidate_target_arm_count"], 1)
            self.assertEqual(roundabout_right["outgoing_arm_id"], "seg-rb:start")
            self.assertEqual(roundabout_right["movement_resolution_state"], "explicit_target")
            self.assertEqual(roundabout_right["movement_resolution_method"], "single_candidate_turn_match")
            self.assertEqual(roundabout_right["signal_priority_variant"], "yield_entry")
            self.assertEqual(roundabout_right["phase_priority_group"], "roundabout_yield_entry")

    def test_build_bari_movement_objects_heuristically_resolves_best_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                import geopandas as gpd  # type: ignore
                from shapely.geometry import LineString, Point  # type: ignore
            except ModuleNotFoundError as exc:  # pragma: no cover
                self.skipTest(str(exc))

            root = Path(temp_dir)
            conflict_zones_path = root / "road_conflict_zones.geojson"
            segments_path = root / "segments.geojson"
            output_dir = root / "movements"

            gpd.GeoDataFrame(
                [
                    {
                        "node_object_id": "approach-zone",
                        "junction_id": "signal-1",
                        "object_type": "conflict_zone",
                        "node_role": "conflict_zone",
                        "zone_type": "junction_approach_conflict_zone",
                        "parent_object_id": "approach-1",
                        "parent_object_type": "junction_approach",
                        "name": "Via A",
                        "movement_family": "approach",
                        "control_state": "signalized",
                        "turn_path_class": "approach_to_signal",
                        "priority_rule": "signal_controlled",
                        "control_detail": "IMP. SEMAF",
                        "approach_node_ref": "s1",
                        "approach_arm_id": "seg-in:start",
                        "approach_bearing_deg": 90.0,
                        "approach_compass": "E",
                        "turn_option_catalog": "straight",
                        "maneuver_complexity": "single_choice",
                        "segment_id": "seg-in",
                        "segment_highway": "primary",
                        "segment_name": "Via A",
                        "segment_ref": "SS16",
                        "segment_junction": "",
                        "geometry": Point(16.87, 41.11),
                    }
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(conflict_zones_path, driver="GeoJSON")

            gpd.GeoDataFrame(
                [
                    {
                        "u": "s1",
                        "v": "s2",
                        "segment_id": "seg-in",
                        "highway": "primary",
                        "name": "Via A",
                        "ref": "SS16",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.87, 41.11), (16.871, 41.11)]),
                    },
                    {
                        "u": "s1",
                        "v": "s3",
                        "segment_id": "seg-main-west",
                        "highway": "primary",
                        "name": "Via A",
                        "ref": "SS16",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.87, 41.11), (16.869, 41.11)]),
                    },
                    {
                        "u": "s1",
                        "v": "s4",
                        "segment_id": "seg-west-alt",
                        "highway": "primary",
                        "name": "Via alternativa",
                        "ref": "",
                        "junction": "",
                        "segment_length_m": 120.0,
                        "geometry": LineString([(16.87, 41.11), (16.869, 41.1102)]),
                    },
                ],
                geometry="geometry",
                crs="EPSG:4326",
            ).to_file(segments_path, driver="GeoJSON")

            manifest = build_bari_movement_objects(
                output_dir=output_dir,
                conflict_zones_path=conflict_zones_path,
                segments_path=segments_path,
                movement_offset_m=8.0,
            )

            self.assertEqual(manifest["stats"]["movement_object_count"], 1)
            self.assertEqual(
                manifest["stats"]["movement_resolution_state_counts"],
                {"heuristic_target_resolution": 1},
            )
            self.assertEqual(
                manifest["stats"]["movement_resolution_method_counts"],
                {"bearing_and_continuity_rank": 1},
            )

            movements = gpd.read_file(output_dir / "road_movement_objects.geojson")
            movement = movements.iloc[0]
            self.assertEqual(movement["outgoing_arm_id"], "seg-main-west:start")
            self.assertEqual(movement["candidate_target_arm_count"], 2)
            self.assertEqual(movement["movement_resolution_state"], "heuristic_target_resolution")
            self.assertEqual(movement["movement_resolution_method"], "bearing_and_continuity_rank")
            self.assertEqual(movement["movement_target_rank"], 1)
            self.assertIn("shared_ref", movement["movement_target_continuity_flags"])
