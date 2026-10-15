"""Compare movement-phase coverage before and after a validated delivery session."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_coverage import summarize_bari_signal_phase_coverage


SIGNAL_PHASE_DELIVERY_UPLIFT_VERSION = "signal_phase_delivery_uplift_v1"
SIGNAL_PHASE_DELIVERY_UPLIFT_CONTRACT_VERSION = "signal_phase_delivery_uplift_public_v1"

_COMPARISON_METRICS: tuple[tuple[str, str], ...] = (
    ("movements_with_provider_data", "Movements with provider data"),
    ("movements_with_phase_timing", "Movements with phase timing"),
    ("movements_with_phase_mapping", "Movements with phase mapping"),
    ("matched_crashes_on_provider_movements", "Matched crashes on provider movements"),
    ("matched_crashes_on_timed_movements", "Matched crashes on timed movements"),
    ("matched_crashes_on_mapped_movements", "Matched crashes on mapped movements"),
    (
        "matched_signalized_crashes_on_timed_movements",
        "Matched signalized crashes on timed movements",
    ),
    (
        "matched_signalized_crashes_on_mapped_movements",
        "Matched signalized crashes on mapped movements",
    ),
    ("target_junctions_with_provider_data", "Target junctions with provider data"),
    ("target_junctions_with_phase_timing", "Target junctions with phase timing"),
    ("target_junctions_with_phase_mapping", "Target junctions with phase mapping"),
    ("unresolved_signalized_movement_count", "Unresolved signalized movements"),
    ("unresolved_signalized_crash_count", "Unresolved signalized crashes"),
    ("uncovered_signalized_hotspot_count", "Uncovered signalized hotspots"),
)


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _metric_comparison_rows(
    *,
    pre_summary: dict[str, Any],
    post_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric_key, label in _COMPARISON_METRICS:
        before_value = _safe_int(pre_summary.get(metric_key))
        after_value = _safe_int(post_summary.get(metric_key))
        rows.append(
            {
                "metric_key": metric_key,
                "metric_label": label,
                "before_value": before_value,
                "after_value": after_value,
                "absolute_delta": after_value - before_value,
            }
        )
    return rows


def _target_key(row: dict[str, Any]) -> str:
    request_id = _clean_text(row.get("request_id"))
    junction_id = _clean_text(row.get("junction_id"))
    return request_id or junction_id or "unknown_target"


def _target_junction_uplift_rows(
    *,
    pre_rows: list[dict[str, Any]],
    post_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pre_lookup = {_target_key(row): row for row in pre_rows}
    post_lookup = {_target_key(row): row for row in post_rows}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(pre_lookup) | set(post_lookup)):
        before = pre_lookup.get(key, {})
        after = post_lookup.get(key, {})
        before_timing = _safe_int(before.get("movements_with_phase_timing"))
        after_timing = _safe_int(after.get("movements_with_phase_timing"))
        before_mapping = _safe_int(before.get("movements_with_phase_mapping"))
        after_mapping = _safe_int(after.get("movements_with_phase_mapping"))
        before_unresolved_crashes = _safe_int(before.get("unresolved_signalized_crash_count"))
        after_unresolved_crashes = _safe_int(after.get("unresolved_signalized_crash_count"))
        rows.append(
            {
                "comparison_key": key,
                "request_id": _clean_text(after.get("request_id")) or _clean_text(before.get("request_id")),
                "junction_id": _clean_text(after.get("junction_id")) or _clean_text(before.get("junction_id")),
                "signal_name": _clean_text(after.get("signal_name")) or _clean_text(before.get("signal_name")),
                "priority_rank": _safe_int(after.get("priority_rank") or before.get("priority_rank")),
                "matched_signalized_crash_count_before": _safe_int(before.get("matched_signalized_crash_count")),
                "matched_signalized_crash_count_after": _safe_int(after.get("matched_signalized_crash_count")),
                "movements_with_provider_data_before": _safe_int(before.get("movements_with_provider_data")),
                "movements_with_provider_data_after": _safe_int(after.get("movements_with_provider_data")),
                "movements_with_phase_timing_before": before_timing,
                "movements_with_phase_timing_after": after_timing,
                "movements_with_phase_timing_delta": after_timing - before_timing,
                "movements_with_phase_mapping_before": before_mapping,
                "movements_with_phase_mapping_after": after_mapping,
                "movements_with_phase_mapping_delta": after_mapping - before_mapping,
                "timing_crash_coverage_pct_before": round(
                    _safe_float(before.get("timing_crash_coverage_pct")), 2
                ),
                "timing_crash_coverage_pct_after": round(
                    _safe_float(after.get("timing_crash_coverage_pct")), 2
                ),
                "timing_crash_coverage_pct_delta": round(
                    _safe_float(after.get("timing_crash_coverage_pct"))
                    - _safe_float(before.get("timing_crash_coverage_pct")),
                    2,
                ),
                "mapping_crash_coverage_pct_before": round(
                    _safe_float(before.get("mapping_crash_coverage_pct")), 2
                ),
                "mapping_crash_coverage_pct_after": round(
                    _safe_float(after.get("mapping_crash_coverage_pct")), 2
                ),
                "mapping_crash_coverage_pct_delta": round(
                    _safe_float(after.get("mapping_crash_coverage_pct"))
                    - _safe_float(before.get("mapping_crash_coverage_pct")),
                    2,
                ),
                "unresolved_signalized_crash_count_before": before_unresolved_crashes,
                "unresolved_signalized_crash_count_after": after_unresolved_crashes,
                "unresolved_signalized_crash_count_delta": after_unresolved_crashes
                - before_unresolved_crashes,
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item["movements_with_phase_mapping_delta"]),
            -int(item["movements_with_phase_timing_delta"]),
            -float(item["mapping_crash_coverage_pct_delta"]),
            int(item["priority_rank"]) if int(item["priority_rank"]) > 0 else 999999,
            str(item["comparison_key"]),
        )
    )
    return rows


def _markdown_summary(
    *,
    payload: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
) -> str:
    stats = payload["stats"]
    lines = [
        "# Signal-Phase Delivery Uplift",
        "",
        f"As of {payload['generated_at_utc']}, the validated delivery session has been compared against the pre-session movement-phase baseline.",
        "",
        "## Summary",
        "",
        f"- movements with provider data: `{stats['movements_with_provider_data_before']} -> {stats['movements_with_provider_data_after']}`",
        f"- movements with phase timing: `{stats['movements_with_phase_timing_before']} -> {stats['movements_with_phase_timing_after']}`",
        f"- movements with phase mapping: `{stats['movements_with_phase_mapping_before']} -> {stats['movements_with_phase_mapping_after']}`",
        f"- matched signalized crashes on timed movements: `{stats['matched_signalized_crashes_on_timed_movements_before']} -> {stats['matched_signalized_crashes_on_timed_movements_after']}`",
        f"- matched signalized crashes on mapped movements: `{stats['matched_signalized_crashes_on_mapped_movements_before']} -> {stats['matched_signalized_crashes_on_mapped_movements_after']}`",
        f"- unresolved signalized crashes: `{stats['unresolved_signalized_crash_count_before']} -> {stats['unresolved_signalized_crash_count_after']}`",
        f"- uncovered signalized hotspots: `{stats['uncovered_signalized_hotspot_count_before']} -> {stats['uncovered_signalized_hotspot_count_after']}`",
        "",
        "## Metric Deltas",
        "",
    ]
    for row in comparison_rows:
        lines.append(
            f"- `{row['metric_label']}`: `{row['before_value']} -> {row['after_value']}` "
            f"(delta `{row['absolute_delta']}`)"
        )
    if target_rows:
        lines.extend(["", "## Target Junction Uplift", ""])
        for row in target_rows[:10]:
            label = row.get("signal_name") or row.get("junction_id") or row["comparison_key"]
            lines.append(
                f"- `{label}`: timed `{row['movements_with_phase_timing_before']} -> {row['movements_with_phase_timing_after']}`, "
                f"mapped `{row['movements_with_phase_mapping_before']} -> {row['movements_with_phase_mapping_after']}`, "
                f"unresolved crashes `{row['unresolved_signalized_crash_count_before']} -> {row['unresolved_signalized_crash_count_after']}`"
            )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_delivery_uplift_report(
    output_dir: str | Path,
    *,
    baseline_movement_objects_path: str | Path,
    updated_movement_objects_path: str | Path,
    matched_records_path: str | Path,
    target_request_queue_path: str | Path | None = "data/planning/signal_phase_outreach/bari/target_request_queue.csv",
    delivery_session_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    baseline_input = Path(baseline_movement_objects_path)
    updated_input = Path(updated_movement_objects_path)
    matched_input = Path(matched_records_path)
    target_request_input = None
    if target_request_queue_path is not None and str(target_request_queue_path).lower() != "none":
        target_request_input = Path(target_request_queue_path)
    delivery_session_input = None
    if delivery_session_manifest_path is not None and str(delivery_session_manifest_path).lower() != "none":
        delivery_session_input = Path(delivery_session_manifest_path)

    baseline = summarize_bari_signal_phase_coverage(
        movement_objects_path=baseline_input,
        matched_records_path=matched_input,
        target_request_queue_path=target_request_input,
    )
    updated = summarize_bari_signal_phase_coverage(
        movement_objects_path=updated_input,
        matched_records_path=matched_input,
        target_request_queue_path=target_request_input,
    )

    comparison_rows = _metric_comparison_rows(
        pre_summary=baseline["summary"],
        post_summary=updated["summary"],
    )
    target_rows = _target_junction_uplift_rows(
        pre_rows=baseline["target_junction_rows"],
        post_rows=updated["target_junction_rows"],
    )

    comparison_path = output_root / "coverage_metric_comparison.csv"
    target_path = output_root / "target_junction_uplift.csv"
    report_json_path = output_root / "signal_phase_delivery_uplift.json"
    report_md_path = output_root / "signal_phase_delivery_uplift.md"
    manifest_path = output_root / "signal_phase_delivery_uplift.manifest.json"

    _write_csv(comparison_path, comparison_rows)
    _write_csv(target_path, target_rows)

    stats = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "movements_with_provider_data_before": _safe_int(
            baseline["summary"].get("movements_with_provider_data")
        ),
        "movements_with_provider_data_after": _safe_int(
            updated["summary"].get("movements_with_provider_data")
        ),
        "movements_with_phase_timing_before": _safe_int(
            baseline["summary"].get("movements_with_phase_timing")
        ),
        "movements_with_phase_timing_after": _safe_int(
            updated["summary"].get("movements_with_phase_timing")
        ),
        "movements_with_phase_mapping_before": _safe_int(
            baseline["summary"].get("movements_with_phase_mapping")
        ),
        "movements_with_phase_mapping_after": _safe_int(
            updated["summary"].get("movements_with_phase_mapping")
        ),
        "matched_signalized_crashes_on_timed_movements_before": _safe_int(
            baseline["summary"].get("matched_signalized_crashes_on_timed_movements")
        ),
        "matched_signalized_crashes_on_timed_movements_after": _safe_int(
            updated["summary"].get("matched_signalized_crashes_on_timed_movements")
        ),
        "matched_signalized_crashes_on_mapped_movements_before": _safe_int(
            baseline["summary"].get("matched_signalized_crashes_on_mapped_movements")
        ),
        "matched_signalized_crashes_on_mapped_movements_after": _safe_int(
            updated["summary"].get("matched_signalized_crashes_on_mapped_movements")
        ),
        "unresolved_signalized_crash_count_before": _safe_int(
            baseline["summary"].get("unresolved_signalized_crash_count")
        ),
        "unresolved_signalized_crash_count_after": _safe_int(
            updated["summary"].get("unresolved_signalized_crash_count")
        ),
        "uncovered_signalized_hotspot_count_before": _safe_int(
            baseline["summary"].get("uncovered_signalized_hotspot_count")
        ),
        "uncovered_signalized_hotspot_count_after": _safe_int(
            updated["summary"].get("uncovered_signalized_hotspot_count")
        ),
        "target_junction_count": len(target_rows),
        "improved_target_junction_count": sum(
            1
            for row in target_rows
            if int(row["movements_with_phase_timing_delta"]) > 0
            or int(row["movements_with_phase_mapping_delta"]) > 0
            or int(row["unresolved_signalized_crash_count_delta"]) < 0
        ),
        "regressed_target_junction_count": sum(
            1
            for row in target_rows
            if int(row["movements_with_phase_timing_delta"]) < 0
            or int(row["movements_with_phase_mapping_delta"]) < 0
            or int(row["unresolved_signalized_crash_count_delta"]) > 0
        ),
    }

    payload = {
        "signal_phase_delivery_uplift_version": SIGNAL_PHASE_DELIVERY_UPLIFT_VERSION,
        "signal_phase_delivery_uplift_contract_version": SIGNAL_PHASE_DELIVERY_UPLIFT_CONTRACT_VERSION,
        "generated_at_utc": stats["generated_at_utc"],
        "stats": stats,
        "baseline_summary": baseline["summary"],
        "updated_summary": updated["summary"],
        "metric_comparison": comparison_rows,
        "target_junction_uplift": target_rows[:20],
    }
    report_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(
        _markdown_summary(payload=payload, comparison_rows=comparison_rows, target_rows=target_rows),
        encoding="utf-8",
    )

    upstream_inputs = [
        _artifact_reference("movement_objects_geojson", baseline_input, _sha256(baseline_input)),
        _artifact_reference("movement_signal_phase_layer", updated_input, _sha256(updated_input)),
        _artifact_reference("matched_movement_records", matched_input, _sha256(matched_input)),
    ]
    if target_request_input and target_request_input.exists():
        upstream_inputs.append(
            _artifact_reference(
                "signal_phase_outreach_target_queue",
                target_request_input,
                _sha256(target_request_input),
            )
        )
    if delivery_session_input and delivery_session_input.exists():
        upstream_inputs.append(
            _artifact_reference(
                "signal_phase_delivery_session",
                delivery_session_input,
                _sha256(delivery_session_input),
            )
        )

    manifest = {
        "signal_phase_delivery_uplift_version": SIGNAL_PHASE_DELIVERY_UPLIFT_VERSION,
        "contract": {
            "resource_name": "signal_phase_delivery_uplift_report",
            "public_contract_version": SIGNAL_PHASE_DELIVERY_UPLIFT_CONTRACT_VERSION,
            "signal_phase_delivery_uplift_version": SIGNAL_PHASE_DELIVERY_UPLIFT_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_delivery_uplift_builder",
        },
        "inputs": {
            "baseline_movement_objects_path": str(baseline_input),
            "updated_movement_objects_path": str(updated_input),
            "matched_records_path": str(matched_input),
            "target_request_queue_path": str(target_request_input) if target_request_input else None,
            "delivery_session_manifest_path": str(delivery_session_input) if delivery_session_input else None,
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "report_json_path": str(report_json_path),
            "report_json_sha256": _sha256(report_json_path),
            "report_md_path": str(report_md_path),
            "report_md_sha256": _sha256(report_md_path),
            "coverage_metric_comparison_path": str(comparison_path),
            "coverage_metric_comparison_sha256": _sha256(comparison_path),
            "target_junction_uplift_path": str(target_path),
            "target_junction_uplift_sha256": _sha256(target_path),
        },
        "stats": stats,
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=upstream_inputs,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_delivery_uplift_report",
                    report_json_path,
                    _sha256(report_json_path),
                ),
                _artifact_reference(
                    "signal_phase_delivery_uplift_markdown",
                    report_md_path,
                    _sha256(report_md_path),
                ),
            ],
            supporting_outputs=[
                _artifact_reference(
                    "signal_phase_delivery_uplift_metric_comparison_csv",
                    comparison_path,
                    _sha256(comparison_path),
                ),
                _artifact_reference(
                    "signal_phase_delivery_uplift_target_junction_csv",
                    target_path,
                    _sha256(target_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_delivery_uplift_version": SIGNAL_PHASE_DELIVERY_UPLIFT_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
    }
