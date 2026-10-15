"""Tests for unified white-label project configuration."""

from pathlib import Path
import tempfile
import pytest

from road_risk_modeling.config import (
    GeospatialConfig,
    GovernanceConfig,
    IngestionConfig,
    InstitutionConfig,
    LocalizationConfig,
    ProjectSettings,
)


def test_legacy_toml_backward_compatibility() -> None:
    toml_content = """
[project]
name = "puglia-road-risk-pilot"
country_code = "IT"
timezone = "Europe/Rome"

[geography]
jurisdiction_name = "Puglia"
admin_level = "region"
network_type = "drive"
segment_length_m = 100

[data]
crash_csv_member = "synthetic_examples/crashes.csv"
weather_provider = "open-meteo"
population_provider = "ghsl"
traffic_provider = "pending"

[modeling]
tasks = ["segment_frequency", "severity_classification"]
spatial_holdout = "city"
temporal_holdout = "year"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tmp:
        tmp.write(toml_content)
        tmp_path = Path(tmp.name)

    try:
        settings = ProjectSettings.from_toml(tmp_path)
        assert settings.name == "puglia-road-risk-pilot"
        assert settings.country_code == "IT"
        assert settings.timezone == "Europe/Rome"
        assert settings.jurisdiction_name == "Puglia"
        assert settings.admin_level == "region"
        assert settings.network_type == "drive"
        assert settings.segment_length_m == 100
        assert settings.crash_csv_member == "synthetic_examples/crashes.csv"
        assert settings.weather_provider == "open-meteo"
        assert settings.tasks == ("segment_frequency", "severity_classification")

        # Sub-configs should have sensible defaults or inherited values
        assert settings.institution.name == "puglia-road-risk-pilot"
        assert settings.geospatial.jurisdiction_name == "Puglia"
        assert settings.localization.driving_side == "right"
        assert settings.localization.distance_unit == "km"
        assert settings.governance.k_anonymity_threshold == 5

        # Check export dictionary
        as_dict = settings.to_dict()
        assert as_dict["name"] == "puglia-road-risk-pilot"
        assert as_dict["institution"]["brand_name"] == "xROAD"
        assert as_dict["geospatial"]["native_crs"] == "EPSG:4326"

        readiness = settings.validate_institutional_readiness()
        assert readiness["all_critical_checks_passed"] is True
        assert readiness["is_ready"] is True
    finally:
        tmp_path.unlink()


def test_full_white_label_toml() -> None:
    toml_content = """
[project]
name = "cerema-france-risk-core"
country_code = "FR"
timezone = "Europe/Paris"

[institution]
id = "cerema_fr"
name = "Centre d'études et d'expertise sur les risques, la mobilité et l'aménagement"
tier = "country"
brand_name = "SécurRoute France"
brand_primary_color = "#0055A5"
brand_logo_url = "/brand/cerema-logo.svg"
contact_email = "road-safety@example.test"
portal_subtitle = "Plateforme nationale d'analyse des risques routiers"

[localization]
language = "fr"
fallback_languages = ["en"]
driving_side = "right"
distance_unit = "km"
speed_unit = "km/h"
currency = "EUR"

[geospatial]
jurisdiction_name = "France métropolitaine"
admin_level = "country"
native_crs = "EPSG:2154"
target_crs = "EPSG:4326"
road_network_source = "ign_bd_topo"
network_type = "drive"
segment_length_m = 200

[ingestion]
schema_standard = "baac"
crash_source_format = "csv"
weather_provider = "open-meteo"
population_provider = "insee"
traffic_provider = "cerema_flux"

[modeling]
tasks = ["segment_frequency", "severity_classification", "vru_exposure"]
spatial_holdout = "departement"
temporal_holdout = "year"

[governance]
k_anonymity_threshold = 5
data_minimization_mode = "strict"
compliance_frameworks = ["eu_ai_act", "gdpr", "secnumcloud"]
allow_public_raw_coordinates = false
"""
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tmp:
        tmp.write(toml_content)
        tmp_path = Path(tmp.name)

    try:
        settings = ProjectSettings.from_toml(tmp_path)
        assert settings.name == "cerema-france-risk-core"
        assert settings.country_code == "FR"
        assert settings.institution.id == "cerema_fr"
        assert settings.institution.brand_name == "SécurRoute France"
        assert settings.institution.brand_primary_color == "#0055A5"
        assert settings.institution.tier == "country"

        assert settings.localization.language == "fr"
        assert settings.geospatial.native_crs == "EPSG:2154"
        assert settings.geospatial.segment_length_m == 200
        assert settings.ingestion.schema_standard == "baac"
        assert "secnumcloud" in settings.governance.compliance_frameworks

        readiness = settings.validate_institutional_readiness()
        assert readiness["all_critical_checks_passed"] is True
        assert readiness["is_ready"] is True
    finally:
        tmp_path.unlink()


def test_uk_left_hand_drive_validation() -> None:
    toml_content = """
[project]
name = "dft-uk-road-safety"
country_code = "GB"
timezone = "Europe/London"

[institution]
id = "dft_uk"
name = "Department for Transport"
tier = "country"
brand_name = "SafeRoads UK"
brand_primary_color = "#003366"

[localization]
language = "en"
driving_side = "left"
distance_unit = "miles"
speed_unit = "mph"
currency = "GBP"

[geospatial]
jurisdiction_name = "Great Britain"
admin_level = "country"
native_crs = "EPSG:27700"

[ingestion]
schema_standard = "stats19"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tmp:
        tmp.write(toml_content)
        tmp_path = Path(tmp.name)

    try:
        settings = ProjectSettings.from_toml(tmp_path)
        assert settings.country_code == "GB"
        assert settings.localization.driving_side == "left"
        assert settings.localization.distance_unit == "miles"
        assert settings.localization.speed_unit == "mph"
        assert settings.localization.currency == "GBP"
        assert settings.geospatial.native_crs == "EPSG:27700"
        assert settings.ingestion.schema_standard == "stats19"

        readiness = settings.validate_institutional_readiness()
        assert readiness["all_critical_checks_passed"] is True
    finally:
        tmp_path.unlink()
