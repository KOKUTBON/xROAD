"""Build Bari signal-phase coverage reports from movement-phase session outputs."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_COVERAGE_VERSION = "signal_phase_coverage_v1"
SIGNAL_PHASE_COVERAGE_CONTRACT_VERSION = "signal_phase_coverage_public_v1"
UNRESOLVED_MOVEMENT_STATES = {"ambiguous_target_variant", "turn_only_fallback"}


def _load_geo_stack() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import pandas as pd  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and pandas are required for signal-phase coverage reports. Install geospatial extras with: "
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
    return int(round(_safe_float(value)))


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100.0, 2)


def _is_unresolved_movement_state(value: Any) -> bool:
    state = _clean_text(value) or ""
    return state in UNRESOLVED_MOVEMENT_STATES


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _load_crash_counts(matched_records_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with matched_records_path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            node_object_id = _clean_text(row.get("node_object_id"))
            if not node_object_id:
                continue
            counts[node_object_id] = counts.get(node_object_id, 0) + 1
    return counts


def _load_target_requests(target_request_queue_path: Path | None) -> list[dict[str, Any]]:
    if target_request_queue_path is None or not target_request_queue_path.exists():
        return []
    with target_request_queue_path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _unique_catalog(values: list[Any]) -> str | None:
    cleaned = sorted({text for value in values if (text := _clean_text(value))})
    return " | ".join(cleaned) or None


def _coverage_by_role_rows(movements: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = movements.groupby(["movement_role", "control_state"], dropna=False, as_index=False)
    for _, frame in grouped:
        movement_role = _clean_text(frame["movement_role"].iloc[0]) or "unknown"
        control_state = _clean_text(frame["control_state"].iloc[0]) or "unknown"
        movement_count = int(len(frame))
        crash_count = int(frame["matched_crash_count"].sum())
        provider_count = int(frame["has_provider_data"].sum())
        timing_count = int(frame["has_phase_timing"].sum())
        mapping_count = int(frame["has_phase_mapping"].sum())
        any_phase_count = int(frame["has_any_phase_data"].sum())
        unresolved_count = int(frame["is_unresolved_movement"].sum())
        crashes_on_provider = int(frame.loc[frame["has_provider_data"], "matched_crash_count"].sum())
        crashes_on_timing = int(frame.loc[frame["has_phase_timing"], "matched_crash_count"].sum())
        crashes_on_mapping = int(frame.loc[frame["has_phase_mapping"], "matched_crash_count"].sum())
        crashes_on_any_phase = int(frame.loc[frame["has_any_phase_data"], "matched_crash_count"].sum())
        unresolved_crash_count = int(frame.loc[frame["is_unresolved_movement"], "matched_crash_count"].sum())
        rows.append(
            {
                "movement_role": movement_role,
                "control_state": control_state,
                "movement_count": movement_count,
                "matched_crash_count": crash_count,
                "movements_with_provider_data": provider_count,
                "movements_with_phase_timing": timing_count,
                "movements_with_phase_mapping": mapping_count,
                "movements_with_any_phase_data": any_phase_count,
                "unresolved_movement_count": unresolved_count,
                "provider_coverage_pct": _safe_pct(provider_count, movement_count),
                "timing_coverage_pct": _safe_pct(timing_count, movement_count),
                "mapping_coverage_pct": _safe_pct(mapping_count, movement_count),
                "any_phase_coverage_pct": _safe_pct(any_phase_count, movement_count),
                "unresolved_coverage_pct": _safe_pct(unresolved_count, movement_count),
                "crashes_on_provider_movements": crashes_on_provider,
                "crashes_on_timed_movements": crashes_on_timing,
                "crashes_on_mapped_movements": crashes_on_mapping,
                "crashes_on_any_phase_movements": crashes_on_any_phase,
                "unresolved_matched_crash_count": unresolved_crash_count,
                "provider_crash_coverage_pct": _safe_pct(crashes_on_provider, crash_count),
                "timing_crash_coverage_pct": _safe_pct(crashes_on_timing, crash_count),
                "mapping_crash_coverage_pct": _safe_pct(crashes_on_mapping, crash_count),
                "any_phase_crash_coverage_pct": _safe_pct(crashes_on_any_phase, crash_count),
                "unresolved_crash_coverage_pct": _safe_pct(unresolved_crash_count, crash_count),
                "phase_priority_groups_present": _unique_catalog(frame["phase_priority_group"].tolist()),
                "signal_priority_variants_present": _unique_catalog(frame["signal_priority_variant"].tolist()),
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item["matched_crash_count"]),
            -int(item["movement_count"]),
            str(item["movement_role"]),
            str(item["control_state"]),
        )
    )
    return rows


def _target_junction_coverage_rows(
    movements: Any,
    target_requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request in target_requests:
        junction_id = _clean_text(request.get("junction_id"))
        if not junction_id:
            continue
        subset = movements[movements["junction_id"] == junction_id].copy()
        signalized_subset = subset[subset["is_signalized"]].copy()
        movement_count = int(len(signalized_subset))
        crash_count = int(signalized_subset["matched_crash_count"].sum())
        provider_count = int(signalized_subset["has_provider_data"].sum())
        timing_count = int(signalized_subset["has_phase_timing"].sum())
        mapping_count = int(signalized_subset["has_phase_mapping"].sum())
        unresolved_count = int(signalized_subset["is_unresolved_movement"].sum())
        crashes_on_provider = int(signalized_subset.loc[signalized_subset["has_provider_data"], "matched_crash_count"].sum())
        crashes_on_timing = int(signalized_subset.loc[signalized_subset["has_phase_timing"], "matched_crash_count"].sum())
        crashes_on_mapping = int(signalized_subset.loc[signalized_subset["has_phase_mapping"], "matched_crash_count"].sum())
        unresolved_crash_count = int(signalized_subset.loc[signalized_subset["is_unresolved_movement"], "matched_crash_count"].sum())
        rows.append(
            {
                "request_id": _clean_text(request.get("request_id")),
                "junction_id": junction_id,
                "signal_name": _clean_text(request.get("signal_name")),
                "priority_rank": _safe_int(request.get("priority_rank")),
                "priority_band": _clean_text(request.get("priority_band")),
                "recommended_provider_profile": _clean_text(request.get("recommended_provider_profile")),
                "acquisition_status": _clean_text(request.get("acquisition_status")),
                "required_profiles": _clean_text(request.get("required_profiles")),
                "signalized_movement_count": movement_count,
                "matched_signalized_crash_count": crash_count,
                "movements_with_provider_data": provider_count,
                "movements_with_phase_timing": timing_count,
                "movements_with_phase_mapping": mapping_count,
                "unresolved_signalized_movement_count": unresolved_count,
                "movements_without_phase_timing": max(movement_count - timing_count, 0),
                "provider_coverage_pct": _safe_pct(provider_count, movement_count),
                "timing_coverage_pct": _safe_pct(timing_count, movement_count),
                "mapping_coverage_pct": _safe_pct(mapping_count, movement_count),
                "unresolved_coverage_pct": _safe_pct(unresolved_count, movement_count),
                "crashes_on_provider_movements": crashes_on_provider,
                "crashes_on_timed_movements": crashes_on_timing,
                "crashes_on_mapped_movements": crashes_on_mapping,
                "unresolved_signalized_crash_count": unresolved_crash_count,
                "crashes_without_phase_timing": max(crash_count - crashes_on_timing, 0),
                "timing_crash_coverage_pct": _safe_pct(crashes_on_timing, crash_count),
                "mapping_crash_coverage_pct": _safe_pct(crashes_on_mapping, crash_count),
                "unresolved_crash_coverage_pct": _safe_pct(unresolved_crash_count, crash_count),
                "phase_priority_groups_present": _unique_catalog(signalized_subset["phase_priority_group"].tolist()),
                "signal_priority_variants_present": _unique_catalog(signalized_subset["signal_priority_variant"].tolist()),
            }
        )
    rows.sort(
        key=lambda item: (
            int(item["priority_rank"]) if item["priority_rank"] else 999999,
            -int(item["matched_signalized_crash_count"]),
            str(item["junction_id"]),
        )
    )
    return rows


def _uncovered_signalized_hotspot_rows(
    movements: Any,
    *,
    target_requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    request_lookup = {
        _clean_text(row.get("junction_id")) or "": row
        for row in target_requests
        if _clean_text(row.get("junction_id"))
    }
    uncovered = movements[
        movements["is_signalized"] & (~movements["has_phase_timing"]) & (movements["matched_crash_count"] > 0)
    ].copy()
    rows: list[dict[str, Any]] = []
    for _, row in uncovered.iterrows():
        junction_id = _clean_text(row.get("junction_id"))
        request = request_lookup.get(junction_id or "", {})
        rows.append(
            {
                "junction_id": junction_id,
                "signal_name": _clean_text(request.get("signal_name")),
                "request_id": _clean_text(request.get("request_id")),
                "priority_rank": _safe_int(request.get("priority_rank")),
                "priority_band": _clean_text(request.get("priority_band")),
                "recommended_provider_profile": _clean_text(request.get("recommended_provider_profile")),
                "is_target_junction": 1 if request else 0,
                "node_object_id": _clean_text(row.get("node_object_id")),
                "movement_role": _clean_text(row.get("movement_role")),
                "movement_turn": _clean_text(row.get("movement_turn")),
                "movement_name": _clean_text(row.get("name")),
                "control_state": _clean_text(row.get("control_state")),
                "phase_priority_group": _clean_text(row.get("phase_priority_group")),
                "signal_priority_variant": _clean_text(row.get("signal_priority_variant")),
                "movement_resolution_state": _clean_text(row.get("movement_resolution_state")),
                "is_unresolved_movement": 1 if bool(row.get("is_unresolved_movement")) else 0,
                "movement_phase_mapping_available": _safe_int(row.get("has_phase_mapping")),
                "junction_phase_provider_available": _safe_int(row.get("has_provider_data")),
                "matched_crash_count": _safe_int(row.get("matched_crash_count")),
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item["matched_crash_count"]),
            int(item["priority_rank"]) if item["priority_rank"] else 999999,
            str(item["junction_id"]),
            str(item["node_object_id"]),
        )
    )
    return rows


def _markdown_summary(
    *,
    summary: dict[str, Any],
    target_rows: list[dict[str, Any]],
    uncovered_rows: list[dict[str, Any]],
    top_n: int,
) -> str:
    lines = [
        "# Bari Signal-Phase Coverage",
        "",
        f"As of {summary['generated_at_utc']}, the current Bari signal-phase sample session has been evaluated against the movement layer and matched Bari official crash records.",
        "",
        "## Summary",
        "",
        f"- total movements: `{summary['movement_count']}`",
        f"- signalized movements: `{summary['signalized_movement_count']}`",
        f"- signalized turn movements: `{summary['signalized_turn_movement_count']}`",
        f"- movements with provider data: `{summary['movements_with_provider_data']}`",
        f"- movements with phase timing: `{summary['movements_with_phase_timing']}`",
        f"- movements with phase mapping: `{summary['movements_with_phase_mapping']}`",
        f"- unresolved signalized movements: `{summary['unresolved_signalized_movement_count']}`",
        f"- matched crashes on all movements: `{summary['matched_crash_count']}`",
        f"- matched crashes on signalized movements: `{summary['matched_signalized_crash_count']}`",
        f"- matched crashes on unresolved signalized movements: `{summary['unresolved_signalized_crash_count']}`",
        f"- matched crashes on provider-covered movements: `{summary['matched_crashes_on_provider_movements']}`",
        f"- matched crashes on timed movements: `{summary['matched_crashes_on_timed_movements']}`",
        f"- matched crashes on mapped movements: `{summary['matched_crashes_on_mapped_movements']}`",
        f"- target junctions with provider data: `{summary['target_junctions_with_provider_data']} / {summary['target_junction_count']}`",
        f"- target junctions with phase timing: `{summary['target_junctions_with_phase_timing']} / {summary['target_junction_count']}`",
        f"- target junctions with phase mapping: `{summary['target_junctions_with_phase_mapping']} / {summary['target_junction_count']}`",
        "",
        "## Target Junction Coverage",
        "",
    ]
    for row in target_rows[:top_n]:
        label = row.get("signal_name") or row["junction_id"]
        lines.append(
            f"- `{label}`: `{row['matched_signalized_crash_count']}` matched signalized crashes, "
            f"`{row['movements_with_phase_timing']}/{row['signalized_movement_count']}` timed, "
            f"`{row['movements_with_phase_mapping']}/{row['signalized_movement_count']}` mapped"
        )
    lines.extend(["", "## Top Uncovered Signalized Hotspots", ""])
    for row in uncovered_rows[:top_n]:
        label = row.get("signal_name") or row.get("junction_id") or row.get("movement_name") or "unknown"
        lines.append(
            f"- `{label}` / `{row['movement_name']}`: `{row['matched_crash_count']}` crashes, "
            f"timing missing, mapping `{row['movement_phase_mapping_available']}`, provider `{row['junction_phase_provider_available']}`, "
            f"unresolved `{row['is_unresolved_movement']}`"
        )
    lines.append("")
    return "\n".join(lines)


def summarize_bari_signal_phase_coverage(
    *,
    movement_objects_path: str | Path,
    matched_records_path: str | Path,
    target_request_queue_path: str | Path | None = None,
) -> dict[str, Any]:
    gpd, pd = _load_geo_stack()

    movement_input = Path(movement_objects_path)
    matched_input = Path(matched_records_path)
    target_request_input = None
    if target_request_queue_path is not None and str(target_request_queue_path).lower() != "none":
        target_request_input = Path(target_request_queue_path)

    movements = gpd.read_file(movement_input)
    if movements.empty:
        raise RuntimeError(f"Movement-phase layer is empty: {movement_input}")
    if "node_object_id" not in movements.columns:
        raise RuntimeError(f"Movement-phase layer is missing required 'node_object_id': {movement_input}")

    movements["node_object_id"] = movements["node_object_id"].astype(str)
    movements["matched_crash_count"] = (
        movements["node_object_id"].map(_load_crash_counts(matched_input)).fillna(0).astype(int)
    )
    movements["movement_role"] = movements["movement_role"].map(lambda value: _clean_text(value) or "unknown")
    movements["control_state"] = movements["control_state"].map(lambda value: _clean_text(value) or "unknown")
    movements["junction_id"] = movements["junction_id"].map(_clean_text)
    if "movement_resolution_state" not in movements.columns:
        movements["movement_resolution_state"] = None
    movements["movement_resolution_state"] = movements["movement_resolution_state"].map(_clean_text)
    movements["is_unresolved_movement"] = movements["movement_resolution_state"].map(_is_unresolved_movement_state)
    for column in [
        "junction_phase_provider_available",
        "movement_phase_timing_available",
        "movement_phase_mapping_available",
    ]:
        if column not in movements.columns:
            movements[column] = 0.0
        movements[column] = pd.to_numeric(movements[column], errors="coerce").fillna(0.0)
    movements["has_provider_data"] = movements["junction_phase_provider_available"] > 0
    movements["has_phase_timing"] = movements["movement_phase_timing_available"] > 0
    movements["has_phase_mapping"] = movements["movement_phase_mapping_available"] > 0
    movements["has_any_phase_data"] = (
        movements["has_provider_data"] | movements["has_phase_timing"] | movements["has_phase_mapping"]
    )
    movements["is_signalized"] = movements["control_state"] == "signalized"
    movements["is_signalized_turn"] = movements["movement_role"] == "signalized_turn_movement"

    target_requests = _load_target_requests(target_request_input)
    coverage_by_role_rows = _coverage_by_role_rows(movements)
    target_rows = _target_junction_coverage_rows(movements, target_requests)
    uncovered_rows = _uncovered_signalized_hotspot_rows(movements, target_requests=target_requests)

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "movement_count": int(len(movements)),
        "signalized_movement_count": int(movements["is_signalized"].sum()),
        "signalized_turn_movement_count": int(movements["is_signalized_turn"].sum()),
        "movements_with_provider_data": int(movements["has_provider_data"].sum()),
        "movements_with_phase_timing": int(movements["has_phase_timing"].sum()),
        "movements_with_phase_mapping": int(movements["has_phase_mapping"].sum()),
        "unresolved_signalized_movement_count": int(
            movements.loc[movements["is_signalized"] & movements["is_unresolved_movement"], "node_object_id"].count()
        ),
        "matched_crash_count": int(movements["matched_crash_count"].sum()),
        "matched_signalized_crash_count": int(movements.loc[movements["is_signalized"], "matched_crash_count"].sum()),
        "unresolved_signalized_crash_count": int(
            movements.loc[movements["is_signalized"] & movements["is_unresolved_movement"], "matched_crash_count"].sum()
        ),
        "matched_signalized_turn_crash_count": int(
            movements.loc[movements["is_signalized_turn"], "matched_crash_count"].sum()
        ),
        "matched_crashes_on_provider_movements": int(
            movements.loc[movements["has_provider_data"], "matched_crash_count"].sum()
        ),
        "matched_crashes_on_timed_movements": int(
            movements.loc[movements["has_phase_timing"], "matched_crash_count"].sum()
        ),
        "matched_crashes_on_mapped_movements": int(
            movements.loc[movements["has_phase_mapping"], "matched_crash_count"].sum()
        ),
        "matched_signalized_crashes_on_timed_movements": int(
            movements.loc[movements["is_signalized"] & movements["has_phase_timing"], "matched_crash_count"].sum()
        ),
        "matched_signalized_crashes_on_mapped_movements": int(
            movements.loc[movements["is_signalized"] & movements["has_phase_mapping"], "matched_crash_count"].sum()
        ),
        "target_junction_count": int(len(target_rows)),
        "target_junctions_with_provider_data": int(
            sum(1 for row in target_rows if int(row["movements_with_provider_data"]) > 0)
        ),
        "target_junctions_with_phase_timing": int(
            sum(1 for row in target_rows if int(row["movements_with_phase_timing"]) > 0)
        ),
        "target_junctions_with_phase_mapping": int(
            sum(1 for row in target_rows if int(row["movements_with_phase_mapping"]) > 0)
        ),
        "uncovered_signalized_hotspot_count": int(len(uncovered_rows)),
    }

    return {
        "inputs": {
            "movement_objects_path": str(movement_input),
            "matched_records_path": str(matched_input),
            "target_request_queue_path": str(target_request_input) if target_request_input else None,
        },
        "summary": summary,
        "coverage_by_role_rows": coverage_by_role_rows,
        "target_junction_rows": target_rows,
        "uncovered_signalized_hotspot_rows": uncovered_rows,
    }


def build_bari_signal_phase_coverage_report(
    output_dir: str | Path,
    *,
    movement_objects_path: str | Path = "data/processed/signal_phase_delivery_sessions/bari_sample/movement_layer/road_movement_objects_signal_phase.geojson",
    matched_records_path: str | Path = "data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    target_request_queue_path: str | Path | None = "data/planning/signal_phase_outreach/bari/target_request_queue.csv",
    delivery_session_manifest_path: str | Path | None = "data/processed/signal_phase_delivery_sessions/bari_sample/signal_phase_delivery_session.manifest.json",
    top_n: int = 20,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    coverage = summarize_bari_signal_phase_coverage(
        movement_objects_path=movement_objects_path,
        matched_records_path=matched_records_path,
        target_request_queue_path=target_request_queue_path,
    )
    movement_input = Path(coverage["inputs"]["movement_objects_path"])
    matched_input = Path(coverage["inputs"]["matched_records_path"])
    target_request_input = (
        Path(coverage["inputs"]["target_request_queue_path"])
        if coverage["inputs"]["target_request_queue_path"]
        else None
    )
    delivery_session_input = None
    if delivery_session_manifest_path is not None and str(delivery_session_manifest_path).lower() != "none":
        delivery_session_input = Path(delivery_session_manifest_path)
    summary = dict(coverage["summary"])
    coverage_by_role_rows = coverage["coverage_by_role_rows"]
    target_rows = coverage["target_junction_rows"]
    uncovered_rows = coverage["uncovered_signalized_hotspot_rows"]

    report_json_path = output_root / "signal_phase_coverage.json"
    report_md_path = output_root / "signal_phase_coverage.md"
    coverage_by_role_path = output_root / "coverage_by_role.csv"
    target_junction_coverage_path = output_root / "target_junction_coverage.csv"
    uncovered_hotspots_path = output_root / "uncovered_signalized_hotspots.csv"
    manifest_path = output_root / "signal_phase_coverage.manifest.json"

    _write_csv(coverage_by_role_path, coverage_by_role_rows)
    _write_csv(target_junction_coverage_path, target_rows)
    _write_csv(uncovered_hotspots_path, uncovered_rows)

    payload = {
        "signal_phase_coverage_version": SIGNAL_PHASE_COVERAGE_VERSION,
        "signal_phase_coverage_contract_version": SIGNAL_PHASE_COVERAGE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "top_role_rows": coverage_by_role_rows[:top_n],
        "target_junction_coverage": target_rows[:top_n],
        "top_uncovered_signalized_hotspots": uncovered_rows[:top_n],
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(
        _markdown_summary(
            summary=summary,
            target_rows=target_rows,
            uncovered_rows=uncovered_rows,
            top_n=top_n,
        ),
        encoding="utf-8",
    )

    upstream_inputs = [
        _artifact_reference("movement_signal_phase_layer", movement_input, _sha256(movement_input)),
        _artifact_reference("matched_movement_records", matched_input, _sha256(matched_input)),
    ]
    if target_request_input and target_request_input.exists():
        upstream_inputs.append(
            _artifact_reference("signal_phase_outreach_target_queue", target_request_input, _sha256(target_request_input))
        )
    if delivery_session_input and delivery_session_input.exists():
        upstream_inputs.append(
            _artifact_reference("signal_phase_delivery_session", delivery_session_input, _sha256(delivery_session_input))
        )

    manifest = {
        "signal_phase_coverage_version": SIGNAL_PHASE_COVERAGE_VERSION,
        "contract": {
            "resource_name": "signal_phase_coverage_report",
            "public_contract_version": SIGNAL_PHASE_COVERAGE_CONTRACT_VERSION,
            "signal_phase_coverage_version": SIGNAL_PHASE_COVERAGE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_coverage_builder",
        },
        "inputs": {
            "movement_objects_path": str(movement_input),
            "matched_records_path": str(matched_input),
            "target_request_queue_path": str(target_request_input) if target_request_input else None,
            "delivery_session_manifest_path": str(delivery_session_input) if delivery_session_input else None,
            "top_n": int(top_n),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "coverage_by_role_path": str(coverage_by_role_path),
            "coverage_by_role_sha256": _sha256(coverage_by_role_path),
            "target_junction_coverage_path": str(target_junction_coverage_path),
            "target_junction_coverage_sha256": _sha256(target_junction_coverage_path),
            "uncovered_signalized_hotspots_path": str(uncovered_hotspots_path),
            "uncovered_signalized_hotspots_sha256": _sha256(uncovered_hotspots_path),
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=upstream_inputs,
        publishable_outputs=[
            _artifact_reference("signal_phase_coverage_report", report_json_path, _sha256(report_json_path)),
            _artifact_reference("signal_phase_coverage_markdown", report_md_path, _sha256(report_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_coverage_by_role_csv", coverage_by_role_path, _sha256(coverage_by_role_path)),
            _artifact_reference(
                "signal_phase_target_junction_coverage_csv",
                target_junction_coverage_path,
                _sha256(target_junction_coverage_path),
            ),
            _artifact_reference(
                "signal_phase_uncovered_hotspots_csv",
                uncovered_hotspots_path,
                _sha256(uncovered_hotspots_path),
            ),
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_coverage_version": SIGNAL_PHASE_COVERAGE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
