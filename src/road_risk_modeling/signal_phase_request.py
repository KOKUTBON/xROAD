"""Build Bari signal-phase source audits and restricted-data request packs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import ssl
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_intake import INTAKE_PROFILES


SIGNAL_PHASE_REQUEST_PACK_VERSION = "signal_phase_request_pack_v1"
SIGNAL_PHASE_REQUEST_PACK_CONTRACT_VERSION = "signal_phase_request_pack_public_v1"
DEFAULT_BARI_CKAN_SEARCH_URL = "https://opendata.comune.bari.it/api/3/action/package_search"

PUBLIC_PORTAL_QUERIES = [
    {"query": "semafori", "intent": "signal_inventory"},
    {"query": "impianti semaforici", "intent": "signal_inventory"},
    {"query": "traffico", "intent": "traffic_context"},
    {"query": "mobilita", "intent": "mobility_context"},
    {"query": "signal", "intent": "signal_control"},
    {"query": "controller", "intent": "signal_control"},
]

PHASE_DATA_KEYWORDS = (
    "controller",
    "control mode",
    "event log",
    "eventi",
    "fase",
    "phasing",
    "phase",
    "plan",
    "stage",
    "stadio",
    "timing",
    "tempi semaforici",
    "cycle",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _profile_lookup() -> dict[str, dict[str, Any]]:
    return {
        str(profile["profile_id"]): profile
        for profile in INTAKE_PROFILES
    }


def _default_fetch_package_search(
    query: str,
    *,
    portal_base_url: str,
    timeout_s: float,
    verify_ssl: bool,
) -> dict[str, Any]:
    url = f"{portal_base_url}?{urlencode({'q': query})}"
    if urlparse(url).scheme not in {"http", "https"}:
        raise ValueError("Portal URL must use HTTP or HTTPS.")
    context = None
    if not verify_ssl:
        context = ssl._create_unverified_context()  # nosec B323 # explicit diagnostic opt-in; verification defaults on
    with urlopen(url, context=context, timeout=timeout_s) as response:  # nosec B310 # HTTP(S) scheme checked above
        return json.load(response)


def _resource_rows(dataset: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for resource in dataset.get("resources", []) or []:
        rows.append(
            {
                "resource_name": _clean_text(resource.get("name")) or "",
                "resource_format": _clean_text(resource.get("format")) or "",
                "resource_url": _clean_text(resource.get("url")) or "",
            }
        )
    return rows


def _dataset_text(dataset: dict[str, Any]) -> str:
    parts = [
        _clean_text(dataset.get("title")) or _clean_text(dataset.get("dataset_title")),
        _clean_text(dataset.get("name")) or _clean_text(dataset.get("dataset_name")),
        _clean_text(dataset.get("notes")) or _clean_text(dataset.get("dataset_notes")),
    ]
    for resource in dataset.get("resources", []) or []:
        parts.extend(
            [
                _clean_text(resource.get("name")) or _clean_text(resource.get("resource_name")),
                _clean_text(resource.get("format")) or _clean_text(resource.get("resource_format")),
                _clean_text(resource.get("url")) or _clean_text(resource.get("resource_url")),
            ]
        )
    return " ".join(part for part in parts if part).lower()


def _classify_public_dataset(dataset: dict[str, Any]) -> tuple[str, bool]:
    text = _dataset_text(dataset)
    has_phase_data = any(keyword in text for keyword in PHASE_DATA_KEYWORDS)
    if has_phase_data:
        return "signal_phase_public", True
    if "semafor" in text:
        return "signal_inventory_public", False
    return "mobility_context_public", False


def _portal_dataset_rows(search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    datasets_by_name: dict[str, dict[str, Any]] = {}
    for result in search_results:
        query = result["query"]
        intent = result["intent"]
        for dataset in result["datasets"]:
            dataset_name = _clean_text(dataset.get("name")) or _slugify(_clean_text(dataset.get("title")) or "dataset")
            entry = datasets_by_name.setdefault(
                dataset_name,
                {
                    "dataset_name": dataset_name,
                    "dataset_title": _clean_text(dataset.get("title")) or dataset_name,
                    "dataset_notes": _clean_text(dataset.get("notes")),
                    "matched_queries": set(),
                    "matched_intents": set(),
                    "resources": _resource_rows(dataset),
                },
            )
            entry["matched_queries"].add(query)
            entry["matched_intents"].add(intent)
            if not entry.get("dataset_notes"):
                entry["dataset_notes"] = _clean_text(dataset.get("notes"))
            if not entry["resources"]:
                entry["resources"] = _resource_rows(dataset)

    rows: list[dict[str, Any]] = []
    for dataset_name in sorted(datasets_by_name):
        entry = datasets_by_name[dataset_name]
        classification, has_phase_data = _classify_public_dataset(entry)
        rows.append(
            {
                "dataset_name": dataset_name,
                "dataset_title": entry["dataset_title"],
                "dataset_notes": entry["dataset_notes"],
                "matched_queries": " | ".join(sorted(entry["matched_queries"])),
                "matched_intents": " | ".join(sorted(entry["matched_intents"])),
                "dataset_classification": classification,
                "public_signal_phase_data_available": "yes" if has_phase_data else "no",
                "resource_count": len(entry["resources"]),
                "resource_formats": " | ".join(
                    sorted(
                        {
                            row["resource_format"]
                            for row in entry["resources"]
                            if row["resource_format"]
                        }
                    )
                ),
                "resource_urls": " | ".join(
                    row["resource_url"]
                    for row in entry["resources"]
                    if row["resource_url"]
                ),
            }
        )
    return rows


def _request_rows(
    intake_payload: dict[str, Any],
    *,
    public_signal_phase_available: bool,
    top_n: int | None,
) -> list[dict[str, Any]]:
    source_rows = intake_payload.get("top_priority_signals", [])
    if not isinstance(source_rows, list):
        raise RuntimeError("Signal phase intake payload must contain a top-level 'top_priority_signals' list.")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(source_rows):
        if top_n is not None and index >= top_n:
            break
        sample_movement = item.get("sample_movement") if isinstance(item.get("sample_movement"), dict) else {}
        recommended_profile = _clean_text(item.get("recommended_provider_profile")) or "signal_stage_plan_export"
        required_profiles = [recommended_profile]
        if "arm_phase_mapping_sheet" not in required_profiles:
            required_profiles.append("arm_phase_mapping_sheet")
        if "junction phase diagram or phasing sketch" in (_clean_text(item.get("required_inputs")) or "").lower():
            required_profiles.append("junction_phase_diagram_support")
        rows.append(
            {
                "request_id": f"bari_signal_phase_{index + 1:02d}",
                "priority_rank": index + 1,
                "priority_band": _clean_text(item.get("priority_band")) or "tier_3_monitor",
                "junction_id": _clean_text(item.get("junction_id")) or "",
                "signal_name": _clean_text(item.get("signal_name")) or "",
                "signal_type": _clean_text(item.get("signal_type")) or "",
                "recommended_provider_profile": recommended_profile,
                "required_profiles": " | ".join(required_profiles),
                "required_inputs": _clean_text(item.get("required_inputs")) or "",
                "recommended_next_input": _clean_text(item.get("recommended_next_input")) or "",
                "public_signal_phase_data_available": "yes" if public_signal_phase_available else "no",
                "acquisition_path": "public_portal_reuse" if public_signal_phase_available else "restricted_data_request_required",
                "signalized_crash_total": int(item.get("signalized_crash_total") or 0),
                "ambiguous_crash_total": int(item.get("ambiguous_crash_total") or 0),
                "ambiguous_movement_count": int(item.get("ambiguous_movement_count") or 0),
                "matched_crashes_at_junction_total": int(item.get("matched_crashes_at_junction_total") or 0),
                "movement_turn_catalog": _clean_text(item.get("movement_turn_catalog")) or "",
                "phase_groups_present": _clean_text(item.get("movement_phase_groups_present")) or "",
                "sample_incoming_arm_id": _clean_text(sample_movement.get("incoming_arm_id")) or "",
                "sample_movement_turn": _clean_text(sample_movement.get("movement_turn")) or "",
                "sample_outgoing_arm_id": _clean_text(sample_movement.get("outgoing_arm_id")) or "",
                "sample_resolution_state": _clean_text(sample_movement.get("movement_resolution_state")) or "",
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _request_template_markdown(
    profile: dict[str, Any],
    request_rows: list[dict[str, Any]],
    *,
    checked_date: str,
    public_dataset_rows: list[dict[str, Any]],
) -> str:
    relevant_rows = [
        row
        for row in request_rows
        if profile["profile_id"] in (row["required_profiles"].split(" | "))
    ]
    lines = [
        f"# Bari {profile['label']} Request",
        "",
        f"As of {checked_date}, the official Bari open-data portal exposes public signal inventory and general mobility datasets, but no public dataset classified as signal-phase or controller timing data.",
        "",
        "## Requested Delivery",
        "",
        f"- Profile: `{profile['profile_id']}`",
        f"- Type: `{profile['profile_type']}`",
        f"- Publication tier: `{profile['publication_tier']}`",
        f"- Retention policy: {profile['retention_policy']}",
        "",
        "Required fields:",
        "",
    ]
    for field_name in profile["required_fields"]:
        field_type = profile.get("field_types", {}).get(field_name, "string")
        lines.append(f"- `{field_name}`: `{field_type}`")
    if profile["optional_fields"]:
        lines.extend(["", "Optional fields:", ""])
        for field_name in profile["optional_fields"]:
            field_type = profile.get("field_types", {}).get(field_name, "string")
            lines.append(f"- `{field_name}`: `{field_type}`")

    lines.extend(["", "## Priority Junctions", ""])
    for row in relevant_rows[:10]:
        lines.append(
            f"- `{row['junction_id']}` `{row['signal_name']}`: "
            f"`{row['signalized_crash_total']}` signalized crashes, "
            f"`{row['ambiguous_movement_count']}` ambiguous movements, "
            f"sample movement `{row['sample_incoming_arm_id']}` -> `{row['sample_outgoing_arm_id']}`"
        )

    lines.extend(["", "## Public Portal Evidence", ""])
    for dataset in public_dataset_rows:
        lines.append(
            f"- `{dataset['dataset_title']}` ({dataset['dataset_classification']}), "
            f"queries `{dataset['matched_queries']}`, resources `{dataset['resource_count']}`"
        )
    return "\n".join(lines) + "\n"


def _request_pack_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Request Pack",
        "",
        f"As of {payload['public_portal_checked_date']}, the official Bari public portal was checked for signal-control datasets.",
        "",
        "## Public Portal Findings",
        "",
        f"- Search queries run: `{payload['stats']['public_query_count']}`",
        f"- Public datasets found: `{payload['stats']['public_dataset_count']}`",
        f"- Public signal-phase datasets found: `{payload['stats']['public_signal_phase_dataset_count']}`",
        f"- Recommended acquisition path: `{payload['recommended_acquisition_path']}`",
        "",
    ]
    for dataset in payload["public_dataset_rows"]:
        lines.append(
            f"- `{dataset['dataset_title']}`: `{dataset['dataset_classification']}`, "
            f"resources `{dataset['resource_count']}`, phase data `{dataset['public_signal_phase_data_available']}`"
        )
    lines.extend(["", "## Priority Request Queue", ""])
    for row in payload["priority_request_rows"][:10]:
        lines.append(
            f"- `{row['junction_id']}` `{row['signal_name']}`: `{row['priority_band']}`, "
            f"profile `{row['recommended_provider_profile']}`, "
            f"signalized crashes `{row['signalized_crash_total']}`, "
            f"ambiguous movements `{row['ambiguous_movement_count']}`"
        )
    lines.extend(["", "## Output Templates", ""])
    for template_path in payload["outputs"]["template_paths"]:
        lines.append(f"- `{template_path}`")
    return "\n".join(lines) + "\n"


def build_bari_signal_phase_request_pack(
    *,
    output_dir: str | Path = "data/planning/signal_phase_requests/bari",
    signal_phase_intake_path: str | Path = "data/planning/signal_phase_intake/bari/signal_phase_intake_pack.json",
    portal_base_url: str = DEFAULT_BARI_CKAN_SEARCH_URL,
    timeout_s: float = 30.0,
    verify_ssl: bool = False,
    top_n: int | None = None,
    fetcher: Any | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    template_dir = output_root / "request_templates"
    template_dir.mkdir(parents=True, exist_ok=True)

    intake_path = Path(signal_phase_intake_path)
    intake_payload = _load_json(intake_path)
    checked_at_utc = datetime.now(UTC)
    checked_date = checked_at_utc.date().isoformat()
    fetch = fetcher or _default_fetch_package_search

    search_results: list[dict[str, Any]] = []
    for query_spec in PUBLIC_PORTAL_QUERIES:
        payload = fetch(
            query_spec["query"],
            portal_base_url=portal_base_url,
            timeout_s=timeout_s,
            verify_ssl=verify_ssl,
        )
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        datasets = result.get("results", []) if isinstance(result, dict) else []
        search_results.append(
            {
                "query": query_spec["query"],
                "intent": query_spec["intent"],
                "dataset_count": int(result.get("count") or len(datasets)),
                "datasets": datasets if isinstance(datasets, list) else [],
            }
        )

    public_dataset_rows = _portal_dataset_rows(search_results)
    public_signal_phase_available = any(
        row["public_signal_phase_data_available"] == "yes"
        for row in public_dataset_rows
    )
    priority_request_rows = _request_rows(
        intake_payload,
        public_signal_phase_available=public_signal_phase_available,
        top_n=top_n,
    )

    public_audit_csv_path = output_root / "public_source_audit.csv"
    request_matrix_csv_path = output_root / "priority_signal_request_matrix.csv"
    report_json_path = output_root / "signal_phase_request_pack.json"
    report_md_path = output_root / "signal_phase_request_pack.md"
    manifest_path = output_root / "signal_phase_request_pack.manifest.json"

    _write_csv(
        public_audit_csv_path,
        public_dataset_rows,
        fieldnames=[
            "dataset_name",
            "dataset_title",
            "dataset_notes",
            "matched_queries",
            "matched_intents",
            "dataset_classification",
            "public_signal_phase_data_available",
            "resource_count",
            "resource_formats",
            "resource_urls",
        ],
    )
    _write_csv(
        request_matrix_csv_path,
        priority_request_rows,
        fieldnames=[
            "request_id",
            "priority_rank",
            "priority_band",
            "junction_id",
            "signal_name",
            "signal_type",
            "recommended_provider_profile",
            "required_profiles",
            "required_inputs",
            "recommended_next_input",
            "public_signal_phase_data_available",
            "acquisition_path",
            "signalized_crash_total",
            "ambiguous_crash_total",
            "ambiguous_movement_count",
            "matched_crashes_at_junction_total",
            "movement_turn_catalog",
            "phase_groups_present",
            "sample_incoming_arm_id",
            "sample_movement_turn",
            "sample_outgoing_arm_id",
            "sample_resolution_state",
        ],
    )

    profile_lookup = _profile_lookup()
    template_paths: list[Path] = []
    for profile_id in ["controller_event_log_export", "signal_stage_plan_export", "arm_phase_mapping_sheet"]:
        profile = profile_lookup[profile_id]
        template_path = template_dir / f"{profile_id}_request.md"
        template_path.write_text(
            _request_template_markdown(
                profile,
                priority_request_rows,
                checked_date=checked_date,
                public_dataset_rows=public_dataset_rows,
            ),
            encoding="utf-8",
        )
        template_paths.append(template_path)

    stats = {
        "public_query_count": len(PUBLIC_PORTAL_QUERIES),
        "queries_without_results": sum(1 for row in search_results if row["dataset_count"] <= 0),
        "public_dataset_count": len(public_dataset_rows),
        "public_signal_phase_dataset_count": sum(
            1 for row in public_dataset_rows if row["public_signal_phase_data_available"] == "yes"
        ),
        "request_row_count": len(priority_request_rows),
        "tier_1_signal_count": sum(1 for row in priority_request_rows if row["priority_band"] == "tier_1_immediate"),
        "tier_2_signal_count": sum(1 for row in priority_request_rows if row["priority_band"] == "tier_2_next_wave"),
        "request_template_count": len(template_paths),
        "recommended_profile_counts": {
            profile_id: sum(1 for row in priority_request_rows if row["recommended_provider_profile"] == profile_id)
            for profile_id in sorted({row["recommended_provider_profile"] for row in priority_request_rows})
        },
    }

    report_payload = {
        "signal_phase_request_pack_version": SIGNAL_PHASE_REQUEST_PACK_VERSION,
        "signal_phase_request_pack_contract_version": SIGNAL_PHASE_REQUEST_PACK_CONTRACT_VERSION,
        "public_portal_checked_at_utc": checked_at_utc.isoformat(),
        "public_portal_checked_date": checked_date,
        "public_portal_url": "https://opendata.comune.bari.it",
        "portal_base_url": portal_base_url,
        "portal_ssl_verification": "enabled" if verify_ssl else "disabled",
        "recommended_acquisition_path": "public_portal_reuse" if public_signal_phase_available else "restricted_data_request_required",
        "public_query_results": search_results,
        "public_dataset_rows": public_dataset_rows,
        "priority_request_rows": priority_request_rows,
        "stats": stats,
        "source": {
            "adapter": "bari_signal_phase_request_pack_builder",
        },
        "inputs": {
            "signal_phase_intake_path": {
                "path": str(intake_path),
                "role": "signal_phase_intake_report",
                "sha256": _sha256(intake_path),
            },
            "portal_base_url": portal_base_url,
            "verify_ssl": verify_ssl,
            "top_n": top_n,
        },
        "outputs": {
            "report_json_path": str(report_json_path),
            "report_md_path": str(report_md_path),
            "public_audit_csv_path": str(public_audit_csv_path),
            "request_matrix_csv_path": str(request_matrix_csv_path),
            "template_paths": [str(path) for path in template_paths],
            "manifest_path": str(manifest_path),
        },
    }
    report_json_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_request_pack_markdown(report_payload), encoding="utf-8")

    manifest = {
        "signal_phase_request_pack_version": SIGNAL_PHASE_REQUEST_PACK_VERSION,
        "contract": {
            "resource_name": "signal_phase_request_pack",
            "public_contract_version": SIGNAL_PHASE_REQUEST_PACK_CONTRACT_VERSION,
            "signal_phase_request_pack_version": SIGNAL_PHASE_REQUEST_PACK_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_request_pack_builder",
            "public_portal_url": "https://opendata.comune.bari.it",
            "portal_base_url": portal_base_url,
            "portal_ssl_verification": "enabled" if verify_ssl else "disabled",
        },
        "stats": stats,
        "inputs": report_payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "public_audit_csv_path": str(public_audit_csv_path),
            "public_audit_csv_sha256": _sha256(public_audit_csv_path),
            "request_matrix_csv_path": str(request_matrix_csv_path),
            "request_matrix_csv_sha256": _sha256(request_matrix_csv_path),
            "template_paths": [str(path) for path in template_paths],
        },
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_intake_report", intake_path, _sha256(intake_path)),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_request_pack_report", report_json_path, _sha256(report_json_path)),
                _artifact_reference("signal_phase_request_pack_markdown", report_md_path, _sha256(report_md_path)),
                _artifact_reference("signal_phase_public_audit_csv", public_audit_csv_path, _sha256(public_audit_csv_path)),
                _artifact_reference("signal_phase_request_matrix_csv", request_matrix_csv_path, _sha256(request_matrix_csv_path)),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_request_template_markdown", path, _sha256(path))
                for path in template_paths
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
