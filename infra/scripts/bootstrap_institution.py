#!/usr/bin/env python3
"""Turnkey Institutional Onboarding & Deployment Verification Script.

Validates an institutional tenant configuration, audits country/geospatial readiness,
and generates the sovereign Docker Compose environment file for one-command deployment.

Usage:
    python infra/scripts/bootstrap_institution.py --config configs/institutional_tenant.example.toml
    python infra/scripts/bootstrap_institution.py --config configs/project.example.toml --generate-env
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import sys
from pathlib import Path

# Ensure src is in Python path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from road_risk_modeling.config import ProjectSettings


def generate_env_content(settings: ProjectSettings, config_rel_path: str) -> str:
    """Generate .env.institution content from validated ProjectSettings."""
    inst = settings.institution
    loc = settings.localization

    def quoted(value: str) -> str:
        # Preserve literal dollars and reject multiline dotenv values.
        if any(char in value for char in ("\n", "\r", "\x00")):
            raise ValueError("Institutional values cannot contain control characters")
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

    return f"""# Auto-generated institutional settings; no credentials are embedded.
# Configure hostname, institution-issued TLS files, and SSO before starting.
ROAD_RISK_HOSTNAME=
ROAD_RISK_DEPLOYMENT_NAME=road-risk-{inst.id.lower()}
ROAD_RISK_INSTITUTION_DATA_DIR=./institution-data/{inst.id.lower()}
ROAD_RISK_INSTITUTION_BRAND_DIR=./institution-data/{inst.id.lower()}/brand
HTTPS_HOST_PORT=443

ROAD_RISK_API_TENANT_ID={quoted(inst.id)}
ROAD_RISK_API_INSTITUTION_NAME={quoted(inst.name)}
ROAD_RISK_API_BRAND_NAME={quoted(inst.brand_name)}
ROAD_RISK_API_BRAND_PRIMARY_COLOR={quoted(inst.brand_primary_color)}
ROAD_RISK_API_BRAND_LOGO_URL={quoted(inst.brand_logo_url)}
ROAD_RISK_API_PORTAL_SUBTITLE={quoted(inst.portal_subtitle)}
ROAD_RISK_API_TENANT_CONFIG_PATH={quoted("/app/" + config_rel_path)}

ROAD_RISK_API_COUNTRY_CODE={quoted(settings.country_code)}
ROAD_RISK_API_DEFAULT_LANGUAGE={quoted(loc.language)}
ROAD_RISK_API_DRIVING_SIDE={quoted(loc.driving_side)}
ROAD_RISK_API_DISTANCE_UNIT={quoted(loc.distance_unit)}
ROAD_RISK_API_SPEED_UNIT={quoted(loc.speed_unit)}
ROAD_RISK_API_CURRENCY={quoted(loc.currency)}
ROAD_RISK_API_ADMINISTRATIVE_TIER={quoted(inst.tier)}

POSTGRES_USER=roadrisk_admin
POSTGRES_DB=road_risk_production
POSTGRES_PASSWORD_FILE=./secrets/{inst.id.lower()}/postgres_password
MINIO_ROOT_USER=storage_admin
MINIO_ROOT_PASSWORD_FILE=./secrets/{inst.id.lower()}/minio_password
ROAD_RISK_STORAGE_BUCKET=road-risk-artifacts

ROAD_RISK_API_AUTH_ENABLED=true
ROAD_RISK_API_AUTH_PROVIDER=keycloak
ROAD_RISK_API_AUTH_JWKS_URL=
ROAD_RISK_API_AUTH_ISSUER=
ROAD_RISK_API_AUTH_AUDIENCE=
ROAD_RISK_API_AUTH_CLIENT_ID=
ROAD_RISK_WEB_OIDC_CLIENT_ID=
ROAD_RISK_WEB_OIDC_CLIENT_SECRET_FILE=./secrets/{inst.id.lower()}/oidc_client_secret
ROAD_RISK_WEB_OIDC_AUTHORIZATION_ENDPOINT=
ROAD_RISK_WEB_OIDC_TOKEN_ENDPOINT=
ROAD_RISK_WEB_OIDC_LOGOUT_ENDPOINT=
ROAD_RISK_TLS_CERTIFICATE_FILE=./secrets/{inst.id.lower()}/tls_certificate
ROAD_RISK_TLS_PRIVATE_KEY_FILE=./secrets/{inst.id.lower()}/tls_private_key
"""


def write_private_file(path: Path, content: str, mode: int = 0o600) -> None:
    """Create without overwriting existing deployment settings or credentials."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def generate_service_secrets(directory: Path) -> None:
    """Generate independent service passwords; keep host access directory-private."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    paths = [directory / name for name in ("postgres_password", "minio_password")]
    if any(path.exists() for path in paths):
        raise FileExistsError("Existing service secrets will not be overwritten")
    # Compose file-backed secrets preserve source permissions. They must be
    # readable by the different non-root container users; the host directory
    # (0700) restricts access, and each service receives only its own mounts.
    for path in paths:
        write_private_file(path, secrets.token_hex(32) + "\n", mode=0o444)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and prepare an institutional deployment."
    )
    parser.add_argument(
        "--config",
        default="configs/institutional_tenant.example.toml",
        help="Path to institutional TOML configuration.",
    )
    parser.add_argument(
        "--generate-env",
        action="store_true",
        help="Generate infra/docker/.env.institution from the configuration.",
    )
    parser.add_argument(
        "--generate-secrets",
        action="store_true",
        help="Create random database and storage secrets; never overwrite existing files.",
    )
    parser.add_argument("--readiness-report", type=Path, help="Write a non-overwriting JSON configuration readiness record; runtime acceptance remains separate.")
    parser.add_argument("--env-output", type=Path, default=REPO_ROOT / "infra/docker/.env.institution", help="Deployment environment file; use a different ignored .env.<institution> file for each installation.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path

    if not config_path.is_file():
        print(f"ERROR: Configuration file not found at: {config_path}", file=sys.stderr)
        return 1

    print("=" * 72)
    print("xROAD Institutional Deployment Readiness Audit")
    print("=" * 72)
    print(
        f"Loading configuration: {config_path.relative_to(REPO_ROOT) if config_path.is_relative_to(REPO_ROOT) else config_path}"
    )

    try:
        settings = ProjectSettings.from_toml(config_path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"FAILED to parse configuration: {exc}", file=sys.stderr)
        return 1

    inst = settings.institution
    loc = settings.localization
    geo = settings.geospatial
    gov = settings.governance

    print("\n[Institution Identity]")
    print(f"  Tenant ID       : {inst.id}")
    print(f"  Institution     : {inst.name}")
    print(f"  Brand Name      : {inst.brand_name}")
    print(f"  Brand Color     : {inst.brand_primary_color}")
    print(f"  Admin Tier      : {inst.tier.upper()}")

    print("\n[Regional & Sovereign Settings]")
    print(f"  Country Code    : {settings.country_code}")
    print(f"  Timezone        : {settings.timezone}")
    print(f"  Language        : {loc.language}")
    print(f"  Driving Side    : {loc.driving_side.upper()}-hand drive")
    print(
        f"  Units           : Distance ({loc.distance_unit}), Speed ({loc.speed_unit}), Currency ({loc.currency})"
    )
    print(f"  Native CRS      : {geo.native_crs}")
    print(f"  Target CRS      : {geo.target_crs}")

    print("\n[Governance & Privacy]")
    print(f"  k-Anonymity     : Threshold >= {gov.k_anonymity_threshold}")
    print(f"  Data Mode       : {gov.data_minimization_mode}")
    print(f"  Compliance      : {', '.join(gov.compliance_frameworks)}")

    print("\n[Installed Product]")
    print(f"  Profile         : {settings.deployment.profile}")
    print(f"  Revision        : {settings.configuration_revision}")
    print(f"  Modules         : {', '.join(settings.deployment.enabled_modules)}")
    print(f"  Organizations   : {len(settings.deployment.organizations)}")
    print(f"  Jurisdictions   : {len(settings.deployment.jurisdictions)}")
    readiness = settings.validate_institutional_readiness()

    print("\n[Audit Checks]")
    for check in readiness["checks"]:
        status = "PASSED" if check["passed"] else "FAILED"
        symbol = "[OK]" if check["passed"] else "[!!]"
        print(f"  {symbol} {check['name']:<28}: {status} ({check['details']})")

    if readiness["warnings"]:
        print("\n[Warnings]")
        for w in readiness["warnings"]:
            print(f"  * {w}")

    if args.readiness_report:
        report = {
            "schema_version": 1,
            "institution_id": settings.institution.id,
            "configuration_revision": settings.configuration_revision,
            "profile": settings.deployment.profile,
            "enabled_modules": list(settings.deployment.enabled_modules),
            "configuration_readiness": readiness,
            "runtime_acceptance": "not_verified",
            "regulatory_certification": "not_asserted",
        }
        try:
            write_private_file(args.readiness_report, json.dumps(report, indent=2) + "\n")
        except OSError as exc:
            print(f"ERROR: Could not create readiness report: {exc}", file=sys.stderr)
            return 1

    if not readiness["all_critical_checks_passed"]:
        print(
            "\nCRITICAL: One or more configuration readiness checks failed. Aborting deployment.",
            file=sys.stderr,
        )
        return 1

    print("\nConfiguration checks passed. TLS, SSO, secrets, and runtime acceptance still require verification.")

    if args.generate_env:
        if not config_path.is_relative_to(REPO_ROOT / "configs"):
            print(
                "ERROR: Deployment configuration must be under the repository configs/ mount.",
                file=sys.stderr,
            )
            return 1
        rel_config = config_path.relative_to(REPO_ROOT)
        env_output_path = args.env_output.resolve()
        try:
            write_private_file(
                env_output_path, generate_env_content(settings, str(rel_config))
            )
        except (OSError, ValueError) as exc:
            print(
                f"ERROR: Could not create deployment environment: {exc}",
                file=sys.stderr,
            )
            return 1
        print(
            f"Wrote production environment file: {env_output_path}"
        )
        print("\nAfter provisioning TLS and SSO, follow docs/institutional-deployment-guide.md. Stack command:")
        print(
            f"  docker compose --env-file {shlex.quote(str(env_output_path))} -f infra/docker/docker-compose.institution.yml up -d"
        )

    if args.generate_secrets:
        try:
            generate_service_secrets(
                REPO_ROOT / "infra" / "docker" / "secrets" / inst.id.lower()
            )
        except OSError as exc:
            print(f"ERROR: Could not create service secrets: {exc}", file=sys.stderr)
            return 1
        print(
            "Created service secret files. Supply the IdP client secret and institutional TLS certificate/key separately."
        )

    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
