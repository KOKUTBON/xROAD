"""Turnkey Institutional Onboarding & Sovereign Verification Demo Harness.

Demonstrates end-to-end institutional onboarding for any country or transport authority:
1. Loads an institutional configuration (e.g. Cerema France, UK DfT, or Puglia Italy).
2. Generates & ingests crash records via DeclarativeCrashAdapter with automatic CRS re-projection.
3. Compiles an authoritative Sovereign Ministerial Safety Dossier (Markdown & PDF) customized
   with the institution's identity, brand colors, and administrative tier.
4. Emits a verifiable onboarding manifest under data/reporting/institutional_onboarding/.

Usage:
    PYTHONPATH=src python3 tools/institutional_onboarding_demo.py
    PYTHONPATH=src python3 tools/institutional_onboarding_demo.py --config configs/project.example.toml
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

# Ensure src is discoverable
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from road_risk_modeling.adapters.declarative_adapter import (
    CodeListCrosswalkConfig,
    DateTimeMappingConfig,
    DeclarativeCrashAdapter,
    DeclarativeSchemaMapping,
    SeverityMappingConfig,
    SpatialMappingConfig,
)
from road_risk_modeling.config import ProjectSettings
from road_risk_modeling.ministerial_dossier import (
    compile_ministerial_dossier,
    render_ministerial_markdown,
    render_ministerial_pdf,
)

REPORT_DIR = REPO_ROOT / "data" / "reporting" / "institutional_onboarding"


def generate_sample_institutional_crashes(country_code: str) -> list[dict[str, str]]:
    """Generate deterministic, structurally faithful sample crash records for the target country."""
    if country_code == "FR":
        # French BAAC / Lambert-93 sample near Paris / Ile-de-France
        # Lambert-93 coordinates (EPSG:2154)
        return [
            {
                "record_id": "FR_2023_001",
                "datetime": "2023-04-12 18:25:00",
                "x_coord": "651980.5",  # Paris region Lambert-93
                "y_coord": "6862140.2",
                "grav": "2",  # Fatal
                "road_cat": "autoroute",
                "light": "plein_jour",
            },
            {
                "record_id": "FR_2023_002",
                "datetime": "2023-06-18 22:40:00",
                "x_coord": "652400.0",
                "y_coord": "6861900.0",
                "grav": "3",  # Serious injury
                "road_cat": "nationale",
                "light": "nuit_eclairee",
            },
            {
                "record_id": "FR_2023_003",
                "datetime": "2023-09-05 08:15:00",
                "x_coord": "653100.0",
                "y_coord": "6862500.0",
                "grav": "4",  # Minor injury
                "road_cat": "voie_urbaine",
                "light": "plein_jour",
            },
        ]
    elif country_code == "GB":
        # British National Grid (EPSG:27700) sample near London
        return [
            {
                "record_id": "GB_2023_001",
                "datetime": "2023-05-14 16:30:00",
                "x_coord": "529090",
                "y_coord": "179645",
                "grav": "1",  # Fatal
                "road_cat": "roundabout",
                "light": "daylight",
            },
            {
                "record_id": "GB_2023_002",
                "datetime": "2023-08-20 21:10:00",
                "x_coord": "530200",
                "y_coord": "180100",
                "grav": "2",  # Serious
                "road_cat": "dual_carriageway",
                "light": "darkness",
            },
        ]
    else:
        # Standard WGS84 sample (Italy / default)
        return [
            {
                "record_id": "IT_2023_001",
                "datetime": "2023-03-10 14:20:00",
                "x_coord": "16.8667",
                "y_coord": "41.1171",
                "grav": "fatal",
                "road_cat": "urbana",
                "light": "giorno",
            },
            {
                "record_id": "IT_2023_002",
                "datetime": "2023-07-22 19:50:00",
                "x_coord": "16.8720",
                "y_coord": "41.1210",
                "grav": "feriti",
                "road_cat": "statale",
                "light": "crepuscolo",
            },
        ]


def build_adapter_mapping_for_demo(settings: ProjectSettings) -> DeclarativeSchemaMapping:
    """Build a DeclarativeSchemaMapping tailored to the loaded ProjectSettings."""
    country = settings.country_code
    native_crs = settings.geospatial.native_crs

    sev_crosswalk = {
        "2": {"fatalities": 1, "injuries": 0, "severity_level": "fatal"},
        "3": {"fatalities": 0, "injuries": 1, "severity_level": "serious"},
        "4": {"fatalities": 0, "injuries": 1, "severity_level": "slight"},
        "1": {"fatalities": 1, "injuries": 0, "severity_level": "fatal"},
        "fatal": {"fatalities": 1, "injuries": 0, "severity_level": "fatal"},
        "feriti": {"fatalities": 0, "injuries": 1, "severity_level": "injury"},
    }

    return DeclarativeSchemaMapping(
        schema_id=f"{settings.institution.id}_demo",
        country_code=country,
        source_system=f"{settings.institution.id}_feed",
        id_column="record_id",
        datetime_mapping=DateTimeMappingConfig(
            datetime_column="datetime",
            datetime_format="%Y-%m-%d %H:%M:%S",
        ),
        spatial_mapping=SpatialMappingConfig(
            x_column="x_coord",
            y_column="y_coord",
            native_crs=native_crs,
        ),
        severity_mapping=SeverityMappingConfig(
            severity_column="grav",
            severity_crosswalk=sev_crosswalk,
        ),
        roadway_type_crosswalk=CodeListCrosswalkConfig(
            column="road_cat",
            mapping={
                "autoroute": "motorway",
                "nationale": "trunk",
                "voie_urbaine": "urban_street",
                "roundabout": "roundabout",
                "dual_carriageway": "dual_carriageway",
                "urbana": "urban_street",
                "statale": "trunk",
            },
        ),
    )


def run_institutional_onboarding_demo(config_path_str: str) -> dict[str, object]:
    config_path = Path(config_path_str)
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path

    print("=" * 72)
    print("xROAD Institutional Onboarding & Sovereign Verification")
    print("=" * 72)
    print(f"Loading institutional configuration: {config_path.relative_to(REPO_ROOT) if config_path.is_relative_to(REPO_ROOT) else config_path}")

    settings = ProjectSettings.from_toml(config_path)
    inst = settings.institution
    loc = settings.localization
    geo = settings.geospatial

    print(f"\n[1] Institutional Verification")
    print(f"  Target Institution : {inst.name}")
    print(f"  Administrative Tier: {inst.tier.upper()} ({settings.country_code})")
    print(f"  White-Label Brand  : {inst.brand_name} (Color: {inst.brand_primary_color})")
    print(f"  Native CRS         : {geo.native_crs} -> Target: {geo.target_crs}")
    print(f"  Localization       : Language [{loc.language}], Units [{loc.distance_unit}, {loc.speed_unit}]")

    # [2] Declarative Ingestion & Auto-CRS reprojection
    print(f"\n[2] Declarative Ingestion & Coordinate Transformation")
    mapping = build_adapter_mapping_for_demo(settings)
    adapter = DeclarativeCrashAdapter(mapping)
    raw_rows = generate_sample_institutional_crashes(settings.country_code)

    canonical_records = []
    for idx, row in enumerate(raw_rows, start=1):
        rec = adapter.map_row(row, source_row_number=idx)
        canonical_records.append(rec)
        print(f"  * Record {rec.crash_id}:")
        print(f"      Native input coordinates: x={row['x_coord']}, y={row['y_coord']} ({geo.native_crs})")
        print(f"      Reprojected WGS84 coords: lat={rec.latitude:.5f}, lon={rec.longitude:.5f} (EPSG:4326)")
        print(f"      Severity outcome        : {rec.severity_level} (fatalities={rec.fatalities}, injuries={rec.injuries})")

    # [3] Sovereign Ministerial Safety Dossier
    print(f"\n[3] Compiling Branded Sovereign Ministerial Dossier")
    authority_title = inst.name
    jurisdiction_title = f"{settings.jurisdiction_name or inst.name} ({settings.country_code})"

    dossier = compile_ministerial_dossier(
        network_label=f"{inst.id}_sovereign_network",
        jurisdiction_name=jurisdiction_title,
        ministry_authority=authority_title,
    )

    markdown_content = render_ministerial_markdown(dossier)
    pdf_bytes = render_ministerial_pdf(dossier)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORT_DIR / f"{inst.id}_ministerial_dossier.md"
    pdf_path = REPORT_DIR / f"{inst.id}_ministerial_dossier.pdf"
    manifest_path = REPORT_DIR / f"{inst.id}_onboarding_manifest.json"

    md_path.write_text(markdown_content, encoding="utf-8")
    pdf_path.write_bytes(pdf_bytes)

    manifest_payload = {
        "institution": inst.to_dict(),
        "localization": loc.to_dict(),
        "geospatial": geo.to_dict(),
        "governance": settings.governance.to_dict(),
        "readiness_checks": settings.validate_institutional_readiness(),
        "ingestion_summary": {
            "records_processed": len(canonical_records),
            "native_crs": geo.native_crs,
            "target_crs": geo.target_crs,
            "fatalities_count": sum(r.fatalities for r in canonical_records),
            "injuries_count": sum(r.injuries for r in canonical_records),
        },
        "artifacts": {
            "ministerial_markdown": str(md_path.relative_to(REPO_ROOT)),
            "ministerial_pdf": str(pdf_path.relative_to(REPO_ROOT)),
            "manifest": str(manifest_path.relative_to(REPO_ROOT)),
        },
        "verified_at_utc": datetime.now(UTC).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"  * Generated Markdown Dossier : {md_path.relative_to(REPO_ROOT)}")
    print(f"  * Generated Multi-Page PDF   : {pdf_path.relative_to(REPO_ROOT)} ({len(pdf_bytes):,} bytes)")
    print(f"  * Verification Manifest      : {manifest_path.relative_to(REPO_ROOT)}")

    print("\nSUCCESS: Institutional onboarding verified and artifacts published.")
    print("=" * 72)
    return manifest_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the institutional onboarding demonstration.")
    parser.add_argument(
        "--config",
        default="configs/institutional_tenant.example.toml",
        help="Path to institutional TOML configuration.",
    )
    args = parser.parse_args()
    run_institutional_onboarding_demo(args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
