"""FastAPI skeleton for the production API service."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from apps.api.auth import (
    AuthContext,
    ROLE_ANALYST,
    ROLE_ADMIN,
    ROLE_DATA_OPERATOR,
    ROLE_MUNICIPALITY_VIEWER,
    ROLE_TRAFFIC_ENGINEER,
    get_auth_context,
    get_auth_provider_integration_path,
    get_role_matrix,
    require_municipality_access,
    require_organization_access,
    require_roles,
)
from apps.api.db import repositories
from apps.api.db.session import get_db_session
from apps.api.settings import ApiSettings, get_settings
from apps.api.storage import resolve_artifact_download
import apps.api.services.admin_control as admin_control
import apps.api.services.automation_controls as automation_controls
import apps.api.services.intervention_portfolio as intervention_portfolio
import apps.api.services.observability as observability
import apps.api.services.postgis_domain as postgis_domain
import apps.api.services.scenario_planner as scenario_planner
import apps.api.services.vru_signals as vru_signals
from apps.api.middleware.security_headers import SecurityHeadersMiddleware
from apps.api.middleware.operational_hardening import (
    InMemoryRateLimitMiddleware,
    RequestObservabilityMiddleware,
    get_runtime_metrics_registry,
)
import apps.api.services.artifact_storage as artifact_storage
import apps.api.services.error_tracking as error_tracking
import apps.api.services.ingestion_jobs as ingestion_jobs
import apps.api.services.published_refresh_jobs as published_refresh_jobs
import apps.api.services.reporting_hub as reporting_hub
import apps.api.services.recommendations as recommendations
import apps.api.services.siting_advisor as siting_advisor
import apps.api.services.risk_map as risk_map
import apps.api.services.segment_drill_down as segment_drill_down
import apps.api.services.national_services as national_services
from road_risk_modeling import published_api
from road_risk_modeling.published_queries import query_published_resource

APP_TITLE = "RARM Road Risk API"
APP_VERSION = "v1"
APP_DESCRIPTION = (
    "RARM (Road Accidents Risk Modeling) — production-oriented FastAPI shell "
    "for the municipal road-safety intelligence platform."
)


class StorageUploadPresignRequest(BaseModel):
    organization_id: str
    job_type: str
    filename: str
    municipality_id: str | None = None
    source_id: str | None = None
    publication_tier: str = "restricted"
    content_type: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ReportUploadPresignRequest(BaseModel):
    organization_id: str
    report_type: str
    title: str
    output_format: str = "pdf"
    municipality_id: str | None = None
    visibility_tier: str = "restricted"
    filename: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class PublishedRefreshJobRequest(BaseModel):
    organization_id: str
    municipality_id: str | None = None
    source_id: str | None = None
    data_root: str = "data"
    registry_output_dir: str = "data/registry"
    published_index_output_dir: str = "data/published_index"
    dashboard_output_dir: str = "data/dashboard"
    output_dir: str = "data/reporting/published_refresh/latest"
    dispatch_mode: str = "auto"


class IngestionUploadRegistrationRequest(BaseModel):
    organization_id: str
    source_id: str
    filename: str
    municipality_id: str | None = None
    content_type: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class IngestionValidationRequest(BaseModel):
    organization_id: str


class IngestionJobDecisionRequest(BaseModel):
    organization_id: str
    decision_note: str | None = None


class IngestionJobExecutionRequest(BaseModel):
    organization_id: str
    dispatch_mode: str = "auto"
    decision_note: str | None = None


class AutomationManualTriggerRequest(BaseModel):
    organization_id: str
    municipality_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class AutomationScheduleControlRequest(BaseModel):
    organization_id: str
    action: str
    schedule_seconds: float | None = None
    notification_channels: list[str] = Field(default_factory=list)


class AutomationNotificationDeliveryRequest(BaseModel):
    organization_id: str
    actions: list[str] | None = None
    limit: int = 50
    email_recipients: list[str] = Field(default_factory=list)
    webhook_url: str | None = None
    dry_run: bool = True


class HsmScreeningRequest(BaseModel):
    organization_id: str
    facility_class: str = "rural_two_lane_two_way"
    calibration_factor_c: float = 1.0
    network_label: str = "custom_network"
    segments: list[dict[str, Any]] = Field(default_factory=list)


class IrapStarRatingRequest(BaseModel):
    organization_id: str
    network_label: str = "custom_network"
    segments: list[dict[str, Any]] = Field(default_factory=list)


class SripGenerationRequest(BaseModel):
    organization_id: str
    network_label: str = "custom_network"
    value_of_statistical_life_eur: float = 1_500_000.0
    value_of_serious_injury_eur: float = 250_000.0
    discount_rate: float = 0.04
    min_bcr_threshold: float = 1.0
    segments: list[dict[str, Any]] = Field(default_factory=list)


class TelematicsIngestionRequest(BaseModel):
    organization_id: str
    network_label: str = "telematics_feed"
    is_waypoints: bool = False
    observations: list[dict[str, Any]] = Field(default_factory=list)


class NearMissScreeningRequest(BaseModel):
    organization_id: str
    network_label: str = "screened_network"
    days_analyzed: int = 365
    fleet_penetration_rate: float = 0.05
    segments: list[dict[str, Any]] = Field(default_factory=list)
    telematics_events: list[dict[str, Any]] = Field(default_factory=list)


class CipOptimizationRequest(BaseModel):
    organization_id: str
    network_label: str = "national_network"
    annual_budgets: list[float] = Field(default_factory=lambda: [10_000_000.0] * 5)
    start_calendar_year: int = 2027
    inflation_rate: float = 0.025
    discount_rate: float = 0.04
    regional_min_quotas: dict[str, float] | None = None
    allow_budget_rollover: bool = False
    candidate_projects: list[dict[str, Any]] = Field(default_factory=list)


class CvRoadAuditRequest(BaseModel):
    organization_id: str
    network_label: str = "audited_network"
    segments: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)


class MicroscopicSsamRequest(BaseModel):
    organization_id: str
    network_label: str = "analyzed_network"
    trajectories: list[dict[str, Any]] = Field(default_factory=list)
    junctions: list[dict[str, Any]] | None = None


class StGnnForecastRequest(BaseModel):
    organization_id: str
    network_label: str = "forecasted_network"
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    time_series_frames: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] | None = None
    horizons: list[int] = Field(default_factory=lambda: [1, 6, 24])


class CausalCountermeasureRequest(BaseModel):
    organization_id: str
    network_label: str = "evaluated_network"
    observational_data: list[dict[str, Any]] = Field(default_factory=list)
    countermeasures: list[str] | None = None


class CitsActuationRequest(BaseModel):
    organization_id: str
    network_label: str = "evaluated_network"
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    sovereign_station_id: str = "IT-MIT-TMC-BA-01"


class SyntheticCountermeasureEvalRequest(BaseModel):
    organization_id: str
    junction_id: str
    baseline_template: str = "BASELINE_SIGNALIZED"
    redesign_template: str = "DUTCH_PROTECTED_JUNCTION"
    duration_seconds: float = 60.0
    vehicle_demand_vph: float = 800.0
    vru_demand_pph: float = 120.0
    random_seed: int = 42
    network_label: str = "evaluated_network"
    include_trajectories: bool = True


class AiActComplianceAuditRequest(BaseModel):
    organization_id: str
    network_label: str = "evaluated_network"
    corridors: list[dict[str, Any]] = Field(default_factory=list)
    protected_attribute: str = "geographic_tier"
    accuracy_auc_roc: float = 0.885
    brier_score_loss: float = 0.082


class FederatedTrainingRoundRequest(BaseModel):
    organization_id: str
    network_label: str = "evaluated_network"
    nodes_data: list[dict[str, Any]] = Field(default_factory=list)
    rounds_count: int = 3
    aggregation_method: str = "fedavg"
    enable_dp: bool = True
    target_epsilon: float = 2.0


class MicromobilityAuditRequest(BaseModel):
    organization_id: str
    network_label: str = "evaluated_network"
    waypoints: list[dict[str, Any]] = Field(default_factory=list)
    segments_data: list[dict[str, Any]] | None = None


class TmcTriggerEvaluateRequest(BaseModel):
    organization_id: str
    threat_type: str = "shockwave_congestion"
    severity_tier: str = "severe"
    crash_probability: float = 0.65
    speed_drop_kmh: float = 25.0
    precipitation_mm_h: float = 0.0
    near_miss_count: int = 0
    corridor_id: str = "CORRIDOR-CUSTOM-01"
    location_name: str = "Metropolitan Corridor"
    latitude: float = 41.1171
    longitude: float = 16.8719


class TmcPlaybookActuateRequest(BaseModel):
    organization_id: str
    incident_id: str
    operator_id: str = "OPERATOR-TMC-CONSOLE"
    authorization_mode: str = "ONE_CLICK"


class CitsIviCompileRequest(BaseModel):
    organization_id: str = "org-default"
    incident_id: str = "INC-CUSTOM-001"
    threat_type: str = "shockwave_congestion"
    severity_tier: str = "severe"
    corridor_id: str = "CORRIDOR-CUSTOM-01"
    location_name: str = "Metropolitan Corridor"
    latitude: float = 41.1085
    longitude: float = 16.8920
    mandatory_vsl_kmh: int = 60
    advisory_vsl_kmh: int = 50
    precipitation_mm_h: float = 0.0
    lane_restrictions: str = "all_open"


class MultiIncidentEvaluationRequest(BaseModel):
    organization_id: str = "org-default"
    scenario_id: str = ""
    upstream_distance_km: float = 2.1
    incidents: list[dict[str, Any]] | None = None


class SpilloverOptimizationRequest(BaseModel):
    organization_id: str = "org-default"
    scenario_id: str = ""
    upstream_distance_km: float = 2.1
    incidents: list[dict[str, Any]] | None = None
    alternative_corridors: list[dict[str, Any]] | None = None


class TelematicsEventPublishRequest(BaseModel):
    organization_id: str = "org-default"
    event_type: str | None = None
    source_type: str = "connected_vehicle"
    severity: str | None = None
    segment_id: str = "corridor-bari-central"
    latitude: float = 41.117143
    longitude: float = 16.871871
    speed_kmh: float = 35.0
    peak_accel_g: float = -0.42
    accel_x_g: float | None = None
    accel_y_g: float = 0.0
    accel_z_g: float = 1.0
    yaw_rate_degs: float = 0.0
    psd_vibration: float = 0.0
    vehicle_id: str | None = None
    description: str = ""


class MinisterialDossierRequest(BaseModel):
    organization_id: str
    network_label: str = "national_network"
    jurisdiction_name: str = "Repubblica Italiana / Regione Puglia / Comune di Bari"
    ministry_authority: str = "Ministero delle Infrastrutture e dei Trasporti"
    hsm_data: dict[str, Any] | None = None
    irap_data: dict[str, Any] | None = None
    telematics_data: dict[str, Any] | None = None
    micromobility_data: dict[str, Any] | None = None
    st_gnn_data: dict[str, Any] | None = None
    cits_data: dict[str, Any] | None = None
    simulation_data: dict[str, Any] | None = None
    causal_data: dict[str, Any] | None = None
    ai_act_data: dict[str, Any] | None = None
    cip_data: dict[str, Any] | None = None


class ResearchPanelRiskRequest(BaseModel):
    organization_id: str
    network_label: str = "evaluated_panel"
    segments_data: list[dict[str, Any]] = Field(default_factory=list)
    crashes_data: list[dict[str, Any]] = Field(default_factory=list)
    weather_data: list[dict[str, Any]] | None = None
    split_strategy: str = "forward_temporal"
    weeks_count: int = 8





class ReportGenerationRequest(BaseModel):
    organization_id: str
    city_key: str
    report_type: str
    output_format: str
    visibility_tier: str = "restricted"
    title: str | None = None
    dispatch_mode: str = "auto"


class ReportLifecycleRequest(BaseModel):
    organization_id: str
    action: str
    visibility_tier: str | None = None
    note: str | None = None


class PostgisArtifactSyncRequest(BaseModel):
    organization_id: str
    municipality_id: str
    city_key: str
    source_id: str | None = None
    ingestion_job_id: str | None = None


class AdminDataSourceCreateRequest(BaseModel):
    organization_id: str
    name: str
    source_type: str
    municipality_id: str | None = None
    provider_name: str | None = None
    governance_status: str = "draft"
    publication_tier: str = "restricted"
    refresh_frequency: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    decision_note: str | None = None


class AdminDataSourceUpdateRequest(BaseModel):
    organization_id: str
    name: str | None = None
    source_type: str | None = None
    municipality_id: str | None = None
    provider_name: str | None = None
    governance_status: str | None = None
    publication_tier: str | None = None
    refresh_frequency: str | None = None
    configuration: dict[str, Any] | None = None
    status: str | None = None
    decision_note: str | None = None


class AdminDataSourceArchiveRequest(BaseModel):
    organization_id: str
    decision_note: str | None = None


class AdminUserLinkRequest(BaseModel):
    organization_id: str
    subject: str
    email: str | None = None
    display_name: str | None = None
    role: str = "analyst"
    status: str = "active"
    decision_note: str | None = None


class AdminMembershipUpdateRequest(BaseModel):
    organization_id: str
    role: str | None = None
    status: str | None = None
    decision_note: str | None = None


class AdminMunicipalityAccessRequest(BaseModel):
    organization_id: str
    municipality_id: str
    access_level: str = "restricted"
    status: str = "active"
    decision_note: str | None = None


class ScenarioDraftCreateRequest(BaseModel):
    organization_id: str
    city_key: str
    name: str
    intervention_code: str
    target_context_key: str | None = None
    target_context_label: str | None = None
    target_asset_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    cost_class: str = "medium"
    uncertainty: str = "medium"


class ScenarioDraftUpdateRequest(BaseModel):
    organization_id: str
    city_key: str | None = None
    name: str | None = None
    intervention_code: str | None = None
    target_context_key: str | None = None
    target_context_label: str | None = None
    target_asset_ids: list[str] | None = None
    target_asset_types: list[str] | None = None
    parameters: dict[str, Any] | None = None
    assumptions: list[str] | None = None
    cost_class: str | None = None
    uncertainty: str | None = None
    status: str | None = None


class ScenarioDraftValidationRequest(BaseModel):
    organization_id: str


class ScenarioRunRequest(BaseModel):
    organization_id: str
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)


class RecommendationReviewRequest(BaseModel):
    organization_id: str
    city_key: str
    to_state: str
    note: str | None = None
    reason_code: str | None = None


class SitingAnalysisRequest(BaseModel):
    organization_id: str
    city_key: str
    facility_type: str
    school_grade: str | None = None
    target_catchment: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)


class InterventionPortfolioCreateRequest(BaseModel):
    organization_id: str
    city_key: str | None = None
    target_object_type: str | None = None
    target_object_id: str | None = None
    intervention_type: str | None = None
    cost_class: str | None = None
    expected_benefit: float | None = None
    priority_score: float | None = None
    status: str = "candidate"
    owner_subject: str | None = None
    planned_start_date: str | None = None
    planned_completion_date: str | None = None
    notes: str | None = None
    scenario_run_id: str | None = None


class InterventionPortfolioUpdateRequest(BaseModel):
    organization_id: str
    status: str | None = None
    owner_subject: str | None = None
    planned_start_date: str | None = None
    planned_completion_date: str | None = None
    notes: str | None = None
    cost_class: str | None = None
    expected_benefit: float | None = None
    priority_score: float | None = None
    after_observed_crashes: float | None = None
    monitoring_period: str | None = None


class InterventionPortfolioRemoveRequest(BaseModel):
    organization_id: str
    reason: str | None = None


def _resolve_path(path_value: Path, *, root_dir: Path) -> Path:
    if path_value.is_absolute():
        return path_value
    return root_dir / path_value


def _load_published_index(settings: ApiSettings) -> tuple[Path, dict]:
    index_path = _resolve_path(settings.published_index_path, root_dir=settings.root_dir)
    payload = published_api._load_published_index(index_path)
    return index_path, payload


def _load_dashboard_summary(settings: ApiSettings) -> tuple[Path, dict]:
    summary_path = _resolve_path(settings.dashboard_summary_path, root_dir=settings.root_dir)
    payload = published_api._load_dashboard_summary(summary_path)
    return summary_path, payload


def _bad_request(exc: RuntimeError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _commit_if_possible(session: Any) -> None:
    commit = getattr(session, "commit", None)
    if callable(commit):
        commit()


def _rollback_if_possible(session: Any) -> None:
    rollback = getattr(session, "rollback", None)
    if callable(rollback):
        rollback()


def _cors_allowed_origins(settings: ApiSettings) -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]


def _rate_limit_exempt_paths(settings: ApiSettings) -> tuple[str, ...]:
    return tuple(
        path.strip()
        for path in settings.rate_limit_exempt_paths.split(",")
        if path.strip()
    )


def _authorize_view(auth: AuthContext, resolved_view: str) -> None:
    if resolved_view == "analyst_segments":
        require_roles(auth, {ROLE_ANALYST})


def _authorize_job_scope(auth: AuthContext, *, organization_id: str, municipality_id: str | None = None) -> None:
    require_organization_access(auth, organization_id)
    if municipality_id:
        require_municipality_access(auth, municipality_id)


def _authorize_analyst_city_scope(auth: AuthContext, municipality_id: str) -> None:
    if not auth.auth_enabled:
        return
    require_roles(auth, {ROLE_ANALYST})
    require_municipality_access(auth, municipality_id)


def _dispatch_published_refresh_job(job_id: str, dispatch_mode: str) -> tuple[str, str | None]:
    resolved_mode = (dispatch_mode or "auto").strip().lower()
    if resolved_mode not in {"auto", "inline", "queued"}:
        raise HTTPException(status_code=400, detail="dispatch_mode must be auto, inline, or queued.")
    if resolved_mode == "inline":
        return "inline", None

    try:
        from services.workers.celery_app import get_celery_app
    except ImportError:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery worker runtime is not installed in this API environment.",
            ) from None
        return "inline", None

    try:
        celery_app = get_celery_app()
    except ImportError:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery worker runtime is not installed in this API environment.",
            ) from None
        return "inline", None

    try:
        async_result = celery_app.send_task(
            published_refresh_jobs.PUBLISHED_REFRESH_TASK_NAME,
            kwargs={"job_id": job_id},
        )
    except Exception:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery broker is unavailable for queued dispatch.",
            ) from None
        return "inline", None
    return "queued", str(async_result.id)


def _dispatch_report_generation(report_id: str, dispatch_mode: str) -> tuple[str, str | None]:
    resolved_mode = (dispatch_mode or "auto").strip().lower()
    if resolved_mode not in {"auto", "inline", "queued"}:
        raise HTTPException(status_code=400, detail="dispatch_mode must be auto, inline, or queued.")
    if resolved_mode == "inline":
        return "inline", None

    try:
        from services.workers.celery_app import get_celery_app
    except ImportError:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery worker runtime is not installed in this API environment.",
            ) from None
        return "inline", None

    try:
        celery_app = get_celery_app()
    except ImportError:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery worker runtime is not installed in this API environment.",
            ) from None
        return "inline", None

    try:
        async_result = celery_app.send_task(
            reporting_hub.REPORT_GENERATION_TASK_NAME,
            kwargs={"report_id": report_id},
        )
    except Exception:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery broker is unavailable for queued dispatch.",
            ) from None
        return "inline", None
    return "queued", str(async_result.id)


def _dispatch_ingestion_execution_job(job_id: str, dispatch_mode: str) -> tuple[str, str | None]:
    resolved_mode = (dispatch_mode or "auto").strip().lower()
    if resolved_mode not in {"auto", "inline", "queued"}:
        raise HTTPException(status_code=400, detail="dispatch_mode must be auto, inline, or queued.")
    if resolved_mode == "inline":
        return "inline", None

    try:
        from services.workers.celery_app import get_celery_app
    except ImportError:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery worker runtime is not installed in this API environment.",
            ) from None
        return "inline", None

    try:
        celery_app = get_celery_app()
    except ImportError:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery worker runtime is not installed in this API environment.",
            ) from None
        return "inline", None

    try:
        async_result = celery_app.send_task(
            ingestion_jobs.INGESTION_EXECUTION_TASK_NAME,
            kwargs={"job_id": job_id},
        )
    except Exception:
        if resolved_mode == "queued":
            raise HTTPException(
                status_code=503,
                detail="Celery broker is unavailable for queued dispatch.",
            ) from None
        return "inline", None
    return "queued", str(async_result.id)


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_production_security()
    from apps.api.middleware.institution_modules import InstitutionModulesMiddleware
    from road_risk_modeling.institutional_product import DeploymentConfig, MODULES
    project = settings.institutional_project
    deployment = project.deployment if project else DeploymentConfig()
    error_tracking.configure_error_tracking(settings)
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(InstitutionModulesMiddleware, enabled_modules=deployment.enabled_modules, jurisdictions=tuple(row.id for row in deployment.jurisdictions) if deployment.profile != "legacy" else None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allowed_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Security hardening: add a small, audited set of response headers
    # to API responses. Exclude HTML docs/static surfaces that need
    # their own script/style policies.
    app.add_middleware(
        SecurityHeadersMiddleware,
        exclude_paths=("/dashboard", "/docs", "/redoc"),
    )
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        request_limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
        exempt_paths=_rate_limit_exempt_paths(settings),
    )
    app.add_middleware(
        RequestObservabilityMiddleware,
        request_id_header=settings.request_id_header,
        logging_enabled=settings.request_logging_enabled,
        json_logs=settings.request_log_json,
        metrics_registry=get_runtime_metrics_registry(),
    )

    dashboard_root = _resolve_path(settings.dashboard_dir, root_dir=settings.root_dir)
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(dashboard_root), html=True, check_dir=False),
        name="dashboard",
    )

    @app.get("/healthz")
    @app.get("/v1/healthz")
    @app.get("/v1/public/health")
    def healthz() -> dict:
        return {
            "api_version": published_api.PUBLISHED_API_VERSION,
            "app_version": APP_VERSION,
            "status": "ok",
        }

    @app.get("/v1/public/institution-config")
    @app.get("/v1/public/branding")
    def public_institution_config() -> dict:
        return settings.get_institutional_branding()


    @app.get("/v1/auth/me")
    def auth_me(auth: AuthContext = Depends(get_auth_context)) -> dict:
        return {
            "auth_enabled": auth.auth_enabled,
            "provider": auth.provider,
            "subject": auth.subject,
            "assigned_roles": sorted(auth.assigned_roles),
            "roles": sorted(auth.roles),
            "scopes": sorted(auth.scopes),
            "organization_ids": sorted(auth.organization_ids),
            "municipality_ids": sorted(auth.municipality_ids),
            "scope_catalog": deployment.scope_catalog(set(auth.organization_ids), set(auth.municipality_ids), super_admin=auth.is_authenticated and "super_admin" in auth.roles) if auth.is_authenticated else {"organizations": [], "municipalities": []},
        }

    @app.get("/v1/admin/institution-deployment")
    def institution_deployment(auth: AuthContext = Depends(get_auth_context)) -> dict:
        require_roles(auth, {"super_admin"})
        return {
            "api_version": APP_VERSION,
            "identity": settings.get_institutional_branding(),
            "configuration": deployment.to_dict(),
            "revision": project.configuration_revision if project else deployment.revision,
            "module_catalog": [{"id": key, "name": name, "enabled": key in deployment.enabled_modules} for key, name in MODULES.items()],
            "change_policy": "Edit the institution's reviewed TOML configuration and restart the services; configuration does not grant user permissions.",
        }

    @app.get("/v1/auth/role-matrix")
    def auth_role_matrix() -> dict:
        return {
            "api_version": APP_VERSION,
            **get_auth_provider_integration_path(settings),
            **get_role_matrix(),
        }

    @app.get("/v1/auth/organizations/{organization_id}/access")
    def auth_organization_access(
        organization_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_organization_access(auth, organization_id)
        return {
            "authorized": True,
            "organization_id": organization_id,
            "subject": auth.subject,
            "roles": sorted(auth.roles),
        }

    @app.get("/v1/auth/municipalities/{municipality_id}/access")
    def auth_municipality_access(
        municipality_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_municipality_access(auth, municipality_id)
        return {
            "authorized": True,
            "municipality_id": municipality_id,
            "subject": auth.subject,
            "roles": sorted(auth.roles),
        }

    @app.post("/v1/storage/uploads/presign")
    def storage_upload_presign(
        request: StorageUploadPresignRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR})
        require_organization_access(auth, request.organization_id)
        plan = artifact_storage.prepare_ingestion_upload(
            session,
            organization_id=request.organization_id,
            municipality_id=request.municipality_id,
            source_id=request.source_id,
            job_type=request.job_type,
            filename=request.filename,
            publication_tier=request.publication_tier,
            content_type=request.content_type,
            parameters=request.parameters,
        )
        return {
            "api_version": APP_VERSION,
            "job_id": str(getattr(plan["job"], "id", "") or ""),
            "input_storage_uri": getattr(plan["job"], "input_storage_uri", None),
            "upload_url": plan["upload_url"],
            "storage_contract": plan["storage_contract"],
        }

    @app.post("/v1/storage/reports/presign")
    def storage_report_presign(
        request: ReportUploadPresignRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        plan = artifact_storage.prepare_report_output(
            session,
            organization_id=request.organization_id,
            municipality_id=request.municipality_id,
            report_type=request.report_type,
            title=request.title,
            output_format=request.output_format,
            visibility_tier=request.visibility_tier,
            filename=request.filename,
            parameters=request.parameters,
        )
        return {
            "api_version": APP_VERSION,
            "report_id": str(getattr(plan["report"], "id", "") or ""),
            "file_storage_uri": getattr(plan["report"], "file_storage_uri", None),
            "upload_url": plan["upload_url"],
            "storage_contract": plan["storage_contract"],
        }

    @app.post("/v1/ingestion-jobs/uploads")
    def register_ingestion_upload(
        request: IngestionUploadRegistrationRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        _authorize_job_scope(
            auth,
            organization_id=request.organization_id,
            municipality_id=request.municipality_id,
        )
        try:
            plan = ingestion_jobs.register_ingestion_upload(
                session,
                organization_id=request.organization_id,
                source_id=request.source_id,
                filename=request.filename,
                municipality_id=request.municipality_id,
                content_type=request.content_type,
                parameters=request.parameters,
                submitted_by_subject=auth.subject,
            )
            _commit_if_possible(session)
        except RuntimeError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Ingestion upload registration failed.") from exc
        return {
            "api_version": APP_VERSION,
            "job_id": str(getattr(plan["job"], "id", "") or ""),
            "input_storage_uri": getattr(plan["job"], "input_storage_uri", None),
            "upload_url": plan["upload_url"],
            "storage_contract": plan["storage_contract"],
            "upload_contract": plan["upload_contract"],
            "source": ingestion_jobs.serialize_ingestion_job_status(session, plan["job"])["source"],
        }

    @app.post("/v1/ingestion-jobs/{job_id}/validate")
    def validate_ingestion_job(
        job_id: str,
        request: IngestionValidationRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != request.organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=request.organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        try:
            payload = ingestion_jobs.validate_ingestion_job_upload(session, job)
            _commit_if_possible(session)
        except RuntimeError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Ingestion validation failed.") from exc
        return {
            "api_version": APP_VERSION,
            "job": payload,
        }

    @app.get("/v1/ingestion-jobs")
    def list_ingestion_jobs(
        organization_id: str = Query(..., description="Owning organization id"),
        municipality_id: str | None = Query(None, description="Optional municipality scope filter"),
        source_id: str | None = Query(None, description="Optional data source filter"),
        status: str | None = Query(None, description="Optional job status filter"),
        limit: int | None = Query(50, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        _authorize_job_scope(
            auth,
            organization_id=organization_id,
            municipality_id=municipality_id,
        )
        jobs = ingestion_jobs.list_ingestion_job_summaries(
            session,
            organization_id=organization_id,
            municipality_id=municipality_id,
            source_id=source_id,
            status=status,
            limit=limit,
        )
        return {
            "api_version": APP_VERSION,
            "jobs": jobs,
        }

    @app.get("/v1/ingestion-jobs/upload-center")
    def get_ingestion_upload_center(
        organization_id: str = Query(..., description="Owning organization id"),
        municipality_id: str | None = Query(None, description="Optional municipality scope filter"),
        source_id: str | None = Query(None, description="Optional data source filter"),
        status: str | None = Query(None, description="Optional job status filter"),
        limit: int | None = Query(50, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        _authorize_job_scope(
            auth,
            organization_id=organization_id,
            municipality_id=municipality_id,
        )
        return {
            "api_version": APP_VERSION,
            **ingestion_jobs.build_upload_center_snapshot(
                session,
                organization_id=organization_id,
                municipality_id=municipality_id,
                source_id=source_id,
                status=status,
                limit=limit,
            ),
        }

    @app.post("/v1/ingestion-jobs/{job_id}/approve")
    def approve_ingestion_job(
        job_id: str,
        request: IngestionJobDecisionRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != request.organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=request.organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        try:
            payload = ingestion_jobs.approve_ingestion_job(
                session,
                job,
                approved_by_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except RuntimeError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Ingestion approval failed.") from exc
        return {
            "api_version": APP_VERSION,
            "job": payload,
        }

    @app.post("/v1/ingestion-jobs/{job_id}/run")
    def run_ingestion_job(
        job_id: str,
        request: IngestionJobExecutionRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != request.organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=request.organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        if job.status not in {ingestion_jobs.INGESTION_STATUS_QUEUED, ingestion_jobs.INGESTION_STATUS_APPROVED}:
            raise _bad_request(RuntimeError(f"Ingestion job status `{job.status}` cannot be executed by a worker."))
        dispatch_mode, task_id = _dispatch_ingestion_execution_job(str(job.id), request.dispatch_mode)
        if dispatch_mode == "inline":
            try:
                payload = ingestion_jobs.execute_ingestion_job(session, job)
                _commit_if_possible(session)
            except RuntimeError as exc:
                _rollback_if_possible(session)
                raise _bad_request(exc) from exc
            except SQLAlchemyError as exc:
                _rollback_if_possible(session)
                raise HTTPException(status_code=503, detail="Ingestion execution failed.") from exc
            return {
                "api_version": APP_VERSION,
                "dispatch_mode": dispatch_mode,
                "task_id": task_id,
                "job": payload,
            }

        repositories.attach_ingestion_job_storage(
            session,
            job,
            job_stats={
                "worker_task_id": task_id,
                "dispatch_mode": dispatch_mode,
                "required_next_action": "wait_for_ingestion_worker_completion",
            },
        )
        _commit_if_possible(session)
        return {
            "api_version": APP_VERSION,
            "dispatch_mode": dispatch_mode,
            "task_id": task_id,
            "job": ingestion_jobs.build_ingestion_job_access_snapshot(session, job),
        }

    @app.post("/v1/ingestion-jobs/{job_id}/retry")
    def retry_ingestion_job(
        job_id: str,
        request: IngestionJobExecutionRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != request.organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=request.organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        try:
            payload = ingestion_jobs.retry_ingestion_job(
                session,
                job,
                retried_by_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except RuntimeError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Ingestion retry failed.") from exc
        return {
            "api_version": APP_VERSION,
            "dispatch_mode": "manual",
            "job": payload,
        }

    @app.post("/v1/ingestion-jobs/{job_id}/cancel")
    def cancel_ingestion_job(
        job_id: str,
        request: IngestionJobExecutionRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != request.organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=request.organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        try:
            payload = ingestion_jobs.cancel_ingestion_job(
                session,
                job,
                cancelled_by_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except RuntimeError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Ingestion cancellation failed.") from exc
        return {
            "api_version": APP_VERSION,
            "job": payload,
        }

    @app.post("/v1/ingestion-jobs/{job_id}/reject")
    def reject_ingestion_job(
        job_id: str,
        request: IngestionJobDecisionRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != request.organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=request.organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        try:
            payload = ingestion_jobs.reject_ingestion_job(
                session,
                job,
                rejected_by_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except RuntimeError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Ingestion rejection failed.") from exc
        return {
            "api_version": APP_VERSION,
            "job": payload,
        }

    @app.get("/v1/ingestion-jobs/{job_id}")
    def get_ingestion_job_status(
        job_id: str,
        organization_id: str = Query(..., description="Owning organization id"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        return {
            "api_version": APP_VERSION,
            "job": ingestion_jobs.build_ingestion_job_access_snapshot(session, job),
        }

    @app.get("/v1/ingestion-jobs/{job_id}/errors")
    def get_ingestion_job_errors(
        job_id: str,
        organization_id: str = Query(..., description="Owning organization id"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        return {
            "api_version": APP_VERSION,
            **ingestion_jobs.load_ingestion_job_error_summary(session, job),
        }

    @app.get("/v1/ingestion-jobs/{job_id}/manifest")
    def get_ingestion_job_manifest(
        job_id: str,
        organization_id: str = Query(..., description="Owning organization id"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        return {
            "api_version": APP_VERSION,
            **ingestion_jobs.load_ingestion_job_manifest(session, job),
        }

    @app.get("/v1/ingestion-jobs/{job_id}/logs")
    def get_ingestion_job_logs(
        job_id: str,
        organization_id: str = Query(..., description="Owning organization id"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_DATA_OPERATOR, ROLE_ADMIN})
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != organization_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found.")
        _authorize_job_scope(
            auth,
            organization_id=organization_id,
            municipality_id=str(job.municipality_id) if job.municipality_id is not None else None,
        )
        return {
            "api_version": APP_VERSION,
            **ingestion_jobs.load_ingestion_job_log(session, job),
        }

    @app.get("/v1/storage/artifacts/access")
    def storage_artifact_access(
        storage_uri: str = Query(..., description="S3-compatible storage URI"),
        publication_tier: str = Query("restricted"),
        organization_id: str | None = None,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        if publication_tier != "public":
            require_roles(auth, {ROLE_ANALYST})
            if organization_id:
                require_organization_access(auth, organization_id)
        access = resolve_artifact_download(
            storage_uri,
            publication_tier=publication_tier,
        )
        return {"api_version": APP_VERSION, **access.as_dict()}

    @app.post("/v1/jobs/published-refresh")
    def trigger_published_refresh_job(
        request: PublishedRefreshJobRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        parameters = published_refresh_jobs.build_published_refresh_job_parameters(
            data_root=_resolve_path(Path(request.data_root), root_dir=settings.root_dir),
            registry_output_dir=_resolve_path(Path(request.registry_output_dir), root_dir=settings.root_dir),
            published_index_output_dir=_resolve_path(
                Path(request.published_index_output_dir),
                root_dir=settings.root_dir,
            ),
            dashboard_output_dir=_resolve_path(
                Path(request.dashboard_output_dir),
                root_dir=settings.root_dir,
            ),
            output_dir=_resolve_path(Path(request.output_dir), root_dir=settings.root_dir),
        )
        parameters["submitted_by_subject"] = auth.subject
        job = published_refresh_jobs.create_published_refresh_job(
            session,
            organization_id=request.organization_id,
            municipality_id=request.municipality_id,
            source_id=request.source_id,
            submitted_by_user_id=None,
            parameters=parameters,
        )
        dispatch_mode, task_id = _dispatch_published_refresh_job(str(job.id), request.dispatch_mode)
        if dispatch_mode == "inline":
            try:
                payload = published_refresh_jobs.execute_published_refresh_job(session, job)
                session.commit()
                return {
                    "api_version": APP_VERSION,
                    "dispatch_mode": dispatch_mode,
                    "task_id": task_id,
                    "job": payload,
                }
            except Exception as exc:
                session.commit()
                raise HTTPException(status_code=500, detail=str(exc)) from exc
        session.commit()
        return {
            "api_version": APP_VERSION,
            "dispatch_mode": dispatch_mode,
            "task_id": task_id,
            "job": published_refresh_jobs.serialize_job_status(session, job),
        }

    @app.get("/v1/jobs/{job_id}")
    def get_backend_job_status(
        job_id: str,
        organization_id: str = Query(..., description="Owning organization id"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        job = repositories.get_ingestion_job(session, job_id)
        if job is None or str(job.organization_id) != organization_id:
            raise HTTPException(status_code=404, detail="Job not found.")
        return {
            "api_version": APP_VERSION,
            "job": published_refresh_jobs.build_job_access_snapshot(session, job),
        }

    @app.get("/v1/published-index")
    def published_index() -> dict:
        try:
            index_path, payload = _load_published_index(settings)
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        return {
            "api_version": published_api.PUBLISHED_API_VERSION,
            "published_index_path": str(index_path),
            "index": payload,
        }

    @app.get("/v1/dashboard-summary")
    def dashboard_summary() -> dict:
        try:
            summary_path, payload = _load_dashboard_summary(settings)
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        return {
            "api_version": published_api.PUBLISHED_API_VERSION,
            "dashboard_summary_path": str(summary_path),
            "summary": payload,
        }

    @app.get("/v1/public/cities")
    def public_city_catalog(session=Depends(get_db_session)) -> dict:
        try:
            payload = risk_map.list_public_cities(settings, session=session)
            if deployment.profile != "legacy":
                jurisdictions = {row.id: row for row in deployment.jurisdictions}
                payload["cities"] = [{**row, "display_name": jurisdictions[row["city_key"]].name} for row in payload.get("cities", []) if row.get("city_key") in jurisdictions]
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/public/cities/{city_key}/risk-map")
    @app.get("/v1/public/cities/{city_key}/risk-tiles")
    def public_city_risk_map(
        city_key: str,
        occurred_year: int | None = None,
        min_score_band: str | None = None,
        limit: int | None = Query(None, gt=0),
        session=Depends(get_db_session),
    ) -> dict:
        try:
            payload = risk_map.build_public_risk_map(
                settings,
                city_key=city_key,
                occurred_year=occurred_year,
                min_score_band=min_score_band,
                limit=limit,
                session=session,
            )
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/public/cities/{city_key}/interventions")
    def public_city_interventions(city_key: str, session=Depends(get_db_session)) -> dict:
        try:
            payload = risk_map.build_public_interventions(settings, city_key=city_key, session=session)
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/public/cities/{city_key}/reports")
    def public_city_reports(
        city_key: str,
        limit: int = Query(reporting_hub.DEFAULT_HISTORY_LIMIT, gt=0, le=200),
        session=Depends(get_db_session),
    ) -> dict:
        payload = reporting_hub.list_public_reports(
            session,
            city_key=city_key,
            limit=limit,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/public/cities/{city_key}/reports/{report_id}/download")
    def public_city_report_download(
        city_key: str,
        report_id: str,
        session=Depends(get_db_session),
    ) -> dict:
        try:
            payload = reporting_hub.get_public_report_download(
                session,
                city_key=city_key,
                report_id=report_id,
            )
        except reporting_hub.ReportingHubAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except reporting_hub.ReportingHubError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/analyst/cities/{city_key}/risk-map")
    def analyst_city_risk_map(
        city_key: str,
        occurred_year: int | None = None,
        min_score_band: str | None = None,
        limit: int | None = Query(None, gt=0),
        junction_limit: int | None = Query(None, gt=0),
        crossing_limit: int | None = Query(None, gt=0),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        _authorize_analyst_city_scope(auth, city_key)
        try:
            payload = risk_map.build_analyst_risk_map(
                settings,
                city_key=city_key,
                occurred_year=occurred_year,
                min_score_band=min_score_band,
                limit=limit,
                junction_limit=junction_limit,
                crossing_limit=crossing_limit,
                session=session,
            )
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/public/cities/{city_key}/segments/{segment_score_id}")
    def public_city_segment_drill_down(
        city_key: str,
        segment_score_id: str,
    ) -> dict:
        try:
            payload = segment_drill_down.build_public_segment_drill_down(
                settings,
                city_key=city_key,
                segment_score_id=segment_score_id,
            )
        except segment_drill_down.SegmentDrillDownError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/analyst/cities/{city_key}/segments/{segment_score_id}")
    def analyst_city_segment_drill_down(
        city_key: str,
        segment_score_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        _authorize_analyst_city_scope(auth, city_key)
        try:
            payload = segment_drill_down.build_analyst_segment_drill_down(
                settings,
                city_key=city_key,
                segment_score_id=segment_score_id,
            )
        except segment_drill_down.SegmentDrillDownError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/admin/postgis-domain/sync-plan")
    def postgis_domain_sync_plan(
        city_key: str | None = None,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        try:
            payload = postgis_domain.build_domain_sync_plan(settings, city_key=city_key)
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.post("/v1/admin/postgis-domain/sync")
    def sync_postgis_domain_from_artifacts(
        request: PostgisArtifactSyncRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        require_municipality_access(auth, request.city_key)
        try:
            payload = postgis_domain.sync_published_artifacts_to_domain(
                session,
                settings,
                organization_id=request.organization_id,
                municipality_id=request.municipality_id,
                city_key=request.city_key,
                source_id=request.source_id,
                ingestion_job_id=request.ingestion_job_id,
            )
            _commit_if_possible(session)
        except RuntimeError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="PostGIS domain sync failed.") from exc
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/reports/overview")
    def reports_overview(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str | None = Query(None, description="Municipality / city scope"),
        history_limit: int = Query(reporting_hub.DEFAULT_HISTORY_LIMIT, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_MUNICIPALITY_VIEWER})
        require_organization_access(auth, organization_id)
        if city_key:
            require_municipality_access(auth, city_key)
        try:
            payload = reporting_hub.build_reporting_overview(
                session,
                settings,
                organization_id=organization_id,
                city_key=city_key,
                history_limit=history_limit,
            )
        except reporting_hub.ReportingHubError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/reports")
    def list_reports(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str | None = Query(None, description="Municipality / city scope"),
        limit: int = Query(reporting_hub.DEFAULT_HISTORY_LIMIT, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_MUNICIPALITY_VIEWER})
        require_organization_access(auth, organization_id)
        if city_key:
            require_municipality_access(auth, city_key)
        return {
            "api_version": APP_VERSION,
            **reporting_hub.list_report_history(
                session,
                organization_id=organization_id,
                city_key=city_key,
                limit=limit,
                role=reporting_hub.resolve_report_role_for_auth(auth.roles),
            ),
        }

    @app.post("/v1/reports/generate")
    def generate_report(
        request: ReportGenerationRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_MUNICIPALITY_VIEWER})
        require_organization_access(auth, request.organization_id)
        require_municipality_access(auth, request.city_key)
        requested_dispatch_mode = (request.dispatch_mode or "auto").strip().lower()
        if requested_dispatch_mode not in {"auto", "inline", "queued"}:
            raise HTTPException(status_code=400, detail="dispatch_mode must be auto, inline, or queued.")
        try:
            require_roles(auth, {reporting_hub.required_role_for_report(request.report_type)})
            payload = reporting_hub.create_report_request(
                session,
                settings,
                organization_id=request.organization_id,
                city_key=request.city_key,
                report_type=request.report_type,
                output_format=request.output_format,
                visibility_tier=request.visibility_tier,
                title=request.title,
            )
            report_id = payload["report"]["report_id"]
            dispatch_mode, task_id = _dispatch_report_generation(report_id, request.dispatch_mode)
            if dispatch_mode == "inline":
                report = repositories.get_report(session, report_id)
                if report is None:
                    raise HTTPException(status_code=500, detail="Generated report record not found.")
                result = reporting_hub.execute_report_generation(session, settings, report)
                _commit_if_possible(session)
                return {
                    "api_version": APP_VERSION,
                    "dispatch_mode": dispatch_mode,
                    "task_id": task_id,
                    **result,
                }
            _commit_if_possible(session)
            return {
                "api_version": APP_VERSION,
                "dispatch_mode": dispatch_mode,
                "task_id": task_id,
                **payload,
            }
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            if requested_dispatch_mode == "queued":
                raise HTTPException(
                    status_code=503,
                    detail="Database is unavailable for persistent queued report generation.",
                ) from exc
            return {
                "api_version": APP_VERSION,
                "dispatch_mode": "inline",
                "task_id": None,
                **reporting_hub.generate_transient_report(
                    settings,
                    organization_id=request.organization_id,
                    city_key=request.city_key,
                    report_type=request.report_type,
                    output_format=request.output_format,
                    visibility_tier=request.visibility_tier,
                    title=request.title,
                ),
            }
        except reporting_hub.ReportingHubError as exc:
            _commit_if_possible(session)
            raise _bad_request(exc) from exc
        except HTTPException:
            _commit_if_possible(session)
            raise
        except Exception as exc:
            _commit_if_possible(session)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/v1/reports/{report_id}")
    def report_detail(
        report_id: str,
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_MUNICIPALITY_VIEWER})
        require_organization_access(auth, organization_id)
        try:
            payload = reporting_hub.get_report_detail(
                session,
                organization_id=organization_id,
                report_id=report_id,
                role=reporting_hub.resolve_report_role_for_auth(auth.roles),
            )
        except reporting_hub.ReportingHubError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.patch("/v1/reports/{report_id}/lifecycle")
    def report_lifecycle(
        report_id: str,
        request: ReportLifecycleRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_MUNICIPALITY_VIEWER})
        require_organization_access(auth, request.organization_id)
        action = request.action.strip().lower()
        if action in {"publish", "unpublish", "archive"}:
            require_roles(auth, {ROLE_ADMIN})
        elif action in {"review", "reopen", "fail"}:
            require_roles(auth, {ROLE_ANALYST, ROLE_DATA_OPERATOR, ROLE_ADMIN})
        try:
            payload = reporting_hub.transition_report_lifecycle(
                session,
                organization_id=request.organization_id,
                report_id=report_id,
                action=action,
                actor_subject=auth.subject,
                visibility_tier=request.visibility_tier,
                note=request.note,
            )
            _commit_if_possible(session)
        except reporting_hub.ReportingHubAuthorizationError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except reporting_hub.ReportingHubError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Report lifecycle update failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/reports/{report_id}/download")
    def report_download(
        report_id: str,
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_MUNICIPALITY_VIEWER})
        require_organization_access(auth, organization_id)
        try:
            payload = reporting_hub.get_report_download(
                session,
                organization_id=organization_id,
                report_id=report_id,
                role_names=set(auth.roles) if auth.auth_enabled else None,
            )
        except reporting_hub.ReportingHubAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except reporting_hub.ReportingHubError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/admin/control-center")
    def admin_control_center(
        organization_id: str = Query(..., description="Organization scope"),
        recent_audit_limit: int = Query(25, gt=0, le=200),
        recent_jobs_limit: int = Query(25, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = admin_control.build_admin_control_center(
            session,
            organization_id=organization_id,
            recent_audit_limit=recent_audit_limit,
            recent_jobs_limit=recent_jobs_limit,
        )
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/admin/governance-matrix")
    def admin_governance_matrix(
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = admin_control.build_governance_matrix(
            session,
            organization_id=organization_id,
        )
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/admin/automations")
    def admin_automations(
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = admin_control.build_automations_roster(
            organization_id=organization_id,
        )
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.get("/v1/admin/user-roster")
    def admin_user_roster(
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = admin_control.build_user_roster(
            session,
            organization_id=organization_id,
        )
        return {
            "api_version": APP_VERSION,
            **payload,
        }

    @app.post("/v1/admin/data-sources")
    def admin_create_data_source(
        request: AdminDataSourceCreateRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        if request.municipality_id:
            require_municipality_access(auth, request.municipality_id)
        try:
            payload = admin_control.create_governed_data_source(
                session,
                organization_id=request.organization_id,
                municipality_id=request.municipality_id,
                name=request.name,
                source_type=request.source_type,
                provider_name=request.provider_name,
                governance_status=request.governance_status,
                publication_tier=request.publication_tier,
                refresh_frequency=request.refresh_frequency,
                configuration=request.configuration,
                actor_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except admin_control.AdminControlError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Data-source creation failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.patch("/v1/admin/data-sources/{source_id}")
    def admin_update_data_source(
        source_id: str,
        request: AdminDataSourceUpdateRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        updates = request.model_dump(exclude_unset=True)
        organization_id = updates.pop("organization_id")
        decision_note = updates.pop("decision_note", None)
        if updates.get("municipality_id"):
            require_municipality_access(auth, str(updates["municipality_id"]))
        try:
            payload = admin_control.update_governed_data_source(
                session,
                organization_id=organization_id,
                source_id=source_id,
                updates=updates,
                actor_subject=auth.subject,
                decision_note=decision_note,
            )
            _commit_if_possible(session)
        except admin_control.AdminControlError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Data-source update failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/admin/data-sources/{source_id}/archive")
    def admin_archive_data_source(
        source_id: str,
        request: AdminDataSourceArchiveRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        try:
            payload = admin_control.archive_governed_data_source(
                session,
                organization_id=request.organization_id,
                source_id=source_id,
                actor_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except admin_control.AdminControlError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Data-source archive failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/admin/users/link")
    def admin_link_user(
        request: AdminUserLinkRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        try:
            payload = admin_control.link_organization_user(
                session,
                organization_id=request.organization_id,
                subject=request.subject,
                email=request.email,
                display_name=request.display_name,
                role=request.role,
                status=request.status,
                actor_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except admin_control.AdminControlError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="User membership link failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.patch("/v1/admin/memberships/{membership_id}")
    def admin_update_membership(
        membership_id: str,
        request: AdminMembershipUpdateRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        try:
            payload = admin_control.update_membership_access(
                session,
                organization_id=request.organization_id,
                membership_id=membership_id,
                role=request.role,
                status=request.status,
                actor_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except admin_control.AdminControlError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Membership update failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/admin/municipality-access")
    def admin_assign_municipality_access(
        request: AdminMunicipalityAccessRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        try:
            payload = admin_control.assign_municipality_access(
                session,
                organization_id=request.organization_id,
                municipality_id=request.municipality_id,
                access_level=request.access_level,
                status=request.status,
                actor_subject=auth.subject,
                decision_note=request.decision_note,
            )
            _commit_if_possible(session)
        except admin_control.AdminControlError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Municipality access assignment failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/siting-analyses")
    def siting_create_analysis(
        request: SitingAnalysisRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        require_municipality_access(auth, request.city_key)
        try:
            payload = siting_advisor.create_analysis(
                settings,
                organization_id=request.organization_id,
                city_key=request.city_key,
                facility_type=request.facility_type,
                school_grade=request.school_grade,
                target_catchment=request.target_catchment,
                constraints=request.constraints,
                actor_subject=auth.subject,
            )
        except siting_advisor.SitingAdvisorError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, "contract_version": siting_advisor.SITING_ADVISOR_CONTRACT_VERSION, **payload}

    @app.get("/v1/siting-analyses/{analysis_id}")
    def siting_analysis_status(
        analysis_id: str,
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        try:
            payload = siting_advisor.analysis_status(
                settings, organization_id=organization_id, analysis_id=analysis_id
            )
        except siting_advisor.SitingAdvisorError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, "contract_version": siting_advisor.SITING_ADVISOR_CONTRACT_VERSION, **payload}

    @app.get("/v1/siting-analyses/{analysis_id}/results")
    def siting_analysis_results(
        analysis_id: str,
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        try:
            payload = siting_advisor.analysis_results(
                settings, organization_id=organization_id, analysis_id=analysis_id
            )
        except siting_advisor.SitingAdvisorError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/siting-analyses/{analysis_id}/export")
    def siting_analysis_export(
        analysis_id: str,
        organization_id: str = Query(..., description="Organization scope"),
        output_format: str = Query("csv", pattern="^(csv|pdf)$"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> Response:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        try:
            payload = siting_advisor.analysis_results(
                settings, organization_id=organization_id, analysis_id=analysis_id
            )
        except siting_advisor.SitingAdvisorError as exc:
            raise _bad_request(exc) from exc
        if output_format == "pdf":
            lines = [
                f"#{row.get('rank')} {row.get('candidate_id')}: "
                f"score {row.get('suitability_score')}, "
                f"served population {row.get('served_population_estimate')}, "
                f"access risk p{row.get('access_route_risk_percentile')}"
                for row in payload["results"]
            ] or ["No candidate sites matched the requested constraints."]
            content = reporting_hub._simple_pdf_bytes(  # noqa: SLF001
                f"{payload['city_key'].title()} siting brief", lines
            )
            return Response(
                content,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{analysis_id}_siting_brief.pdf"'},
            )
        return Response(
            siting_advisor.results_csv(payload),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{analysis_id}_siting_brief.csv"'},
        )

    @app.get("/v1/recommendations")
    def recommendations_list(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str = Query(..., description="Network/city scope"),
        object_type: str | None = Query(None),
        minimum_bcr: float | None = Query(None, ge=0),
        review_state: str | None = Query(None),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        require_municipality_access(auth, city_key)
        try:
            payload = recommendations.list_recommendations(
                settings,
                organization_id=organization_id,
                city_key=city_key,
                object_type=object_type,
                minimum_bcr=minimum_bcr,
                review_state=review_state,
            )
        except recommendations.RecommendationsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/recommendations/{recommendation_id}")
    def recommendations_detail(
        recommendation_id: str,
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str = Query(..., description="Network/city scope"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        require_municipality_access(auth, city_key)
        try:
            payload = recommendations.recommendation_detail(
                settings,
                organization_id=organization_id,
                city_key=city_key,
                recommendation_id=recommendation_id,
            )
        except recommendations.RecommendationsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/recommendations/{recommendation_id}/review")
    def recommendations_review(
        recommendation_id: str,
        request: RecommendationReviewRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_TRAFFIC_ENGINEER, ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        require_municipality_access(auth, request.city_key)
        try:
            payload = recommendations.transition_recommendation(
                settings,
                organization_id=request.organization_id,
                city_key=request.city_key,
                recommendation_id=recommendation_id,
                to_state=request.to_state,
                actor=auth.subject or "authenticated-reviewer",
                note=request.note,
                reason_code=request.reason_code,
            )
        except recommendations.RecommendationsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/recommendations/action-plan/export")
    def recommendations_export(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str = Query(..., description="Network/city scope"),
        output_format: str = Query("csv", pattern="^(csv|pdf)$"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> Response:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        require_municipality_access(auth, city_key)
        try:
            rows = recommendations.approved_action_plan(
                settings, organization_id=organization_id, city_key=city_key
            )
        except recommendations.RecommendationsError as exc:
            raise _bad_request(exc) from exc
        if output_format == "pdf":
            lines = [
                f"{row['payload'].get('segment_label')}: "
                f"{row['payload'].get('countermeasure_name')} "
                f"(BCR {row['payload'].get('benefit_cost_ratio')})"
                for row in rows
            ] or ["No approved recommendations."]
            content = reporting_hub._simple_pdf_bytes(  # noqa: SLF001
                f"{city_key.title()} municipal action plan", lines
            )
            return Response(
                content,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{city_key}_action_plan.pdf"'},
            )
        return Response(
            recommendations.action_plan_csv(rows),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{city_key}_action_plan.csv"'},
        )

    @app.get("/v1/scenarios/catalog")
    def scenarios_catalog(
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        try:
            payload = scenario_planner.build_scenario_catalog(settings)
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/scenarios/intervention-library")
    def scenarios_intervention_library(
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        try:
            payload = scenario_planner.build_intervention_library(settings)
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/scenarios/drafts")
    def scenarios_drafts(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str | None = Query(None, description="Optional city filter"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        try:
            payload = scenario_planner.list_scenario_drafts(
                settings,
                organization_id=organization_id,
                city_key=city_key,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/scenarios/drafts")
    def scenarios_create_draft(
        request: ScenarioDraftCreateRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        try:
            payload = scenario_planner.create_scenario_draft(
                settings,
                organization_id=request.organization_id,
                city_key=request.city_key,
                name=request.name,
                intervention_code=request.intervention_code,
                target_context_key=request.target_context_key,
                target_context_label=request.target_context_label,
                target_asset_ids=request.target_asset_ids,
                parameters=request.parameters,
                assumptions=request.assumptions,
                cost_class=request.cost_class,
                uncertainty=request.uncertainty,
                actor_subject=auth.subject,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/scenarios/drafts/{scenario_draft_id}")
    def scenarios_get_draft(
        scenario_draft_id: str,
        organization_id: str = Query(..., description="Organization scope"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        try:
            payload = scenario_planner.get_scenario_draft(
                settings,
                organization_id=organization_id,
                scenario_draft_id=scenario_draft_id,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.patch("/v1/scenarios/drafts/{scenario_draft_id}")
    def scenarios_update_draft(
        scenario_draft_id: str,
        request: ScenarioDraftUpdateRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        updates = request.model_dump(exclude_unset=True)
        organization_id = updates.pop("organization_id")
        try:
            payload = scenario_planner.update_scenario_draft(
                settings,
                organization_id=organization_id,
                scenario_draft_id=scenario_draft_id,
                updates=updates,
                actor_subject=auth.subject,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/scenarios/drafts/{scenario_draft_id}/validate")
    def scenarios_validate_draft(
        scenario_draft_id: str,
        request: ScenarioDraftValidationRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        try:
            payload = scenario_planner.validate_scenario_draft(
                settings,
                organization_id=request.organization_id,
                scenario_draft_id=scenario_draft_id,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/scenarios/drafts/{scenario_draft_id}/run")
    def scenarios_run_draft(
        scenario_draft_id: str,
        request: ScenarioRunRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        try:
            payload = scenario_planner.run_scenario_draft(
                settings,
                organization_id=request.organization_id,
                scenario_draft_id=scenario_draft_id,
                parameter_overrides=request.parameter_overrides,
                actor_subject=auth.subject,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/scenarios/runs")
    def scenarios_runs(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str | None = Query(None, description="Optional city filter"),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        try:
            payload = scenario_planner.list_scenario_runs(
                settings,
                organization_id=organization_id,
                city_key=city_key,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/scenarios/cities/{city_key}")
    def scenarios_city_bundle(
        city_key: str,
        scenario_limit: int | None = Query(None, gt=0, le=200),
        portfolio_limit: int | None = Query(None, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        try:
            payload = scenario_planner.build_city_scenario_bundle(
                settings,
                city_key=city_key,
                scenario_limit=scenario_limit,
                portfolio_limit=portfolio_limit,
                role=ROLE_ANALYST,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/scenarios/cities/{city_key}/portfolios")
    def scenarios_city_portfolios(
        city_key: str,
        limit: int | None = Query(None, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        try:
            payload = scenario_planner.build_portfolio_rankings(
                settings,
                city_key=city_key,
                limit=limit,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/scenarios/cities/{city_key}/scenarios/{scenario_id}")
    def scenarios_city_scenario_detail(
        city_key: str,
        scenario_id: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        try:
            payload = scenario_planner.build_scenario_detail(
                settings,
                city_key=city_key,
                scenario_id=scenario_id,
                role=ROLE_ANALYST,
            )
        except scenario_planner.ScenarioPlannerError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/interventions/portfolio")
    def interventions_portfolio(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str | None = Query(None, description="Optional city filter"),
        status: str | None = Query(None, description="Optional portfolio status filter"),
        limit: int = Query(100, gt=0, le=500),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        if city_key:
            require_municipality_access(auth, city_key)
        try:
            payload = intervention_portfolio.build_portfolio(
                session,
                organization_id=organization_id,
                city_key=city_key,
                status=status,
                limit=limit,
            )
        except intervention_portfolio.InterventionPortfolioError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/interventions/portfolio")
    def interventions_create_portfolio_item(
        request: InterventionPortfolioCreateRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        if request.city_key:
            require_municipality_access(auth, request.city_key)
        try:
            payload = intervention_portfolio.create_portfolio_item(
                session,
                settings,
                organization_id=request.organization_id,
                city_key=request.city_key,
                target_object_type=request.target_object_type,
                target_object_id=request.target_object_id,
                intervention_type=request.intervention_type,
                cost_class=request.cost_class,
                expected_benefit=request.expected_benefit,
                priority_score=request.priority_score,
                status=request.status,
                owner_subject=request.owner_subject,
                planned_start_date=request.planned_start_date,
                planned_completion_date=request.planned_completion_date,
                notes=request.notes,
                scenario_run_id=request.scenario_run_id,
                actor_subject=auth.subject,
            )
            _commit_if_possible(session)
        except intervention_portfolio.InterventionPortfolioError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Intervention portfolio persistence failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.patch("/v1/interventions/portfolio/{intervention_id}")
    def interventions_update_portfolio_item(
        intervention_id: str,
        request: InterventionPortfolioUpdateRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        updates = request.model_dump(exclude_unset=True)
        organization_id = updates.pop("organization_id")
        try:
            payload = intervention_portfolio.update_portfolio_item(
                session,
                organization_id=organization_id,
                intervention_id=intervention_id,
                updates=updates,
                actor_subject=auth.subject,
            )
            _commit_if_possible(session)
        except intervention_portfolio.InterventionPortfolioError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Intervention portfolio update failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/interventions/portfolio/{intervention_id}/remove")
    def interventions_remove_portfolio_item(
        intervention_id: str,
        request: InterventionPortfolioRemoveRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, request.organization_id)
        try:
            payload = intervention_portfolio.remove_portfolio_item(
                session,
                organization_id=request.organization_id,
                intervention_id=intervention_id,
                actor_subject=auth.subject,
                reason=request.reason,
            )
            _commit_if_possible(session)
        except intervention_portfolio.InterventionPortfolioError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        except SQLAlchemyError as exc:
            _rollback_if_possible(session)
            raise HTTPException(status_code=503, detail="Intervention portfolio removal failed.") from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/interventions/portfolio/export")
    def interventions_portfolio_export(
        organization_id: str = Query(..., description="Organization scope"),
        city_key: str | None = Query(None, description="Optional city filter"),
        status: str | None = Query(None, description="Optional portfolio status filter"),
        limit: int = Query(200, gt=0, le=1000),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_organization_access(auth, organization_id)
        if city_key:
            require_municipality_access(auth, city_key)
        try:
            payload = intervention_portfolio.build_portfolio_export(
                session,
                organization_id=organization_id,
                city_key=city_key,
                status=status,
                limit=limit,
            )
        except intervention_portfolio.InterventionPortfolioError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/traffic-operations/cities/{city_key}/capabilities")
    def traffic_operations_city_capabilities(
        city_key: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_TRAFFIC_ENGINEER})
        require_municipality_access(auth, city_key)
        payload = vru_signals.build_traffic_operations_capabilities(
            settings, city_key=city_key,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/vru/cities/{city_key}/summary")
    def vru_city_summary(
        city_key: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_municipality_access(auth, city_key)
        try:
            payload = vru_signals.build_vru_summary(settings, city_key=city_key)
        except vru_signals.VruSignalsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/vru/cities/{city_key}/top-corridors")
    def vru_city_top_corridors(
        city_key: str,
        limit: int | None = Query(None, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST})
        require_municipality_access(auth, city_key)
        try:
            payload = vru_signals.build_vru_top_corridors(
                settings, city_key=city_key, limit=limit,
            )
        except vru_signals.VruSignalsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/signal-phase/cities/{city_key}/coverage")
    def signal_phase_city_coverage(
        city_key: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_TRAFFIC_ENGINEER})
        require_municipality_access(auth, city_key)
        try:
            payload = vru_signals.build_signal_phase_coverage(settings, city_key=city_key)
        except vru_signals.VruSignalsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/signal-phase/cities/{city_key}/targets")
    def signal_phase_city_targets(
        city_key: str,
        limit: int | None = Query(None, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_TRAFFIC_ENGINEER})
        require_municipality_access(auth, city_key)
        try:
            payload = vru_signals.build_signal_phase_targets(
                settings, city_key=city_key, limit=limit,
            )
        except vru_signals.VruSignalsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/signal-phase/cities/{city_key}/operator-board")
    def signal_phase_city_operator_board(
        city_key: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_TRAFFIC_ENGINEER})
        require_municipality_access(auth, city_key)
        try:
            payload = vru_signals.build_signal_phase_operator_board(
                settings, city_key=city_key,
            )
        except vru_signals.VruSignalsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/signal-phase/cities/{city_key}/overview")
    def signal_phase_city_overview(
        city_key: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_TRAFFIC_ENGINEER})
        require_municipality_access(auth, city_key)
        try:
            payload = vru_signals.build_signal_phase_overview(
                settings, city_key=city_key,
            )
        except vru_signals.VruSignalsError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/automation/schedules")
    def automation_schedules(
        organization_id: str | None = Query(None, description="Optional organization scope for persisted schedule controls"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        if organization_id:
            require_organization_access(auth, organization_id)
        payload = automation_controls.list_automation_schedules(
            session=session if organization_id else None,
            organization_id=organization_id,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.patch("/v1/automation/schedules/{schedule_name}")
    def automation_schedule_control(
        schedule_name: str,
        request: AutomationScheduleControlRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        try:
            payload = automation_controls.control_schedule(
                session,
                organization_id=request.organization_id,
                schedule_name=schedule_name,
                action=request.action,
                schedule_seconds=request.schedule_seconds,
                notification_channels=request.notification_channels,
                actor_user_id=auth.subject,
            )
            _commit_if_possible(session)
        except ValueError as exc:
            _rollback_if_possible(session)
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/automation/runs")
    def automation_runs(
        organization_id: str = Query(..., description="Organization scope"),
        job_type: str | None = Query(
            None,
            description="Optional automation job_type filter",
        ),
        limit: int = Query(50, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = automation_controls.list_automation_runs(
            session,
            organization_id=organization_id,
            job_type=job_type,
            limit=limit,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/automation/runs/trigger")
    def automation_runs_trigger(
        request: AutomationManualTriggerRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        payload = automation_controls.trigger_manual_refresh(
            session,
            organization_id=request.organization_id,
            municipality_id=request.municipality_id,
            submitted_by_user_id=auth.subject,
            parameters=request.parameters,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/automation/notifications")
    def automation_notifications(
        organization_id: str = Query(..., description="Organization scope"),
        limit: int = Query(50, gt=0, le=200),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = automation_controls.list_notifications(
            session,
            organization_id=organization_id,
            limit=limit,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/automation/notifications/deliver")
    def automation_notifications_deliver(
        request: AutomationNotificationDeliveryRequest,
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, request.organization_id)
        payload = automation_controls.deliver_notifications(
            session,
            organization_id=request.organization_id,
            actions=request.actions,
            limit=request.limit,
            email_recipients=request.email_recipients,
            webhook_url=request.webhook_url,
            dry_run=request.dry_run,
        )
        _commit_if_possible(session)
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/automation/stale-sources")
    def automation_stale_sources(
        organization_id: str = Query(..., description="Organization scope"),
        record_notifications: bool = Query(False, description="Whether to write data_source.stale audit notifications"),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = automation_controls.detect_stale_sources(
            session,
            organization_id=organization_id,
            record_notifications=record_notifications,
        )
        if record_notifications:
            _commit_if_possible(session)
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/automation/overview")
    def automation_overview(
        organization_id: str = Query(..., description="Organization scope"),
        runs_limit: int = Query(10, gt=0, le=100),
        notifications_limit: int = Query(10, gt=0, le=100),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = automation_controls.build_automation_overview(
            session,
            organization_id=organization_id,
            runs_limit=runs_limit,
            notifications_limit=notifications_limit,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/observability/info")
    def observability_info() -> dict:
        # Public unauthenticated endpoint for load balancers and ops
        # dashboards. Returns stable identity metadata only.
        payload = observability.build_info_payload(settings)
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/observability/readiness")
    def observability_readiness(
        session=Depends(get_db_session),
    ) -> dict:
        payload = observability.build_readiness_payload(settings, session=session)
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/observability/metrics")
    def observability_metrics(
        organization_id: str = Query(..., description="Organization scope"),
        recent_runs_limit: int = Query(100, gt=0, le=500),
        auth: AuthContext = Depends(get_auth_context),
        session=Depends(get_db_session),
    ) -> dict:
        require_roles(auth, {ROLE_ADMIN})
        require_organization_access(auth, organization_id)
        payload = observability.build_metrics_payload(
            session,
            organization_id=organization_id,
            recent_runs_limit=recent_runs_limit,
            settings=settings,
        )
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/published-resource/latest")
    def published_resource_latest(
        resource_name: str = Query(..., description="Published resource name"),
        prediction_run_label: str | None = None,
        occurred_year: int | None = None,
        tile_size_m: float | None = None,
        view: str | None = None,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        try:
            index_path, index_payload = _load_published_index(settings)
            resolution = published_api._resolve_latest_from_index(
                index_payload,
                resource_name=resource_name,
                prediction_run_label=prediction_run_label,
                occurred_year=occurred_year,
                tile_size_m=tile_size_m,
                view=view,
            )
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        _authorize_view(auth, resolution["resolved"]["resolved_view"])
        return {
            "api_version": published_api.PUBLISHED_API_VERSION,
            "published_index_path": str(index_path),
            "selection_policy": index_payload.get("selection_policy"),
            **resolution,
        }

    @app.get("/v1/published-resource/query")
    def published_resource_query(
        resource_name: str = Query(..., description="Published resource name"),
        prediction_run_label: str | None = None,
        occurred_year: int | None = None,
        tile_size_m: float | None = None,
        view: str | None = None,
        min_score_band: str | None = None,
        limit: int | None = Query(None, gt=0),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        try:
            index_path, index_payload = _load_published_index(settings)
            resolution = published_api._resolve_latest_from_index(
                index_payload,
                resource_name=resource_name,
                prediction_run_label=prediction_run_label,
                occurred_year=occurred_year,
                tile_size_m=tile_size_m,
                view=view,
            )
            resource_payload = query_published_resource(
                resolution["resolved"]["manifest_path"],
                view=resolution["resolved"]["resolved_view"],
                occurred_year=occurred_year,
                min_score_band=min_score_band,
                limit=limit,
                root_dir=settings.root_dir,
            )
        except RuntimeError as exc:
            raise _bad_request(exc) from exc
        _authorize_view(auth, resolution["resolved"]["resolved_view"])
        return {
            "api_version": published_api.PUBLISHED_API_VERSION,
            "published_index_path": str(index_path),
            "selection_policy": index_payload.get("selection_policy"),
            "resolution": resolution["resolved"],
            "resource": resource_payload,
        }

    @app.get("/v1/national/hierarchies/{country_code}")
    def national_hierarchy(
        country_code: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        return {"api_version": APP_VERSION, **national_services.get_national_hierarchy(country_code)}

    @app.get("/v1/national/rollups/{country_code}")
    def national_rollups(
        country_code: str,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        return {"api_version": APP_VERSION, **national_services.get_national_rollups(country_code)}

    @app.get("/v1/hsm/functional-classes")
    def hsm_functional_classes() -> dict:
        return {
            "api_version": APP_VERSION,
            "classes": national_services.list_hsm_functional_classes(),
        }

    @app.post("/v1/hsm/screen-network")
    def hsm_screen_network(
        request: HsmScreeningRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_hsm_network_screening(
                segments=request.segments,
                facility_class=request.facility_class,
                calibration_c=request.calibration_factor_c,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/irap/star-ratings")
    def irap_star_ratings(
        request: IrapStarRatingRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_irap_star_rating(
                segments=request.segments,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/irap/investment-plans")
    def irap_investment_plans(
        request: SripGenerationRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_srip_generation(
                segments=request.segments,
                value_of_statistical_life_eur=request.value_of_statistical_life_eur,
                value_of_serious_injury_eur=request.value_of_serious_injury_eur,
                discount_rate=request.discount_rate,
                min_bcr_threshold=request.min_bcr_threshold,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/telematics/ingest")
    def telematics_ingest(
        request: TelematicsIngestionRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_telematics_ingestion(
                observations=request.observations,
                is_waypoints=request.is_waypoints,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/telematics/near-misses")
    def telematics_near_misses(
        request: NearMissScreeningRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_near_miss_screening(
                segments=request.segments,
                telematics_events=request.telematics_events,
                days_analyzed=request.days_analyzed,
                fleet_penetration_rate=request.fleet_penetration_rate,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/cip/optimize-schedule")
    def cip_optimize_schedule(
        request: CipOptimizationRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_cip_portfolio_optimization(
                candidates=request.candidate_projects,
                annual_budgets=request.annual_budgets,
                start_calendar_year=request.start_calendar_year,
                inflation_rate=request.inflation_rate,
                discount_rate=request.discount_rate,
                regional_min_quotas=request.regional_min_quotas,
                allow_budget_rollover=request.allow_budget_rollover,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/cv/audit-roadway")
    def cv_audit_roadway(
        request: CvRoadAuditRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_cv_road_audit(
                observations=request.observations,
                segments=request.segments,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/ssam/analyze-conflicts")
    def ssam_analyze_conflicts(
        request: MicroscopicSsamRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_microscopic_ssam_analysis(
                trajectories=request.trajectories,
                junctions=request.junctions,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/forecasting/st-gnn-predict")
    def forecasting_st_gnn_predict(
        request: StGnnForecastRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_st_gnn_risk_forecasting(
                nodes=request.nodes,
                time_series_frames=request.time_series_frames,
                edges=request.edges,
                horizons=request.horizons,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/causal/evaluate-countermeasures")
    def causal_evaluate_countermeasures(
        request: CausalCountermeasureRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_causal_countermeasure_evaluation(
                observational_data=request.observational_data,
                countermeasures=request.countermeasures,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/cits/generate-actuation")
    def cits_generate_actuation(
        request: CitsActuationRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_cits_v2x_actuation(
                alerts_data=request.alerts,
                network_label=request.network_label,
                sovereign_station_id=request.sovereign_station_id,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/simulation/synthetic-countermeasure-eval")
    def simulation_synthetic_countermeasure_eval(
        request: SyntheticCountermeasureEvalRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_synthetic_countermeasure_evaluation(
                junction_id=request.junction_id,
                baseline_template=request.baseline_template,
                redesign_template=request.redesign_template,
                duration_seconds=request.duration_seconds,
                vehicle_demand_vph=request.vehicle_demand_vph,
                vru_demand_pph=request.vru_demand_pph,
                random_seed=request.random_seed,
                network_label=request.network_label,
                include_trajectories=request.include_trajectories,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/compliance/ai-act-audit")
    def compliance_ai_act_audit(
        request: AiActComplianceAuditRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_ai_act_conformity_audit(
                corridors=request.corridors,
                network_label=request.network_label,
                protected_attribute=request.protected_attribute,
                accuracy_auc_roc=request.accuracy_auc_roc,
                brier_score_loss=request.brier_score_loss,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/federated/train-round")
    def federated_train_round(
        request: FederatedTrainingRoundRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_federated_learning_round(
                nodes_data=request.nodes_data,
                rounds_count=request.rounds_count,
                aggregation_method=request.aggregation_method,
                enable_dp=request.enable_dp,
                target_epsilon=request.target_epsilon,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/micromobility/analyze-trips")
    def micromobility_analyze_trips(
        request: MicromobilityAuditRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_micromobility_risk_audit(
                waypoints=request.waypoints,
                segments_data=request.segments_data,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/reporting/ministerial-dossier")
    def reporting_ministerial_dossier(
        request: MinisterialDossierRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.generate_sovereign_ministerial_dossier(
                network_label=request.network_label,
                jurisdiction_name=request.jurisdiction_name,
                ministry_authority=request.ministry_authority,
                hsm_data=request.hsm_data,
                irap_data=request.irap_data,
                telematics_data=request.telematics_data,
                micromobility_data=request.micromobility_data,
                st_gnn_data=request.st_gnn_data,
                cits_data=request.cits_data,
                simulation_data=request.simulation_data,
                causal_data=request.causal_data,
                ai_act_data=request.ai_act_data,
                cip_data=request.cip_data,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/research/evaluate-panel-risk")
    def research_evaluate_panel_risk(
        request: ResearchPanelRiskRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        require_organization_access(auth, request.organization_id)
        try:
            payload = national_services.run_segment_panel_risk_evaluation(
                segments_data=request.segments_data,
                crashes_data=request.crashes_data,
                weather_data=request.weather_data,
                split_strategy=request.split_strategy,
                weeks_count=request.weeks_count,
                network_label=request.network_label,
            )
        except national_services.NationalServiceError as exc:
            raise _bad_request(exc) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/telematics/events/publish")
    def telematics_publish_event(
        request: TelematicsEventPublishRequest,
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER, ROLE_DATA_OPERATOR})
        req_data = request.model_dump() if hasattr(request, "model_dump") else request.dict()
        payload = national_services.publish_telematics_stream_event(req_data)
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/telematics/events/recent")
    def telematics_recent_events(
        limit: int = Query(50, ge=1, le=100),
        auth: AuthContext = Depends(get_auth_context),
    ) -> dict:
        payload = national_services.get_recent_telematics_events(limit=limit)
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/telematics/events/sse")
    async def telematics_events_sse(
        topics: str | None = Query(None),
        min_severity: str = Query("moderate"),
    ):
        import uuid
        import json
        from road_risk_modeling.streaming_gateway import (
            StreamSubscriptionFilter,
            get_global_stream_manager,
        )
        mgr = get_global_stream_manager()
        sub_id = f"sse-{uuid.uuid4().hex[:8]}"
        topic_tuple = tuple(t.strip() for t in topics.split(",")) if topics else ()
        sub_filter = StreamSubscriptionFilter(topics=topic_tuple, min_severity=min_severity)
        queue = mgr.register_subscriber(sub_id, sub_filter)

        async def sse_generator():
            try:
                yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'sub_id': sub_id})}\n\n"
                while True:
                    evt = await queue.get()
                    yield evt.to_sse_format()
            except asyncio.CancelledError:
                mgr.unregister_subscriber(sub_id)

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    @app.websocket("/v1/telematics/stream")
    async def telematics_stream_ws(websocket: WebSocket):
        import uuid
        import json
        from road_risk_modeling.streaming_gateway import (
            STREAM_CONTRACT_VERSION,
            get_global_stream_manager,
        )
        await websocket.accept()
        mgr = get_global_stream_manager()
        sub_id = f"ws-{uuid.uuid4().hex[:8]}"
        queue = mgr.register_subscriber(sub_id)
        try:
            await websocket.send_text(
                json.dumps({
                    "type": "connected",
                    "sub_id": sub_id,
                    "contract_version": STREAM_CONTRACT_VERSION,
                    "recent_events": mgr.get_recent_events(limit=5),
                })
            )
            while True:
                evt = await queue.get()
                await websocket.send_text(json.dumps({"type": "telematics_event", "event": evt.to_dict()}))
        except WebSocketDisconnect:
            pass
        except Exception:
            logging.getLogger(__name__).exception("Telematics WebSocket stream failed")
        finally:
            mgr.unregister_subscriber(sub_id)

    @app.post("/v1/forensics/analyze")
    def analyze_forensic_case(request: dict[str, Any], auth: AuthContext = Depends(get_auth_context)):
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        try:
            case = national_services.build_forensic_case_from_payload(request)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise HTTPException(status_code=422, detail="Invalid case input: " + str(exc)) from exc
        return {"api_version": APP_VERSION, "case": case.to_dict(include_samples=True)}

    @app.post("/v1/cits/fleets/analyze")
    def analyze_fleet(request: dict[str, Any], auth: AuthContext = Depends(get_auth_context)):
        require_roles(auth, {ROLE_ANALYST, ROLE_ADMIN, ROLE_TRAFFIC_ENGINEER})
        try:
            message = CitsIviCompileRequest.model_validate(request.get("message", {}))
            inputs = message.model_dump(exclude={"organization_id"})
            ivi = national_services.compile_iso19321_ivi_message(**inputs)
            vehicles = request.get("vehicles")
            if not isinstance(vehicles, list) or any(not isinstance(row, dict) for row in vehicles):
                raise ValueError("vehicles must be an array of reported vehicle objects")
            fleet = national_services.build_connected_fleet_view(vehicles, ivi)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise HTTPException(status_code=422, detail="Invalid fleet input: " + str(exc)) from exc
        return {"api_version": APP_VERSION, "fleet": [v.to_dict() for v in fleet]}

    @app.get("/v1/forensics/cases")
    def list_forensic_cases(auth: AuthContext = Depends(get_auth_context)):
        return {"api_version": APP_VERSION, **national_services.get_forensic_cases()}

    @app.get("/v1/forensics/cases/{case_id}")
    def get_forensic_case(case_id: str, auth: AuthContext = Depends(get_auth_context)):
        payload = national_services.get_forensic_case_detail(case_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Forensic case '{case_id}' not found.")
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/forensics/cases/{case_id}/dossier")
    def get_forensic_case_dossier(case_id: str, auth: AuthContext = Depends(get_auth_context)):
        payload = national_services.generate_forensic_dossier_content(case_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Forensic case '{case_id}' not found.")
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/tmc/playbooks")
    def list_tmc_playbooks(auth: AuthContext = Depends(get_auth_context)):
        return {"api_version": APP_VERSION, **national_services.get_tmc_playbooks()}

    @app.get("/v1/tmc/active-incidents")
    def list_active_tmc_incidents(auth: AuthContext = Depends(get_auth_context)):
        return {"api_version": APP_VERSION, **national_services.get_active_tmc_incidents_list()}

    @app.post("/v1/tmc/evaluate-trigger")
    def evaluate_tmc_trigger(request: TmcTriggerEvaluateRequest, auth: AuthContext = Depends(get_auth_context)):
        payload = national_services.evaluate_tmc_trigger_service(request.model_dump())
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/tmc/actuate-playbook")
    def actuate_tmc_playbook(request: TmcPlaybookActuateRequest, auth: AuthContext = Depends(get_auth_context)):
        try:
            payload = national_services.actuate_tmc_playbook_service(
                incident_id=request.incident_id,
                operator_id=request.operator_id,
                authorization_mode=request.authorization_mode,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/cits/ivi/messages")
    def list_cits_ivi_messages(auth: AuthContext = Depends(get_auth_context)):
        return {"api_version": APP_VERSION, **national_services.get_cits_ivi_messages()}

    @app.get("/v1/cits/fleets/telemetry")
    def get_cits_fleet_telemetry(hazard_lat: float = 41.1085, hazard_lon: float = 16.8920, auth: AuthContext = Depends(get_auth_context)):
        return {"api_version": APP_VERSION, **national_services.get_connected_fleet_telemetry(hazard_lat, hazard_lon)}

    @app.post("/v1/cits/ivi/compile")
    def compile_cits_ivi_message(request: CitsIviCompileRequest, auth: AuthContext = Depends(get_auth_context)):
        payload = national_services.compile_cits_ivi_broadcast_service(request.model_dump())
        return {"api_version": APP_VERSION, **payload}

    @app.get("/v1/tmc/multi-incident/scenarios")
    def list_multi_incident_scenarios(auth: AuthContext = Depends(get_auth_context)):
        return {"api_version": APP_VERSION, **national_services.get_multi_incident_scenarios()}

    @app.post("/v1/tmc/multi-incident/evaluate-conflicts")
    def evaluate_multi_incident_conflicts(request: MultiIncidentEvaluationRequest, auth: AuthContext = Depends(get_auth_context)):
        try:
            payload = national_services.evaluate_incident_conflict_spillover_service(request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"api_version": APP_VERSION, **payload}

    @app.post("/v1/tmc/multi-incident/optimize-mitigation")
    def optimize_multi_incident_mitigation(request: SpilloverOptimizationRequest, auth: AuthContext = Depends(get_auth_context)):
        try:
            payload = national_services.optimize_spillover_mitigation_service(request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"api_version": APP_VERSION, **payload}

    return app






app = create_app()
