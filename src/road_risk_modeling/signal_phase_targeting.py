"""Build Bari signal-phase delivery targets from coverage and outreach artifacts."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_TARGET_BUNDLE_VERSION = "signal_phase_target_bundle_v1"
SIGNAL_PHASE_TARGET_BUNDLE_CONTRACT_VERSION = "signal_phase_target_bundle_public_v1"
WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
WEEKEND_NAMES = {"saturday", "sunday"}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


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


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _coverage_state(row: dict[str, Any]) -> str:
    provider = _safe_int(row.get("movements_with_provider_data"))
    timing = _safe_int(row.get("movements_with_phase_timing"))
    mapping = _safe_int(row.get("movements_with_phase_mapping"))
    movement_count = _safe_int(row.get("signalized_movement_count"))
    if provider <= 0:
        return "no_provider_data"
    if timing <= 0 and mapping <= 0:
        return "provider_only_no_phase_resolution"
    if timing > 0 and mapping <= 0:
        return "timing_only_partial"
    if timing <= 0 and mapping > 0:
        return "mapping_only_partial"
    if timing < movement_count or mapping < movement_count:
        return "partial_phase_coverage"
    return "phase_ready"


def _recommended_action(row: dict[str, Any], hotspot_rows: list[dict[str, Any]]) -> str:
    top_hotspot = hotspot_rows[0] if hotspot_rows else {}
    top_name = _clean_text(top_hotspot.get("movement_name")) or "highest-crash uncovered movement"
    profile = _clean_text(row.get("recommended_provider_profile")) or "signal-phase delivery"
    state = _coverage_state(row)
    unresolved_movement_count = _safe_int(row.get("unresolved_signalized_movement_count"))
    unresolved_crash_count = _safe_int(row.get("unresolved_signalized_crash_count"))
    unresolved_suffix = ""
    if unresolved_movement_count > 0 or unresolved_crash_count > 0:
        unresolved_suffix = (
            f" Prioritize unresolved movement resolution ({unresolved_movement_count} movements, "
            f"{unresolved_crash_count} crashes)."
        )
    if state == "no_provider_data":
        return f"Request first {profile} delivery plus arm-phase mapping for {top_name}.{unresolved_suffix}"
    if state == "provider_only_no_phase_resolution":
        return f"Convert existing provider coverage into timed and mapped movements, starting with {top_name}.{unresolved_suffix}"
    if state == "timing_only_partial":
        return f"Complete arm-phase mapping for timed junction data, starting with {top_name}.{unresolved_suffix}"
    if state == "mapping_only_partial":
        return f"Request controller timing and event history for mapped movements, starting with {top_name}.{unresolved_suffix}"
    if state == "partial_phase_coverage":
        return f"Expand timing and mapping coverage beyond the current sample movement, starting with {top_name}.{unresolved_suffix}"
    return f"Validate whether current phase coverage actually reaches crash-bearing movements such as {top_name}.{unresolved_suffix}"


def _gap_priority_score(row: dict[str, Any], hotspot_rows: list[dict[str, Any]]) -> int:
    crashes_without_timing = _safe_int(row.get("crashes_without_phase_timing"))
    top_hotspot_crashes = _safe_int(hotspot_rows[0]["matched_crash_count"]) if hotspot_rows else 0
    movements_without_timing = _safe_int(row.get("movements_without_phase_timing"))
    unresolved_crash_count = _safe_int(row.get("unresolved_signalized_crash_count"))
    unresolved_movement_count = _safe_int(row.get("unresolved_signalized_movement_count"))
    return (
        crashes_without_timing * 100
        + top_hotspot_crashes * 10
        + movements_without_timing
        + unresolved_crash_count * 25
        + unresolved_movement_count * 5
    )


def _time_of_day_bucket(hour: int | None) -> str | None:
    if hour is None:
        return None
    if hour < 6:
        return "overnight"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _format_hour_label(hour: int | None) -> str | None:
    if hour is None or hour < 0 or hour > 23:
        return None
    return f"{hour:02d}:00-{hour:02d}:59"


def _counter_peak(counter: Counter[Any]) -> tuple[Any | None, int]:
    if not counter:
        return None, 0
    key = sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))[0][0]
    return key, int(counter[key])


def _top_hours(counter: Counter[int], *, limit: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "hour": int(hour),
            "hour_label": _format_hour_label(int(hour)),
            "crash_count": int(count),
        }
        for hour, count in ranked[:limit]
    ]


def _safe_share(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole, 4)


def _dominant_day_type(weekday_crash_count: int, weekend_crash_count: int) -> str:
    if weekday_crash_count > weekend_crash_count:
        return "weekday"
    if weekend_crash_count > weekday_crash_count:
        return "weekend"
    if weekday_crash_count > 0:
        return "balanced"
    return "unknown"


def _recommended_time_window(temporal_profile: dict[str, Any]) -> str | None:
    crash_count = _safe_int(temporal_profile.get("timed_signalized_crash_count"))
    if crash_count <= 0:
        return None
    dominant_day_type = _clean_text(temporal_profile.get("dominant_day_type")) or "weekday"
    peak_bucket = _clean_text(temporal_profile.get("peak_time_of_day_bucket")) or "daytime"
    top_hours = temporal_profile.get("top_hours") or []
    if top_hours:
        hour_labels = ", ".join(
            label
            for label in (_clean_text(item.get("hour_label")) for item in top_hours)
            if label is not None
        )
        if hour_labels:
            return f"{dominant_day_type} {peak_bucket}, especially {hour_labels}"
    return f"{dominant_day_type} {peak_bucket}"


def _is_signalized_target_record(record: dict[str, Any], *, junction_id: str) -> bool:
    if _clean_text(record.get("junction_id")) != junction_id:
        return False
    control_state = _clean_text(record.get("control_state"))
    phase_priority_group = _clean_text(record.get("phase_priority_group")) or ""
    if control_state is None:
        return phase_priority_group.startswith("signalized") or junction_id.startswith("it-bari-signal-")
    return control_state == "signalized" or phase_priority_group.startswith("signalized")


def _build_temporal_profiles(
    matched_movement_records_path: Path,
    *,
    target_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tracked_junctions = {
        _clean_text(row.get("junction_id")) or "": {
            "request_id": _clean_text(row.get("request_id")),
            "signal_name": _clean_text(row.get("signal_name")),
        }
        for row in target_rows
    }
    profile_state: dict[str, dict[str, Any]] = {
        junction_id: {
            "timed_signalized_crash_count": 0,
            "hour_counts": Counter(),
            "weekday_counts": Counter(),
            "bucket_counts": Counter(),
        }
        for junction_id in tracked_junctions
        if junction_id
    }

    for record in _read_jsonl_rows(matched_movement_records_path):
        junction_id = _clean_text(record.get("junction_id")) or ""
        if junction_id not in profile_state:
            continue
        if not _is_signalized_target_record(record, junction_id=junction_id):
            continue

        occurred_hour = record.get("occurred_hour")
        hour = None
        if occurred_hour is not None:
            try:
                hour = int(occurred_hour)
            except (TypeError, ValueError):
                hour = None

        occurred_at = _clean_text(record.get("occurred_at"))
        weekday_name = None
        if occurred_at is not None:
            try:
                weekday_name = WEEKDAY_NAMES[datetime.fromisoformat(occurred_at).weekday()]
            except ValueError:
                weekday_name = None

        extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
        official_extra = extra.get("official_bari_open_data") if isinstance(extra, dict) else {}
        bucket = None
        if isinstance(official_extra, dict):
            bucket = _clean_text(official_extra.get("time_of_day_bucket"))
        bucket = bucket or _time_of_day_bucket(hour)

        state = profile_state[junction_id]
        state["timed_signalized_crash_count"] += 1
        if hour is not None:
            state["hour_counts"][hour] += 1
        if weekday_name is not None:
            state["weekday_counts"][weekday_name] += 1
        if bucket is not None:
            state["bucket_counts"][bucket] += 1

    target_time_profile_rows: list[dict[str, Any]] = []
    target_hourly_profile_rows: list[dict[str, Any]] = []
    temporal_profiles: dict[str, dict[str, Any]] = {}

    for junction_id, state in profile_state.items():
        target = tracked_junctions[junction_id]
        timed_signalized_crash_count = int(state["timed_signalized_crash_count"])
        hour_counts: Counter[int] = state["hour_counts"]
        weekday_counts: Counter[str] = state["weekday_counts"]
        bucket_counts: Counter[str] = state["bucket_counts"]

        peak_hour, peak_hour_crash_count = _counter_peak(hour_counts)
        peak_weekday_name, peak_weekday_crash_count = _counter_peak(weekday_counts)
        peak_time_of_day_bucket, peak_time_of_day_bucket_count = _counter_peak(bucket_counts)
        weekday_crash_count = sum(
            count for weekday_name, count in weekday_counts.items() if weekday_name not in WEEKEND_NAMES
        )
        weekend_crash_count = sum(
            count for weekday_name, count in weekday_counts.items() if weekday_name in WEEKEND_NAMES
        )
        dominant_day_type = _dominant_day_type(weekday_crash_count, weekend_crash_count)
        top_hours = _top_hours(hour_counts)

        temporal_profile = {
            "timed_signalized_crash_count": timed_signalized_crash_count,
            "distinct_hour_count": len(hour_counts),
            "peak_crash_hour": peak_hour,
            "peak_crash_hour_label": _format_hour_label(peak_hour),
            "peak_crash_hour_count": peak_hour_crash_count,
            "peak_crash_hour_share": _safe_share(peak_hour_crash_count, timed_signalized_crash_count),
            "peak_time_of_day_bucket": peak_time_of_day_bucket,
            "peak_time_of_day_bucket_count": peak_time_of_day_bucket_count,
            "peak_weekday_name": peak_weekday_name,
            "peak_weekday_count": peak_weekday_crash_count,
            "weekday_crash_count": weekday_crash_count,
            "weekend_crash_count": weekend_crash_count,
            "dominant_day_type": dominant_day_type,
            "overnight_crash_count": int(bucket_counts.get("overnight", 0)),
            "morning_crash_count": int(bucket_counts.get("morning", 0)),
            "afternoon_crash_count": int(bucket_counts.get("afternoon", 0)),
            "evening_crash_count": int(bucket_counts.get("evening", 0)),
            "top_hours": top_hours,
        }
        temporal_profile["recommended_time_window"] = _recommended_time_window(temporal_profile)
        temporal_profiles[junction_id] = temporal_profile

        target_time_profile_rows.append(
            {
                "request_id": target["request_id"],
                "junction_id": junction_id,
                "signal_name": target["signal_name"],
                **{key: value for key, value in temporal_profile.items() if key != "top_hours"},
            }
        )
        for hour in range(24):
            target_hourly_profile_rows.append(
                {
                    "request_id": target["request_id"],
                    "junction_id": junction_id,
                    "signal_name": target["signal_name"],
                    "hour": hour,
                    "hour_label": _format_hour_label(hour),
                    "matched_crash_count": int(hour_counts.get(hour, 0)),
                }
            )

    return temporal_profiles, target_time_profile_rows, target_hourly_profile_rows


def _request_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Signal-Phase Target Dossier: {packet['request_id']}",
        "",
        "## Coverage Summary",
        "",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Priority rank: `{packet['priority_rank']}`",
        f"- Coverage state: `{packet['coverage_state']}`",
        f"- Recommended provider profile: `{packet['recommended_provider_profile']}`",
        f"- Required profiles: `{packet['required_profiles']}`",
        f"- Signalized movements: `{packet['signalized_movement_count']}`",
        f"- Matched signalized crashes: `{packet['matched_signalized_crash_count']}`",
        f"- Movements with provider data: `{packet['movements_with_provider_data']}`",
        f"- Movements with phase timing: `{packet['movements_with_phase_timing']}`",
        f"- Movements with phase mapping: `{packet['movements_with_phase_mapping']}`",
        f"- Unresolved signalized movements: `{packet['unresolved_signalized_movement_count']}`",
        f"- Unresolved signalized crashes: `{packet['unresolved_signalized_crash_count']}`",
        f"- Crashes without phase timing: `{packet['crashes_without_phase_timing']}`",
        "",
        "## Crash Timing Profile",
        "",
    ]
    temporal_profile = packet.get("temporal_profile") or {}
    if _safe_int(temporal_profile.get("timed_signalized_crash_count")) > 0:
        lines.extend(
            [
                f"- Timed signalized crashes: `{temporal_profile['timed_signalized_crash_count']}`",
                f"- Peak crash hour: `{temporal_profile['peak_crash_hour_label']}` with `{temporal_profile['peak_crash_hour_count']}` crashes",
                f"- Dominant day type: `{temporal_profile['dominant_day_type']}` "
                f"(`{temporal_profile['weekday_crash_count']}` weekday / `{temporal_profile['weekend_crash_count']}` weekend)",
                f"- Peak time-of-day bucket: `{temporal_profile['peak_time_of_day_bucket']}` "
                f"with `{temporal_profile['peak_time_of_day_bucket_count']}` crashes",
                f"- Recommended observation window: `{temporal_profile['recommended_time_window']}`",
            ]
        )
        top_hours = temporal_profile.get("top_hours") or []
        if top_hours:
            lines.append(
                "- Top crash hours: "
                + ", ".join(
                    f"`{item['hour_label']}` (`{item['crash_count']}`)"
                    for item in top_hours
                )
            )
    else:
        lines.append("- No crash timing profile is available yet for this target.")
    lines.extend(
        [
            "",
        "## Recommended Next Action",
        "",
        f"- {packet['recommended_next_action']}",
        "",
        "## Top Uncovered Movements",
        "",
        ]
    )
    for hotspot in packet["top_uncovered_movements"]:
        lines.append(
            f"- `{hotspot['movement_name']}` `{hotspot['movement_turn']}`: "
            f"`{hotspot['matched_crash_count']}` crashes, state `{hotspot['movement_resolution_state']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_target_bundle(
    *,
    output_dir: str | Path = "data/reporting/signal_phase_targets/bari",
    target_junction_coverage_path: str | Path = "data/reporting/signal_phase_coverage/bari_sample/target_junction_coverage.csv",
    uncovered_signalized_hotspots_path: str | Path = "data/reporting/signal_phase_coverage/bari_sample/uncovered_signalized_hotspots.csv",
    target_request_queue_path: str | Path = "data/planning/signal_phase_outreach/bari/target_request_queue.csv",
    matched_movement_records_path: str | Path = "data/processed/node_matches/bari_open_data_movements/matched_node_records.jsonl",
    top_hotspots_per_target: int = 5,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "target_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    target_coverage_input = Path(target_junction_coverage_path)
    uncovered_hotspots_input = Path(uncovered_signalized_hotspots_path)
    target_queue_input = Path(target_request_queue_path)
    matched_movement_records_input = Path(matched_movement_records_path)

    coverage_rows = _read_csv_rows(target_coverage_input)
    hotspot_rows = _read_csv_rows(uncovered_hotspots_input)
    queue_rows = _read_csv_rows(target_queue_input)
    temporal_profiles, target_time_profile_rows, target_hourly_profile_rows = _build_temporal_profiles(
        matched_movement_records_input,
        target_rows=queue_rows,
    )

    coverage_by_request = {
        _clean_text(row.get("request_id")) or _clean_text(row.get("junction_id")) or "": row
        for row in coverage_rows
    }
    hotspots_by_request: dict[str, list[dict[str, Any]]] = {}
    for row in hotspot_rows:
        request_key = _clean_text(row.get("request_id")) or _clean_text(row.get("junction_id")) or ""
        hotspots_by_request.setdefault(request_key, []).append(row)
    for rows in hotspots_by_request.values():
        rows.sort(
            key=lambda item: (
                -_safe_int(item.get("matched_crash_count")),
                _priority_value(item.get("priority_rank")),
                str(item.get("junction_id") or ""),
                str(item.get("node_object_id") or ""),
            )
        )

    target_priority_rows: list[dict[str, Any]] = []
    packet_paths: list[str] = []
    packet_payloads: list[dict[str, Any]] = []
    filtered_hotspot_rows: list[dict[str, Any]] = []

    for queue_row in sorted(
        queue_rows,
        key=lambda item: (
            _priority_value(item.get("priority_rank")),
            str(item.get("junction_id") or ""),
        ),
    ):
        request_id = _clean_text(queue_row.get("request_id")) or ""
        junction_id = _clean_text(queue_row.get("junction_id")) or ""
        coverage_row = coverage_by_request.get(request_id) or coverage_by_request.get(junction_id) or {}
        target_hotspots = hotspots_by_request.get(request_id) or hotspots_by_request.get(junction_id) or []
        top_hotspots = target_hotspots[:top_hotspots_per_target]
        filtered_hotspot_rows.extend(top_hotspots)

        merged = {
            **queue_row,
            **coverage_row,
        }
        coverage_state = _coverage_state(merged)
        recommended_next_action = _recommended_action(merged, top_hotspots)
        gap_priority_score = _gap_priority_score(merged, top_hotspots)
        top_hotspot = top_hotspots[0] if top_hotspots else {}
        temporal_profile = temporal_profiles.get(junction_id, {})
        target_row = {
            "request_id": request_id,
            "junction_id": junction_id,
            "signal_name": _clean_text(merged.get("signal_name")),
            "priority_rank": _safe_int(merged.get("priority_rank")),
            "priority_band": _clean_text(merged.get("priority_band")),
            "recommended_provider_profile": _clean_text(merged.get("recommended_provider_profile")),
            "required_profiles": _clean_text(merged.get("required_profiles")),
            "coverage_state": coverage_state,
            "signalized_movement_count": _safe_int(merged.get("signalized_movement_count")),
            "matched_signalized_crash_count": _safe_int(merged.get("matched_signalized_crash_count")),
            "movements_with_provider_data": _safe_int(merged.get("movements_with_provider_data")),
            "movements_with_phase_timing": _safe_int(merged.get("movements_with_phase_timing")),
            "movements_with_phase_mapping": _safe_int(merged.get("movements_with_phase_mapping")),
            "unresolved_signalized_movement_count": _safe_int(merged.get("unresolved_signalized_movement_count")),
            "unresolved_signalized_crash_count": _safe_int(merged.get("unresolved_signalized_crash_count")),
            "unresolved_coverage_pct": round(_safe_float(merged.get("unresolved_coverage_pct")), 2),
            "unresolved_crash_coverage_pct": round(_safe_float(merged.get("unresolved_crash_coverage_pct")), 2),
            "movements_without_phase_timing": _safe_int(merged.get("movements_without_phase_timing")),
            "crashes_without_phase_timing": _safe_int(merged.get("crashes_without_phase_timing")),
            "top_hotspot_name": _clean_text(top_hotspot.get("movement_name")),
            "top_hotspot_turn": _clean_text(top_hotspot.get("movement_turn")),
            "top_hotspot_crash_count": _safe_int(top_hotspot.get("matched_crash_count")),
            "top_hotspot_resolution_state": _clean_text(top_hotspot.get("movement_resolution_state")),
            "top_uncovered_hotspot_count": len(top_hotspots),
            "gap_priority_score": gap_priority_score,
            "timed_signalized_crash_count": _safe_int(temporal_profile.get("timed_signalized_crash_count")),
            "peak_crash_hour": temporal_profile.get("peak_crash_hour"),
            "peak_crash_hour_label": _clean_text(temporal_profile.get("peak_crash_hour_label")),
            "peak_crash_hour_count": _safe_int(temporal_profile.get("peak_crash_hour_count")),
            "peak_time_of_day_bucket": _clean_text(temporal_profile.get("peak_time_of_day_bucket")),
            "peak_time_of_day_bucket_count": _safe_int(temporal_profile.get("peak_time_of_day_bucket_count")),
            "weekday_crash_count": _safe_int(temporal_profile.get("weekday_crash_count")),
            "weekend_crash_count": _safe_int(temporal_profile.get("weekend_crash_count")),
            "dominant_day_type": _clean_text(temporal_profile.get("dominant_day_type")),
            "recommended_time_window": _clean_text(temporal_profile.get("recommended_time_window")),
            "recommended_next_action": recommended_next_action,
        }
        target_priority_rows.append(target_row)

        packet_payload = {
            **target_row,
            "temporal_profile": temporal_profile,
            "top_uncovered_movements": [
                {
                    "node_object_id": _clean_text(row.get("node_object_id")),
                    "movement_name": _clean_text(row.get("movement_name")),
                    "movement_turn": _clean_text(row.get("movement_turn")),
                    "matched_crash_count": _safe_int(row.get("matched_crash_count")),
                    "movement_resolution_state": _clean_text(row.get("movement_resolution_state")),
                    "phase_priority_group": _clean_text(row.get("phase_priority_group")),
                }
                for row in top_hotspots
            ],
        }
        packet_json_path = packet_dir / f"{_slugify(request_id or junction_id)}.json"
        packet_md_path = packet_dir / f"{_slugify(request_id or junction_id)}.md"
        packet_json_path.write_text(json.dumps(packet_payload, indent=2, sort_keys=True), encoding="utf-8")
        packet_md_path.write_text(_request_markdown(packet_payload), encoding="utf-8")
        packet_paths.extend([str(packet_json_path), str(packet_md_path)])
        packet_payloads.append(packet_payload)

    target_priority_rows.sort(
        key=lambda item: (
            _priority_value(item.get("priority_rank")),
            -_safe_int(item.get("gap_priority_score")),
            str(item.get("junction_id") or ""),
        )
    )

    target_priority_matrix_path = output_root / "target_priority_matrix.csv"
    target_time_profiles_path = output_root / "target_time_profiles.csv"
    target_hourly_profile_path = output_root / "target_hourly_profile.csv"
    target_hotspots_path = output_root / "target_hotspots.csv"
    bundle_json_path = output_root / "signal_phase_target_bundle.json"
    bundle_md_path = output_root / "signal_phase_target_bundle.md"
    manifest_path = output_root / "signal_phase_target_bundle.manifest.json"

    _write_csv(
        target_priority_matrix_path,
        target_priority_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "recommended_provider_profile",
            "required_profiles",
            "coverage_state",
            "signalized_movement_count",
            "matched_signalized_crash_count",
            "movements_with_provider_data",
            "movements_with_phase_timing",
            "movements_with_phase_mapping",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
            "movements_without_phase_timing",
            "crashes_without_phase_timing",
            "top_hotspot_name",
            "top_hotspot_turn",
            "top_hotspot_crash_count",
            "top_hotspot_resolution_state",
            "top_uncovered_hotspot_count",
            "gap_priority_score",
            "timed_signalized_crash_count",
            "peak_crash_hour",
            "peak_crash_hour_label",
            "peak_crash_hour_count",
            "peak_time_of_day_bucket",
            "peak_time_of_day_bucket_count",
            "weekday_crash_count",
            "weekend_crash_count",
            "dominant_day_type",
            "recommended_time_window",
            "recommended_next_action",
        ],
    )
    _write_csv(
        target_time_profiles_path,
        target_time_profile_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "timed_signalized_crash_count",
            "distinct_hour_count",
            "peak_crash_hour",
            "peak_crash_hour_label",
            "peak_crash_hour_count",
            "peak_crash_hour_share",
            "peak_time_of_day_bucket",
            "peak_time_of_day_bucket_count",
            "peak_weekday_name",
            "peak_weekday_count",
            "weekday_crash_count",
            "weekend_crash_count",
            "dominant_day_type",
            "overnight_crash_count",
            "morning_crash_count",
            "afternoon_crash_count",
            "evening_crash_count",
            "recommended_time_window",
        ],
    )
    _write_csv(
        target_hourly_profile_path,
        target_hourly_profile_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "hour",
            "hour_label",
            "matched_crash_count",
        ],
    )
    _write_csv(
        target_hotspots_path,
        filtered_hotspot_rows,
        sorted({key for row in filtered_hotspot_rows for key in row.keys()}),
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "target_count": len(target_priority_rows),
        "packet_count": len(packet_payloads),
        "targets_with_provider_data": sum(1 for row in target_priority_rows if _safe_int(row["movements_with_provider_data"]) > 0),
        "targets_with_phase_timing": sum(1 for row in target_priority_rows if _safe_int(row["movements_with_phase_timing"]) > 0),
        "targets_with_phase_mapping": sum(1 for row in target_priority_rows if _safe_int(row["movements_with_phase_mapping"]) > 0),
        "targets_with_unresolved_movements": sum(
            1 for row in target_priority_rows if _safe_int(row["unresolved_signalized_movement_count"]) > 0
        ),
        "matched_signalized_crash_total": sum(_safe_int(row["matched_signalized_crash_count"]) for row in target_priority_rows),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row["unresolved_signalized_movement_count"]) for row in target_priority_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row["unresolved_signalized_crash_count"]) for row in target_priority_rows
        ),
        "crashes_without_phase_timing_total": sum(_safe_int(row["crashes_without_phase_timing"]) for row in target_priority_rows),
        "top_hotspot_crash_total": sum(_safe_int(row["top_hotspot_crash_count"]) for row in target_priority_rows),
        "targets_with_time_profiles": sum(1 for row in target_priority_rows if _safe_int(row["timed_signalized_crash_count"]) > 0),
        "timed_signalized_crash_total": sum(_safe_int(row["timed_signalized_crash_count"]) for row in target_priority_rows),
        "filtered_hotspot_row_count": len(filtered_hotspot_rows),
    }

    bundle_payload = {
        "signal_phase_target_bundle_version": SIGNAL_PHASE_TARGET_BUNDLE_VERSION,
        "signal_phase_target_bundle_contract_version": SIGNAL_PHASE_TARGET_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "targets": packet_payloads,
    }
    bundle_json_path.write_text(json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Bari Signal-Phase Target Bundle",
        "",
        f"As of {summary['generated_at_utc']}, the tier-1 Bari request queue has been merged with the current signal-phase coverage gaps and uncovered signalized crash hotspots.",
        "",
        "## Summary",
        "",
        f"- targets: `{summary['target_count']}`",
        f"- target packets: `{summary['packet_count']}`",
        f"- targets with provider data: `{summary['targets_with_provider_data']}`",
        f"- targets with phase timing: `{summary['targets_with_phase_timing']}`",
        f"- targets with phase mapping: `{summary['targets_with_phase_mapping']}`",
        f"- targets with unresolved movements: `{summary['targets_with_unresolved_movements']}`",
        f"- targets with time profiles: `{summary['targets_with_time_profiles']}`",
        f"- matched signalized crashes across targets: `{summary['matched_signalized_crash_total']}`",
        f"- unresolved signalized movements across targets: `{summary['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across targets: `{summary['unresolved_signalized_crash_total']}`",
        f"- timed signalized crashes across targets: `{summary['timed_signalized_crash_total']}`",
        f"- crashes without phase timing across targets: `{summary['crashes_without_phase_timing_total']}`",
        "",
        "## Target Queue",
        "",
    ]
    for row in target_priority_rows:
        lines.append(
            f"- `{row['signal_name']}`: state `{row['coverage_state']}`, "
            f"`{row['matched_signalized_crash_count']}` signalized crashes, "
            f"`{row['unresolved_signalized_crash_count']}` unresolved crashes, "
            f"top hotspot `{row['top_hotspot_name']}` with `{row['top_hotspot_crash_count']}` crashes, "
            f"peak hour `{row['peak_crash_hour_label']}`"
        )
    lines.append("")
    bundle_md_path.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "signal_phase_target_bundle_version": SIGNAL_PHASE_TARGET_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_target_bundle",
            "public_contract_version": SIGNAL_PHASE_TARGET_BUNDLE_CONTRACT_VERSION,
            "signal_phase_target_bundle_version": SIGNAL_PHASE_TARGET_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_target_bundle_builder",
        },
        "inputs": {
            "target_junction_coverage_path": str(target_coverage_input),
            "uncovered_signalized_hotspots_path": str(uncovered_hotspots_input),
            "target_request_queue_path": str(target_queue_input),
            "matched_movement_records_path": str(matched_movement_records_input),
            "top_hotspots_per_target": int(top_hotspots_per_target),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "target_priority_matrix_path": str(target_priority_matrix_path),
            "target_priority_matrix_sha256": _sha256(target_priority_matrix_path),
            "target_time_profiles_path": str(target_time_profiles_path),
            "target_time_profiles_sha256": _sha256(target_time_profiles_path),
            "target_hourly_profile_path": str(target_hourly_profile_path),
            "target_hourly_profile_sha256": _sha256(target_hourly_profile_path),
            "target_hotspots_path": str(target_hotspots_path),
            "target_hotspots_sha256": _sha256(target_hotspots_path),
            "packet_dir": str(packet_dir),
            "packet_paths": packet_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_target_junction_coverage", target_coverage_input, _sha256(target_coverage_input)),
            _artifact_reference(
                "signal_phase_uncovered_hotspots",
                uncovered_hotspots_input,
                _sha256(uncovered_hotspots_input),
            ),
            _artifact_reference("signal_phase_target_request_queue", target_queue_input, _sha256(target_queue_input)),
            _artifact_reference(
                "signalized_movement_match_records",
                matched_movement_records_input,
                _sha256(matched_movement_records_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_target_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("signal_phase_target_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_target_priority_matrix",
                target_priority_matrix_path,
                _sha256(target_priority_matrix_path),
            ),
            _artifact_reference(
                "signal_phase_target_time_profiles",
                target_time_profiles_path,
                _sha256(target_time_profiles_path),
            ),
            _artifact_reference(
                "signal_phase_target_hourly_profile",
                target_hourly_profile_path,
                _sha256(target_hourly_profile_path),
            ),
            _artifact_reference("signal_phase_target_hotspots", target_hotspots_path, _sha256(target_hotspots_path)),
        ]
        + [
            _artifact_reference("signal_phase_target_packet", Path(path), _sha256(Path(path)))
            for path in packet_paths
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_target_bundle_version": SIGNAL_PHASE_TARGET_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
