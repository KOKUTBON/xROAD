"""Assess exposure and context readiness against the next platform maturity steps."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


EXPOSURE_READINESS_VERSION = "exposure_readiness_v1"
EXPOSURE_READINESS_CONTRACT_VERSION = "exposure_readiness_public_v1"

CAPABILITY_SPECS = [
    {
        "code": "motorized_exposure",
        "label": "Motor traffic exposure",
        "priority": 1,
        "required_columns": ["aadt", "traffic_volume", "vehicle_km_travelled", "traffic_count_daily"],
        "proxy_columns": ["exposure_proxy_index", "exposure_movement_index", "maxspeed"],
        "next_step": "Acquire AADT, traffic counts, or floating-car traffic volume aggregates per segment.",
    },
    {
        "code": "speed_observation",
        "label": "Observed speed and variability",
        "priority": 1,
        "required_columns": ["mean_speed_kph", "p85_speed_kph", "speed_std_kph", "speed_variance"],
        "proxy_columns": ["maxspeed"],
        "next_step": "Replace static speed-limit fields with observed speed distributions or aggregated probe-speed feeds.",
    },
    {
        "code": "vru_exposure",
        "label": "Pedestrian and cyclist exposure",
        "priority": 1,
        "required_columns": ["pedestrian_count", "cyclist_count", "vru_exposure_index", "crossing_flow"],
        "proxy_columns": ["poi_education_count", "poi_retail_count", "landuse_residential_count"],
        "next_step": "Add pedestrian and cyclist counters or defensible VRU exposure proxies at crossings and corridors.",
    },
    {
        "code": "micromobility_exposure",
        "label": "Micromobility exposure",
        "priority": 2,
        "required_columns": ["micromobility_trip_count", "scooter_count", "bike_share_trip_count"],
        "proxy_columns": [],
        "next_step": "Add shared-mobility or micromobility operator aggregates where the municipal scope justifies it.",
    },
    {
        "code": "weather_visibility",
        "label": "Weather and visibility",
        "priority": 2,
        "required_columns": ["weather_code", "visibility_m", "precipitation_mm", "surface_condition"],
        "proxy_columns": [],
        "next_step": "Integrate hourly weather and visibility feeds aligned to segment-time or event-time scoring.",
    },
    {
        "code": "event_operations",
        "label": "Events and operational state",
        "priority": 2,
        "required_columns": ["planned_event", "work_zone", "congestion_state", "incident_state"],
        "proxy_columns": [],
        "next_step": "Add event, work-zone, and congestion-state feeds so short-term risk states can be modeled.",
    },
    {
        "code": "road_geometry_design",
        "label": "Road geometry and design controls",
        "priority": 1,
        "required_columns": ["lanes", "maxspeed", "road_class_rank", "is_intersection_connector", "segment_length_m"],
        "proxy_columns": ["width", "junction", "bridge", "tunnel"],
        "next_step": "Keep extending geometry coverage toward crossings, lighting, signals, and continuity attributes.",
    },
    {
        "code": "asset_condition",
        "label": "Asset condition",
        "priority": 2,
        "required_columns": ["surface_condition", "skid_resistance", "lighting_quality", "marking_condition"],
        "proxy_columns": [],
        "next_step": "Add pavement, lighting, and road-marking condition layers for maintenance-plus-safety planning.",
    },
    {
        "code": "realtime_v2x",
        "label": "Real-time sensing and V2X",
        "priority": 3,
        "required_columns": ["rsu_event_count", "connected_vehicle_count", "signal_phase_state", "edge_alert_state"],
        "proxy_columns": [],
        "next_step": "Define the digital-twin boundary for live sensing, V2X, and warning-state ingestion.",
    },
]


def _parse_dataset_spec(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise RuntimeError(f"Invalid dataset specification: {value}. Expected label=/path/to/file.geojson")
    label, path = value.split("=", 1)
    label = label.strip()
    path = path.strip()
    if not label or not path:
        raise RuntimeError(f"Invalid dataset specification: {value}. Expected label=/path/to/file.geojson")
    return label, path


def _load_feature_collection(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"Expected FeatureCollection at: {path}")
    return list(payload.get("features", []))


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _column_coverage(features: list[dict[str, Any]]) -> dict[str, float]:
    feature_count = max(1, len(features))
    counts: Counter[str] = Counter()
    for feature in features:
        properties = feature.get("properties") or {}
        for key, value in properties.items():
            if _value_present(value):
                counts[str(key)] += 1
    return {
        key: counts[key] / feature_count
        for key in sorted(counts)
    }


def _feature_coverage_share(features: list[dict[str, Any]], columns: list[str]) -> tuple[int, float]:
    if not features:
        return (0, 0.0)
    covered = 0
    for feature in features:
        properties = feature.get("properties") or {}
        if any(_value_present(properties.get(column)) for column in columns):
            covered += 1
    return (covered, round(covered / float(len(features)), 4))


def _connector_contract_state(
    *,
    mapping_stub_root: Path,
    dataset_label: str,
    capability_code: str,
) -> dict[str, Any]:
    if not mapping_stub_root.exists():
        return {
            "connector_contract_state": "not_configured",
            "connector_mapping_stub_count": 0,
            "ready_connector_profiles": [],
        }

    pattern = f"{dataset_label}_*_{capability_code}_*.json"
    stub_paths = sorted(mapping_stub_root.glob(pattern))
    if not stub_paths:
        return {
            "connector_contract_state": "not_configured",
            "connector_mapping_stub_count": 0,
            "ready_connector_profiles": [],
        }

    ready_profiles: list[str] = []
    for stub_path in stub_paths:
        stub_payload = json.loads(stub_path.read_text(encoding="utf-8"))
        if not isinstance(stub_payload, dict):
            continue
        required_mappings = [
            mapping
            for mapping in stub_payload.get("field_mappings", [])
            if isinstance(mapping, dict) and bool(mapping.get("required"))
        ]
        if not required_mappings:
            continue
        is_ready = all(
            str(mapping.get("source_field") or "").strip()
            and not str(mapping.get("source_field") or "").strip().startswith("TODO_")
            for mapping in required_mappings
        )
        if is_ready:
            profile_id = str(stub_payload.get("provider_profile_id") or "").strip() or stub_path.stem
            ready_profiles.append(profile_id)

    state = "contract_ready" if ready_profiles else "todo_mapping"
    return {
        "connector_contract_state": state,
        "connector_mapping_stub_count": len(stub_paths),
        "ready_connector_profiles": sorted(set(ready_profiles)),
    }


def _capability_status(
    coverage_by_column: dict[str, float],
    *,
    required_columns: list[str],
    proxy_columns: list[str],
) -> tuple[str, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    for column in required_columns:
        coverage = coverage_by_column.get(column)
        if coverage is not None and coverage > 0:
            evidence.append({"column": column, "coverage": round(coverage, 4), "type": "required"})
    if evidence:
        return "available", evidence
    for column in proxy_columns:
        coverage = coverage_by_column.get(column)
        if coverage is not None and coverage > 0:
            evidence.append({"column": column, "coverage": round(coverage, 4), "type": "proxy"})
    if evidence:
        return "proxy_only", evidence
    return "missing", []


def _dataset_assessment(label: str, dataset_path: Path, mapping_stub_root: Path) -> dict[str, Any]:
    features = _load_feature_collection(dataset_path)
    coverage_by_column = _column_coverage(features)
    present_columns = sorted(coverage_by_column)
    capabilities: list[dict[str, Any]] = []
    for spec in CAPABILITY_SPECS:
        status, evidence = _capability_status(
            coverage_by_column,
            required_columns=spec["required_columns"],
            proxy_columns=spec["proxy_columns"],
        )
        required_feature_count, required_feature_share = _feature_coverage_share(
            features,
            spec["required_columns"],
        )
        proxy_feature_count, proxy_feature_share = _feature_coverage_share(
            features,
            spec["proxy_columns"],
        )
        contract_state = _connector_contract_state(
            mapping_stub_root=mapping_stub_root,
            dataset_label=label,
            capability_code=spec["code"],
        )
        next_step = spec["next_step"]
        if status != "available" and contract_state["connector_contract_state"] == "contract_ready":
            next_step = (
                "Connector contract is ready; ingest an approved provider extract and publish refreshed join/readiness coverage outputs."
            )
        capabilities.append(
            {
                "code": spec["code"],
                "label": spec["label"],
                "priority": spec["priority"],
                "status": status,
                "evidence": evidence,
                "required_feature_count": required_feature_count,
                "required_feature_share": required_feature_share,
                "proxy_feature_count": proxy_feature_count,
                "proxy_feature_share": proxy_feature_share,
                "connector_contract_state": contract_state["connector_contract_state"],
                "connector_mapping_stub_count": contract_state["connector_mapping_stub_count"],
                "ready_connector_profiles": contract_state["ready_connector_profiles"],
                "next_step": next_step,
            }
        )

    next_steps = [
        {
            "priority": capability["priority"],
            "capability": capability["label"],
            "status": capability["status"],
            "action": capability["next_step"],
        }
        for capability in capabilities
        if capability["status"] != "available"
    ]
    next_steps.sort(key=lambda item: (int(item["priority"]), item["capability"]))

    return {
        "label": label,
        "dataset_path": str(dataset_path),
        "feature_count": len(features),
        "present_column_count": len(present_columns),
        "present_columns_sample": present_columns[:40],
        "capabilities": capabilities,
        "next_steps": next_steps,
    }


def _report_markdown(dataset_reports: list[dict[str, Any]]) -> str:
    lines = [
        "# Exposure Backbone Readiness Report",
        "",
        "This report compares the current segment layers against the next maturity steps implied by the Horizon-aligned roadmap.",
        "",
    ]
    for report in dataset_reports:
        lines.extend(
            [
                f"## {report['label']}",
                "",
                f"- Dataset path: `{report['dataset_path']}`",
                f"- Features: `{report['feature_count']}`",
                f"- Non-empty columns discovered: `{report['present_column_count']}`",
                "",
                "### Capability Status",
                "",
            ]
        )
        for capability in report["capabilities"]:
            evidence = ", ".join(
                f"{item['column']} ({item['coverage']:.0%}, {item['type']})"
                for item in capability["evidence"]
            ) or "none"
            lines.append(
                f"- **{capability['label']}**: `{capability['status']}`. Evidence: {evidence}. "
                f"Contract state: `{capability['connector_contract_state']}` "
                f"({capability['connector_mapping_stub_count']} stubs, ready profiles: {', '.join(capability['ready_connector_profiles']) or 'none'}). "
                f"Required coverage: {capability['required_feature_share']:.0%} ({capability['required_feature_count']} features), "
                f"proxy coverage: {capability['proxy_feature_share']:.0%} ({capability['proxy_feature_count']} features). "
                f"Next: {capability['next_step']}"
            )
        lines.extend(["", "### Priority Next Steps", ""])
        for next_step in report["next_steps"][:5]:
            lines.append(
                f"1. **{next_step['capability']}** ({next_step['status']}). {next_step['action']}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_exposure_readiness_report(
    *,
    datasets: list[tuple[str, str]] | list[str],
    output_dir: str | Path = "data/planning/exposure_readiness",
    mapping_stub_root: str | Path = "data/planning/exposure_connector_intake/mapping_stubs",
) -> dict[str, Any]:
    parsed_datasets = [
        _parse_dataset_spec(spec) if isinstance(spec, str) else (spec[0], spec[1])
        for spec in datasets
    ]
    if not parsed_datasets:
        raise RuntimeError("At least one dataset must be provided for exposure readiness assessment.")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    mapping_stub_root_path = Path(mapping_stub_root)
    report_json_path = output_root / "exposure_readiness.json"
    report_markdown_path = output_root / "exposure_readiness.md"
    manifest_path = output_root / "exposure_readiness.manifest.json"

    dataset_reports = [
        _dataset_assessment(label, Path(path), mapping_stub_root_path)
        for label, path in parsed_datasets
    ]
    dataset_reports.sort(key=lambda item: item["label"])

    status_counts = Counter(
        capability["status"]
        for report in dataset_reports
        for capability in report["capabilities"]
    )
    payload = {
        "exposure_readiness_version": EXPOSURE_READINESS_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "datasets": dataset_reports,
        "stats": {
            "dataset_count": len(dataset_reports),
            "status_counts": dict(sorted(status_counts.items())),
            "highest_priority_missing_count": sum(
                1
                for report in dataset_reports
                for capability in report["capabilities"]
                if capability["priority"] == 1 and capability["status"] != "available"
            ),
        },
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_markdown_path.write_text(_report_markdown(dataset_reports), encoding="utf-8")

    manifest = {
        "exposure_readiness_version": EXPOSURE_READINESS_VERSION,
        "inputs": {
            "mapping_stub_root": str(mapping_stub_root_path),
            "datasets": [
                {
                    "label": label,
                    "path": str(Path(path)),
                    "sha256": _sha256(Path(path)),
                }
                for label, path in parsed_datasets
            ]
        },
        "outputs": {
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_markdown_path": str(report_markdown_path),
            "report_markdown_sha256": _sha256(report_markdown_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "exposure_readiness",
            "public_contract_version": EXPOSURE_READINESS_CONTRACT_VERSION,
            "exposure_readiness_version": EXPOSURE_READINESS_VERSION,
        },
        "stats": payload["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("segment_context_layer", Path(path), _sha256(Path(path)))
                for _, path in parsed_datasets
            ],
            publishable_outputs=[
                _artifact_reference("exposure_readiness_json", report_json_path, _sha256(report_json_path)),
                _artifact_reference("exposure_readiness_markdown", report_markdown_path, _sha256(report_markdown_path)),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "exposure_readiness_version": EXPOSURE_READINESS_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": payload["stats"],
    }
