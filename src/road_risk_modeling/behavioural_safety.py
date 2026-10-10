"""Behavioural-safety analytics: aggregate, privacy-safe enforcement targeting.

The D6-09 call asks for *"evidence-based enforcement strategies … addressing
risky driving and multi-offender populations."* The platform is
infrastructure/place-focused; this adds the **behavioural and enforcement
evidence layer** — **where and when** behavioural-crash risk concentrates, so
authorities can target enforcement and incentives.

It deliberately produces an **aggregate, privacy-safe** view only. Consistent
with the [DPIA](../ethics/dpia.md) purpose-limitation and GDPR Art. 22, there is
**no person-level profiling or targeting**: outputs are segment (corridor) ×
time-of-day aggregates, and cells below an anonymity floor are **suppressed**.



## Behavioural KPIs

The EC tracks four behavioural Safe-System KPIs; this module maps each to the
platform signal that proxies it, and is explicit where a signal is not yet held:

- **speed** — observed operating speed vs limit (`observed_p85_speed_kph` vs
  `observed_speed_limit_kph`) — *available* (the connector observation layer).
- **sober driving** — requires impairment coding on crashes — *not held*
  (proxy: night/weekend over-representation).
- **protective equipment** — seatbelt/helmet use — *not held* (proxy: VRU /
  unprotected-user crash share).
- **distraction** — requires crash-narrative coding — *not held*.

Where a KPI signal is absent it is reported as a **coverage gap**, not invented.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _artifact_reference, _build_lineage_contract, _sha256

BEHAVIOURAL_SAFETY_VERSION = "behavioural_safety_v1"
BEHAVIOURAL_SAFETY_CONTRACT_VERSION = "behavioural_safety_public_v1"

# Privacy guardrail: aggregate cells with fewer than this many crashes are
# suppressed to prevent re-identification (k-anonymity style floor).
DEFAULT_MIN_CELL = 5

TIME_BUCKETS = ("overnight", "morning", "afternoon", "evening")

# EC behavioural KPI -> platform signal mapping (the evidence framework).
BEHAVIOURAL_KPIS: tuple[dict[str, str], ...] = (
    {
        "kpi": "speed",
        "ec_definition": "Share of vehicles travelling within the speed limit",
        "platform_signal": "observed_p85_speed_kph vs observed_speed_limit_kph",
        "status": "available",
    },
    {
        "kpi": "sober_driving",
        "ec_definition": "Share of drivers within the legal alcohol limit",
        "platform_signal": "night/weekend crash over-representation (proxy)",
        "status": "proxy_only",
    },
    {
        "kpi": "protective_equipment",
        "ec_definition": "Seatbelt/helmet wearing rate",
        "platform_signal": "VRU / unprotected-user crash share (proxy)",
        "status": "proxy_only",
    },
    {
        "kpi": "distraction",
        "ec_definition": "Share of drivers not using a handheld device",
        "platform_signal": "requires crash-narrative coding",
        "status": "not_held",
    },
)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    f = _to_float(value)
    return int(f) if f is not None else None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def speeding_pressure(row: Mapping[str, Any]) -> float | None:
    """Speeding-behaviour pressure for a segment: how far observed operating
    speed (85th percentile) exceeds the limit, normalised to [0, 1].

    p85 at or below the limit -> 0; p85 ≥ limit + 20 km/h -> 1.
    """
    p85 = _to_float(row.get("observed_p85_speed_kph")) or _to_float(row.get("observed_mean_speed_kph"))
    limit = _to_float(row.get("observed_speed_limit_kph")) or _to_float(row.get("maxspeed_numeric"))
    if p85 is None or limit is None or limit <= 0:
        return None
    return round(_clamp((p85 - limit) / 20.0), 4)


def _time_bucket(hour: int | None) -> str | None:
    if hour is None:
        return None
    if hour < 6:
        return "overnight"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _night_or_weekend(row: Mapping[str, Any]) -> bool:
    hour = _to_int(row.get("occurred_hour"))
    if hour is not None and (hour < 6 or hour >= 22):
        return True
    # occurred_weekday: 5=Sat, 6=Sun (Python convention) if present.
    weekday = _to_int(row.get("occurred_weekday"))
    return weekday is not None and weekday >= 5


def behavioural_crash_indicator(row: Mapping[str, Any]) -> dict[str, Any]:
    """Per-crash behavioural typing from available signals. Returns the
    contributing flags and a composite behavioural-risk weight in [0, 1]."""
    speeding = speeding_pressure(row)
    night_weekend = _night_or_weekend(row)
    vru = str(row.get("involves_vru") or "").strip().lower() in {"yes", "true", "1"}

    signals: list[str] = []
    weight = 0.0
    if speeding is not None and speeding > 0.0:
        signals.append("speeding")
        weight = max(weight, speeding)
    if night_weekend:
        signals.append("night_or_weekend")  # sober-driving proxy
        weight = max(weight, 0.5)
    if vru:
        signals.append("vru_unprotected")  # protective-equipment proxy
        weight = max(weight, 0.4)

    return {
        "behavioural_signals": signals,
        "behavioural_weight": round(weight, 4),
        "is_behavioural": bool(signals),
    }


def build_enforcement_priorities(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_cell: int = DEFAULT_MIN_CELL,
) -> dict[str, Any]:
    """Aggregate behavioural-crash risk by **corridor × time-of-day**.

    Returns the surviving (non-suppressed) priority cells ranked by a
    behavioural concentration score, plus the suppression accounting. No
    person-level fields are ever emitted.
    """
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        corridor = str(row.get("corridor_id") or row.get("road_ref") or row.get("segment_id") or "unknown")
        bucket = _time_bucket(_to_int(row.get("occurred_hour")))
        if bucket is None:
            continue
        indicator = behavioural_crash_indicator(row)
        key = (corridor, bucket)
        cell = cells.setdefault(
            key,
            {
                "corridor_id": corridor,
                "time_of_day": bucket,
                "crash_count": 0,
                "behavioural_crash_count": 0,
                "behavioural_weight_sum": 0.0,
                "signal_counts": {},
            },
        )
        cell["crash_count"] += 1
        if indicator["is_behavioural"]:
            cell["behavioural_crash_count"] += 1
            cell["behavioural_weight_sum"] += indicator["behavioural_weight"]
            for signal in indicator["behavioural_signals"]:
                cell["signal_counts"][signal] = cell["signal_counts"].get(signal, 0) + 1

    surviving: list[dict[str, Any]] = []
    suppressed = 0
    for cell in cells.values():
        if cell["crash_count"] < min_cell:
            suppressed += 1
            continue
        crash_count = cell["crash_count"]
        behavioural_share = cell["behavioural_crash_count"] / crash_count if crash_count else 0.0
        # Concentration score = behavioural crashes × mean behavioural weight.
        mean_weight = (
            cell["behavioural_weight_sum"] / cell["behavioural_crash_count"]
            if cell["behavioural_crash_count"]
            else 0.0
        )
        surviving.append(
            {
                "corridor_id": cell["corridor_id"],
                "time_of_day": cell["time_of_day"],
                "crash_count": crash_count,
                "behavioural_crash_count": cell["behavioural_crash_count"],
                "behavioural_share": round(behavioural_share, 4),
                "concentration_score": round(cell["behavioural_crash_count"] * mean_weight, 4),
                "dominant_signal": (
                    max(cell["signal_counts"], key=lambda k: cell["signal_counts"][k])
                    if cell["signal_counts"]
                    else None
                ),
            }
        )
    surviving.sort(key=lambda cell: cell["concentration_score"], reverse=True)
    return {
        "priorities": surviving,
        "cells_total": len(cells),
        "cells_suppressed": suppressed,
        "min_cell": min_cell,
    }


def run_behavioural_analysis(
    *,
    crashes_path: str | Path,
    output_dir: str | Path,
    min_cell: int = DEFAULT_MIN_CELL,
) -> dict[str, Any]:
    """Read a crash table with behavioural signals and write a privacy-safe
    enforcement-prioritisation table + KPI evidence framework + manifest."""
    crashes_file = Path(crashes_path)
    with crashes_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Crash table is empty.")

    enforcement = build_enforcement_priorities(rows, min_cell=min_cell)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "enforcement_priorities.csv"
    json_path = output_root / "behavioural_safety.json"
    manifest_path = output_root / "behavioural_safety.manifest.json"

    fieldnames = [
        "corridor_id",
        "time_of_day",
        "crash_count",
        "behavioural_crash_count",
        "behavioural_share",
        "concentration_score",
        "dominant_signal",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enforcement["priorities"])

    payload = {
        "behavioural_safety_version": BEHAVIOURAL_SAFETY_VERSION,
        "privacy": {
            "aggregate_only": True,
            "person_level_targeting": False,
            "min_cell_suppression": min_cell,
            "basis": "DPIA purpose-limitation; GDPR Art. 22 (no automated individual decisions).",
        },
        "behavioural_kpis": list(BEHAVIOURAL_KPIS),
        "crash_count": len(rows),
        "cells_total": enforcement["cells_total"],
        "cells_suppressed": enforcement["cells_suppressed"],
        "priority_count": len(enforcement["priorities"]),
        "priorities": enforcement["priorities"],
        "lineage": _build_lineage_contract(
            run_record_path=json_path,
            upstream_inputs=[_artifact_reference("behavioural_crashes", crashes_file, _sha256(crashes_file))],
            publishable_outputs=[_artifact_reference("enforcement_priorities_csv", csv_path, None)],
        ),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "behavioural_safety_version": BEHAVIOURAL_SAFETY_VERSION,
        "contract": {
            "resource_name": "behavioural_safety",
            "public_contract_version": BEHAVIOURAL_SAFETY_CONTRACT_VERSION,
        },
        "outputs": {
            "enforcement_priorities_csv_path": str(csv_path),
            "enforcement_priorities_csv_sha256": _sha256(csv_path),
            "summary_json_path": str(json_path),
            "summary_json_sha256": _sha256(json_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "enforcement_priorities_csv_path": str(csv_path),
        "summary_json_path": str(json_path),
        "manifest_path": str(manifest_path),
        "priority_count": len(enforcement["priorities"]),
        "cells_suppressed": enforcement["cells_suppressed"],
    }
