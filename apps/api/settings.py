"""Shared API settings with multi-tenant institutional white-label support."""

from __future__ import annotations

from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROAD_RISK_API_")

    root_dir: Path = Field(default=Path("."))
    published_index_path: Path = Field(
        default=Path("data/published_index/published_resources.json")
    )
    dashboard_summary_path: Path = Field(
        default=Path("data/dashboard/dashboard_summary.json")
    )
    dashboard_dir: Path = Field(default=Path("dashboard"))
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # White-Label Institutional & Regional Customization
    tenant_id: str = Field(default="default")
    institution_name: str = Field(default="xROAD Road Safety Analytics")
    brand_name: str = Field(default="xROAD")
    brand_primary_color: str = Field(default="#4B2A8C")
    brand_logo_url: str = Field(default="/brand/road-accidents-risk-modeling-icon.svg")
    portal_subtitle: str = Field(
        default="Open road-safety analytics for reproducible risk screening"
    )
    country_code: str = Field(default="IT")
    default_language: str = Field(default="en")
    driving_side: str = Field(default="right")
    distance_unit: str = Field(default="km")
    speed_unit: str = Field(default="km/h")
    currency: str = Field(default="EUR")
    administrative_tier: str = Field(default="region")
    tenant_config_path: Path | None = Field(default=None)

    # Dynamic Support Layer Path Templates (supporting any city_key)
    signal_junction_metrics_template: str = Field(
        default="data/processed/node_aggregates/{city_key}_open_data_signals/node_year_metrics.geojson"
    )
    crossing_priority_template: str = Field(
        default="data/planning/vru_exposure/{city_key}_frequency_baseline_context_v2/crossing_vru_exposure.geojson"
    )

    # Legacy explicit paths (preserved for full backward compatibility)
    bari_signal_junction_metrics_path: Path = Field(
        default=Path(
            "data/processed/node_aggregates/bari_open_data_signals/node_year_metrics.geojson"
        )
    )
    bari_crossing_priority_path: Path = Field(
        default=Path(
            "data/planning/vru_exposure/bari_frequency_baseline_context_v2/crossing_vru_exposure.geojson"
        )
    )

    scenario_workspace_path: Path = Field(
        default=Path("data/runtime/scenario_workspace/scenarios.json")
    )
    traffic_operations_signal_preview_enabled: bool = Field(default=True)
    env: str = "local"
    request_logging_enabled: bool = Field(default=True)
    request_log_json: bool = Field(default=True)
    request_id_header: str = "X-Request-ID"
    rate_limit_enabled: bool = Field(default=False)
    rate_limit_requests: int = Field(default=120)
    rate_limit_window_seconds: int = Field(default=60)
    rate_limit_exempt_paths: str = (
        "/healthz,/v1/healthz,/v1/public/health,/v1/observability/info,/v1/observability/readiness,"
        "/v1/public/institution-config,/v1/public/branding"
    )
    error_tracking_enabled: bool = Field(default=False)
    sentry_dsn: str | None = None
    sentry_environment: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.0)

    auth_enabled: bool = Field(default=False)
    auth_provider: str = "keycloak"
    auth_jwks_url: str | None = None
    auth_audience: str | None = None
    auth_issuer: str | None = None
    auth_client_id: str | None = None
    auth_role_claim: str = "realm_access.roles"
    auth_organization_claim: str = "organization_ids"
    auth_municipality_claim: str = "municipality_ids"
    auth_algorithms: str = "RS256"
    auth_jwks_cache_seconds: int = 300

    def validate_production_security(self) -> None:
        """Refuse production API startup with disabled or incomplete authentication."""
        project = self.institutional_project
        if self.env.lower() != "production":
            return
        if project is None or project.deployment.profile == "legacy":
            raise ValueError(
                "Production API requires a versioned institutional deployment configuration"
            )
        readiness = project.validate_institutional_readiness()
        if not readiness["all_critical_checks_passed"]:
            failed = [
                check["name"] for check in readiness["checks"] if not check["passed"]
            ]
            raise ValueError(
                f"Institutional configuration checks failed: {', '.join(failed)}"
            )
        if not self.auth_enabled:
            raise ValueError("Production API requires authentication to be enabled")
        for name in ("auth_jwks_url", "auth_issuer"):
            parsed = urlsplit(getattr(self, name) or "")
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ValueError(f"Production API requires a valid HTTPS {name}")
        if not self.auth_audience or not self.auth_audience.strip():
            raise ValueError("Production API requires an explicit auth_audience")

    def get_signal_junction_metrics_path(self, city_key: str) -> Path:
        """Resolve signal junction metrics path dynamically per city/jurisdiction."""
        if city_key == "bari":
            return self.bari_signal_junction_metrics_path
        templated = self.signal_junction_metrics_template.format(city_key=city_key)
        return Path(templated)

    def get_crossing_priority_path(self, city_key: str) -> Path:
        """Resolve crossing priority path dynamically per city/jurisdiction."""
        if city_key == "bari":
            return self.bari_crossing_priority_path
        templated = self.crossing_priority_template.format(city_key=city_key)
        return Path(templated)

    @cached_property
    def institutional_project(self):
        """Load once per process; invalid configured files fail startup explicitly."""
        if self.tenant_config_path is None:
            return None
        from road_risk_modeling.config import ProjectSettings

        project = ProjectSettings.from_toml(self.tenant_config_path)
        if project.localization.language not in ("en", "it", "fr", "es", "de"):
            raise ValueError(
                "Institutional default language is not supported by the web interface"
            )
        return project

    def get_institutional_branding(self) -> dict[str, Any]:
        """Expose identity and product modules; never expose private scope catalogs."""
        project = self.institutional_project
        from road_risk_modeling.institutional_product import DeploymentConfig

        deployment = project.deployment if project else DeploymentConfig()
        return {
            "tenant_id": project.institution.id if project else self.tenant_id,
            "institution_name": project.institution.name
            if project
            else self.institution_name,
            "brand_name": project.institution.brand_name
            if project
            else self.brand_name,
            "brand_primary_color": project.institution.brand_primary_color
            if project
            else self.brand_primary_color,
            "brand_logo_url": project.institution.brand_logo_url
            if project
            else self.brand_logo_url,
            "portal_subtitle": project.institution.portal_subtitle
            if project
            else self.portal_subtitle,
            "country_code": project.country_code if project else self.country_code,
            "default_language": project.localization.language
            if project
            else self.default_language,
            "driving_side": project.localization.driving_side
            if project
            else self.driving_side,
            "units": {
                "distance": project.localization.distance_unit
                if project
                else self.distance_unit,
                "speed": project.localization.speed_unit
                if project
                else self.speed_unit,
                "currency": project.localization.currency if project else self.currency,
            },
            "administrative_tier": project.institution.tier
            if project
            else self.administrative_tier,
            "deployment": {
                **deployment.public_dict(),
                "revision": project.configuration_revision
                if project
                else deployment.revision,
            },
        }


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
