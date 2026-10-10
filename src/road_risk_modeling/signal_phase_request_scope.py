"""Build Bari signal-phase request scopes from target dossiers and delivery checklists."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_VERSION = "signal_phase_request_scope_bundle_v1"
SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_CONTRACT_VERSION = "signal_phase_request_scope_bundle_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _compress_hours(hours: list[int]) -> list[str]:
    if not hours:
        return []
    ordered = sorted(set(hour for hour in hours if 0 <= hour <= 23))
    if not ordered:
        return []
    groups: list[list[int]] = [[ordered[0]]]
    for hour in ordered[1:]:
        if hour == groups[-1][-1] + 1:
            groups[-1].append(hour)
        else:
            groups.append([hour])
    ranges: list[str] = []
    for group in groups:
        start = group[0]
        end = group[-1]
        ranges.append(f"{start:02d}:00-{end:02d}:59")
    return ranges


def _top_hour_ranges(temporal_profile: dict[str, Any]) -> list[str]:
    hours: list[int] = []
    for item in temporal_profile.get("top_hours", []):
        try:
            hours.append(int(item["hour"]))
        except (KeyError, TypeError, ValueError):
            continue
    return _compress_hours(hours)


def _pilot_sample_scope(temporal_profile: dict[str, Any]) -> str | None:
    dominant_day_type = _clean_text(temporal_profile.get("dominant_day_type"))
    ranges = _top_hour_ranges(temporal_profile)
    if dominant_day_type is None or not ranges:
        return None
    hours_text = " | ".join(ranges)
    if dominant_day_type == "weekend":
        return f"8 weekend weeks covering {hours_text}"
    if dominant_day_type == "balanced":
        return f"8 weeks with weekday and weekend coverage around {hours_text}"
    return f"8 weeks of {dominant_day_type} coverage around {hours_text}"


def _primary_scope_statement(target: dict[str, Any]) -> str:
    temporal_profile = target.get("temporal_profile") or {}
    base_window = _clean_text(target.get("recommended_time_window")) or _clean_text(
        temporal_profile.get("recommended_time_window")
    )
    top_hotspot = _clean_text(target.get("top_hotspot_name"))
    unresolved_movement_count = _safe_int(target.get("unresolved_signalized_movement_count"))
    unresolved_crash_count = _safe_int(target.get("unresolved_signalized_crash_count"))
    unresolved_suffix = ""
    if unresolved_movement_count > 0 or unresolved_crash_count > 0:
        unresolved_suffix = (
            f" Resolve unresolved burden ({unresolved_movement_count} movements / "
            f"{unresolved_crash_count} crashes)."
        )
    if base_window and top_hotspot:
        return f"Prioritize {base_window} for {top_hotspot}.{unresolved_suffix}"
    if base_window:
        return f"Prioritize {base_window}.{unresolved_suffix}"
    if top_hotspot:
        return f"Prioritize the crash-heavy movement {top_hotspot}.{unresolved_suffix}"
    return f"Prioritize the highest-crash unresolved movement set.{unresolved_suffix}"


def _profile_scope_row(
    *,
    target: dict[str, Any],
    delivery_row: dict[str, str],
) -> dict[str, Any]:
    temporal_profile = target.get("temporal_profile") or {}
    profile_id = delivery_row["profile_id"]
    dominant_day_type = _clean_text(temporal_profile.get("dominant_day_type"))
    peak_bucket = _clean_text(temporal_profile.get("peak_time_of_day_bucket"))
    preferred_hour_ranges = " | ".join(_top_hour_ranges(temporal_profile))
    recommended_time_window = _clean_text(target.get("recommended_time_window")) or _clean_text(
        temporal_profile.get("recommended_time_window")
    )
    pilot_scope = _pilot_sample_scope(temporal_profile)
    top_hotspot = _clean_text(target.get("top_hotspot_name")) or "top unresolved movement"
    unresolved_movement_count = _safe_int(target.get("unresolved_signalized_movement_count"))
    unresolved_crash_count = _safe_int(target.get("unresolved_signalized_crash_count"))
    unresolved_coverage_pct = round(_safe_float(target.get("unresolved_coverage_pct")), 2)
    unresolved_crash_coverage_pct = round(_safe_float(target.get("unresolved_crash_coverage_pct")), 2)
    unresolved_note = ""
    if unresolved_movement_count > 0 or unresolved_crash_count > 0:
        unresolved_note = (
            f" Unresolved burden is {unresolved_movement_count} movements and "
            f"{unresolved_crash_count} crashes."
        )

    if profile_id == "controller_event_log_export":
        scope_mode = "full_export_with_time_window_fallback"
        scoped_requested_window = delivery_row["requested_window"]
        if pilot_scope:
            scoped_requested_window = f"{scoped_requested_window}; fallback pilot scope: {pilot_scope}"
        recommended_minimum_coverage_days = 56
        scope_rationale = (
            f"Keep the full historical request, but if only a partial delivery is possible, focus on "
            f"{recommended_time_window or pilot_scope or 'the highest-crash hours'} for {top_hotspot}."
        ) + unresolved_note
    elif profile_id == "arm_phase_mapping_sheet":
        scope_mode = "current_layout_mapping_for_priority_movements"
        scoped_requested_window = (
            f"{delivery_row['requested_window']}; focus mapping on {top_hotspot} and the same incoming arms as the top-hour crashes"
        )
        recommended_minimum_coverage_days = 0
        scope_rationale = (
            f"Mapping is needed so the targeted controller exports can be joined back to Bari movement objects, "
            f"starting with {top_hotspot}."
        ) + unresolved_note
    elif profile_id == "junction_phase_diagram_support":
        scope_mode = "current_layout_phase_diagram_for_priority_movements"
        scoped_requested_window = (
            f"{delivery_row['requested_window']}; highlight pedestrian phases and protected turns affecting {top_hotspot}"
        )
        recommended_minimum_coverage_days = 0
        scope_rationale = (
            f"Diagram support should explain which stages and protected conflicts govern {top_hotspot} during the prioritized crash window."
        ) + unresolved_note
    else:
        scope_mode = "base_requested_window"
        scoped_requested_window = delivery_row["requested_window"]
        recommended_minimum_coverage_days = 0
        scope_rationale = "Use the base requested window." + unresolved_note

    return {
        "delivery_item_id": delivery_row["delivery_item_id"],
        "request_id": delivery_row["request_id"],
        "junction_id": delivery_row["junction_id"],
        "signal_name": delivery_row["signal_name"],
        "priority_band": delivery_row["priority_band"],
        "profile_id": profile_id,
        "owner_team": delivery_row["owner_team"],
        "delivery_format": delivery_row["delivery_format"],
        "base_requested_window": delivery_row["requested_window"],
        "scoped_requested_window": scoped_requested_window,
        "scope_mode": scope_mode,
        "timed_signalized_crash_count": _safe_int(temporal_profile.get("timed_signalized_crash_count")),
        "dominant_day_type": dominant_day_type,
        "peak_time_of_day_bucket": peak_bucket,
        "peak_crash_hour_label": _clean_text(temporal_profile.get("peak_crash_hour_label")),
        "preferred_focus_hour_ranges": preferred_hour_ranges,
        "recommended_time_window": recommended_time_window,
        "recommended_pilot_scope": pilot_scope,
        "recommended_minimum_coverage_days": recommended_minimum_coverage_days,
        "top_hotspot_name": top_hotspot,
        "top_hotspot_crash_count": _safe_int(target.get("top_hotspot_crash_count")),
        "unresolved_signalized_movement_count": unresolved_movement_count,
        "unresolved_signalized_crash_count": unresolved_crash_count,
        "unresolved_coverage_pct": unresolved_coverage_pct,
        "unresolved_crash_coverage_pct": unresolved_crash_coverage_pct,
        "scope_rationale": scope_rationale,
    }


def _packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Signal-Phase Request Scope: {packet['request_id']}",
        "",
        "## Target Summary",
        "",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Priority rank: `{packet['priority_rank']}`",
        f"- Coverage state: `{packet['coverage_state']}`",
        f"- Matched signalized crashes: `{packet['matched_signalized_crash_count']}`",
        f"- Timed signalized crashes: `{packet['timed_signalized_crash_count']}`",
        f"- Unresolved signalized movements: `{packet['unresolved_signalized_movement_count']}`",
        f"- Unresolved signalized crashes: `{packet['unresolved_signalized_crash_count']}`",
        f"- Unresolved movement coverage: `{packet['unresolved_coverage_pct']}`%",
        f"- Unresolved crash coverage: `{packet['unresolved_crash_coverage_pct']}`%",
        f"- Recommended time window: `{packet['recommended_time_window']}`",
        f"- Preferred focus hour ranges: `{packet['preferred_focus_hour_ranges']}`",
        f"- Recommended pilot scope: `{packet['recommended_pilot_scope']}`",
        "",
        "## Scoped Delivery Items",
        "",
    ]
    for row in packet["delivery_scopes"]:
        lines.extend(
            [
                f"- `{row['profile_id']}`",
                f"  base requested window: `{row['base_requested_window']}`",
                f"  scoped requested window: `{row['scoped_requested_window']}`",
                f"  scope mode: `{row['scope_mode']}`",
                f"  rationale: {row['scope_rationale']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Top Hotspots",
            "",
        ]
    )
    for row in packet["top_uncovered_movements"]:
        lines.append(
            f"- `{row['movement_name']}` `{row['movement_turn']}`: `{row['matched_crash_count']}` crashes"
        )
    lines.append("")
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Request Scope Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the tier-1 Bari target dossiers have been converted into scoped delivery asks.",
        "",
        "## Summary",
        "",
        f"- targets: `{payload['summary']['target_count']}`",
        f"- delivery scope rows: `{payload['summary']['delivery_scope_count']}`",
        f"- controller event scope rows: `{payload['summary']['controller_event_scope_count']}`",
        f"- targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- targets with pilot scopes: `{payload['summary']['targets_with_pilot_scopes']}`",
        f"- unresolved signalized movements across targets: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across targets: `{payload['summary']['unresolved_signalized_crash_total']}`",
        f"- timed signalized crashes across targets: `{payload['summary']['timed_signalized_crash_total']}`",
        "",
        "## Scoped Queue",
        "",
    ]
    for row in payload["targets"]:
        lines.append(
            f"- `{row['signal_name']}`: `{row['recommended_time_window']}`, "
            f"`{row['preferred_focus_hour_ranges']}`, unresolved crashes `{row['unresolved_signalized_crash_count']}`, "
            f"pilot `{row['recommended_pilot_scope']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_request_scope_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_request_scope/bari",
    signal_phase_target_bundle_path: str | Path = "data/reporting/signal_phase_targets/bari/signal_phase_target_bundle.json",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "scope_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    target_bundle_input = Path(signal_phase_target_bundle_path)
    delivery_checklist_input = Path(delivery_checklist_path)

    target_bundle = _load_json(target_bundle_input)
    target_rows = target_bundle.get("targets", [])
    if not isinstance(target_rows, list):
        raise RuntimeError("Signal phase target bundle must include a top-level 'targets' list.")

    delivery_rows = _read_csv_rows(delivery_checklist_input)
    delivery_rows_by_request: dict[str, list[dict[str, str]]] = {}
    for row in delivery_rows:
        delivery_rows_by_request.setdefault(str(row["request_id"]), []).append(row)

    target_rows = sorted(
        [row for row in target_rows if isinstance(row, dict)],
        key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("junction_id") or "")),
    )

    target_window_rows: list[dict[str, Any]] = []
    delivery_scope_rows: list[dict[str, Any]] = []
    packet_payloads: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for target in target_rows:
        request_id = str(target["request_id"])
        target_delivery_rows = delivery_rows_by_request.get(request_id, [])
        scoped_rows = [
            _profile_scope_row(target=target, delivery_row=row)
            for row in sorted(target_delivery_rows, key=lambda item: str(item.get("profile_id") or ""))
        ]
        delivery_scope_rows.extend(scoped_rows)

        temporal_profile = target.get("temporal_profile") or {}
        preferred_focus_hour_ranges = " | ".join(_top_hour_ranges(temporal_profile))
        recommended_pilot_scope = _pilot_sample_scope(temporal_profile)
        target_window_row = {
            "request_id": request_id,
            "junction_id": target["junction_id"],
            "signal_name": target["signal_name"],
            "priority_rank": _safe_int(target.get("priority_rank")),
            "priority_band": _clean_text(target.get("priority_band")),
            "coverage_state": _clean_text(target.get("coverage_state")),
            "matched_signalized_crash_count": _safe_int(target.get("matched_signalized_crash_count")),
            "timed_signalized_crash_count": _safe_int(temporal_profile.get("timed_signalized_crash_count")),
            "unresolved_signalized_movement_count": _safe_int(target.get("unresolved_signalized_movement_count")),
            "unresolved_signalized_crash_count": _safe_int(target.get("unresolved_signalized_crash_count")),
            "unresolved_coverage_pct": round(_safe_float(target.get("unresolved_coverage_pct")), 2),
            "unresolved_crash_coverage_pct": round(_safe_float(target.get("unresolved_crash_coverage_pct")), 2),
            "dominant_day_type": _clean_text(temporal_profile.get("dominant_day_type")),
            "peak_time_of_day_bucket": _clean_text(temporal_profile.get("peak_time_of_day_bucket")),
            "peak_crash_hour_label": _clean_text(temporal_profile.get("peak_crash_hour_label")),
            "preferred_focus_hour_ranges": preferred_focus_hour_ranges,
            "recommended_time_window": _clean_text(target.get("recommended_time_window"))
            or _clean_text(temporal_profile.get("recommended_time_window")),
            "recommended_pilot_scope": recommended_pilot_scope,
            "top_hotspot_name": _clean_text(target.get("top_hotspot_name")),
            "top_hotspot_crash_count": _safe_int(target.get("top_hotspot_crash_count")),
            "primary_scope_statement": _primary_scope_statement(target),
        }
        target_window_rows.append(target_window_row)

        packet_payload = {
            **target_window_row,
            "delivery_scopes": scoped_rows,
            "top_uncovered_movements": list(target.get("top_uncovered_movements", []))[:5],
        }
        packet_payloads.append(packet_payload)

        packet_json_path = packet_dir / f"{_slugify(request_id)}.json"
        packet_md_path = packet_dir / f"{_slugify(request_id)}.md"
        packet_json_path.write_text(json.dumps(packet_payload, indent=2, sort_keys=True), encoding="utf-8")
        packet_md_path.write_text(_packet_markdown(packet_payload), encoding="utf-8")
        packet_paths.extend([str(packet_json_path), str(packet_md_path)])

    target_collection_windows_path = output_root / "target_collection_windows.csv"
    delivery_scope_matrix_path = output_root / "delivery_scope_matrix.csv"
    bundle_json_path = output_root / "signal_phase_request_scope_bundle.json"
    bundle_md_path = output_root / "signal_phase_request_scope_bundle.md"
    manifest_path = output_root / "signal_phase_request_scope_bundle.manifest.json"

    _write_csv(
        target_collection_windows_path,
        target_window_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "coverage_state",
            "matched_signalized_crash_count",
            "timed_signalized_crash_count",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
            "dominant_day_type",
            "peak_time_of_day_bucket",
            "peak_crash_hour_label",
            "preferred_focus_hour_ranges",
            "recommended_time_window",
            "recommended_pilot_scope",
            "top_hotspot_name",
            "top_hotspot_crash_count",
            "primary_scope_statement",
        ],
    )
    _write_csv(
        delivery_scope_matrix_path,
        delivery_scope_rows,
        [
            "delivery_item_id",
            "request_id",
            "junction_id",
            "signal_name",
            "priority_band",
            "profile_id",
            "owner_team",
            "delivery_format",
            "base_requested_window",
            "scoped_requested_window",
            "scope_mode",
            "timed_signalized_crash_count",
            "dominant_day_type",
            "peak_time_of_day_bucket",
            "peak_crash_hour_label",
            "preferred_focus_hour_ranges",
            "recommended_time_window",
            "recommended_pilot_scope",
            "recommended_minimum_coverage_days",
            "top_hotspot_name",
            "top_hotspot_crash_count",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
            "scope_rationale",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "target_count": len(target_window_rows),
        "delivery_scope_count": len(delivery_scope_rows),
        "controller_event_scope_count": sum(1 for row in delivery_scope_rows if row["profile_id"] == "controller_event_log_export"),
        "targets_with_unresolved_movements": sum(
            1 for row in target_window_rows if _safe_int(row["unresolved_signalized_movement_count"]) > 0
        ),
        "targets_with_pilot_scopes": sum(1 for row in target_window_rows if _clean_text(row["recommended_pilot_scope"]) is not None),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row["unresolved_signalized_movement_count"]) for row in target_window_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row["unresolved_signalized_crash_count"]) for row in target_window_rows
        ),
        "timed_signalized_crash_total": sum(_safe_int(row["timed_signalized_crash_count"]) for row in target_window_rows),
    }

    bundle_payload = {
        "signal_phase_request_scope_bundle_version": SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_VERSION,
        "signal_phase_request_scope_bundle_contract_version": SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "targets": packet_payloads,
    }
    bundle_json_path.write_text(json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(bundle_payload), encoding="utf-8")

    manifest = {
        "signal_phase_request_scope_bundle_version": SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_request_scope_bundle",
            "public_contract_version": SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_CONTRACT_VERSION,
            "signal_phase_request_scope_bundle_version": SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_request_scope_builder",
        },
        "inputs": {
            "signal_phase_target_bundle_path": str(target_bundle_input),
            "delivery_checklist_path": str(delivery_checklist_input),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "target_collection_windows_path": str(target_collection_windows_path),
            "target_collection_windows_sha256": _sha256(target_collection_windows_path),
            "delivery_scope_matrix_path": str(delivery_scope_matrix_path),
            "delivery_scope_matrix_sha256": _sha256(delivery_scope_matrix_path),
            "packet_dir": str(packet_dir),
            "packet_paths": packet_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_target_bundle", target_bundle_input, _sha256(target_bundle_input)),
            _artifact_reference("signal_phase_delivery_checklist", delivery_checklist_input, _sha256(delivery_checklist_input)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_request_scope_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("signal_phase_request_scope_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_target_collection_windows",
                target_collection_windows_path,
                _sha256(target_collection_windows_path),
            ),
            _artifact_reference(
                "signal_phase_delivery_scope_matrix",
                delivery_scope_matrix_path,
                _sha256(delivery_scope_matrix_path),
            ),
        ]
        + [
            _artifact_reference("signal_phase_request_scope_packet", Path(path), _sha256(Path(path)))
            for path in packet_paths
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_request_scope_bundle_version": SIGNAL_PHASE_REQUEST_SCOPE_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
