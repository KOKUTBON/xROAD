"""Load mounted institutional secrets before starting the API or worker."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit


def read_secret(env: dict[str, str], name: str) -> str:
    path = env.get(name, "")
    if not path:
        raise ValueError(f"{name} must name a mounted secret file")
    value = Path(path).read_text(encoding="utf-8").rstrip("\r\n")
    if len(value) < 24 or any(
        marker in value.lower() for marker in ("changeme", "example", "replace_me")
    ):
        raise ValueError(
            f"{name} must contain a non-placeholder secret of at least 24 characters"
        )
    return value


def https_url(env: dict[str, str], name: str) -> str:
    value = env.get(name, "")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError(
            f"{name} must be an HTTPS URL without embedded credentials or fragments"
        )
    return value


def prepare_environment(env: dict[str, str]) -> dict[str, str]:
    result = dict(env)
    if env.get("ROAD_RISK_INSTITUTION_DEPLOYMENT") != "true":
        return result
    if env.get("ROAD_RISK_API_AUTH_ENABLED") != "true":
        raise ValueError(
            "Institutional deployment requires ROAD_RISK_API_AUTH_ENABLED=true"
        )
    for name in (
        "ROAD_RISK_API_AUTH_JWKS_URL",
        "ROAD_RISK_API_AUTH_ISSUER",
        "ROAD_RISK_PUBLIC_ORIGIN",
    ):
        https_url(env, name)
    origin = urlsplit(env["ROAD_RISK_PUBLIC_ORIGIN"])
    if origin.path not in ("", "/") or origin.query:
        raise ValueError(
            "ROAD_RISK_PUBLIC_ORIGIN must be an origin without a path or query"
        )
    for name in (
        "ROAD_RISK_API_AUTH_AUDIENCE",
        "POSTGRES_USER",
        "POSTGRES_DB",
        "ROAD_RISK_STORAGE_ACCESS_KEY_ID",
    ):
        if not env.get(name, "").strip():
            raise ValueError(f"{name} is required")
    database_password = read_secret(env, "POSTGRES_PASSWORD_FILE")
    storage_password = read_secret(env, "ROAD_RISK_STORAGE_SECRET_ACCESS_KEY_FILE")
    if database_password == storage_password:
        raise ValueError("Database and object-storage secrets must be different")
    result["ROAD_RISK_DATABASE_URL"] = (
        f"postgresql+psycopg://{quote(env['POSTGRES_USER'], safe='')}:{quote(database_password, safe='')}"
        f"@postgres:5432/{quote(env['POSTGRES_DB'], safe='')}"
    )
    result["ROAD_RISK_STORAGE_SECRET_ACCESS_KEY"] = storage_password
    return result


def main() -> int:
    try:
        env = prepare_environment(dict(os.environ))
    except (ValueError, OSError):
        # Never emit secret values, file contents, or a credential-bearing DSN.
        print(
            "Institutional startup rejected: check required HTTPS/auth settings and mounted secret files (minimum 24 characters; no placeholders).",
            file=sys.stderr,
        )
        return 1
    if sys.argv[1:] == ["--check"]:
        print("Institutional configuration checks passed.")
        return 0
    if len(sys.argv) < 2:
        return 1
    os.execvpe(sys.argv[1], sys.argv[1:], env)
    return 0


if __name__ == "__main__":
    sys.exit(main())
