"""Organization-scoped Siting Advisor jobs and standards-cited results."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from io import StringIO
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.api.settings import ApiSettings


SITING_ADVISOR_CONTRACT_VERSION = "siting_advisor_v1"
WORKSPACE_RELATIVE_PATH = Path("data/runtime/siting_advisor/analyses.json")


class SitingAdvisorError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _workspace_path(settings: ApiSettings) -> Path:
    return settings.root_dir / WORKSPACE_RELATIVE_PATH


def _load_workspace(settings: ApiSettings) -> dict[str, Any]:
    path = _workspace_path(settings)
    if not path.exists():
        return {"contract_version": SITING_ADVISOR_CONTRACT_VERSION, "analyses": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("analyses"), list):
        raise SitingAdvisorError("Siting advisor workspace is invalid.")
    return payload


def _write_workspace(settings: ApiSettings, payload: dict[str, Any]) -> None:
    path = _workspace_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _artifact_name(facility_type: str, school_grade: str | None) -> str:
    if facility_type == "park":
        return "top_park_sites.json"
    if facility_type == "school" and school_grade == "primaria":
        return "top_primary_school_sites.json"
    raise SitingAdvisorError(
        "The current Bari demo supports parks and primary schools; "
        "other facility types require a generated SIT-02 bundle."
    )


def _load_ranked_bundle(
    settings: ApiSettings, *, city_key: str, facility_type: str, school_grade: str | None
) -> tuple[dict[str, Any], Path]:
    path = (
        settings.root_dir
        / "data"
        / "planning"
        / "siting"
        / city_key
        / _artifact_name(facility_type, school_grade)
    )
    if not path.exists():
        raise SitingAdvisorError(f"No siting bundle is available for city '{city_key}'.")
    return json.loads(path.read_text(encoding="utf-8")), path


def _find_analysis(
    settings: ApiSettings, *, organization_id: str, analysis_id: str
) -> dict[str, Any]:
    analysis = next(
        (
            row
            for row in _load_workspace(settings)["analyses"]
            if row.get("analysis_id") == analysis_id
            and row.get("organization_id") == organization_id
        ),
        None,
    )
    if analysis is None:
        raise SitingAdvisorError("Siting analysis not found in the requested organization.")
    return analysis


def create_analysis(
    settings: ApiSettings,
    *,
    organization_id: str,
    city_key: str,
    facility_type: str,
    school_grade: str | None,
    target_catchment: str | None,
    constraints: dict[str, Any],
    actor_subject: str | None,
) -> dict[str, Any]:
    bundle, source_path = _load_ranked_bundle(
        settings,
        city_key=city_key,
        facility_type=facility_type,
        school_grade=school_grade,
    )
    minimum_population = float(constraints.get("minimum_served_population") or 0)
    maximum_risk = float(constraints.get("maximum_access_route_risk_percentile") or 100)
    limit = max(1, min(50, int(constraints.get("limit") or 10)))
    candidates = [
        row
        for row in bundle.get("top_candidates", [])
        if float(row.get("served_population_estimate") or 0) >= minimum_population
        and float(row.get("access_route_risk_percentile") or 100) <= maximum_risk
    ][:limit]
    source_mtime = datetime.fromtimestamp(source_path.stat().st_mtime, UTC).isoformat()
    analysis = {
        "analysis_id": f"sit-{uuid4().hex}",
        "organization_id": organization_id,
        "city_key": city_key,
        "facility_type": facility_type,
        "school_grade": school_grade,
        "target_catchment": target_catchment,
        "constraints": constraints,
        "status": "completed",
        "dispatch_mode": "synchronous_local_artifact",
        "requested_by": actor_subject,
        "created_at_utc": _now(),
        "completed_at_utc": _now(),
        "result_count": len(candidates),
        "results": candidates,
        "provision_gap": {
            "metric": "public_green_m2_per_inhabitant"
            if facility_type == "park"
            else "education_m2_per_inhabitant",
            "dm_1444_quota": 9.0 if facility_type == "park" else 4.5,
            "current_estimate": None,
            "availability": "unavailable",
            "caveat": (
                "The current built-environment demo has no audited district-level "
                "facility-area inventory; the quota is shown without fabricating a current value."
            ),
        },
        "data_freshness": {
            "source_path": str(source_path),
            "source_modified_at_utc": source_mtime,
            "candidate_source": "built_environment_v2_demo_grid",
            "caveats": [
                "Candidate geometry is a deterministic demo grid, not verified cadastral availability.",
                "Rule results are screening evidence and require current legal and site review.",
                "Usage-model training inputs are synthetic until observed facility usage is supplied.",
            ],
        },
    }
    workspace = _load_workspace(settings)
    workspace["analyses"].append(analysis)
    _write_workspace(settings, workspace)
    return {key: value for key, value in analysis.items() if key != "results"}


def analysis_status(
    settings: ApiSettings, *, organization_id: str, analysis_id: str
) -> dict[str, Any]:
    analysis = _find_analysis(
        settings, organization_id=organization_id, analysis_id=analysis_id
    )
    return {key: value for key, value in analysis.items() if key != "results"}


def analysis_results(
    settings: ApiSettings, *, organization_id: str, analysis_id: str
) -> dict[str, Any]:
    analysis = _find_analysis(
        settings, organization_id=organization_id, analysis_id=analysis_id
    )
    return {
        "contract_version": SITING_ADVISOR_CONTRACT_VERSION,
        **analysis,
    }


def results_csv(payload: dict[str, Any]) -> bytes:
    output = StringIO()
    fields = [
        "rank",
        "candidate_id",
        "suitability_score",
        "served_population_estimate",
        "access_route_risk_percentile",
        "asset_type",
        "school_grade",
        "mandatory_failure_count",
        "mandatory_insufficient_data_count",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in payload["results"]:
        writer.writerow(
            {
                **{field: row.get(field) for field in fields},
                "mandatory_failure_count": row["compliance"]["mandatory_failure_count"],
                "mandatory_insufficient_data_count": row["compliance"][
                    "mandatory_insufficient_data_count"
                ],
            }
        )
    return output.getvalue().encode("utf-8")
