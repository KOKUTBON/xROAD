"""Configuration helpers for project and jurisdiction settings."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping
import tomllib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from road_risk_modeling.institutional_product import DeploymentConfig


@dataclass(slots=True)
class InstitutionConfig:
    """White-label institutional identity and metadata."""

    id: str = "default"
    name: str = "xROAD Analytics"
    tier: str = "region"  # country, region, province, municipality, concessionaire, police_precinct
    brand_name: str = "xROAD"
    brand_primary_color: str = "#4B2A8C"
    brand_logo_url: str = "/brand/road-accidents-risk-modeling-icon.svg"
    contact_email: str | None = None
    portal_subtitle: str = "Open road-safety analytics and risk screening"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tier": self.tier,
            "brand_name": self.brand_name,
            "brand_primary_color": self.brand_primary_color,
            "brand_logo_url": self.brand_logo_url,
            "contact_email": self.contact_email,
            "portal_subtitle": self.portal_subtitle,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InstitutionConfig:
        return cls(
            id=str(data.get("id") or "default"),
            name=str(data.get("name") or "xROAD Analytics"),
            tier=str(data.get("tier") or "region"),
            brand_name=str(data.get("brand_name") or "xROAD"),
            brand_primary_color=str(data.get("brand_primary_color") or "#4B2A8C"),
            brand_logo_url=str(data.get("brand_logo_url") or "/brand/road-accidents-risk-modeling-icon.svg"),
            contact_email=data.get("contact_email"),
            portal_subtitle=str(data.get("portal_subtitle") or "Open road-safety analytics and risk screening"),
        )


@dataclass(slots=True)
class LocalizationConfig:
    """Regional localization, units of measurement, and driving conventions."""

    language: str = "en"
    fallback_languages: tuple[str, ...] = ("en",)
    driving_side: str = "right"  # "right" or "left" (e.g. UK, Australia, Japan)
    distance_unit: str = "km"    # "km" or "miles"
    speed_unit: str = "km/h"     # "km/h" or "mph"
    currency: str = "EUR"

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "fallback_languages": list(self.fallback_languages),
            "driving_side": self.driving_side,
            "distance_unit": self.distance_unit,
            "speed_unit": self.speed_unit,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LocalizationConfig:
        fallbacks = data.get("fallback_languages") or ["en"]
        return cls(
            language=str(data.get("language") or "en"),
            fallback_languages=tuple(str(x) for x in fallbacks),
            driving_side=str(data.get("driving_side") or "right"),
            distance_unit=str(data.get("distance_unit") or "km"),
            speed_unit=str(data.get("speed_unit") or "km/h"),
            currency=str(data.get("currency") or "EUR"),
        )


@dataclass(slots=True)
class GeospatialConfig:
    """Geospatial projections, road network sources, and boundary definitions."""

    jurisdiction_name: str | None = None
    admin_level: str | None = None
    native_crs: str = "EPSG:4326"
    target_crs: str = "EPSG:4326"
    road_network_source: str = "osm"  # "osm", "cadastral", "here", "tomtom"
    network_type: str = "drive"
    segment_length_m: int = 100
    bounding_box: tuple[float, float, float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "jurisdiction_name": self.jurisdiction_name,
            "admin_level": self.admin_level,
            "native_crs": self.native_crs,
            "target_crs": self.target_crs,
            "road_network_source": self.road_network_source,
            "network_type": self.network_type,
            "segment_length_m": self.segment_length_m,
            "bounding_box": list(self.bounding_box) if self.bounding_box else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GeospatialConfig:
        bbox = data.get("bounding_box")
        bounding_box = tuple(float(x) for x in bbox) if bbox and len(bbox) == 4 else None
        return cls(
            jurisdiction_name=data.get("jurisdiction_name"),
            admin_level=data.get("admin_level"),
            native_crs=str(data.get("native_crs") or "EPSG:4326"),
            target_crs=str(data.get("target_crs") or "EPSG:4326"),
            road_network_source=str(data.get("road_network_source") or "osm"),
            network_type=str(data.get("network_type") or "drive"),
            segment_length_m=int(data.get("segment_length_m", 100)),
            bounding_box=bounding_box,  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class IngestionConfig:
    """Crash records ingestion format and external environmental providers."""

    schema_standard: str = "cadas"  # cadas (EU), baac (FR), istat (IT), stats19 (UK), mmucc (US), generic
    crash_source_format: str = "csv"
    crash_csv_member: str | None = None
    weather_provider: str | None = None
    population_provider: str | None = None
    traffic_provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_standard": self.schema_standard,
            "crash_source_format": self.crash_source_format,
            "crash_csv_member": self.crash_csv_member,
            "weather_provider": self.weather_provider,
            "population_provider": self.population_provider,
            "traffic_provider": self.traffic_provider,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IngestionConfig:
        return cls(
            schema_standard=str(data.get("schema_standard") or "cadas"),
            crash_source_format=str(data.get("crash_source_format") or "csv"),
            crash_csv_member=data.get("crash_csv_member"),
            weather_provider=data.get("weather_provider"),
            population_provider=data.get("population_provider"),
            traffic_provider=data.get("traffic_provider"),
        )


@dataclass(slots=True)
class GovernanceConfig:
    """Privacy, anonymization thresholds, and regulatory compliance settings."""

    k_anonymity_threshold: int = 5
    data_minimization_mode: str = "strict"
    compliance_frameworks: tuple[str, ...] = ("eu_ai_act", "gdpr")
    allow_public_raw_coordinates: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "k_anonymity_threshold": self.k_anonymity_threshold,
            "data_minimization_mode": self.data_minimization_mode,
            "compliance_frameworks": list(self.compliance_frameworks),
            "allow_public_raw_coordinates": self.allow_public_raw_coordinates,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GovernanceConfig:
        frameworks = data.get("compliance_frameworks") or ["eu_ai_act", "gdpr"]
        return cls(
            k_anonymity_threshold=int(data.get("k_anonymity_threshold", 5)),
            data_minimization_mode=str(data.get("data_minimization_mode") or "strict"),
            compliance_frameworks=tuple(str(x) for x in frameworks),
            allow_public_raw_coordinates=bool(data.get("allow_public_raw_coordinates", False)),
        )


@dataclass(slots=True)
class ProjectSettings:
    """Unified configuration for risk modeling projects and institutional white-label tenants."""

    # Core project attributes (legacy compatible)
    name: str
    country_code: str
    timezone: str
    legacy_zip: Path | None = None
    jurisdiction_name: str | None = None
    admin_level: str | None = None
    network_type: str = "drive"
    segment_length_m: int = 100
    crash_csv_member: str | None = None
    weather_provider: str | None = None
    population_provider: str | None = None
    traffic_provider: str | None = None
    tasks: tuple[str, ...] = field(default_factory=tuple)
    spatial_holdout: str | None = None
    temporal_holdout: str | None = None

    # Modular sub-configurations for white-label multi-country execution
    institution: InstitutionConfig = field(default_factory=InstitutionConfig)
    localization: LocalizationConfig = field(default_factory=LocalizationConfig)
    geospatial: GeospatialConfig = field(default_factory=GeospatialConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)

    @classmethod
    def from_toml(cls, path: str | Path) -> "ProjectSettings":
        config_path = Path(path)
        with config_path.open("rb") as handle:
            payload = tomllib.load(handle)

        project = payload.get("project", {})
        geography = payload.get("geography", {})
        data = payload.get("data", {})
        modeling = payload.get("modeling", {})

        # Sub-configurations (support both new section names and fallbacks from legacy sections)
        institution_raw = payload.get("institution", {})
        localization_raw = payload.get("localization", {})
        geospatial_raw = payload.get("geospatial", geography)
        ingestion_raw = payload.get("ingestion", data)
        governance_raw = payload.get("governance", {})

        # Reconcile legacy fields into sub-configs if not explicitly provided
        if not institution_raw.get("name") and project.get("name"):
            institution_raw = {"name": project.get("name"), **institution_raw}
        if not geospatial_raw.get("jurisdiction_name") and geography.get("jurisdiction_name"):
            geospatial_raw = {
                "jurisdiction_name": geography.get("jurisdiction_name"),
                "admin_level": geography.get("admin_level"),
                "network_type": geography.get("network_type", "drive"),
                "segment_length_m": geography.get("segment_length_m", 100),
                **geospatial_raw,
            }
        if not ingestion_raw.get("crash_csv_member") and data.get("crash_csv_member"):
            ingestion_raw = {
                "crash_csv_member": data.get("crash_csv_member"),
                "weather_provider": data.get("weather_provider"),
                "population_provider": data.get("population_provider"),
                "traffic_provider": data.get("traffic_provider"),
                **ingestion_raw,
            }

        legacy_zip = project.get("legacy_zip")
        return cls(
            name=project.get("name", "unnamed-project"),
            country_code=project.get("country_code", "XX").upper(),
            timezone=project.get("timezone", "UTC"),
            legacy_zip=Path(legacy_zip) if legacy_zip else None,
            jurisdiction_name=geography.get("jurisdiction_name") or geospatial_raw.get("jurisdiction_name"),
            admin_level=geography.get("admin_level") or geospatial_raw.get("admin_level"),
            network_type=geography.get("network_type") or geospatial_raw.get("network_type", "drive"),
            segment_length_m=int(geography.get("segment_length_m") or geospatial_raw.get("segment_length_m", 100)),
            crash_csv_member=data.get("crash_csv_member") or ingestion_raw.get("crash_csv_member"),
            weather_provider=data.get("weather_provider") or ingestion_raw.get("weather_provider"),
            population_provider=data.get("population_provider") or ingestion_raw.get("population_provider"),
            traffic_provider=data.get("traffic_provider") or ingestion_raw.get("traffic_provider"),
            tasks=tuple(modeling.get("tasks", ())),
            spatial_holdout=modeling.get("spatial_holdout"),
            temporal_holdout=modeling.get("temporal_holdout"),
            institution=InstitutionConfig.from_dict(institution_raw),
            localization=LocalizationConfig.from_dict(localization_raw),
            geospatial=GeospatialConfig.from_dict(geospatial_raw),
            ingestion=IngestionConfig.from_dict(ingestion_raw),
            governance=GovernanceConfig.from_dict(governance_raw),
            deployment=DeploymentConfig.from_dict(payload.get("deployment")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary preserving both top-level keys and nested configs."""
        return {
            # Legacy top-level fields
            "name": self.name,
            "country_code": self.country_code,
            "timezone": self.timezone,
            "legacy_zip": str(self.legacy_zip) if self.legacy_zip else None,
            "jurisdiction_name": self.jurisdiction_name,
            "admin_level": self.admin_level,
            "network_type": self.network_type,
            "segment_length_m": self.segment_length_m,
            "crash_csv_member": self.crash_csv_member,
            "weather_provider": self.weather_provider,
            "population_provider": self.population_provider,
            "traffic_provider": self.traffic_provider,
            "tasks": list(self.tasks),
            "spatial_holdout": self.spatial_holdout,
            "temporal_holdout": self.temporal_holdout,
            # Modular white-label configurations
            "institution": self.institution.to_dict(),
            "localization": self.localization.to_dict(),
            "geospatial": self.geospatial.to_dict(),
            "ingestion": self.ingestion.to_dict(),
            "governance": self.governance.to_dict(),
            "deployment": self.deployment.to_dict(),
        }

    @property
    def configuration_revision(self) -> str:
        """Identify the complete reviewed installation settings, including branding."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]

    def validate_institutional_readiness(self) -> dict[str, Any]:
        """Audit configuration readiness for international and white-label multi-tenant deployment."""
        checks: list[dict[str, Any]] = []
        warnings: list[str] = []

        # 1. Country code validation
        import pycountry
        is_iso2 = pycountry.countries.get(alpha_2=self.country_code) is not None
        checks.append({
            "name": "valid_country_code",
            "passed": is_iso2,
            "details": f"Country code is '{self.country_code}' (valid 2-letter ISO): {is_iso2}",
        })

        # 2. Timezone validation
        try:
            ZoneInfo(self.timezone)
            has_valid_tz = True
        except (ZoneInfoNotFoundError, ValueError):
            has_valid_tz = False
        checks.append({
            "name": "valid_timezone",
            "passed": has_valid_tz,
            "details": f"Timezone is '{self.timezone}'",
        })

        # 3. CRS validation
        try:
            from pyproj import CRS
            CRS.from_user_input(self.geospatial.native_crs)
            CRS.from_user_input(self.geospatial.target_crs)
            crs_valid = True
        except (ImportError, ValueError, RuntimeError):
            crs_valid = False
        checks.append({
            "name": "valid_native_crs",
            "passed": crs_valid,
            "details": f"Native CRS: {self.geospatial.native_crs}; target CRS: {self.geospatial.target_crs} (pyproj required for verification)",
        })

        # 4. Driving side convention
        driving_side_ok = self.localization.driving_side in ("right", "left")
        checks.append({
            "name": "valid_driving_side",
            "passed": driving_side_ok,
            "details": f"Driving side is '{self.localization.driving_side}'",
        })

        # 5. Units validation
        units_ok = self.localization.distance_unit in ("km", "miles") and self.localization.speed_unit in ("km/h", "mph")
        checks.append({
            "name": "valid_measurement_units",
            "passed": units_ok,
            "details": f"Distance: {self.localization.distance_unit}, Speed: {self.localization.speed_unit}",
        })

        # 6. Governance checks
        k_anon_ok = self.governance.k_anonymity_threshold >= 3
        checks.append({
            "name": "k_anonymity_threshold_safe",
            "passed": k_anon_ok,
            "details": f"k-anonymity threshold is {self.governance.k_anonymity_threshold}",
        })

        safe_institution_id = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", self.institution.id))
        checks.append({"name": "safe_institution_id", "passed": safe_institution_id, "details": "Institution ID must be safe for dedicated deployment and secret directory names"})
        currency_valid = pycountry.currencies.get(alpha_3=self.localization.currency) is not None
        checks.append({"name": "valid_currency", "passed": currency_valid, "details": f"Currency is {self.localization.currency}"})

        if not self.jurisdiction_name and not self.geospatial.jurisdiction_name:
            warnings.append("Jurisdiction name is not specified; reports will default to unnamed region.")

        if self.country_code == "XX":
            warnings.append("Country code is placeholder 'XX'; set a real ISO 3166-1 alpha-2 code.")

        all_passed = all(check["passed"] for check in checks)
        return {
            "is_ready": all_passed and len(warnings) == 0,
            "all_critical_checks_passed": all_passed,
            "checks": checks,
            "warnings": warnings,
        }
