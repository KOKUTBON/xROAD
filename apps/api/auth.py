"""Authentication and RBAC helpers for the API service."""

from __future__ import annotations

import json
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import PyJWTError

from apps.api.db.repositories import record_audit_log
from apps.api.settings import ApiSettings, get_settings


ROLE_MATRIX_VERSION = "road_risk_role_matrix_v1"

ROLE_PUBLIC = "public"
ROLE_MUNICIPALITY_VIEWER = "municipality_viewer"
ROLE_ANALYST = "analyst"
ROLE_DATA_OPERATOR = "data_operator"
ROLE_TRAFFIC_ENGINEER = "traffic_engineer"
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"

ALL_ROLES = (
    ROLE_PUBLIC,
    ROLE_MUNICIPALITY_VIEWER,
    ROLE_ANALYST,
    ROLE_DATA_OPERATOR,
    ROLE_TRAFFIC_ENGINEER,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
)

ROLE_SPECS: dict[str, dict[str, Any]] = {
    ROLE_PUBLIC: {
        "description": "View public dashboard content and public reports.",
        "implies": (),
        "capabilities": (
            "view_public_map",
            "view_public_reports",
        ),
    },
    ROLE_MUNICIPALITY_VIEWER: {
        "description": "Read-only internal access for scoped municipalities.",
        "implies": (ROLE_PUBLIC,),
        "capabilities": (
            "view_internal_dashboards",
            "view_scoped_municipality_data",
        ),
    },
    ROLE_ANALYST: {
        "description": "Inspect hotspots, run analysis workflows, and export scoped technical outputs.",
        "implies": (ROLE_MUNICIPALITY_VIEWER,),
        "capabilities": (
            "query_internal_risk_layers",
            "export_internal_reports",
            "run_scenario_analysis",
        ),
    },
    ROLE_DATA_OPERATOR: {
        "description": "Upload, validate, and manage ingestion jobs for scoped municipalities.",
        "implies": (ROLE_MUNICIPALITY_VIEWER,),
        "capabilities": (
            "manage_uploads",
            "manage_ingestion_jobs",
            "review_data_quality",
        ),
    },
    ROLE_TRAFFIC_ENGINEER: {
        "description": "Manage signal-phase, movement, and traffic operations workflows.",
        "implies": (ROLE_ANALYST,),
        "capabilities": (
            "manage_signal_phase_workflows",
            "manage_traffic_engineering_views",
            "approve_operational_updates",
        ),
    },
    ROLE_ADMIN: {
        "description": "Manage organization-level governance, users, and sensitive internal data.",
        "implies": (ROLE_TRAFFIC_ENGINEER, ROLE_DATA_OPERATOR),
        "capabilities": (
            "manage_users",
            "manage_governance_policies",
            "publish_internal_outputs",
        ),
    },
    ROLE_SUPER_ADMIN: {
        "description": "Platform-level administration across organizations and municipalities.",
        "implies": (ROLE_ADMIN,),
        "capabilities": (
            "manage_platform_configuration",
            "override_organization_scope",
            "view_cross_organization_audit_logs",
        ),
    },
}

AUTH_PROVIDER_DECISION = {
    "recommended_provider": "keycloak",
    "rationale": (
        "Keycloak is the default recommendation for municipal and EU-sensitive deployments. "
        "The API remains OIDC/JWKS-compatible for Entra ID, Cognito, and Auth0."
    ),
    "supported_providers": (
        {"provider": "keycloak", "fit": "self-hosted OIDC for municipal deployments"},
        {"provider": "entra_id", "fit": "Microsoft-heavy public-sector environments"},
        {"provider": "cognito", "fit": "AWS-native managed identity"},
        {"provider": "auth0", "fit": "fast SaaS rollout with external identity management"},
    ),
    "validation_flow": (
        "Bearer token -> JWKS signature validation -> role extraction -> "
        "organization and municipality scope enforcement"
    ),
}


@dataclass(frozen=True)
class AuthContext:
    subject: str | None
    assigned_roles: frozenset[str]
    roles: frozenset[str]
    scopes: frozenset[str]
    claims: dict[str, Any]
    organization_ids: frozenset[str]
    municipality_ids: frozenset[str]
    is_authenticated: bool
    auth_enabled: bool
    provider: str

    @property
    def primary_organization_id(self) -> str | None:
        return sorted(self.organization_ids)[0] if self.organization_ids else None

    @property
    def primary_municipality_id(self) -> str | None:
        return sorted(self.municipality_ids)[0] if self.municipality_ids else None

    @staticmethod
    def anonymous(auth_enabled: bool, provider: str) -> "AuthContext":
        return AuthContext(
            subject=None,
            assigned_roles=frozenset({ROLE_PUBLIC}),
            roles=frozenset({ROLE_PUBLIC}),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset(),
            municipality_ids=frozenset(),
            is_authenticated=False,
            auth_enabled=auth_enabled,
            provider=provider,
        )


_JWKS_CACHE: dict[str, Any] = {"payload": None, "expires_at": 0.0}
_security = HTTPBearer(auto_error=False)
_CURRENT_AUTH_CONTEXT: ContextVar[AuthContext | None] = ContextVar(
    "road_risk_current_auth_context",
    default=None,
)


def get_current_auth_context() -> AuthContext | None:
    """Return the auth context resolved for the active request, if any."""
    return _CURRENT_AUTH_CONTEXT.get()


def set_current_auth_context(context: AuthContext | None) -> None:
    """Publish safe auth context for request logging and incident metrics."""
    _CURRENT_AUTH_CONTEXT.set(context)


def _publish_auth_context(request: Request | None, context: AuthContext) -> AuthContext:
    set_current_auth_context(context)
    if request is not None:
        request.state.auth_context = context
    return context


def _algorithm_list(settings: ApiSettings) -> list[str]:
    return [item.strip() for item in settings.auth_algorithms.split(",") if item.strip()]


def _load_jwks(settings: ApiSettings) -> dict[str, Any]:
    if not settings.auth_jwks_url:
        raise RuntimeError("JWKS URL is required when auth is enabled.")

    if urlparse(settings.auth_jwks_url).scheme not in {"http", "https"}:
        raise RuntimeError("JWKS URL must use HTTP or HTTPS.")

    now = time.time()
    cached = _JWKS_CACHE.get("payload")
    expires_at = float(_JWKS_CACHE.get("expires_at") or 0.0)
    if cached is not None and now < expires_at:
        return cached

    with urlopen(settings.auth_jwks_url, timeout=10) as response:  # nosec B310 # HTTP(S) scheme checked above
        payload = json.load(response)
    if not isinstance(payload, dict) or "keys" not in payload:
        raise RuntimeError("JWKS payload must be a JSON object with a 'keys' list.")

    _JWKS_CACHE["payload"] = payload
    _JWKS_CACHE["expires_at"] = now + max(settings.auth_jwks_cache_seconds, 0)
    return payload


def _select_jwk(payload: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    if not kid:
        return None
    for key in payload.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def _claim_path(payload: dict[str, Any], path: str) -> list[str]:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return []
        current = current.get(part)
    if current is None:
        return []
    if isinstance(current, list):
        return [str(item) for item in current if item is not None]
    return [str(current)]


def _extract_claim_values(
    payload: dict[str, Any],
    primary_path: str,
    *,
    fallback_paths: Iterable[str] = (),
) -> frozenset[str]:
    values: set[str] = set()
    for claim_path in (primary_path, *fallback_paths):
        if not claim_path:
            continue
        values.update(item.strip() for item in _claim_path(payload, claim_path) if item and item.strip())
    return frozenset(values)


def _extract_roles(payload: dict[str, Any], settings: ApiSettings) -> frozenset[str]:
    roles = set(_extract_claim_values(payload, settings.auth_role_claim))
    roles.update(_extract_claim_values(payload, "roles"))
    roles.update(_extract_claim_values(payload, "realm_access.roles"))
    if settings.auth_client_id:
        resource_access = payload.get("resource_access") or {}
        client_access = (
            resource_access.get(settings.auth_client_id)
            if isinstance(resource_access, dict)
            else None
        )
        if isinstance(client_access, dict):
            roles.update(_claim_path(client_access, "roles"))
    if not roles:
        roles.add(ROLE_PUBLIC)
    return frozenset(role for role in roles if role)


def _expand_roles(roles: Iterable[str]) -> frozenset[str]:
    expanded: set[str] = set()
    pending = list(roles)
    while pending:
        role = pending.pop()
        if role in expanded:
            continue
        expanded.add(role)
        spec = ROLE_SPECS.get(role)
        if spec is None:
            continue
        pending.extend(spec.get("implies", ()))
    if not expanded:
        expanded.add(ROLE_PUBLIC)
    return frozenset(expanded)


def _extract_scopes(payload: dict[str, Any]) -> frozenset[str]:
    scopes: set[str] = set()
    scope_value = payload.get("scope")
    if isinstance(scope_value, str):
        scopes.update(scope_value.split())
    scp_value = payload.get("scp")
    if isinstance(scp_value, list):
        scopes.update(str(item) for item in scp_value if item)
    return frozenset(scope for scope in scopes if scope)


def _decode_token(token: str, settings: ApiSettings) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    jwks = _load_jwks(settings)
    key = _select_jwk(jwks, header.get("kid"))
    if key is None:
        raise RuntimeError("JWKS did not contain a matching key for the token.")

    options = {"verify_aud": settings.auth_audience is not None}
    return jwt.decode(
        token,
        jwt.PyJWK.from_dict(key),
        algorithms=_algorithm_list(settings),
        audience=settings.auth_audience,
        issuer=settings.auth_issuer,
        options=options,
    )


def get_role_matrix() -> dict[str, Any]:
    return {
        "role_matrix_version": ROLE_MATRIX_VERSION,
        "roles": [
            {
                "role": role,
                "description": ROLE_SPECS[role]["description"],
                "implies": list(ROLE_SPECS[role]["implies"]),
                "capabilities": list(ROLE_SPECS[role]["capabilities"]),
            }
            for role in ALL_ROLES
        ],
    }


def get_auth_provider_integration_path(settings: ApiSettings) -> dict[str, Any]:
    return {
        **AUTH_PROVIDER_DECISION,
        "selected_provider": settings.auth_provider,
        "claim_configuration": {
            "role_claim": settings.auth_role_claim,
            "organization_claim": settings.auth_organization_claim,
            "municipality_claim": settings.auth_municipality_claim,
        },
    }


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Security(_security),
    request: Request = None,
) -> AuthContext:
    settings = get_settings()
    if not settings.auth_enabled:
        context = AuthContext.anonymous(auth_enabled=False, provider="disabled")
        return _publish_auth_context(request, context)
    if credentials is None or not credentials.credentials:
        context = AuthContext.anonymous(auth_enabled=True, provider=settings.auth_provider)
        return _publish_auth_context(request, context)

    try:
        payload = _decode_token(credentials.credentials, settings)
    except (PyJWTError, RuntimeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    assigned_roles = _extract_roles(payload, settings)
    roles = _expand_roles(assigned_roles)
    scopes = _extract_scopes(payload)
    subject = payload.get("sub") if isinstance(payload, dict) else None
    organization_ids = _extract_claim_values(
        payload,
        settings.auth_organization_claim,
        fallback_paths=("org_ids", "organizations"),
    )
    municipality_ids = _extract_claim_values(
        payload,
        settings.auth_municipality_claim,
        fallback_paths=("municipalities", "municipality_scopes"),
    )
    project = settings.institutional_project
    if project and project.deployment.profile != "legacy":
        configured_orgs = {row.id for row in project.deployment.organizations}
        organization_ids = organization_ids.intersection(configured_orgs)
        linked_jurisdictions = {item for row in project.deployment.organizations if row.id in organization_ids for item in row.municipality_ids}
        municipality_ids = municipality_ids.intersection(linked_jurisdictions)
    context = AuthContext(
        subject=subject,
        assigned_roles=assigned_roles,
        roles=roles,
        scopes=scopes,
        claims=payload,
        organization_ids=organization_ids,
        municipality_ids=municipality_ids,
        is_authenticated=True,
        auth_enabled=True,
        provider=settings.auth_provider,
    )
    return _publish_auth_context(request, context)


def require_roles(principal: AuthContext, required: Iterable[str]) -> None:
    if not principal.auth_enabled:
        return
    if not principal.is_authenticated:
        raise HTTPException(status_code=401, detail="Authentication required.")
    required_roles = {role for role in required if role}
    effective_roles = _expand_roles({*principal.assigned_roles, *principal.roles})
    if required_roles and not effective_roles.intersection(required_roles):
        raise HTTPException(status_code=403, detail="Insufficient role.")


def require_organization_access(principal: AuthContext, organization_id: str) -> None:
    if not principal.auth_enabled:
        return
    if not principal.is_authenticated:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if not organization_id:
        raise HTTPException(status_code=400, detail="organization_id is required.")
    effective_roles = _expand_roles({*principal.assigned_roles, *principal.roles})
    if ROLE_SUPER_ADMIN in effective_roles:
        return
    require_roles(principal, {ROLE_MUNICIPALITY_VIEWER})
    if organization_id not in principal.organization_ids:
        raise HTTPException(status_code=403, detail="Organization scope denied.")


def require_municipality_access(principal: AuthContext, municipality_id: str) -> None:
    if not principal.auth_enabled:
        return
    if not principal.is_authenticated:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if not municipality_id:
        raise HTTPException(status_code=400, detail="municipality_id is required.")
    effective_roles = _expand_roles({*principal.assigned_roles, *principal.roles})
    if ROLE_SUPER_ADMIN in effective_roles:
        return
    require_roles(principal, {ROLE_MUNICIPALITY_VIEWER})
    if municipality_id not in principal.municipality_ids:
        raise HTTPException(status_code=403, detail="Municipality scope denied.")


def build_sensitive_action_audit_event(
    principal: AuthContext,
    *,
    action: str,
    target_type: str,
    organization_id: str | None = None,
    municipality_id: str | None = None,
    target_id: str | None = None,
    status: str = "recorded",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_organization_id = organization_id or principal.primary_organization_id
    if principal.auth_enabled and resolved_organization_id is None:
        raise ValueError("organization_id is required for authenticated audit events.")

    event_metadata = dict(metadata or {})
    event_metadata.setdefault("auth_provider", principal.provider)
    event_metadata.setdefault("assigned_roles", sorted(principal.assigned_roles))
    event_metadata.setdefault("effective_roles", sorted(principal.roles))
    event_metadata.setdefault("organization_scope", sorted(principal.organization_ids))
    event_metadata.setdefault("municipality_scope", sorted(principal.municipality_ids))

    return {
        "organization_id": resolved_organization_id,
        "municipality_id": municipality_id,
        "user_id": principal.subject,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "status": status,
        "metadata": event_metadata,
    }


def record_sensitive_action(
    session: Any,
    principal: AuthContext,
    *,
    action: str,
    target_type: str,
    organization_id: str | None = None,
    municipality_id: str | None = None,
    target_id: str | None = None,
    status: str = "recorded",
    metadata: dict[str, Any] | None = None,
) -> Any:
    payload = build_sensitive_action_audit_event(
        principal,
        action=action,
        target_type=target_type,
        organization_id=organization_id,
        municipality_id=municipality_id,
        target_id=target_id,
        status=status,
        metadata=metadata,
    )
    return record_audit_log(
        session,
        organization_id=payload["organization_id"],
        municipality_id=payload["municipality_id"],
        user_id=payload["user_id"],
        action=payload["action"],
        target_type=payload["target_type"],
        target_id=payload["target_id"],
        status=payload["status"],
        metadata=payload["metadata"],
    )


__all__ = [
    "ALL_ROLES",
    "AUTH_PROVIDER_DECISION",
    "AuthContext",
    "ROLE_ADMIN",
    "ROLE_ANALYST",
    "ROLE_DATA_OPERATOR",
    "ROLE_MATRIX_VERSION",
    "ROLE_MUNICIPALITY_VIEWER",
    "ROLE_PUBLIC",
    "ROLE_SPECS",
    "ROLE_SUPER_ADMIN",
    "ROLE_TRAFFIC_ENGINEER",
    "build_sensitive_action_audit_event",
    "get_current_auth_context",
    "get_auth_context",
    "get_auth_provider_integration_path",
    "get_role_matrix",
    "record_sensitive_action",
    "require_municipality_access",
    "require_organization_access",
    "require_roles",
    "set_current_auth_context",
]
