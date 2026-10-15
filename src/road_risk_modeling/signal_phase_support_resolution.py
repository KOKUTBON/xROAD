"""Build analyst support-resolution queues from validated support artifacts."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_SUPPORT_RESOLUTION_BUNDLE_VERSION = "signal_phase_support_resolution_bundle_v1"
SIGNAL_PHASE_SUPPORT_RESOLUTION_BUNDLE_CONTRACT_VERSION = "signal_phase_support_resolution_bundle_public_v1"

UNRESOLVED_MOVEMENT_STATES = {"ambiguous_target_variant", "turn_only_fallback"}


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


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100.0, 2)


def _split_catalog(value: Any) -> list[str]:
    text = _clean_text(value)
    if text is None:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _load_aggregate_lookup(aggregate_csv_path: Path) -> dict[str, dict[str, Any]]:
    summary_by_id: dict[str, dict[str, Any]] = {}
    with aggregate_csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            node_object_id = _clean_text(row.get("node_object_id"))
            if not node_object_id:
                continue
            crash_count = _safe_int(row.get("crash_count"))
            injuries_total = _safe_int(row.get("injuries_total"))
            occurred_year = _safe_int(row.get("occurred_year"))
            entry = summary_by_id.setdefault(
                node_object_id,
                {
                    "total_crashes": 0,
                    "total_injuries": 0,
                    "peak_year": None,
                    "peak_year_crash_count": 0,
                },
            )
            entry["total_crashes"] += crash_count
            entry["total_injuries"] += injuries_total
            if crash_count > int(entry["peak_year_crash_count"] or 0):
                entry["peak_year"] = occurred_year or None
                entry["peak_year_crash_count"] = crash_count
    return summary_by_id


def _load_phase_readiness_lookup(
    movement_review_path: Path,
    *,
    phase_readiness_csv_path: Path | None,
) -> dict[str, dict[str, Any]]:
    if phase_readiness_csv_path is not None and phase_readiness_csv_path.exists():
        with phase_readiness_csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        review_payload = _load_json(movement_review_path)
        rows = review_payload.get("signal_phase_readiness", [])
        if not isinstance(rows, list):
            raise RuntimeError("Movement review JSON must include a 'signal_phase_readiness' list.")
    return {
        junction_id: dict(row)
        for row in rows
        if isinstance(row, dict) and (junction_id := _clean_text(row.get("junction_id")))
    }


def _load_movement_rows_by_junction(movement_objects_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(movement_objects_path)
    features = payload.get("features", [])
    if not isinstance(features, list):
        raise RuntimeError("Movement object GeoJSON must contain a top-level 'features' list.")

    lookup: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        properties = feature.get("properties", {})
        if not isinstance(properties, dict):
            continue
        junction_id = _clean_text(properties.get("junction_id"))
        if not junction_id:
            continue
        lookup.setdefault(junction_id, []).append(dict(properties))
    return lookup


def _support_context_from_manifest(manifest_path: Path) -> dict[str, Any] | None:
    manifest = _load_json(manifest_path)
    profile = manifest.get("profile") if isinstance(manifest.get("profile"), dict) else {}
    stats = manifest.get("stats") if isinstance(manifest.get("stats"), dict) else {}
    inputs = manifest.get("inputs") if isinstance(manifest.get("inputs"), dict) else {}
    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), dict) else {}

    if _clean_text(profile.get("profile_type")) != "support_artifact":
        return None
    if _clean_text(stats.get("validation_outcome")) != "accepted_support_artifact":
        return None

    junction_id = _clean_text(inputs.get("junction_id"))
    if junction_id is None:
        junction_ids_found = stats.get("junction_ids_found")
        if isinstance(junction_ids_found, list):
            for value in junction_ids_found:
                junction_id = _clean_text(value)
                if junction_id is not None:
                    break

    support_input = inputs.get("input_csv_path") if isinstance(inputs.get("input_csv_path"), dict) else {}
    mapping_stub_input = inputs.get("mapping_stub_path") if isinstance(inputs.get("mapping_stub_path"), dict) else {}
    support_path = _clean_text(support_input.get("path"))
    request_id = _clean_text(inputs.get("request_id")) or manifest_path.parent.name
    return {
        "request_id": request_id,
        "junction_id": junction_id,
        "profile_id": _clean_text(profile.get("profile_id")) or "junction_phase_diagram_support",
        "profile_label": _clean_text(profile.get("profile_label")) or "Junction phase diagram support",
        "support_artifact_path": support_path,
        "support_artifact_name": Path(support_path).name if support_path else None,
        "support_artifact_extension": Path(support_path).suffix.lower() if support_path else None,
        "support_file_size_bytes": _safe_int(stats.get("support_file_size_bytes")),
        "validation_manifest_path": str(manifest_path),
        "validation_report_path": _clean_text(outputs.get("report_json_path")),
        "mapping_stub_path": _clean_text(mapping_stub_input.get("path")),
        "validation_outcome": "accepted_support_artifact",
    }


def _unresolved_group_key(row: dict[str, Any]) -> tuple[str, str, str]:
    incoming_arm_id = _clean_text(row.get("incoming_arm_id")) or _clean_text(row.get("approach_arm_id")) or "unknown_incoming_arm"
    movement_turn = _clean_text(row.get("movement_turn")) or "unknown_turn"
    phase_priority_group = _clean_text(row.get("phase_priority_group")) or "unknown_phase_priority_group"
    return incoming_arm_id, movement_turn, phase_priority_group


def _build_manual_arm_phase_review_rows(
    request_context: dict[str, Any],
    *,
    signal_name: str | None,
    signal_type: str | None,
    movement_rows: list[dict[str, Any]],
    aggregate_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in movement_rows:
        if _clean_text(row.get("movement_role")) != "signalized_turn_movement":
            continue
        resolution_state = _clean_text(row.get("movement_resolution_state")) or ""
        if resolution_state not in UNRESOLVED_MOVEMENT_STATES:
            continue
        node_object_id = _clean_text(row.get("node_object_id"))
        if not node_object_id:
            continue
        aggregate = aggregate_lookup.get(node_object_id, {})
        group_key = _unresolved_group_key(row)
        entry = grouped.setdefault(
            group_key,
            {
                "request_id": request_context["request_id"],
                "junction_id": request_context["junction_id"],
                "signal_name": signal_name,
                "signal_type": signal_type,
                "incoming_arm_id": group_key[0],
                "movement_turn": group_key[1],
                "phase_priority_group": group_key[2],
                "movement_name": _clean_text(row.get("name")),
                "movement_variant_count": 0,
                "movement_resolution_states": set(),
                "movement_resolution_methods": set(),
                "candidate_target_arm_count_max": 0,
                "candidate_target_arm_catalog": set(),
                "outgoing_arm_catalog": set(),
                "movement_ids": [],
                "crash_total": 0,
                "injury_total": 0,
                "peak_year": None,
                "peak_year_crash_count": 0,
            },
        )
        entry["movement_variant_count"] += 1
        entry["movement_resolution_states"].add(resolution_state)
        method = _clean_text(row.get("movement_resolution_method"))
        if method:
            entry["movement_resolution_methods"].add(method)
        entry["candidate_target_arm_count_max"] = max(
            int(entry["candidate_target_arm_count_max"]),
            _safe_int(row.get("candidate_target_arm_count")),
        )
        for item in _split_catalog(row.get("candidate_target_arm_catalog")):
            entry["candidate_target_arm_catalog"].add(item)
        outgoing_arm_id = _clean_text(row.get("outgoing_arm_id"))
        if outgoing_arm_id:
            entry["outgoing_arm_catalog"].add(outgoing_arm_id)
        entry["movement_ids"].append(node_object_id)
        entry["crash_total"] += _safe_int(aggregate.get("total_crashes"))
        entry["injury_total"] += _safe_int(aggregate.get("total_injuries"))
        if _safe_int(aggregate.get("peak_year_crash_count")) > int(entry["peak_year_crash_count"] or 0):
            entry["peak_year"] = aggregate.get("peak_year")
            entry["peak_year_crash_count"] = _safe_int(aggregate.get("peak_year_crash_count"))

    rows: list[dict[str, Any]] = []
    for entry in grouped.values():
        review_priority_score = int(entry["crash_total"]) * 100 + int(entry["candidate_target_arm_count_max"]) * 10 + int(
            entry["movement_variant_count"]
        )
        rows.append(
            {
                "request_id": entry["request_id"],
                "junction_id": entry["junction_id"],
                "signal_name": entry["signal_name"],
                "signal_type": entry["signal_type"],
                "incoming_arm_id": entry["incoming_arm_id"],
                "movement_turn": entry["movement_turn"],
                "phase_priority_group": entry["phase_priority_group"],
                "movement_name": entry["movement_name"],
                "movement_variant_count": int(entry["movement_variant_count"]),
                "movement_resolution_states": " | ".join(sorted(entry["movement_resolution_states"])),
                "movement_resolution_methods": " | ".join(sorted(entry["movement_resolution_methods"])),
                "candidate_target_arm_count_max": int(entry["candidate_target_arm_count_max"]),
                "candidate_target_arm_catalog": " | ".join(sorted(entry["candidate_target_arm_catalog"])),
                "outgoing_arm_catalog": " | ".join(sorted(entry["outgoing_arm_catalog"])),
                "movement_ids": " | ".join(entry["movement_ids"]),
                "crash_total": int(entry["crash_total"]),
                "injury_total": int(entry["injury_total"]),
                "peak_year": entry["peak_year"],
                "peak_year_crash_count": int(entry["peak_year_crash_count"]),
                "review_priority_score": review_priority_score,
                "support_artifact_path": request_context["support_artifact_path"],
                "validation_manifest_path": request_context["validation_manifest_path"],
                "manual_mapping_hint": "Use the validated support diagram to choose the outgoing arm target, then fill phase_id, stage_id, and protection_state in the arm-phase mapping sheet.",
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item["review_priority_score"]),
            -int(item["crash_total"]),
            str(item["incoming_arm_id"]),
            str(item["movement_turn"]),
        )
    )
    return rows


def _build_pedestrian_stage_review_rows(
    request_context: dict[str, Any],
    *,
    signal_name: str | None,
    signal_type: str | None,
    movement_rows: list[dict[str, Any]],
    aggregate_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in movement_rows:
        phase_priority_group = _clean_text(row.get("phase_priority_group"))
        if phase_priority_group != "signalized_pedestrian_stage":
            continue
        node_object_id = _clean_text(row.get("node_object_id"))
        if not node_object_id:
            continue
        aggregate = aggregate_lookup.get(node_object_id, {})
        crash_total = _safe_int(aggregate.get("total_crashes"))
        rows.append(
            {
                "request_id": request_context["request_id"],
                "junction_id": request_context["junction_id"],
                "signal_name": signal_name,
                "signal_type": signal_type,
                "node_object_id": node_object_id,
                "movement_name": _clean_text(row.get("name")),
                "movement_role": _clean_text(row.get("movement_role")),
                "movement_turn": _clean_text(row.get("movement_turn")),
                "movement_resolution_state": _clean_text(row.get("movement_resolution_state")),
                "control_state": _clean_text(row.get("control_state")),
                "phase_priority_group": phase_priority_group,
                "crash_total": crash_total,
                "injury_total": _safe_int(aggregate.get("total_injuries")),
                "peak_year": aggregate.get("peak_year"),
                "peak_year_crash_count": _safe_int(aggregate.get("peak_year_crash_count")),
                "review_priority_score": crash_total * 100 + 10,
                "support_artifact_path": request_context["support_artifact_path"],
                "validation_manifest_path": request_context["validation_manifest_path"],
                "manual_mapping_hint": "Use the validated support diagram to assign the pedestrian walk and clearance stage, or confirm the crossing is controlled by a shared stage.",
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item["review_priority_score"]),
            -int(item["crash_total"]),
            str(item["node_object_id"]),
        )
    )
    return rows


def _support_resolution_scope(*, manual_rows: list[dict[str, Any]], pedestrian_rows: list[dict[str, Any]]) -> str:
    if manual_rows and pedestrian_rows:
        return "arm_phase_and_pedestrian_stage_resolution"
    if manual_rows:
        return "arm_phase_resolution"
    if pedestrian_rows:
        return "pedestrian_stage_resolution"
    return "support_artifact_catalog_only"


def _recommended_next_action(*, manual_rows: list[dict[str, Any]], pedestrian_rows: list[dict[str, Any]]) -> str:
    if manual_rows and pedestrian_rows:
        return "Resolve ambiguous arm-to-phase mappings first, then assign pedestrian walk and clearance stages from the same validated support diagram."
    if manual_rows:
        return "Resolve ambiguous arm-to-phase mappings and populate the arm_phase_mapping_sheet before requesting more controller exports."
    if pedestrian_rows:
        return "Assign pedestrian walk and clearance stages from the validated support diagram before finalizing the movement-to-phase mapping sheet."
    return "Catalog the support artifact and wait for joinable timing or mapping deliveries."


def _request_queue_row(
    request_context: dict[str, Any],
    *,
    phase_row: dict[str, Any],
    movement_rows: list[dict[str, Any]],
    manual_rows: list[dict[str, Any]],
    pedestrian_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    signal_name = _clean_text(phase_row.get("signal_name")) or request_context["junction_id"]
    signal_type = _clean_text(phase_row.get("signal_type"))
    signalized_movement_count = _safe_int(phase_row.get("signalized_movement_count"))
    if signalized_movement_count <= 0:
        signalized_movement_count = sum(
            1 for row in movement_rows if _clean_text(row.get("movement_role")) == "signalized_turn_movement"
        )
    matched_crashes_at_junction_total = _safe_int(phase_row.get("matched_crashes_at_junction_total"))
    if matched_crashes_at_junction_total <= 0:
        matched_crashes_at_junction_total = sum(int(row["crash_total"]) for row in manual_rows) + sum(
            int(row["crash_total"]) for row in pedestrian_rows
        )
    manual_crash_total = sum(int(row["crash_total"]) for row in manual_rows)
    pedestrian_crash_total = sum(int(row["crash_total"]) for row in pedestrian_rows)
    unresolved_signalized_movement_count = len(manual_rows)
    unresolved_signalized_crash_total = manual_crash_total
    review_priority_score = (
        _safe_int(phase_row.get("review_priority_score"))
        + manual_crash_total * 10
        + pedestrian_crash_total * 5
        + len(manual_rows)
        + len(pedestrian_rows)
    )
    return {
        "request_id": request_context["request_id"],
        "junction_id": request_context["junction_id"],
        "signal_name": signal_name,
        "signal_type": signal_type,
        "validation_outcome": request_context["validation_outcome"],
        "support_artifact_name": request_context["support_artifact_name"],
        "support_artifact_extension": request_context["support_artifact_extension"],
        "support_artifact_path": request_context["support_artifact_path"],
        "support_file_size_bytes": int(request_context["support_file_size_bytes"]),
        "validation_manifest_path": request_context["validation_manifest_path"],
        "validation_report_path": request_context["validation_report_path"],
        "mapping_stub_path": request_context["mapping_stub_path"],
        "signalized_movement_count": signalized_movement_count,
        "signalized_crash_total": _safe_int(phase_row.get("signalized_crash_total")),
        "matched_crashes_at_junction_total": matched_crashes_at_junction_total,
        "ambiguous_movement_count": _safe_int(phase_row.get("ambiguous_movement_count")),
        "unresolved_signalized_movement_count": unresolved_signalized_movement_count,
        "unresolved_signalized_crash_total": unresolved_signalized_crash_total,
        "unresolved_signalized_movement_share_pct": _safe_pct(
            unresolved_signalized_movement_count, signalized_movement_count
        ),
        "unresolved_signalized_crash_coverage_pct": _safe_pct(
            unresolved_signalized_crash_total, matched_crashes_at_junction_total
        ),
        "manual_arm_phase_review_count": len(manual_rows),
        "manual_arm_phase_crash_total": manual_crash_total,
        "pedestrian_stage_review_count": len(pedestrian_rows),
        "pedestrian_stage_crash_total": pedestrian_crash_total,
        "phase_priority_groups_present": _clean_text(phase_row.get("phase_priority_groups_present")),
        "support_resolution_scope": _support_resolution_scope(manual_rows=manual_rows, pedestrian_rows=pedestrian_rows),
        "recommended_next_action": _recommended_next_action(manual_rows=manual_rows, pedestrian_rows=pedestrian_rows),
        "review_priority_score": review_priority_score,
        "top_manual_mapping_hint": (
            f"{manual_rows[0]['movement_turn']} from {manual_rows[0]['incoming_arm_id']}" if manual_rows else None
        ),
        "top_pedestrian_mapping_hint": pedestrian_rows[0]["node_object_id"] if pedestrian_rows else None,
    }


def _packet_markdown(
    queue_row: dict[str, Any],
    *,
    manual_rows: list[dict[str, Any]],
    pedestrian_rows: list[dict[str, Any]],
    top_n: int,
) -> str:
    lines = [
        f"# Support Resolution Packet: {queue_row['request_id']}",
        "",
        f"- Junction: `{queue_row['junction_id']}`",
        f"- Signal: `{queue_row.get('signal_name') or queue_row['junction_id']}`",
        f"- Support artifact: `{queue_row.get('support_artifact_name') or 'unknown'}`",
        f"- Resolution scope: `{queue_row['support_resolution_scope']}`",
        f"- Signalized crashes at junction: `{queue_row['matched_crashes_at_junction_total']}`",
        f"- Manual arm-phase review rows: `{queue_row['manual_arm_phase_review_count']}`",
        f"- Pedestrian-stage review rows: `{queue_row['pedestrian_stage_review_count']}`",
        f"- Unresolved signalized movements: `{queue_row['unresolved_signalized_movement_count']}` (`{queue_row['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
        f"- Unresolved signalized crashes: `{queue_row['unresolved_signalized_crash_total']}` (`{queue_row['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
        "",
        "## Next Analyst Step",
        "",
        f"- {queue_row['recommended_next_action']}",
        "",
        "## Top Manual Arm-Phase Rows",
        "",
    ]
    for row in manual_rows[:top_n]:
        lines.append(
            f"- `{row['movement_turn']}` from `{row['incoming_arm_id']}`: `{row['crash_total']}` crashes, "
            f"`{row['movement_variant_count']}` variants, candidates `{row['candidate_target_arm_catalog'] or 'n/a'}`"
        )
    if not manual_rows:
        lines.append("- No unresolved signalized turn rows were found for this support artifact.")
    lines.extend(["", "## Top Pedestrian-Stage Rows", ""])
    for row in pedestrian_rows[:top_n]:
        lines.append(
            f"- `{row['node_object_id']}`: `{row['crash_total']}` crashes, state "
            f"`{row.get('movement_resolution_state') or 'unknown'}`"
        )
    if not pedestrian_rows:
        lines.append("- No pedestrian-stage rows were found for this support artifact.")
    lines.append("")
    return "\n".join(lines)


def _markdown_report(
    *,
    summary: dict[str, Any],
    queue_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# Bari Signal-Phase Support Resolution Bundle",
        "",
        "This bundle turns accepted support diagrams into analyst queues for arm-to-phase resolution and pedestrian-stage review.",
        "",
        "## Summary",
        "",
        f"- supplied validation manifests: `{summary['validation_manifest_count']}`",
        f"- accepted support artifacts: `{summary['accepted_support_artifact_count']}`",
        f"- support-resolution requests: `{summary['support_request_count']}`",
        f"- manual arm-phase review rows: `{summary['manual_arm_phase_review_row_count']}`",
        f"- pedestrian-stage review rows: `{summary['pedestrian_stage_review_row_count']}`",
        f"- requests with unresolved signalized movements: `{summary['requests_with_unresolved_signalized_movements_count']}`",
        f"- unresolved signalized movement rows: `{summary['unresolved_signalized_movement_count_total']}` (`{summary['unresolved_signalized_movement_share_pct']:.2f}%` of signalized movements)",
        f"- unresolved signalized crashes: `{summary['unresolved_signalized_crash_total']}` (`{summary['unresolved_signalized_crash_coverage_pct']:.2f}%` of matched junction crashes)",
        f"- analyst packets: `{summary['analyst_packet_count']}`",
        "",
        "## Active Requests",
        "",
    ]
    for row in queue_rows[:5]:
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: "
            f"`{row['manual_arm_phase_review_count']}` manual rows, "
            f"`{row['pedestrian_stage_review_count']}` pedestrian rows, "
            f"`{row['unresolved_signalized_movement_count']}` unresolved movements, "
            f"`{row['unresolved_signalized_crash_total']}` unresolved crashes, "
            f"`{row['matched_crashes_at_junction_total']}` matched junction crashes"
        )
    if not queue_rows:
        lines.append("- No accepted support artifacts are currently available for analyst resolution.")
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_support_resolution_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_support_resolution/bari",
    support_validation_manifest_paths: list[str | Path],
    movement_review_path: str | Path = "data/reporting/movement_review/bari/movement_review_pack.json",
    phase_readiness_csv_path: str | Path | None = None,
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    aggregate_path: str | Path = "data/processed/node_aggregates/bari_open_data_movements/node_year_metrics.csv",
    top_n: int = 10,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    movement_review_file = Path(movement_review_path)
    phase_readiness_file = Path(phase_readiness_csv_path) if phase_readiness_csv_path else movement_review_file.with_name(
        "signal_phase_readiness.csv"
    )
    movement_objects_file = Path(movement_objects_path)
    aggregate_file = Path(aggregate_path)
    validation_manifest_files = [Path(path) for path in support_validation_manifest_paths]

    phase_lookup = _load_phase_readiness_lookup(
        movement_review_file,
        phase_readiness_csv_path=phase_readiness_file if phase_readiness_file.exists() else None,
    )
    movement_rows_by_junction = _load_movement_rows_by_junction(movement_objects_file)
    aggregate_lookup = _load_aggregate_lookup(aggregate_file)

    queue_rows: list[dict[str, Any]] = []
    manual_review_rows: list[dict[str, Any]] = []
    pedestrian_review_rows: list[dict[str, Any]] = []
    packet_paths: list[Path] = []
    accepted_support_artifact_count = 0

    for manifest_path in validation_manifest_files:
        request_context = _support_context_from_manifest(manifest_path)
        if request_context is None:
            continue
        accepted_support_artifact_count += 1
        junction_id = request_context["junction_id"]
        phase_row = phase_lookup.get(junction_id, {}) if junction_id else {}
        signal_name = _clean_text(phase_row.get("signal_name")) or junction_id
        signal_type = _clean_text(phase_row.get("signal_type"))
        movement_rows = movement_rows_by_junction.get(junction_id, []) if junction_id else []

        manual_rows = _build_manual_arm_phase_review_rows(
            request_context,
            signal_name=signal_name,
            signal_type=signal_type,
            movement_rows=movement_rows,
            aggregate_lookup=aggregate_lookup,
        )
        pedestrian_rows = _build_pedestrian_stage_review_rows(
            request_context,
            signal_name=signal_name,
            signal_type=signal_type,
            movement_rows=movement_rows,
            aggregate_lookup=aggregate_lookup,
        )
        queue_row = _request_queue_row(
            request_context,
            phase_row=phase_row,
            movement_rows=movement_rows,
            manual_rows=manual_rows,
            pedestrian_rows=pedestrian_rows,
        )
        queue_rows.append(queue_row)
        manual_review_rows.extend(manual_rows)
        pedestrian_review_rows.extend(pedestrian_rows)

    queue_rows.sort(
        key=lambda item: (
            -int(item["review_priority_score"]),
            -int(item["matched_crashes_at_junction_total"]),
            str(item["request_id"]),
        )
    )
    request_rank = {row["request_id"]: index for index, row in enumerate(queue_rows)}
    manual_review_rows.sort(
        key=lambda item: (
            request_rank.get(item["request_id"], 999999),
            -int(item["review_priority_score"]),
            str(item["incoming_arm_id"]),
        )
    )
    pedestrian_review_rows.sort(
        key=lambda item: (
            request_rank.get(item["request_id"], 999999),
            -int(item["review_priority_score"]),
            str(item["node_object_id"]),
        )
    )

    packets_dir = output_root / "analyst_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    for queue_row in queue_rows:
        request_id = queue_row["request_id"]
        packet_path = packets_dir / f"{request_id}.md"
        request_manual_rows = [row for row in manual_review_rows if row["request_id"] == request_id]
        request_pedestrian_rows = [row for row in pedestrian_review_rows if row["request_id"] == request_id]
        packet_path.write_text(
            _packet_markdown(
                queue_row,
                manual_rows=request_manual_rows,
                pedestrian_rows=request_pedestrian_rows,
                top_n=top_n,
            ),
            encoding="utf-8",
        )
        queue_row["analyst_packet_path"] = str(packet_path)
        packet_paths.append(packet_path)

    queue_csv_path = output_root / "support_resolution_queue.csv"
    manual_csv_path = output_root / "manual_arm_phase_review.csv"
    pedestrian_csv_path = output_root / "pedestrian_stage_review.csv"
    report_json_path = output_root / "signal_phase_support_resolution_bundle.json"
    report_md_path = output_root / "signal_phase_support_resolution_bundle.md"
    manifest_path = output_root / "signal_phase_support_resolution_bundle.manifest.json"

    _write_csv(
        queue_csv_path,
        queue_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "signal_type",
            "validation_outcome",
            "support_artifact_name",
            "support_artifact_extension",
            "support_artifact_path",
            "support_file_size_bytes",
            "validation_manifest_path",
            "validation_report_path",
            "mapping_stub_path",
            "signalized_movement_count",
            "signalized_crash_total",
            "matched_crashes_at_junction_total",
            "ambiguous_movement_count",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_total",
            "unresolved_signalized_movement_share_pct",
            "unresolved_signalized_crash_coverage_pct",
            "manual_arm_phase_review_count",
            "manual_arm_phase_crash_total",
            "pedestrian_stage_review_count",
            "pedestrian_stage_crash_total",
            "phase_priority_groups_present",
            "support_resolution_scope",
            "recommended_next_action",
            "review_priority_score",
            "top_manual_mapping_hint",
            "top_pedestrian_mapping_hint",
            "analyst_packet_path",
        ],
    )
    _write_csv(
        manual_csv_path,
        manual_review_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "signal_type",
            "incoming_arm_id",
            "movement_turn",
            "phase_priority_group",
            "movement_name",
            "movement_variant_count",
            "movement_resolution_states",
            "movement_resolution_methods",
            "candidate_target_arm_count_max",
            "candidate_target_arm_catalog",
            "outgoing_arm_catalog",
            "movement_ids",
            "crash_total",
            "injury_total",
            "peak_year",
            "peak_year_crash_count",
            "review_priority_score",
            "support_artifact_path",
            "validation_manifest_path",
            "manual_mapping_hint",
        ],
    )
    _write_csv(
        pedestrian_csv_path,
        pedestrian_review_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "signal_type",
            "node_object_id",
            "movement_name",
            "movement_role",
            "movement_turn",
            "movement_resolution_state",
            "control_state",
            "phase_priority_group",
            "crash_total",
            "injury_total",
            "peak_year",
            "peak_year_crash_count",
            "review_priority_score",
            "support_artifact_path",
            "validation_manifest_path",
            "manual_mapping_hint",
        ],
    )

    summary = {
        "validation_manifest_count": len(validation_manifest_files),
        "accepted_support_artifact_count": accepted_support_artifact_count,
        "support_request_count": len(queue_rows),
        "manual_arm_phase_review_row_count": len(manual_review_rows),
        "pedestrian_stage_review_row_count": len(pedestrian_review_rows),
        "analyst_packet_count": len(packet_paths),
        "manual_arm_phase_crash_total": int(sum(int(row["crash_total"]) for row in manual_review_rows)),
        "pedestrian_stage_crash_total": int(sum(int(row["crash_total"]) for row in pedestrian_review_rows)),
        "requests_with_unresolved_signalized_movements_count": int(
            sum(1 for row in queue_rows if int(row["unresolved_signalized_movement_count"]) > 0)
        ),
        "unresolved_signalized_movement_count_total": int(
            sum(int(row["unresolved_signalized_movement_count"]) for row in queue_rows)
        ),
        "unresolved_signalized_crash_total": int(
            sum(int(row["unresolved_signalized_crash_total"]) for row in queue_rows)
        ),
        "unresolved_signalized_movement_share_pct": _safe_pct(
            int(sum(int(row["unresolved_signalized_movement_count"]) for row in queue_rows)),
            int(sum(int(row["signalized_movement_count"]) for row in queue_rows)),
        ),
        "unresolved_signalized_crash_coverage_pct": _safe_pct(
            int(sum(int(row["unresolved_signalized_crash_total"]) for row in queue_rows)),
            int(sum(int(row["matched_crashes_at_junction_total"]) for row in queue_rows)),
        ),
    }

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_resolution_bundle_version": SIGNAL_PHASE_SUPPORT_RESOLUTION_BUNDLE_VERSION,
        "signal_phase_support_resolution_contract_version": SIGNAL_PHASE_SUPPORT_RESOLUTION_BUNDLE_CONTRACT_VERSION,
        "summary": summary,
        "support_resolution_requests": queue_rows,
        "manual_arm_phase_review": manual_review_rows,
        "pedestrian_stage_review": pedestrian_review_rows,
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_markdown_report(summary=summary, queue_rows=queue_rows), encoding="utf-8")

    manifest = {
        "source": {
            "adapter": "bari_signal_phase_support_resolution_bundle_builder",
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "signal_phase_support_resolution_bundle_version": SIGNAL_PHASE_SUPPORT_RESOLUTION_BUNDLE_VERSION,
        "contract_version": SIGNAL_PHASE_SUPPORT_RESOLUTION_BUNDLE_CONTRACT_VERSION,
        "inputs": {
            "support_validation_manifest_paths": [str(path) for path in validation_manifest_files],
            "movement_review_path": str(movement_review_file),
            "phase_readiness_csv_path": str(phase_readiness_file) if phase_readiness_file.exists() else None,
            "movement_objects_path": str(movement_objects_file),
            "aggregate_path": str(aggregate_file),
            "top_n": int(top_n),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "support_resolution_queue_path": str(queue_csv_path),
            "support_resolution_queue_sha256": _sha256(queue_csv_path),
            "manual_arm_phase_review_path": str(manual_csv_path),
            "manual_arm_phase_review_sha256": _sha256(manual_csv_path),
            "pedestrian_stage_review_path": str(pedestrian_csv_path),
            "pedestrian_stage_review_sha256": _sha256(pedestrian_csv_path),
            "analyst_packet_paths": [str(path) for path in packet_paths],
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            *[
                _artifact_reference("signal_phase_delivery_validation", path, _sha256(path))
                for path in validation_manifest_files
            ],
            _artifact_reference("movement_review_report", movement_review_file, _sha256(movement_review_file)),
            *(
                [_artifact_reference("phase_readiness_csv", phase_readiness_file, _sha256(phase_readiness_file))]
                if phase_readiness_file.exists()
                else []
            ),
            _artifact_reference("movement_objects", movement_objects_file, _sha256(movement_objects_file)),
            _artifact_reference("movement_aggregate", aggregate_file, _sha256(aggregate_file)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_support_resolution_report", report_json_path, _sha256(report_json_path)),
            _artifact_reference("signal_phase_support_resolution_markdown", report_md_path, _sha256(report_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("support_resolution_queue_csv", queue_csv_path, _sha256(queue_csv_path)),
            _artifact_reference("manual_arm_phase_review_csv", manual_csv_path, _sha256(manual_csv_path)),
            _artifact_reference("pedestrian_stage_review_csv", pedestrian_csv_path, _sha256(pedestrian_csv_path)),
            *[_artifact_reference("support_resolution_packet", path, _sha256(path)) for path in packet_paths],
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
