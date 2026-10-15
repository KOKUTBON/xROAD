"""Tests for white-label institutional branding and API settings configuration."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.settings import ApiSettings


def test_default_institution_branding_endpoint() -> None:
    settings = ApiSettings(
        tenant_id="cerema_fr",
        institution_name="Cerema France",
        brand_name="SécurRoute",
        brand_primary_color="#0055A5",
        country_code="FR",
        default_language="fr",
        driving_side="right",
        distance_unit="km",
        speed_unit="km/h",
        currency="EUR",
        administrative_tier="country",
    )
    app = create_app(settings)
    client = TestClient(app)

    response = client.get("/v1/public/institution-config")
    assert response.status_code == 200
    data = response.json()

    assert data["tenant_id"] == "cerema_fr"
    assert data["institution_name"] == "Cerema France"
    assert data["brand_name"] == "SécurRoute"
    assert data["brand_primary_color"] == "#0055A5"
    assert data["country_code"] == "FR"
    assert data["default_language"] == "fr"
    assert data["driving_side"] == "right"
    assert data["units"]["distance"] == "km"
    assert data["units"]["speed"] == "km/h"
    assert data["units"]["currency"] == "EUR"
    assert data["administrative_tier"] == "country"

    # Alias /v1/public/branding returns the identical payload
    alias_resp = client.get("/v1/public/branding")
    assert alias_resp.status_code == 200
    assert alias_resp.json() == data


def test_branding_loaded_from_tenant_toml() -> None:
    toml_content = """
[project]
name = "uk-dft-pilot"
country_code = "GB"
timezone = "Europe/London"

[institution]
id = "dft_uk"
name = "Department for Transport"
tier = "country"
brand_name = "SafeRoads UK"
brand_primary_color = "#003366"
portal_subtitle = "National road-risk intelligence"

[localization]
language = "en"
driving_side = "left"
distance_unit = "miles"
speed_unit = "mph"
currency = "GBP"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tmp:
        tmp.write(toml_content)
        tmp_path = Path(tmp.name)

    try:
        settings = ApiSettings(tenant_config_path=tmp_path)
        app = create_app(settings)
        client = TestClient(app)

        response = client.get("/v1/public/institution-config")
        assert response.status_code == 200
        data = response.json()

        assert data["tenant_id"] == "dft_uk"
        assert data["institution_name"] == "Department for Transport"
        assert data["brand_name"] == "SafeRoads UK"
        assert data["brand_primary_color"] == "#003366"
        assert data["country_code"] == "GB"
        assert data["driving_side"] == "left"
        assert data["units"]["distance"] == "miles"
        assert data["units"]["speed"] == "mph"
        assert data["units"]["currency"] == "GBP"
        assert data["administrative_tier"] == "country"
    finally:
        tmp_path.unlink()


def test_dynamic_city_support_path_resolution() -> None:
    settings = ApiSettings()

    # Legacy city Bari
    assert settings.get_signal_junction_metrics_path("bari") == settings.bari_signal_junction_metrics_path
    assert settings.get_crossing_priority_path("bari") == settings.bari_crossing_priority_path

    # Dynamic non-Bari city
    paris_junction = settings.get_signal_junction_metrics_path("paris")
    assert "paris_open_data_signals" in str(paris_junction)

    paris_crossing = settings.get_crossing_priority_path("paris")
    assert "paris_frequency_baseline_context_v2" in str(paris_crossing)
