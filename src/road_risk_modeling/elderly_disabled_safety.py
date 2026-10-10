"""Elderly & disabled road-user safety extension.

The D6-09 call requires tailored prevention *"including considerations for
elderly and disabled populations"* — central to rural fatality reduction given
ageing rural populations. The generic VRU layer covers pedestrians/cyclists
without **age- and disability-specific** vulnerability; this module adds it.

It produces, per segment:

1. **Age-band severity** — the elderly (65+) casualty share where casualty age
   is recorded, or an ageing-area exposure proxy where it is not.
2. **Accessibility provision / deficit** — a score over disability-relevant
   infrastructure (crossing continuity, kerb ramps, refuge islands, lighting).
3. **An elderly/disabled priority score** combining the two with crossing
   context.
4. **Tailored countermeasure profiles** mapped to the specific deficits, for the
   intervention briefs.

All outputs are **aggregate, segment-level**; no person-level data is retained
(consistent with the [ethics pack](../ethics/)).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _artifact_reference, _build_lineage_contract, _sha256

ELDERLY_DISABLED_VERSION = "elderly_disabled_safety_v1"
ELDERLY_DISABLED_CONTRACT_VERSION = "elderly_disabled_safety_public_v1"

RISK_SCALE_MAX = 100.0

# Disability-relevant infrastructure provisions and the share of accessibility
# adequacy each contributes (sums to 1.0). Absence of a known-present provision
# is treated as a deficit; an entirely unattributed segment reports low coverage.
ACCESSIBILITY_PROVISIONS: dict[str, float] = {
    "pedestrian_crossing": 0.30,  # a formal crossing at all
    "refuge_island": 0.25,        # crossing continuity / staged crossing
    "dropped_kerb": 0.25,         # wheelchair / mobility-aid access
    "lit": 0.20,                  # lighting (low-vision, dusk)
}

# Tailored elderly/disabled countermeasures, keyed by the deficit they address.
COUNTERMEASURE_LIBRARY: dict[str, dict[str, str]] = {
    "pedestrian_crossing": {
        "code": "add_formal_crossing",
        "measure": "Install a formal, high-visibility pedestrian crossing",
        "benefits": "elderly, disabled, low-vision",
    },
    "refuge_island": {
        "code": "central_refuge_island",
        "measure": "Add a central refuge island for staged crossing",
        "benefits": "slower walkers, wheelchair users, elderly",
    },
    "dropped_kerb": {
        "code": "dropped_kerb_tactile",
        "measure": "Provide dropped kerbs with tactile paving",
        "benefits": "wheelchair users, mobility-aid and visually-impaired users",
    },
    "lit": {
        "code": "improve_lighting",
        "measure": "Improve pedestrian-scale lighting",
        "benefits": "low-vision and elderly users at dusk/night",
    },
    "crossing_time": {
        "code": "extend_crossing_time",
        "measure": "Extend signal crossing time to a slower walking speed",
        "benefits": "elderly and disabled pedestrians",
    },
}


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _is_present(value: Any) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def _is_known(row: Mapping[str, Any], key: str) -> bool:
    return key in row and str(row.get(key)).strip() != ""


def elderly_exposure(row: Mapping[str, Any]) -> dict[str, Any]:
    """Elderly exposure for a segment: the 65+ casualty share where recorded,
    else an ageing-area population proxy. Returns the value and its basis."""
    elderly_casualties = _to_float(row.get("elderly_casualty_count"))
    total_casualties = _to_float(row.get("casualty_count"))
    if elderly_casualties is not None and total_casualties and total_casualties > 0:
        return {
            "elderly_exposure": round(_clamp(elderly_casualties / total_casualties), 4),
            "basis": "recorded_casualty_age",
        }
    # Proxy: share of 65+ residents in the segment's area, if available.
    elderly_pop_share = _to_float(row.get("area_elderly_population_share"))
    if elderly_pop_share is not None:
        return {
            "elderly_exposure": round(_clamp(elderly_pop_share), 4),
            "basis": "ageing_area_proxy",
        }
    return {"elderly_exposure": None, "basis": "unavailable"}


def accessibility_provision(row: Mapping[str, Any]) -> dict[str, Any]:
    """Accessibility provision score (0..100, higher = better provision) over
    disability-relevant infrastructure, with renormalised coverage and the list
    of missing provisions."""
    provided_weight = 0.0
    known_weight = 0.0
    missing: list[str] = []
    for provision, weight in ACCESSIBILITY_PROVISIONS.items():
        if not _is_known(row, provision):
            continue
        known_weight += weight
        if _is_present(row.get(provision)):
            provided_weight += weight
        else:
            missing.append(provision)
    if known_weight == 0.0:
        return {"provision_score": None, "coverage": 0.0, "missing_provisions": []}
    return {
        "provision_score": round((provided_weight / known_weight) * RISK_SCALE_MAX, 2),
        "coverage": round(known_weight / sum(ACCESSIBILITY_PROVISIONS.values()), 3),
        "missing_provisions": missing,
    }


def recommend_countermeasures(missing_provisions: Sequence[str]) -> list[dict[str, str]]:
    """Tailored elderly/disabled countermeasure profile for a segment's
    accessibility deficits."""
    recommendations = [
        COUNTERMEASURE_LIBRARY[provision]
        for provision in missing_provisions
        if provision in COUNTERMEASURE_LIBRARY
    ]
    # A signalised crossing that exists but may be too fast also warrants the
    # extended-crossing-time measure.
    return recommendations


def score_segment(row: Mapping[str, Any]) -> dict[str, Any]:
    """Per-segment elderly/disabled risk priority and countermeasure profile."""
    exposure = elderly_exposure(row)
    access = accessibility_provision(row)
    has_crossing_context = _is_present(row.get("pedestrian_crossing")) or _is_present(row.get("involves_vru"))

    exposure_value = exposure["elderly_exposure"]
    provision_score = access["provision_score"]
    deficit = None if provision_score is None else (RISK_SCALE_MAX - provision_score)

    # Priority = elderly exposure x accessibility deficit, lifted where there is
    # a pedestrian/crossing context (where these users are actually present).
    if exposure_value is None or deficit is None:
        priority = None
    else:
        context = 1.0 if has_crossing_context else 0.6
        priority = round(_clamp(exposure_value * (deficit / RISK_SCALE_MAX) * context) * RISK_SCALE_MAX, 2)

    countermeasures = recommend_countermeasures(access["missing_provisions"])
    return {
        "segment_id": str(row.get("segment_id") or row.get("section_id") or "segment"),
        "elderly_exposure": exposure_value,
        "elderly_exposure_basis": exposure["basis"],
        "accessibility_provision_score": provision_score,
        "accessibility_coverage": access["coverage"],
        "missing_provisions": access["missing_provisions"],
        "elderly_disabled_priority": priority,
        "countermeasures": countermeasures,
    }


def assess_elderly_disabled(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [score_segment(row) for row in rows]


def _summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    priorities = [r["elderly_disabled_priority"] for r in results if r["elderly_disabled_priority"] is not None]
    measure_counts: dict[str, int] = {}
    for result in results:
        for measure in result["countermeasures"]:
            measure_counts[measure["code"]] = measure_counts.get(measure["code"], 0) + 1
    return {
        "segment_count": len(results),
        "scored_count": len(priorities),
        "mean_priority": round(sum(priorities) / len(priorities), 2) if priorities else 0.0,
        "high_priority_segments": sum(1 for p in priorities if p >= 40.0),
        "countermeasure_demand": measure_counts,
    }


def run_elderly_disabled_assessment(
    *,
    segments_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Read a segment table and write elderly/disabled priority + countermeasure
    outputs (CSV + JSON + manifest), distinct from generic VRU views."""
    segments_file = Path(segments_path)
    with segments_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Segment table is empty.")

    results = assess_elderly_disabled(rows)
    ranked = sorted(
        (r for r in results if r["elderly_disabled_priority"] is not None),
        key=lambda r: r["elderly_disabled_priority"],
        reverse=True,
    )
    summary = _summary(results)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "elderly_disabled_priority.csv"
    json_path = output_root / "elderly_disabled_safety.json"
    manifest_path = output_root / "elderly_disabled_safety.manifest.json"

    fieldnames = [
        "segment_id",
        "elderly_exposure",
        "elderly_exposure_basis",
        "accessibility_provision_score",
        "accessibility_coverage",
        "elderly_disabled_priority",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    payload = {
        "elderly_disabled_version": ELDERLY_DISABLED_VERSION,
        "segment_count": len(results),
        "summary": summary,
        "countermeasure_library": COUNTERMEASURE_LIBRARY,
        "priority_segments": ranked[:15],
        "results": results,
        "lineage": _build_lineage_contract(
            run_record_path=json_path,
            upstream_inputs=[_artifact_reference("elderly_disabled_segments", segments_file, _sha256(segments_file))],
            publishable_outputs=[_artifact_reference("elderly_disabled_priority_csv", csv_path, None)],
        ),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "elderly_disabled_version": ELDERLY_DISABLED_VERSION,
        "contract": {
            "resource_name": "elderly_disabled_safety",
            "public_contract_version": ELDERLY_DISABLED_CONTRACT_VERSION,
        },
        "outputs": {
            "priority_csv_path": str(csv_path),
            "priority_csv_sha256": _sha256(csv_path),
            "summary_json_path": str(json_path),
            "summary_json_sha256": _sha256(json_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "priority_csv_path": str(csv_path),
        "summary_json_path": str(json_path),
        "manifest_path": str(manifest_path),
        "summary": summary,
    }
