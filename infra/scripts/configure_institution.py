#!/usr/bin/env python3
"""Create a reviewed institution profile without changing application code."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from road_risk_modeling.config import ProjectSettings
from road_risk_modeling.institutional_product import PROFILES

TIERS = {
    "municipality": "municipality",
    "regional_authority": "region",
    "transport_ministry": "country",
    "police": "police_precinct",
    "highway_operator": "concessionaire",
    "custom": "region",
}


def render_config(
    *,
    profile: str,
    institution_id: str,
    institution_name: str,
    jurisdiction_id: str,
    jurisdiction_name: str,
    country_code: str,
    timezone: str,
    language: str = "en",
    currency: str = "EUR",
    native_crs: str = "EPSG:4326",
    additional_modules: list[str] | None = None,
) -> str:
    if profile not in TIERS:
        raise ValueError("Choose a supported institution profile")
    import pycountry

    if pycountry.countries.get(alpha_2=country_code.upper()) is None:
        raise ValueError("Provide the institution's two-letter country code")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Provide a registered IANA timezone") from exc
    if language not in ("en", "it", "fr", "es", "de"):
        raise ValueError("Choose a supported interface language")
    if pycountry.currencies.get(alpha_3=currency.upper()) is None:
        raise ValueError("Provide a three-letter currency code")
    try:
        from pyproj import CRS

        CRS.from_user_input(native_crs)
    except (ImportError, ValueError, RuntimeError) as exc:
        raise ValueError(
            "Provide a registered native CRS and install the api or geospatial extras for CRS validation"
        ) from exc
    modules = list(dict.fromkeys([*PROFILES[profile], *(additional_modules or [])]))
    q = lambda value: json.dumps(value, ensure_ascii=False)
    return f"""# Generated institutional configuration. Review before deployment.
# No identity-provider credentials or production datasets are embedded.
[project]
name = {q(institution_id)}
country_code = {q(country_code.upper())}
timezone = {q(timezone)}

[institution]
id = {q(institution_id)}
name = {q(institution_name)}
tier = {q(TIERS[profile])}
brand_name = {q(institution_name)}
brand_primary_color = "#4B2A8C"
brand_logo_url = "/brand/road-accidents-risk-modeling-icon.svg"
portal_subtitle = "Road safety intelligence and decision support"

[localization]
language = {q(language)}
fallback_languages = ["en"]
driving_side = "right"
distance_unit = "km"
speed_unit = "km/h"
currency = {q(currency.upper())}

[geospatial]
jurisdiction_name = {q(jurisdiction_name)}
admin_level = {q(TIERS[profile])}
native_crs = {q(native_crs)}
target_crs = "EPSG:4326"
road_network_source = "osm"
segment_length_m = 100

[ingestion]
schema_standard = "generic"
crash_source_format = "csv"

[governance]
k_anonymity_threshold = 5
data_minimization_mode = "strict"
allow_public_raw_coordinates = false

[deployment]
schema_version = 1
profile = {q(profile)}
enabled_modules = {q(modules)}

[[deployment.organizations]]
id = {q(institution_id)}
name = {q(institution_name)}
short_label = {q(institution_name)}
municipality_ids = [{q(jurisdiction_id)}]

[[deployment.jurisdictions]]
id = {q(jurisdiction_id)}
name = {q(jurisdiction_name)}
region_label = {q(country_code.upper())}
coverage_label = "Awaiting validated data"
"""


def create_config(output: Path, **kwargs) -> ProjectSettings:
    import tomllib

    from road_risk_modeling.institutional_product import DeploymentConfig

    content = render_config(**kwargs)
    # Validate the product topology before writing any file.
    DeploymentConfig.from_dict(tomllib.loads(content)["deployment"])
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
    return ProjectSettings.from_toml(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(TIERS), required=True)
    parser.add_argument("--institution-id", required=True)
    parser.add_argument("--institution-name", required=True)
    parser.add_argument("--jurisdiction-id", required=True)
    parser.add_argument("--jurisdiction-name", required=True)
    parser.add_argument("--country-code", required=True)
    parser.add_argument("--timezone", required=True)
    parser.add_argument("--language", default="en")
    parser.add_argument("--currency", default="EUR")
    parser.add_argument("--native-crs", default="EPSG:4326")
    parser.add_argument("--enable-module", action="append", dest="additional_modules")
    parser.add_argument("--output", type=Path, required=True)
    args = vars(parser.parse_args())
    output = args.pop("output")
    try:
        settings = create_config(output, **args)
    except (ValueError, OSError) as exc:
        print(f"Configuration creation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Created {output}; profile={settings.deployment.profile}; revision={settings.configuration_revision}"
    )
    print(
        "Review branding, driving conventions, units, governance, modules, and data mappings before bootstrapping."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
