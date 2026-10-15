#!/usr/bin/env python3
"""Export the stable v1 OpenAPI schema and route contract snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.main import create_app  # noqa: E402
from apps.api.settings import ApiSettings  # noqa: E402


OPENAPI_CONTRACT_VERSION = "road_risk_openapi_v1"
ROUTE_CONTRACT_VERSION = "road_risk_route_contract_v1"


def _json_dump(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _path_category(path: str) -> str:
    if path in {"/healthz", "/v1/healthz", "/v1/public/health"}:
        return "public"
    if path.startswith("/v1/public/"):
        return "public"
    if path.startswith("/v1/auth/"):
        return "auth"
    if path.startswith("/v1/analyst/"):
        return "analyst"
    if path.startswith("/v1/admin/"):
        return "admin"
    if path.startswith("/v1/ingestion-jobs") or path.startswith("/v1/storage/"):
        return "ingestion"
    if path.startswith("/v1/scenarios/"):
        return "scenario"
    if path.startswith("/v1/interventions/"):
        return "intervention"
    if path.startswith("/v1/recommendations"):
        return "recommendation"
    if path.startswith("/v1/siting-analyses"):
        return "siting"
    if path.startswith("/v1/reports"):
        return "reporting"
    if path.startswith("/v1/automation/"):
        return "automation"
    if path.startswith("/v1/observability/"):
        return "observability"
    if path.startswith("/v1/vru/") or path.startswith("/v1/signal-phase/") or path.startswith("/v1/traffic-operations/"):
        return "traffic_operations"
    if path.startswith("/v1/published"):
        return "published_resource"
    return "core"


def _auth_policy(path: str, methods: list[str]) -> dict[str, Any]:
    category = _path_category(path)
    if category == "public":
        return {
            "auth": "none",
            "roles": ["public"],
            "publication_tier": "public aggregated only",
        }
    if path in {"/v1/observability/info", "/v1/observability/readiness", "/v1/auth/role-matrix"}:
        return {"auth": "none", "roles": ["public"], "publication_tier": "operational metadata"}
    if path == "/v1/observability/metrics":
        return {"auth": "bearer", "roles": ["admin", "super_admin"], "publication_tier": "internal ops"}
    if path == "/v1/admin/institution-deployment":
        return {"auth": "bearer", "roles": ["super_admin"], "publication_tier": "restricted installation configuration"}
    if category == "admin" or category == "automation":
        return {"auth": "bearer", "roles": ["admin", "super_admin"], "publication_tier": "restricted internal"}
    if category == "ingestion":
        return {
            "auth": "bearer",
            "roles": ["data_operator", "admin", "super_admin"],
            "publication_tier": "restricted upload/artifact metadata",
        }
    if category == "traffic_operations":
        return {
            "auth": "bearer",
            "roles": ["traffic_engineer", "admin", "super_admin"],
            "publication_tier": "internal engineering",
        }
    if category == "recommendation" and path.endswith("/review"):
        return {
            "auth": "bearer",
            "roles": ["traffic_engineer", "admin", "super_admin"],
            "publication_tier": "internal engineering",
        }
    if category == "recommendation":
        return {
            "auth": "bearer",
            "roles": ["analyst", "traffic_engineer", "admin", "super_admin"],
            "publication_tier": "internal; exports contain approved records only",
        }
    if category in {"analyst", "scenario", "intervention", "reporting", "siting"}:
        return {
            "auth": "bearer",
            "roles": ["analyst", "traffic_engineer", "admin", "super_admin"],
            "publication_tier": "internal unless explicitly public",
        }
    if category == "published_resource":
        return {
            "auth": "publication-tier aware",
            "roles": ["public", "municipality_viewer", "analyst", "admin"],
            "publication_tier": "public/internal/restricted according to source policy",
        }
    if category == "auth":
        return {"auth": "bearer when auth is enabled", "roles": ["public"], "publication_tier": "identity metadata"}
    return {"auth": "bearer when auth is enabled", "roles": ["municipality_viewer"], "publication_tier": "internal"}


def build_openapi_schema() -> dict[str, Any]:
    app = create_app(ApiSettings(root_dir=REPO_ROOT, request_logging_enabled=False))
    schema = app.openapi()
    schema.setdefault("info", {})["x-contract-version"] = OPENAPI_CONTRACT_VERSION
    return schema


def build_route_contract(schema: dict[str, Any]) -> dict[str, Any]:
    routes: list[dict[str, Any]] = []
    for path, path_item in sorted(schema.get("paths", {}).items()):
        methods = sorted(method.upper() for method in path_item if method.lower() in {"get", "post", "patch", "put", "delete"})
        operations = {
            method.upper(): path_item[method.lower()].get("operationId")
            for method in methods
            if method.lower() in path_item
        }
        route = {
            "path": path,
            "methods": methods,
            "category": _path_category(path),
            "operation_ids": operations,
            **_auth_policy(path, methods),
        }
        routes.append(route)
    return {
        "contract_version": ROUTE_CONTRACT_VERSION,
        "openapi_contract_version": OPENAPI_CONTRACT_VERSION,
        "api_version": schema.get("info", {}).get("version"),
        "route_count": len(routes),
        "operation_count": sum(len(route["methods"]) for route in routes),
        "routes": routes,
    }


def export_contracts(output_dir: Path) -> tuple[Path, Path]:
    schema = build_openapi_schema()
    route_contract = build_route_contract(schema)
    openapi_path = output_dir / "openapi-v1.json"
    route_contract_path = output_dir / "v1-route-contract.json"
    _json_dump(schema, openapi_path)
    _json_dump(route_contract, route_contract_path)
    return openapi_path, route_contract_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Road Risk v1 OpenAPI and route contract files.")
    parser.add_argument("--output-dir", default="docs/api", help="Directory for generated contract artifacts.")
    args = parser.parse_args(argv)
    openapi_path, route_contract_path = export_contracts(REPO_ROOT / args.output_dir)
    print(f"wrote {openapi_path.relative_to(REPO_ROOT)}")
    print(f"wrote {route_contract_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
