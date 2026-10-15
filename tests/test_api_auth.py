from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest import mock

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.auth import (  # noqa: E402
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_DATA_OPERATOR,
    ROLE_MATRIX_VERSION,
    ROLE_MUNICIPALITY_VIEWER,
    ROLE_PUBLIC,
    ROLE_SUPER_ADMIN,
    ROLE_TRAFFIC_ENGINEER,
    AuthContext,
    build_sensitive_action_audit_event,
    get_auth_context,
    get_auth_provider_integration_path,
    get_role_matrix,
    record_sensitive_action,
    require_municipality_access,
    require_organization_access,
    require_roles,
)
from apps.api.settings import ApiSettings  # noqa: E402


class ApiAuthTests(unittest.TestCase):
    def test_role_matrix_and_provider_path_cover_production_roles(self) -> None:
        matrix = get_role_matrix()
        self.assertEqual(matrix["role_matrix_version"], ROLE_MATRIX_VERSION)
        role_ids = [entry["role"] for entry in matrix["roles"]]
        self.assertEqual(
            role_ids,
            [
                "public",
                "municipality_viewer",
                "analyst",
                "data_operator",
                "traffic_engineer",
                "admin",
                "super_admin",
            ],
        )

        provider_path = get_auth_provider_integration_path(ApiSettings(auth_provider="entra_id"))
        self.assertEqual(provider_path["selected_provider"], "entra_id")
        self.assertEqual(provider_path["recommended_provider"], "keycloak")
        self.assertEqual(provider_path["claim_configuration"]["organization_claim"], "organization_ids")

    def test_get_auth_context_extracts_effective_roles_and_scope_claims(self) -> None:
        settings = ApiSettings(
            auth_enabled=True,
            auth_provider="keycloak",
            auth_client_id="road-risk-api",
            auth_organization_claim="organization_ids",
            auth_municipality_claim="municipality_ids",
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="demo-token")
        payload = {
            "sub": "user-123",
            "realm_access": {"roles": [ROLE_ANALYST]},
            "resource_access": {"road-risk-api": {"roles": [ROLE_DATA_OPERATOR]}},
            "organization_ids": ["org-bari"],
            "municipality_ids": ["bari"],
            "scope": "openid profile",
        }

        with (
            mock.patch("apps.api.auth.get_settings", return_value=settings),
            mock.patch("apps.api.auth._decode_token", return_value=payload),
        ):
            context = get_auth_context(credentials)

        self.assertTrue(context.is_authenticated)
        self.assertEqual(context.provider, "keycloak")
        self.assertEqual(context.subject, "user-123")
        self.assertEqual(context.assigned_roles, frozenset({ROLE_ANALYST, ROLE_DATA_OPERATOR}))
        self.assertIn(ROLE_MUNICIPALITY_VIEWER, context.roles)
        self.assertIn(ROLE_PUBLIC, context.roles)
        self.assertEqual(context.organization_ids, frozenset({"org-bari"}))
        self.assertEqual(context.municipality_ids, frozenset({"bari"}))
        self.assertEqual(context.primary_organization_id, "org-bari")
        self.assertEqual(context.primary_municipality_id, "bari")

    def test_anonymous_and_scope_requirements_enforce_rbac(self) -> None:
        anonymous = AuthContext.anonymous(auth_enabled=True, provider="keycloak")
        with self.assertRaises(HTTPException) as anonymous_error:
            require_roles(anonymous, {ROLE_ANALYST})
        self.assertEqual(anonymous_error.exception.status_code, 401)

        scoped_analyst = AuthContext(
            subject="user-1",
            assigned_roles=frozenset({ROLE_ANALYST}),
            roles=frozenset({ROLE_PUBLIC, ROLE_MUNICIPALITY_VIEWER, ROLE_ANALYST}),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset({"org-bari"}),
            municipality_ids=frozenset({"bari"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        require_roles(scoped_analyst, {ROLE_ANALYST})
        require_organization_access(scoped_analyst, "org-bari")
        require_municipality_access(scoped_analyst, "bari")

        with self.assertRaises(HTTPException) as org_error:
            require_organization_access(scoped_analyst, "org-lecce")
        self.assertEqual(org_error.exception.status_code, 403)

        with self.assertRaises(HTTPException) as municipality_error:
            require_municipality_access(scoped_analyst, "lecce")
        self.assertEqual(municipality_error.exception.status_code, 403)

        super_admin = AuthContext(
            subject="platform-admin",
            assigned_roles=frozenset({ROLE_SUPER_ADMIN}),
            roles=frozenset(
                {
                    ROLE_PUBLIC,
                    ROLE_MUNICIPALITY_VIEWER,
                    ROLE_ANALYST,
                    ROLE_DATA_OPERATOR,
                    ROLE_TRAFFIC_ENGINEER,
                    ROLE_ADMIN,
                    ROLE_SUPER_ADMIN,
                }
            ),
            scopes=frozenset(),
            claims={},
            organization_ids=frozenset(),
            municipality_ids=frozenset(),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )
        require_organization_access(super_admin, "org-any")
        require_municipality_access(super_admin, "municipality-any")

    def test_build_and_record_sensitive_action_audit_events(self) -> None:
        principal = AuthContext(
            subject="user-9",
            assigned_roles=frozenset({ROLE_ADMIN}),
            roles=frozenset(
                {
                    ROLE_PUBLIC,
                    ROLE_MUNICIPALITY_VIEWER,
                    ROLE_ANALYST,
                    ROLE_DATA_OPERATOR,
                    ROLE_TRAFFIC_ENGINEER,
                    ROLE_ADMIN,
                }
            ),
            scopes=frozenset({"openid"}),
            claims={"sub": "user-9"},
            organization_ids=frozenset({"org-bari"}),
            municipality_ids=frozenset({"bari"}),
            is_authenticated=True,
            auth_enabled=True,
            provider="keycloak",
        )

        event = build_sensitive_action_audit_event(
            principal,
            action="publish_artifact",
            target_type="artifact_reference",
            target_id="artifact-1",
            municipality_id="bari",
            metadata={"publication_tier": "internal"},
        )
        self.assertEqual(event["organization_id"], "org-bari")
        self.assertEqual(event["municipality_id"], "bari")
        self.assertEqual(event["user_id"], "user-9")
        self.assertEqual(event["metadata"]["auth_provider"], "keycloak")
        self.assertIn(ROLE_ADMIN, event["metadata"]["assigned_roles"])

        with mock.patch("apps.api.auth.record_audit_log", return_value={"id": "audit-1"}) as record_mock:
            result = record_sensitive_action(
                object(),
                principal,
                action="publish_artifact",
                target_type="artifact_reference",
                municipality_id="bari",
                target_id="artifact-1",
            )

        self.assertEqual(result, {"id": "audit-1"})
        record_mock.assert_called_once()
        self.assertEqual(record_mock.call_args.kwargs["organization_id"], "org-bari")
        self.assertEqual(record_mock.call_args.kwargs["target_type"], "artifact_reference")
