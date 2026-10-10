"""Tests for Declarative Ingestion Adapter and cross-border CRS re-projection."""

from datetime import datetime
from pathlib import Path
import tempfile
import pytest

from road_risk_modeling.adapters.declarative_adapter import (
    CodeListCrosswalkConfig,
    DateTimeMappingConfig,
    DeclarativeCrashAdapter,
    DeclarativeSchemaMapping,
    SeverityMappingConfig,
    SpatialMappingConfig,
    UK_STATS19_PRESET,
    US_MMUCC_PRESET,
)


def test_uk_stats19_preset_ingestion() -> None:
    adapter = DeclarativeCrashAdapter(UK_STATS19_PRESET)

    # Sample UK row with British National Grid (EPSG:27700) coordinates for Central London
    row = {
        "collision_reference": "2023010012345",
        "date": "15/10/2023",
        "time": "14:35",
        "location_easting_osgr": "529090",
        "location_northing_osgr": "179645",
        "collision_severity": "1",  # Fatal
        "road_type": "1",  # Roundabout
        "light_conditions": "4",  # Darkness lights lit
    }

    record = adapter.map_row(row, source_row_number=1)

    assert record.crash_id == "dft_stats19:2023010012345"
    assert record.country_code == "GB"
    assert record.occurred_at == datetime(2023, 10, 15, 14, 35)
    assert record.occurred_year == 2023
    assert record.occurred_month == 10
    assert record.occurred_day == 15
    assert record.occurred_hour == 14
    assert record.occurred_minute == 35

    # Coordinates must be reprojected from EPSG:27700 to WGS84
    assert record.latitude is not None
    assert record.longitude is not None
    assert 51.49 < record.latitude < 51.52
    assert -0.16 < record.longitude < -0.12

    # Severity crosswalk
    assert record.fatalities == 1
    assert record.injuries == 0
    assert record.severity_level == "fatal"

    # Code-list crosswalks
    assert record.roadway_type == "roundabout"
    assert record.light_condition == "daylight" or record.light_condition == "darkness_lights_lit"
    assert "coordinates_outside_bounds" not in record.quality_flags


def test_us_mmucc_preset_ingestion() -> None:
    adapter = DeclarativeCrashAdapter(US_MMUCC_PRESET)

    row = {
        "crash_id": "CA_2024_9876",
        "crash_date": "2024-03-21 08:15:00",
        "latitude": "37.7749",
        "longitude": "-122.4194",
        "fatal_count": "0",
        "injury_count": "2",
    }

    record = adapter.map_row(row, source_row_number=1)

    assert record.crash_id == "nhtsa_mmucc:CA_2024_9876"
    assert record.country_code == "US"
    assert record.occurred_at == datetime(2024, 3, 21, 8, 15)
    assert record.latitude == pytest.approx(37.7749, rel=1e-4)
    assert record.longitude == pytest.approx(-122.4194, rel=1e-4)
    assert record.fatalities == 0
    assert record.injuries == 2
    assert record.severity_level == "injury"


def test_custom_declarative_csv_file_ingestion() -> None:
    mapping = DeclarativeSchemaMapping(
        schema_id="custom_city_crashes",
        country_code="ES",
        source_system="madrid_movilidad",
        id_column="id_accidente",
        datetime_mapping=DateTimeMappingConfig(
            datetime_column="fecha_hora",
            datetime_format="%Y-%m-%d %H:%M",
        ),
        spatial_mapping=SpatialMappingConfig(
            latitude_column="lat",
            longitude_column="lon",
            native_crs="EPSG:4326",
            bounding_box=(-4.0, 40.0, -3.4, 40.7),
        ),
        severity_mapping=SeverityMappingConfig(
            fatalities_column="fallecidos",
            injuries_column="heridos",
        ),
        roadway_type_crosswalk=CodeListCrosswalkConfig(
            column="tipo_via",
            mapping={"calle": "urban_street", "autovia": "motorway"},
        ),
    )

    adapter = DeclarativeCrashAdapter(mapping)

    csv_data = """id_accidente,fecha_hora,lat,lon,fallecidos,heridos,tipo_via
ACC-001,2025-01-10 10:30,40.4168,-3.7038,0,1,calle
ACC-002,2025-01-11 19:45,40.4200,-3.7100,1,0,autovia
ACC-003,2025-01-12 23:00,10.0000,10.0000,0,0,desconocido
"""

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tmp:
        tmp.write(csv_data)
        tmp_path = Path(tmp.name)

    try:
        records = adapter.ingest_csv(tmp_path)
        assert len(records) == 3

        # Row 1
        assert records[0].crash_id == "madrid_movilidad:ACC-001"
        assert records[0].country_code == "ES"
        assert records[0].injuries == 1
        assert records[0].fatalities == 0
        assert records[0].roadway_type == "urban_street"
        assert "coordinates_outside_bounds" not in records[0].quality_flags

        # Row 2
        assert records[1].crash_id == "madrid_movilidad:ACC-002"
        assert records[1].fatalities == 1
        assert records[1].severity_level == "fatal"
        assert records[1].roadway_type == "motorway"

        # Row 3 - Out of bounds coordinates (10, 10 is far from Madrid)
        assert "coordinates_outside_bounds" in records[2].quality_flags
        assert "unmapped_code_list_value" in records[2].quality_flags
    finally:
        tmp_path.unlink()


def test_ingest_declarative_dataset_and_cli() -> None:
    import json
    import sys
    from road_risk_modeling.adapters.declarative_adapter import ingest_declarative_dataset
    from road_risk_modeling.cli import main

    csv_data = """id_accidente,fecha_hora,lat,lon,fallecidos,heridos,tipo_via
ACC-101,2025-02-01 11:00,40.4168,-3.7038,1,0,calle
ACC-102,2025-02-02 12:00,40.4200,-3.7100,0,2,autovia
"""
    mapping_dict = {
        "schema_id": "test_cli_crashes",
        "country_code": "ES",
        "source_system": "madrid_test",
        "id_column": "id_accidente",
        "datetime_mapping": {
            "datetime_column": "fecha_hora",
            "datetime_format": "%Y-%m-%d %H:%M",
        },
        "spatial_mapping": {
            "latitude_column": "lat",
            "longitude_column": "lon",
            "native_crs": "EPSG:4326",
        },
        "severity_mapping": {
            "fatalities_column": "fallecidos",
            "injuries_column": "heridos",
        },
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        csv_file = tmp_dir_path / "crashes.csv"
        cfg_file = tmp_dir_path / "mapping.json"
        out_dir = tmp_dir_path / "output"

        csv_file.write_text(csv_data, encoding="utf-8")
        cfg_file.write_text(json.dumps(mapping_dict), encoding="utf-8")

        # 1. Test programmatic ingestion function
        manifest = ingest_declarative_dataset(csv_file, cfg_file, output_dir=out_dir)
        assert manifest["stats"]["total_records"] == 2
        assert manifest["stats"]["fatalities_total"] == 1
        assert manifest["stats"]["injuries_total"] == 2
        assert Path(manifest["outputs"]["records_path"]).is_file()
        assert Path(manifest["outputs"]["manifest_path"]).is_file()

        # 2. Test CLI command dispatch
        cli_out_dir = tmp_dir_path / "cli_output"
        original_argv = sys.argv
        try:
            sys.argv = [
                "road-risk",
                "ingest-declarative",
                "--csv-path",
                str(csv_file),
                "--mapping-config",
                str(cfg_file),
                "--output-dir",
                str(cli_out_dir),
            ]
            exit_code = main()
            assert exit_code == 0
            assert (cli_out_dir / "test_cli_crashes_canonical.jsonl").is_file()
            assert (cli_out_dir / "test_cli_crashes_canonical.manifest.json").is_file()
        finally:
            sys.argv = original_argv
