"""Security acceptance checks for the dedicated institutional installation."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from apps.api.settings import ApiSettings
from infra.scripts.bootstrap_institution import (
    generate_env_content,
    generate_service_secrets,
    write_private_file,
)
from road_risk_modeling.config import ProjectSettings

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "infra/docker/institution-entrypoint.py"
WEB_SCRIPT = ROOT / "infra/docker/institution-web-entrypoint.mjs"
spec = importlib.util.spec_from_file_location("institution_entrypoint", SCRIPT)
entrypoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrypoint)


@pytest.fixture
def institutional_env(tmp_path):
    generate_service_secrets(tmp_path / "secrets")
    return {
        "ROAD_RISK_INSTITUTION_DEPLOYMENT": "true",
        "ROAD_RISK_API_AUTH_ENABLED": "true",
        "ROAD_RISK_API_AUTH_JWKS_URL": "https://sso.example.test/certs",
        "ROAD_RISK_API_AUTH_ISSUER": "https://sso.example.test/realm",
        "ROAD_RISK_API_AUTH_AUDIENCE": "road-risk-api",
        "ROAD_RISK_PUBLIC_ORIGIN": "https://roads.example.test",
        "POSTGRES_USER": "roaduser",
        "POSTGRES_DB": "road_risk",
        "POSTGRES_PASSWORD_FILE": str(tmp_path / "secrets/postgres_password"),
        "ROAD_RISK_STORAGE_ACCESS_KEY_ID": "storage_admin",
        "ROAD_RISK_STORAGE_SECRET_ACCESS_KEY_FILE": str(
            tmp_path / "secrets/minio_password"
        ),
    }


def test_loader_constructs_encoded_database_credentials(institutional_env):
    path = Path(institutional_env["POSTGRES_PASSWORD_FILE"])
    path.chmod(0o600)
    password = "x" * 24 + ":/@?#%$"
    path.write_text(password + "\n")
    result = entrypoint.prepare_environment(institutional_env)
    assert (
        "xxxxxxxxxxxxxxxxxxxxxxxx%3A%2F%40%3F%23%25%24@postgres:5432/road_risk"
        in result["ROAD_RISK_DATABASE_URL"]
    )
    assert result["ROAD_RISK_STORAGE_SECRET_ACCESS_KEY"]
    assert "ROAD_RISK_DATABASE_URL" not in institutional_env


@pytest.mark.parametrize(
    "key,value",
    [
        ("ROAD_RISK_API_AUTH_ENABLED", "false"),
        ("ROAD_RISK_API_AUTH_AUDIENCE", ""),
        ("ROAD_RISK_API_AUTH_JWKS_URL", "http://sso.example.test/certs"),
        ("ROAD_RISK_API_AUTH_ISSUER", "https://user:pass@sso.example.test/realm"),
        ("ROAD_RISK_PUBLIC_ORIGIN", "https://roads.example.test/path"),
        ("ROAD_RISK_PUBLIC_ORIGIN", "https://roads.example.test?query=1"),
    ],
)
def test_institution_refuses_insecure_config(institutional_env, key, value):
    institutional_env[key] = value
    with pytest.raises(ValueError):
        entrypoint.prepare_environment(institutional_env)


@pytest.mark.parametrize("kind", ["short", "placeholder", "missing", "reused"])
def test_institution_refuses_bad_secrets(institutional_env, kind):
    path = Path(institutional_env["POSTGRES_PASSWORD_FILE"])
    path.chmod(0o600)
    if kind == "missing":
        path.unlink()
    elif kind == "reused":
        path.write_text(
            Path(
                institutional_env["ROAD_RISK_STORAGE_SECRET_ACCESS_KEY_FILE"]
            ).read_text()
        )
    else:
        path.write_text("short" if kind == "short" else "ChangeMe_" + "x" * 32)
    with pytest.raises((ValueError, OSError)):
        entrypoint.prepare_environment(institutional_env)


def test_secret_loader_does_not_affect_development():
    assert entrypoint.prepare_environment({"LOCAL": "yes"}) == {"LOCAL": "yes"}


def test_secret_generation_preserves_existing_credentials(tmp_path):
    directory = tmp_path / "secrets"
    generate_service_secrets(directory)
    before = (directory / "postgres_password").read_bytes()
    assert before != (directory / "minio_password").read_bytes()
    assert directory.stat().st_mode & 0o777 == 0o700
    with pytest.raises(FileExistsError):
        generate_service_secrets(directory)
    assert (directory / "postgres_password").read_bytes() == before
    path = tmp_path / ".env"
    write_private_file(path, "first")
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private_file(path, "second")
    assert path.read_text() == "first"


def test_generated_env_has_no_plaintext_passwords():
    settings = ProjectSettings.from_toml(
        ROOT / "configs/institutional_tenant.example.toml"
    )
    content = generate_env_content(
        settings, "configs/institutional_tenant.example.toml"
    )
    assert "ROAD_RISK_API_AUTH_ENABLED=true" in content
    assert "POSTGRES_PASSWORD_FILE=" in content
    assert "POSTGRES_PASSWORD=" not in content
    assert "MINIO_ROOT_PASSWORD=" not in content
    assert "ChangeMe" not in content
    assert "ROAD_RISK_DEPLOYMENT_NAME=road-risk-cerema_fr" in content
    assert "ROAD_RISK_INSTITUTION_DATA_DIR=./institution-data/cerema_fr" in content
    assert "./secrets/cerema_fr/postgres_password" in content


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"auth_enabled": True},
        {
            "auth_enabled": True,
            "auth_jwks_url": "http://sso.test/certs",
            "auth_issuer": "https://sso.test",
            "auth_audience": "api",
        },
        {
            "auth_enabled": True,
            "auth_jwks_url": "https://sso.test/certs",
            "auth_issuer": "https://sso.test",
        },
    ],
)
def test_production_api_refuses_disabled_or_incomplete_auth(kwargs):
    with pytest.raises(ValueError):
        ApiSettings(env="production", **kwargs).validate_production_security()


def test_production_api_accepts_complete_auth():
    ApiSettings(
        tenant_config_path=ROOT / "configs/institutional_tenant.example.toml",
        env="production",
        auth_enabled=True,
        auth_jwks_url="https://sso.test/certs",
        auth_issuer="https://sso.test",
        auth_audience="api",
    ).validate_production_security()
    ApiSettings(env="local").validate_production_security()


@pytest.mark.skipif(not shutil.which("node"), reason="Node runtime unavailable")
def test_web_entrypoint_checks_real_oidc_config(tmp_path):
    path = tmp_path / "oidc-secret"
    path.write_text("a" * 32)
    env = {
        **os.environ,
        "ROAD_RISK_INSTITUTION_DEPLOYMENT": "true",
        "ROAD_RISK_PUBLIC_ORIGIN": "https://roads.example.test",
        "ROAD_RISK_WEB_OIDC_ISSUER": "https://sso.example.test",
        "ROAD_RISK_WEB_OIDC_CLIENT_ID": "roads-web",
        "ROAD_RISK_WEB_OIDC_CLIENT_SECRET_FILE": str(path),
        "ROAD_RISK_WEB_OIDC_REDIRECT_URI": "https://roads.example.test/api/auth/callback",
    }
    command = ["node", str(WEB_SCRIPT), "--check"]
    assert subprocess.run(command, env=env, check=False, capture_output=True).returncode == 0
    for key, value in [
        ("ROAD_RISK_WEB_OIDC_REDIRECT_URI", "https://other.test/api/auth/callback"),
        ("ROAD_RISK_WEB_OIDC_CLIENT_ID", ""),
        ("ROAD_RISK_WEB_OIDC_TOKEN_ENDPOINT", "http://sso.test/token"),
    ]:
        result = subprocess.run(command, env={**env, key: value}, check=False, capture_output=True)
        assert result.returncode == 1
        assert path.read_bytes() not in result.stdout + result.stderr
    path.write_text("short")
    assert subprocess.run(command, env=env, check=False, capture_output=True).returncode == 1


@pytest.mark.skipif(not shutil.which("docker"), reason="Docker Compose unavailable")
def test_compose_only_publishes_https_and_scopes_secrets(tmp_path):
    env = {
        **os.environ,
        "ROAD_RISK_HOSTNAME": "roads.example.test",
        "ROAD_RISK_API_AUTH_JWKS_URL": "https://sso.example.test/certs",
        "ROAD_RISK_API_AUTH_ISSUER": "https://sso.example.test",
        "ROAD_RISK_API_AUTH_AUDIENCE": "roads-api",
        "ROAD_RISK_WEB_OIDC_CLIENT_ID": "roads-web",
    }
    command = [
        "docker",
        "compose",
        "--env-file",
        str(ROOT / "infra/docker/.env.institution.example"),
        "-f",
        str(ROOT / "infra/docker/docker-compose.institution.yml"),
        "config",
        "--format",
        "json",
    ]
    result = subprocess.run(command, env=env, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name, service in services.items():
        if name == "gateway":
            assert [port["target"] for port in service["ports"]] == [443]
            assert set(service["networks"]) == {"frontend"}
        else:
            assert not service.get("ports"), name
        assert "POSTGRES_PASSWORD" not in service.get("environment", {})
        assert "ROAD_RISK_STORAGE_SECRET_ACCESS_KEY" not in service.get(
            "environment", {}
        )
    for name in ("api", "worker", "web"):
        assert services[name]["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in services[name]["security_opt"]
    assert services["api"]["environment"]["ROAD_RISK_API_AUTH_ENABLED"] == "true"
    assert (
        services["web"]["build"]["args"]["NEXT_PUBLIC_API_BASE_URL"] == "/api/backend"
    )
    assert {secret["source"] for secret in services["web"]["secrets"]} == {
        "oidc_client_secret"
    }
    env["ROAD_RISK_API_AUTH_AUDIENCE"] = ""
    assert subprocess.run(command, env=env, check=False, capture_output=True).returncode != 0


def test_release_check_accepts_templates_but_rejects_deployment_env():
    from tools.security_release_checks import check_no_plain_env_files

    assert check_no_plain_env_files([ROOT / "infra/docker/.env.institution.example"]) == []
    assert len(check_no_plain_env_files([ROOT / "infra/docker/.env.institution", ROOT / ".env", ROOT / "production.env"])) == 3
