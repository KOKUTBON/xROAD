"""Build review packs for movement-resolution and phase-readiness follow-up."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


MOVEMENT_REVIEW_VERSION = "movement_review_v1"


def _load_geo_stack() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import pandas as pd  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and pandas are required for movement review builds. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, pd


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    return int(_safe_float(value))


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


def _load_matched_lookup(matched_jsonl_path: Path) -> tuple[dict[str, int], dict[str, int]]:
    crashes_by_junction: dict[str, int] = {}
    crashes_by_movement: dict[str, int] = {}
    with matched_jsonl_path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            node_object_id = _clean_text(row.get("node_object_id"))
            junction_id = _clean_text(row.get("junction_id"))
            if node_object_id:
                crashes_by_movement[node_object_id] = crashes_by_movement.get(node_object_id, 0) + 1
            if junction_id:
                crashes_by_junction[junction_id] = crashes_by_junction.get(junction_id, 0) + 1
    return crashes_by_junction, crashes_by_movement


def _priority_score(*, total_crashes: int, candidate_target_arm_count: int, movement_role: str, movement_turn: str) -> int:
    score = total_crashes * 100
    score += candidate_target_arm_count * 10
    if movement_role == "signalized_turn_movement":
        score += 25
    if movement_turn in {"left", "u_turn"}:
        score += 10
    return score


def _build_unresolved_rows(
    movements: Any,
    *,
    aggregate_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    unresolved_rows: list[dict[str, Any]] = []
    unresolved_states = {"ambiguous_target_variant", "turn_only_fallback"}
    for _, row in movements.iterrows():
        movement_id = _clean_text(row.get("node_object_id"))
        resolution_state = _clean_text(row.get("movement_resolution_state")) or "unknown"
        if not movement_id or resolution_state not in unresolved_states:
            continue
        aggregate = aggregate_lookup.get(movement_id, {})
        total_crashes = _safe_int(aggregate.get("total_crashes"))
        unresolved_rows.append(
            {
                "node_object_id": movement_id,
                "junction_id": _clean_text(row.get("junction_id")),
                "name": _clean_text(row.get("name")),
                "movement_role": _clean_text(row.get("movement_role")),
                "movement_turn": _clean_text(row.get("movement_turn")),
                "movement_resolution_state": resolution_state,
                "movement_resolution_method": _clean_text(row.get("movement_resolution_method")),
                "candidate_target_arm_count": _safe_int(row.get("candidate_target_arm_count")),
                "candidate_target_arm_catalog": _clean_text(row.get("candidate_target_arm_catalog")),
                "phase_priority_group": _clean_text(row.get("phase_priority_group")),
                "signal_priority_variant": _clean_text(row.get("signal_priority_variant")),
                "control_state": _clean_text(row.get("control_state")),
                "segment_name": _clean_text(row.get("segment_name")),
                "segment_ref": _clean_text(row.get("segment_ref")),
                "total_crashes": total_crashes,
                "total_injuries": _safe_int(aggregate.get("total_injuries")),
                "peak_year": aggregate.get("peak_year"),
                "peak_year_crash_count": _safe_int(aggregate.get("peak_year_crash_count")),
                "review_priority_score": _priority_score(
                    total_crashes=total_crashes,
                    candidate_target_arm_count=_safe_int(row.get("candidate_target_arm_count")),
                    movement_role=_clean_text(row.get("movement_role")) or "",
                    movement_turn=_clean_text(row.get("movement_turn")) or "",
                ),
            }
        )
    unresolved_rows.sort(
        key=lambda item: (
            -int(item["review_priority_score"]),
            -int(item["total_crashes"]),
            str(item["node_object_id"]),
        )
    )
    return unresolved_rows


def _build_heuristic_rows(
    movements: Any,
    *,
    aggregate_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    heuristic_rows: list[dict[str, Any]] = []
    for _, row in movements.iterrows():
        movement_id = _clean_text(row.get("node_object_id"))
        if not movement_id:
            continue
        resolution_state = _clean_text(row.get("movement_resolution_state"))
        if resolution_state != "heuristic_target_resolution":
            continue
        aggregate = aggregate_lookup.get(movement_id, {})
        heuristic_rows.append(
            {
                "node_object_id": movement_id,
                "junction_id": _clean_text(row.get("junction_id")),
                "name": _clean_text(row.get("name")),
                "movement_role": _clean_text(row.get("movement_role")),
                "movement_turn": _clean_text(row.get("movement_turn")),
                "movement_resolution_method": _clean_text(row.get("movement_resolution_method")),
                "candidate_target_arm_count": _safe_int(row.get("candidate_target_arm_count")),
                "candidate_target_arm_catalog": _clean_text(row.get("candidate_target_arm_catalog")),
                "movement_target_rank": _safe_int(row.get("movement_target_rank")),
                "movement_target_score": round(_safe_float(row.get("movement_target_score")), 3),
                "movement_target_heading_delta_deg": round(
                    _safe_float(row.get("movement_target_heading_delta_deg")),
                    3,
                ),
                "movement_target_continuity_flags": _clean_text(row.get("movement_target_continuity_flags")),
                "phase_priority_group": _clean_text(row.get("phase_priority_group")),
                "total_crashes": _safe_int(aggregate.get("total_crashes")),
                "peak_year": aggregate.get("peak_year"),
                "peak_year_crash_count": _safe_int(aggregate.get("peak_year_crash_count")),
            }
        )
    heuristic_rows.sort(
        key=lambda item: (
            -int(item["total_crashes"]),
            -float(item["movement_target_score"]),
            str(item["node_object_id"]),
        )
    )
    return heuristic_rows


def _signal_node_lookup(signal_nodes_path: Path | None) -> dict[str, dict[str, Any]]:
    if signal_nodes_path is None or not signal_nodes_path.exists():
        return {}
    gpd, _pd = _load_geo_stack()
    frame = gpd.read_file(signal_nodes_path)
    lookup: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        node_object_id = _clean_text(row.get("node_object_id"))
        if not node_object_id:
            continue
        lookup[node_object_id] = {
            "signal_name": _clean_text(row.get("name")),
            "signal_type": _clean_text(row.get("signal_type")),
        }
    return lookup


def _build_phase_rows(
    movements: Any,
    *,
    aggregate_lookup: dict[str, dict[str, Any]],
    crashes_by_junction: dict[str, int],
    signal_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for _, row in movements.iterrows():
        movement_role = _clean_text(row.get("movement_role")) or ""
        phase_group = _clean_text(row.get("phase_priority_group")) or ""
        if movement_role != "signalized_turn_movement" and phase_group != "signalized_pedestrian_stage":
            continue
        junction_id = _clean_text(row.get("junction_id"))
        if not junction_id:
            continue
        movement_id = _clean_text(row.get("node_object_id")) or ""
        aggregate = aggregate_lookup.get(movement_id, {})
        entry = grouped.setdefault(
            junction_id,
            {
                "junction_id": junction_id,
                "signal_name": signal_lookup.get(junction_id, {}).get("signal_name"),
                "signal_type": signal_lookup.get(junction_id, {}).get("signal_type"),
                "signalized_movement_count": 0,
                "ambiguous_movement_count": 0,
                "heuristic_resolved_movement_count": 0,
                "signalized_crash_total": 0,
                "ambiguous_crash_total": 0,
                "heuristic_resolved_crash_total": 0,
                "phase_priority_groups_present": set(),
                "timing_data_status": "missing_from_current_sources",
                "recommended_next_input": "controller timing plan, phase table, or stage log export",
            },
        )
        entry["signalized_movement_count"] += 1
        total_crashes = _safe_int(aggregate.get("total_crashes"))
        entry["signalized_crash_total"] += total_crashes
        entry["phase_priority_groups_present"].add(phase_group)
        resolution_state = _clean_text(row.get("movement_resolution_state"))
        if resolution_state == "ambiguous_target_variant":
            entry["ambiguous_movement_count"] += 1
            entry["ambiguous_crash_total"] += total_crashes
        elif resolution_state == "heuristic_target_resolution":
            entry["heuristic_resolved_movement_count"] += 1
            entry["heuristic_resolved_crash_total"] += total_crashes

    phase_rows: list[dict[str, Any]] = []
    for junction_id, entry in grouped.items():
        phase_groups = sorted(group for group in entry["phase_priority_groups_present"] if group)
        review_priority_score = (
            int(entry["signalized_crash_total"]) * 100
            + int(entry["ambiguous_crash_total"]) * 20
            + int(entry["signalized_movement_count"])
        )
        phase_rows.append(
            {
                "junction_id": junction_id,
                "signal_name": entry["signal_name"],
                "signal_type": entry["signal_type"],
                "signalized_movement_count": int(entry["signalized_movement_count"]),
                "ambiguous_movement_count": int(entry["ambiguous_movement_count"]),
                "heuristic_resolved_movement_count": int(entry["heuristic_resolved_movement_count"]),
                "signalized_crash_total": int(entry["signalized_crash_total"]),
                "ambiguous_crash_total": int(entry["ambiguous_crash_total"]),
                "heuristic_resolved_crash_total": int(entry["heuristic_resolved_crash_total"]),
                "matched_crashes_at_junction_total": int(crashes_by_junction.get(junction_id, 0)),
                "phase_priority_groups_present": " | ".join(phase_groups) or None,
                "timing_data_status": entry["timing_data_status"],
                "recommended_next_input": entry["recommended_next_input"],
                "review_priority_score": review_priority_score,
            }
        )
    phase_rows.sort(
        key=lambda item: (
            -int(item["review_priority_score"]),
            -int(item["signalized_crash_total"]),
            str(item["junction_id"]),
        )
    )
    return phase_rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _markdown_summary(
    *,
    unresolved_rows: list[dict[str, Any]],
    heuristic_rows: list[dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    top_n: int,
) -> str:
    lines = [
        "# Bari Movement Review Pack",
        "",
        "## Unresolved Target Review",
        "",
        f"- unresolved movements: `{len(unresolved_rows)}`",
        f"- heuristically resolved movements: `{len(heuristic_rows)}`",
        f"- signalized junctions needing timing data: `{len(phase_rows)}`",
        "",
        "## Top Unresolved Movements",
        "",
    ]
    for row in unresolved_rows[:top_n]:
        lines.append(
            f"- `{row['node_object_id']}`: `{row['movement_role']}` `{row['movement_turn']}`, "
            f"{row['total_crashes']} crashes, `{row['candidate_target_arm_count']}` candidates"
        )
    lines.extend(["", "## Top Heuristic Resolutions", ""])
    for row in heuristic_rows[:top_n]:
        lines.append(
            f"- `{row['node_object_id']}`: `{row['movement_role']}` `{row['movement_turn']}`, "
            f"score `{row['movement_target_score']}`, heading delta `{row['movement_target_heading_delta_deg']}`"
        )
    lines.extend(["", "## Signal Phase Readiness", ""])
    for row in phase_rows[:top_n]:
        label = row.get("signal_name") or row["junction_id"]
        lines.append(
            f"- `{label}`: `{row['signalized_crash_total']}` signalized-movement crashes, "
            f"`{row['ambiguous_movement_count']}` ambiguous movements, status `{row['timing_data_status']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_movement_review_pack(
    output_dir: str | Path,
    *,
    movement_objects_path: str | Path = "data/processed/movement_objects/bari/road_movement_objects.geojson",
    matched_records_path: str | Path = "data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    aggregate_path: str | Path = "data/processed/node_aggregates/bari_open_data_movements/node_year_metrics.csv",
    signal_nodes_path: str | Path | None = "data/processed/node_objects/bari_signals/traffic_signal_nodes.geojson",
    top_n: int = 20,
) -> dict[str, Any]:
    gpd, _pd = _load_geo_stack()

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    movement_objects_input = Path(movement_objects_path)
    matched_records_input = Path(matched_records_path)
    aggregate_input = Path(aggregate_path)
    signal_nodes_input = Path(signal_nodes_path) if signal_nodes_path is not None else None

    movements = gpd.read_file(movement_objects_input)
    if movements.empty:
        raise RuntimeError(f"Movement-object input is empty: {movement_objects_input}")

    aggregate_lookup = _load_aggregate_lookup(aggregate_input)
    crashes_by_junction, _crashes_by_movement = _load_matched_lookup(matched_records_input)
    signal_lookup = _signal_node_lookup(signal_nodes_input)

    unresolved_rows = _build_unresolved_rows(movements, aggregate_lookup=aggregate_lookup)
    heuristic_rows = _build_heuristic_rows(movements, aggregate_lookup=aggregate_lookup)
    phase_rows = _build_phase_rows(
        movements,
        aggregate_lookup=aggregate_lookup,
        crashes_by_junction=crashes_by_junction,
        signal_lookup=signal_lookup,
    )

    unresolved_csv_path = output_root / "unresolved_target_review.csv"
    heuristic_csv_path = output_root / "heuristic_target_review.csv"
    phase_csv_path = output_root / "signal_phase_readiness.csv"
    review_json_path = output_root / "movement_review_pack.json"
    review_md_path = output_root / "movement_review_pack.md"
    manifest_path = output_root / "movement_review_pack.manifest.json"

    _write_csv(unresolved_csv_path, unresolved_rows)
    _write_csv(heuristic_csv_path, heuristic_rows)
    _write_csv(phase_csv_path, phase_rows)

    payload = {
        "movement_review_version": MOVEMENT_REVIEW_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "summary": {
            "movement_object_count": int(len(movements)),
            "unresolved_movement_count": int(len(unresolved_rows)),
            "heuristic_resolved_movement_count": int(len(heuristic_rows)),
            "signal_phase_review_row_count": int(len(phase_rows)),
            "unresolved_crash_total": int(sum(int(row["total_crashes"]) for row in unresolved_rows)),
            "heuristic_resolved_crash_total": int(sum(int(row["total_crashes"]) for row in heuristic_rows)),
        },
        "top_unresolved_movements": unresolved_rows[:top_n],
        "top_heuristic_resolutions": heuristic_rows[:top_n],
        "signal_phase_readiness": phase_rows[:top_n],
    }
    review_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    review_md_path.write_text(
        _markdown_summary(
            unresolved_rows=unresolved_rows,
            heuristic_rows=heuristic_rows,
            phase_rows=phase_rows,
            top_n=top_n,
        ),
        encoding="utf-8",
    )

    manifest = {
        "source": {
            "adapter": "bari_movement_review_builder",
            "movement_objects_source_path": str(movement_objects_input),
            "movement_objects_source_sha256": _sha256(movement_objects_input),
            "matched_records_source_path": str(matched_records_input),
            "matched_records_source_sha256": _sha256(matched_records_input),
            "aggregate_source_path": str(aggregate_input),
            "aggregate_source_sha256": _sha256(aggregate_input),
            "signal_nodes_source_path": str(signal_nodes_input) if signal_nodes_input else None,
            "signal_nodes_source_sha256": _sha256(signal_nodes_input) if signal_nodes_input and signal_nodes_input.exists() else None,
        },
        "inputs": {
            "movement_objects_path": str(movement_objects_input),
            "matched_records_path": str(matched_records_input),
            "aggregate_path": str(aggregate_input),
            "signal_nodes_path": str(signal_nodes_input) if signal_nodes_input else None,
            "top_n": int(top_n),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(review_json_path),
            "report_json_sha256": _sha256(review_json_path),
            "report_md_path": str(review_md_path),
            "report_md_sha256": _sha256(review_md_path),
            "unresolved_review_path": str(unresolved_csv_path),
            "unresolved_review_sha256": _sha256(unresolved_csv_path),
            "heuristic_review_path": str(heuristic_csv_path),
            "heuristic_review_sha256": _sha256(heuristic_csv_path),
            "phase_readiness_path": str(phase_csv_path),
            "phase_readiness_sha256": _sha256(phase_csv_path),
        },
        "stats": payload["summary"],
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("movement_objects", movement_objects_input, _sha256(movement_objects_input)),
            _artifact_reference("matched_records", matched_records_input, _sha256(matched_records_input)),
            _artifact_reference("movement_aggregate", aggregate_input, _sha256(aggregate_input)),
        ]
        + (
            [_artifact_reference("signal_nodes", signal_nodes_input, _sha256(signal_nodes_input))]
            if signal_nodes_input and signal_nodes_input.exists()
            else []
        ),
        publishable_outputs=[
            _artifact_reference("movement_review_report", review_json_path, _sha256(review_json_path)),
            _artifact_reference("movement_review_markdown", review_md_path, _sha256(review_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("unresolved_review_csv", unresolved_csv_path, _sha256(unresolved_csv_path)),
            _artifact_reference("heuristic_review_csv", heuristic_csv_path, _sha256(heuristic_csv_path)),
            _artifact_reference("phase_readiness_csv", phase_csv_path, _sha256(phase_csv_path)),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
