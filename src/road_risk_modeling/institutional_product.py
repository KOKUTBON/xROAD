"""Versioned product configuration for dedicated institutional installations.

Profiles select workflows, not permissions. Existing API RBAC and data governance
remain authoritative; selecting a module never grants a user access.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

MODULES = {
    "public_portal": "Public transparency",
    "risk_analysis": "Risk analysis",
    "reporting": "Reports and dossiers",
    "interventions": "Intervention planning",
    "data_ingestion": "Data ingestion",
    "traffic_operations": "Traffic operations",
    "automation": "Scheduled workflows",
    "administration": "Administration",
    "siting_advisor": "Facility siting",
    "climate_resilience": "Climate resilience",
    "connected_fleets": "Connected fleets",
    "digital_twin": "Simulation and digital twin",
    "forensics": "Crash reconstruction",
    "incident_coordination": "Incident coordination",
    "research": "Research workflows",
}

PROFILES = {
    "municipality": (
        "public_portal",
        "risk_analysis",
        "reporting",
        "interventions",
        "data_ingestion",
        "administration",
    ),
    "regional_authority": (
        "public_portal",
        "risk_analysis",
        "reporting",
        "interventions",
        "data_ingestion",
        "administration",
        "automation",
    ),
    "transport_ministry": (
        "public_portal",
        "risk_analysis",
        "reporting",
        "interventions",
        "data_ingestion",
        "administration",
        "automation",
        "research",
    ),
    "police": (
        "risk_analysis",
        "reporting",
        "data_ingestion",
        "administration",
        "forensics",
    ),
    "highway_operator": (
        "risk_analysis",
        "reporting",
        "interventions",
        "data_ingestion",
        "administration",
        "traffic_operations",
        "incident_coordination",
    ),
    "custom": ("administration",),
    # Backward compatibility is restricted to configurations without [deployment].
    "legacy": tuple(MODULES),
}
DEPENDENCIES = {
    "interventions": ("risk_analysis",),
    "siting_advisor": ("risk_analysis",),
    "traffic_operations": ("risk_analysis",),
    "digital_twin": ("risk_analysis",),
    "incident_coordination": ("traffic_operations",),
}


def _id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value
    ):
        raise ValueError(
            "Organization/jurisdiction IDs must use letters, digits, underscores or hyphens (maximum 128 characters)"
        )
    return value


def _text(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"{name} must be non-empty text without control characters")
    return value.strip()


def _strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} cannot contain duplicate values")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class Jurisdiction:
    id: str
    name: str
    region_label: str
    coverage_label: str = "Awaiting validated data"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Jurisdiction:
        return cls(
            _id(data.get("id")),
            _text(data.get("name"), "Jurisdiction name"),
            _text(data.get("region_label"), "Region label"),
            _text(
                data.get("coverage_label", "Awaiting validated data"), "Coverage label"
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "regionLabel": self.region_label,
            "coverageLabel": self.coverage_label,
        }


@dataclass(frozen=True, slots=True)
class Organization:
    id: str
    name: str
    short_label: str
    municipality_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Organization:
        return cls(
            _id(data.get("id")),
            _text(data.get("name"), "Organization name"),
            _text(data.get("short_label", data.get("name")), "Organization label"),
            _strings(data.get("municipality_ids", []), "municipality_ids"),
        )

    def to_dict(self, allowed: set[str] | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "shortLabel": self.short_label,
            "municipalityIds": [
                item
                for item in self.municipality_ids
                if allowed is None or item in allowed
            ],
        }


@dataclass(frozen=True, slots=True)
class DeploymentConfig:
    schema_version: int = 1
    profile: str = "legacy"
    enabled_modules: tuple[str, ...] = field(default_factory=lambda: tuple(MODULES))
    organizations: tuple[Organization, ...] = ()
    jurisdictions: tuple[Jurisdiction, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> DeploymentConfig:
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("deployment must be a TOML table")  # noqa: TRY004 - configuration validation has one public error type
        unknown = set(data) - {
            "schema_version",
            "profile",
            "enabled_modules",
            "organizations",
            "jurisdictions",
        }
        if unknown:
            raise ValueError(
                f"Unknown deployment settings: {', '.join(sorted(unknown))}"
            )
        version = data.get("schema_version", 1)
        if type(version) is not int or version != 1:
            raise ValueError(
                "Unsupported deployment schema_version; supported version is 1"
            )
        profile = data.get("profile", "municipality")
        if (
            not isinstance(profile, str)
            or profile not in PROFILES
            or profile == "legacy"
        ):
            raise ValueError("Unknown deployment profile")
        modules = _strings(
            data.get("enabled_modules", list(PROFILES[profile])), "enabled_modules"
        )
        unknown_modules = set(modules) - MODULES.keys()
        if unknown_modules:
            raise ValueError(f"Unknown modules: {', '.join(sorted(unknown_modules))}")
        if "administration" not in modules:
            raise ValueError(
                "The administration module is required for institutional support"
            )
        for module in modules:
            if not set(DEPENDENCIES.get(module, ())).issubset(modules):
                raise ValueError(
                    f"Module {module} requires {', '.join(DEPENDENCIES[module])}"
                )
        parsed: dict[str, tuple] = {}
        for key, model in (
            ("organizations", Organization),
            ("jurisdictions", Jurisdiction),
        ):
            rows = data.get(key, [])
            if not isinstance(rows, list) or not all(
                isinstance(row, dict) for row in rows
            ):
                raise ValueError(f"{key} must be an array of tables")
            parsed[key] = tuple(model.from_dict(row) for row in rows)
            ids = [row.id for row in parsed[key]]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {key} IDs")
        jurisdictions = {row.id for row in parsed["jurisdictions"]}
        for organization in parsed["organizations"]:
            if not set(organization.municipality_ids).issubset(jurisdictions):
                raise ValueError(
                    f"Organization {organization.id} references unconfigured jurisdictions"
                )
            if not organization.municipality_ids:
                raise ValueError(
                    f"Organization {organization.id} must have at least one jurisdiction"
                )
        assigned = {
            item for org in parsed["organizations"] for item in org.municipality_ids
        }
        if assigned != jurisdictions:
            raise ValueError(
                "Every configured jurisdiction must belong to an organization"
            )
        if not parsed["organizations"] or not parsed["jurisdictions"]:
            raise ValueError(
                "Institutional profiles require organizations and jurisdictions"
            )
        return cls(
            version, profile, modules, parsed["organizations"], parsed["jurisdictions"]
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile": self.profile,
            "enabled_modules": list(self.enabled_modules),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.public_dict(),
            "organizations": [
                {
                    "id": row.id,
                    "name": row.name,
                    "short_label": row.short_label,
                    "municipality_ids": list(row.municipality_ids),
                }
                for row in self.organizations
            ],
            "jurisdictions": [
                {
                    "id": row.id,
                    "name": row.name,
                    "region_label": row.region_label,
                    "coverage_label": row.coverage_label,
                }
                for row in self.jurisdictions
            ],
        }

    @property
    def revision(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]

    def scope_catalog(
        self,
        organization_ids: set[str],
        municipality_ids: set[str],
        *,
        super_admin: bool = False,
    ) -> dict[str, Any]:
        organizations = [
            row
            for row in self.organizations
            if super_admin or row.id in organization_ids
        ]
        linked = {item for row in organizations for item in row.municipality_ids}
        allowed = linked if super_admin else linked.intersection(municipality_ids)
        return {
            "organizations": [row.to_dict(allowed) for row in organizations],
            "municipalities": [
                row.to_dict() for row in self.jurisdictions if row.id in allowed
            ],
        }


# Prefix matching respects path boundaries; /v1/reports-extra is not /v1/reports.
API_MODULE_PREFIXES = {
    "public_portal": ("/v1/public/cities",),
    "risk_analysis": (
        "/v1/analyst",
        "/v1/dashboard-summary",
        "/v1/published-index",
        "/v1/published-resource",
        "/v1/national",
        "/v1/hsm",
        "/v1/irap",
        "/v1/forecasting",
        "/v1/cv",
    ),
    "reporting": ("/v1/reports", "/v1/reporting", "/v1/storage/reports"),
    "interventions": (
        "/v1/interventions",
        "/v1/recommendations",
        "/v1/scenarios",
        "/v1/cip",
        "/v1/causal",
    ),
    "data_ingestion": (
        "/v1/ingestion-jobs",
        "/v1/storage/uploads",
        "/v1/admin/postgis-domain",
        "/v1/jobs",
    ),
    "traffic_operations": (
        "/v1/traffic-operations",
        "/v1/vru",
        "/v1/signal-phase",
        "/v1/ssam",
        "/v1/micromobility",
    ),
    "automation": ("/v1/automation", "/v1/admin/automations"),
    "administration": ("/v1/admin", "/v1/compliance", "/v1/storage/artifacts"),
    "siting_advisor": ("/v1/siting-analyses",),
    "connected_fleets": ("/v1/telematics", "/v1/cits"),
    "digital_twin": ("/v1/simulation",),
    "forensics": ("/v1/forensics",),
    "incident_coordination": ("/v1/tmc",),
    "research": ("/v1/research", "/v1/federated"),
}


def module_for_api_path(path: str) -> str | None:
    if re.match(r"^/v1/public/cities/[^/]+/reports(?:/|$)", path):
        return "reporting"
    if re.match(r"^/v1/public/cities/[^/]+/interventions(?:/|$)", path):
        return "interventions"
    matches = [
        (len(prefix), module)
        for module, prefixes in API_MODULE_PREFIXES.items()
        for prefix in prefixes
        if path == prefix or path.startswith(prefix + "/")
    ]
    return max(matches)[1] if matches else None
