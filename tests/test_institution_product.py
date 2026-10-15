"""Institution configuration, module enforcement, and scope acceptance tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from apps.api.auth import AuthContext, get_auth_context
from apps.api.main import create_app
from apps.api.settings import ApiSettings
from infra.scripts.configure_institution import create_config
from road_risk_modeling.config import ProjectSettings
from road_risk_modeling.institutional_product import (
    PROFILES,
    DeploymentConfig,
    module_for_api_path,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def deployment_payload():
    return {
        "schema_version": 1,
        "profile": "police",
        "organizations": [
            {"id": "agency-a", "name": "Agency A", "municipality_ids": ["city-a"]},
            {"id": "agency-b", "name": "Agency B", "municipality_ids": ["city-b"]},
        ],
        "jurisdictions": [
            {"id": "city-a", "name": "City A", "region_label": "Region"},
            {"id": "city-b", "name": "City B", "region_label": "Region"},
        ],
    }


@pytest.mark.parametrize("profile", [key for key in PROFILES if key != "legacy"])
def test_profiles_generate_installable_config_without_overwrites(tmp_path, profile):
    path = tmp_path / "tenant.toml"
    settings = create_config(
        path,
        profile=profile,
        institution_id="agency-a",
        institution_name='Agency "A"',
        jurisdiction_id="city-a",
        jurisdiction_name="City A",
        country_code="IT",
        timezone="Europe/Rome",
        language="it",
    )
    assert settings.deployment.profile == profile
    assert settings.institution.name == 'Agency "A"'
    assert settings.deployment.enabled_modules == PROFILES[profile]
    assert (
        settings.deployment.jurisdictions[0].coverage_label == "Awaiting validated data"
    )
    with pytest.raises(FileExistsError):
        create_config(
            path,
            profile=profile,
            institution_id="agency-a",
            institution_name="Agency",
            jurisdiction_id="city-a",
            jurisdiction_name="City A",
            country_code="IT",
            timezone="Europe/Rome",
        )
    assert (
        settings.configuration_revision
        == ProjectSettings.from_toml(path).configuration_revision
    )


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"profile": "unknown"},
        {"profile": "legacy"},
        {"enabled_modules": ["administration", "unknown"]},
        {"enabled_modules": ["forensics"]},
        {"enabled_modules": ["administration", "interventions"]},
        {"enabled_modules": ["administration", "incident_coordination"]},
        {"enabled_modules": "administration"},
        {"enabled_modules": ["administration", "administration"]},
        {"organizations": []},
        {"jurisdictions": []},
        {"enable_modules": []},
    ],
)
def test_invalid_product_settings_fail_explicitly(deployment_payload, change):
    with pytest.raises(ValueError):
        DeploymentConfig.from_dict({**deployment_payload, **change})


def test_scope_catalog_never_grants_unassigned_or_unlinked_jurisdictions(
    deployment_payload,
):
    config = DeploymentConfig.from_dict(deployment_payload)
    catalog = config.scope_catalog({"agency-a"}, {"city-a", "city-b"})
    assert [row["id"] for row in catalog["organizations"]] == ["agency-a"]
    assert [row["id"] for row in catalog["municipalities"]] == ["city-a"]
    assert config.scope_catalog(set(), set()) == {
        "organizations": [],
        "municipalities": [],
    }
    assert (
        len(config.scope_catalog(set(), set(), super_admin=True)["municipalities"]) == 2
    )
    assert "organizations" not in config.public_dict()


def test_duplicate_or_unlinked_scopes_fail(deployment_payload):
    for key in ["organizations", "jurisdictions"]:
        invalid = deepcopy(deployment_payload)
        invalid[key].append(deepcopy(invalid[key][0]))
        with pytest.raises(ValueError):
            DeploymentConfig.from_dict(invalid)
    invalid = deepcopy(deployment_payload)
    invalid["organizations"][0]["municipality_ids"] = ["not-configured"]
    with pytest.raises(ValueError):
        DeploymentConfig.from_dict(invalid)


def test_canonical_configuration_roundtrips_and_revision_changes(deployment_payload):
    config = DeploymentConfig.from_dict(deployment_payload)
    assert DeploymentConfig.from_dict(config.to_dict()) == config
    assert (
        replace(config, enabled_modules=(*config.enabled_modules, "research")).revision
        != config.revision
    )
    settings = ProjectSettings.from_toml(
        ROOT / "configs/institutional_tenant.example.toml"
    )
    before = settings.configuration_revision
    settings.institution.brand_name = "Changed institution"
    assert settings.configuration_revision != before


def configured_settings(tmp_path, profile="police"):
    path = tmp_path / "tenant.toml"
    create_config(
        path,
        profile=profile,
        institution_id="agency-a",
        institution_name="Agency A",
        jurisdiction_id="city-a",
        jurisdiction_name="City A",
        country_code="IT",
        timezone="Europe/Rome",
    )
    return ApiSettings(tenant_config_path=path, request_logging_enabled=False)


def test_disabled_modules_and_unconfigured_cities_never_execute_handlers(tmp_path):
    from apps.api.middleware.institution_modules import InstitutionModulesMiddleware

    settings = configured_settings(tmp_path)
    config = settings.institutional_project.deployment
    app = FastAPI()
    app.add_middleware(
        InstitutionModulesMiddleware,
        enabled_modules=config.enabled_modules,
        jurisdictions=("city-a",),
    )
    executed = []

    @app.get("/v1/simulation/synthetic-countermeasure-eval")
    @app.get("/v1/analyst/cities/city-b/risk-map")
    @app.get("/v1/forensics/cases")
    def operation():
        executed.append(True)
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/v1/simulation/synthetic-countermeasure-eval").status_code == 404
    assert client.get("/v1/analyst/cities/city-b/risk-map").status_code == 404
    assert executed == []
    assert client.get("/v1/forensics/cases").status_code == 200
    assert executed == [True]


def test_public_portal_disabled_but_branding_available(tmp_path):
    client = TestClient(create_app(configured_settings(tmp_path)))
    assert client.get("/v1/public/cities").status_code == 404
    response = client.get("/v1/public/institution-config")
    assert response.status_code == 200
    assert response.json()["deployment"]["profile"] == "police"
    assert "organizations" not in response.json()["deployment"]
    assert client.get("/healthz").status_code == 200


def test_claims_are_intersected_with_installed_catalog(tmp_path):
    settings = configured_settings(tmp_path)
    settings.auth_enabled = True
    payload = {
        "sub": "analyst-a",
        "roles": ["analyst"],
        "organization_ids": ["agency-a", "foreign-agency"],
        "municipality_ids": ["city-a", "foreign-city"],
    }
    with (
        patch("apps.api.auth.get_settings", return_value=settings),
        patch("apps.api.auth._decode_token", return_value=payload),
    ):
        auth = get_auth_context(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="test")
        )
    assert auth.organization_ids == frozenset({"agency-a"})
    assert auth.municipality_ids == frozenset({"city-a"})


def test_deployment_details_require_platform_admin(tmp_path):
    app = create_app(configured_settings(tmp_path))
    auth = AuthContext.anonymous(auth_enabled=True, provider="test")
    app.dependency_overrides[get_auth_context] = lambda: auth
    client = TestClient(app)
    assert client.get("/v1/admin/institution-deployment").status_code == 401
    auth = replace(
        auth,
        subject="analyst-a",
        assigned_roles=frozenset({"analyst"}),
        roles=frozenset({"analyst"}),
        is_authenticated=True,
    )
    assert client.get("/v1/admin/institution-deployment").status_code == 403
    auth = replace(
        auth,
        assigned_roles=frozenset({"super_admin"}),
        roles=frozenset({"super_admin"}),
    )
    response = client.get("/v1/admin/institution-deployment")
    assert response.status_code == 200
    assert response.json()["configuration"]["profile"] == "police"
    assert (
        response.json()["revision"]
        == response.json()["identity"]["deployment"]["revision"]
    )
    assert len(client.get("/v1/auth/me").json()["scope_catalog"]["municipalities"]) == 1


def test_configured_file_errors_do_not_silently_use_another_institution(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_app(ApiSettings(tenant_config_path=tmp_path / "missing.toml"))
    settings = configured_settings(tmp_path)
    Path(settings.tenant_config_path).write_text("bad config !")
    with pytest.raises(ValueError):
        create_app(settings)


@pytest.mark.parametrize(
    "path,module",
    [
        ("/v1/admin/automations", "automation"),
        ("/v1/admin/users/link", "administration"),
        ("/v1/public/cities/city-a/reports", "reporting"),
        ("/v1/reports-extra", None),
        ("/v1/healthz", None),
    ],
)
def test_endpoint_module_boundaries(path, module):
    assert module_for_api_path(path) == module


@pytest.mark.parametrize(
    "kwargs",
    [
        {"country_code": "ZZ"},
        {"timezone": "Europe/Imaginary"},
        {"native_crs": "EPSG:999999999"},
        {"currency": "ZZZ"},
    ],
)
def test_invalid_regional_configuration_does_not_write_a_profile(tmp_path, kwargs):
    arguments = {
        "profile": "municipality", "institution_id": "agency-a", "institution_name": "Agency", "jurisdiction_id": "city-a", "jurisdiction_name": "City A", "country_code": "IT", "timezone": "Europe/Rome",
    }
    path = tmp_path / "invalid.toml"
    with pytest.raises(ValueError):
        create_config(path, **{**arguments, **kwargs})
    assert not path.exists()


def test_readiness_checks_real_timezone_country_and_crs():
    settings = ProjectSettings.from_toml(
        ROOT / "configs/institutional_tenant.example.toml"
    )
    settings.country_code = "ZZ"
    settings.timezone = "Europe/Imaginary"
    settings.geospatial.native_crs = "EPSG:999999999"
    failed = {
        check["name"]
        for check in settings.validate_institutional_readiness()["checks"]
        if not check["passed"]
    }
    assert {"valid_country_code", "valid_timezone", "valid_native_crs"}.issubset(failed)
