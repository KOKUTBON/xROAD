"""Climate-resilience scoring: extreme-weather impact on road-network safety.

The D6-09 call requires a *"GIS-based application to assist local and regional
authorities in identifying and mapping the impact"* of **extreme weather** on
**road-network safety and infrastructure resilience**. Weather was a **missing
layer** on the platform. This module adds the data foundation and a map-ready
surface.

It provides:

1. **Hazard ingestion** — per-segment exposure to the four extreme-weather
   hazard families (flood, heat, snow/ice, wind), the shape a Copernicus/EEA
   climate-hazard join produces.
2. **Weather-conditioned crash risk** — the relative risk of crashes under
   adverse conditions vs the baseline, from the crash record's weather split.
3. **Infrastructure-resilience scoring** — a transparent per-segment climate
   risk that multiplies hazard exposure by an attribute-derived structural
   **vulnerability**, amplified by the observed adverse-weather crash signal.
4. **A map-ready GeoJSON surface** the apps/web risk map can render, plus
   data-governance classifications for the new weather/hazard record kinds.

Scoring is rule-based and auditable (a resilience classification informs public
investment, so it must be inspectable). See ``docs/climate-resilience.md``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .data_governance import (
    CLASSIFICATION_INTERNAL,
    CLASSIFICATION_PUBLIC,
    FieldClassification,
)
from .modeling import _artifact_reference, _build_lineage_contract, _sha256

CLIMATE_RESILIENCE_VERSION = "climate_resilience_v1"
CLIMATE_RESILIENCE_CONTRACT_VERSION = "climate_resilience_public_v1"

# The four extreme-weather hazard families the call names.
HAZARD_KINDS: tuple[str, ...] = ("flood", "heat", "snow_ice", "wind")

RISK_SCALE_MAX = 100.0

# Documented fallback weights used only where no trained WX-02 profile exists.
HAZARD_WEIGHTS: dict[str, float] = {
    "flood": 0.32,
    "snow_ice": 0.28,
    "wind": 0.22,
    "heat": 0.18,
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


def _is_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def ingest_hazard_layer(
    hazard_records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    """Fold hazard-grid records into per-segment hazard exposures.

    Each record carries ``segment_id``, ``hazard_kind`` (one of HAZARD_KINDS),
    and ``intensity`` in [0, 1] (e.g. a normalised Copernicus/EEA hazard index).
    Returns ``segment_id -> {hazard_kind: max_intensity}`` (the worst exposure
    per hazard wins when a segment spans several hazard cells).
    """
    exposures: dict[str, dict[str, float]] = {}
    for record in hazard_records:
        segment_id = record.get("segment_id") or record.get("section_id")
        kind = str(record.get("hazard_kind") or "").strip().lower()
        intensity = _to_float(record.get("intensity"))
        if segment_id is None or kind not in HAZARD_KINDS or intensity is None:
            continue
        bucket = exposures.setdefault(str(segment_id), {})
        bucket[kind] = max(bucket.get(kind, 0.0), _clamp(intensity))
    return exposures


def _structural_vulnerability(row: Mapping[str, Any], hazard: str) -> float:
    """Attribute-derived structural vulnerability of a segment to one hazard."""
    speed = _to_float(row.get("maxspeed_numeric")) or 50.0
    sinuosity = _to_float(row.get("sinuosity")) or 1.0
    has_bridge = _is_truthy(row.get("bridge"))
    has_tunnel = _is_truthy(row.get("tunnel"))
    road_class_rank = _to_float(row.get("road_class_rank")) or 3.0
    speed_factor = _clamp((speed - 50.0) / 50.0)
    curve_factor = _clamp((sinuosity - 1.0) / 0.3)

    if hazard == "flood":
        # Bridges, tunnels and underpasses are the flood-critical structures.
        return _clamp(0.5 + 0.5 * (1.0 if (has_bridge or has_tunnel) else 0.0))
    if hazard == "snow_ice":
        # Ice risk concentrates on fast, curvy sections (and bridges freeze first).
        return _clamp(0.4 * speed_factor + 0.4 * curve_factor + (0.2 if has_bridge else 0.0))
    if hazard == "wind":
        # Exposed structures (bridges, embankments) take the wind load.
        return _clamp(0.4 + (0.6 if has_bridge else 0.2 * speed_factor))
    if hazard == "heat":
        # Heat degrades higher-traffic (higher-class) pavements fastest.
        return _clamp((5.0 - road_class_rank) / 4.0)
    return 0.0


def weather_conditioned_risk(row: Mapping[str, Any]) -> float | None:
    """Relative crash risk under adverse weather vs baseline for one segment.

    Uses the crash record's adverse/total split. Returns a multiplier ≥ 1.0
    where adverse-weather crashes are over-represented, or ``None`` if the split
    is unavailable. Capped at 3.0 to bound sparse-cell noise.
    """
    total = _to_float(row.get("crash_count"))
    adverse = _to_float(row.get("adverse_weather_crash_count"))
    if total is None or adverse is None or total <= 0:
        return None
    adverse_share = _clamp(adverse / total)
    # Baseline expectation: adverse conditions are present a minority of the time
    # (~25%); over-representation above that is the conditioned risk.
    baseline_share = 0.25
    return round(1.0 + max(0.0, adverse_share - baseline_share) / baseline_share, 4)


def score_segment_climate_risk(
    row: Mapping[str, Any],
    hazard_exposure: Mapping[str, float] | None,
) -> dict[str, Any]:
    """Per-segment climate-resilience risk (0..100, higher = least resilient)."""
    hazard_exposure = hazard_exposure or {}
    trained_weights = row.get("weather_model_hazard_weights")
    weights = (
        {hazard: _to_float(trained_weights.get(hazard)) or 0.0 for hazard in HAZARD_KINDS}
        if isinstance(trained_weights, Mapping)
        else HAZARD_WEIGHTS
    )
    per_hazard: dict[str, float] = {}
    weighted = 0.0
    total_weight = 0.0
    for hazard in HAZARD_KINDS:
        exposure = _clamp(_to_float(hazard_exposure.get(hazard)) or 0.0)
        vulnerability = _structural_vulnerability(row, hazard)
        component = exposure * vulnerability
        per_hazard[hazard] = round(component, 4)
        weighted += weights[hazard] * component
        total_weight += weights[hazard]
    base_risk = (weighted / total_weight) * RISK_SCALE_MAX if total_weight else 0.0

    trained_multiplier = _to_float(row.get("weather_model_multiplier"))
    multiplier = trained_multiplier if trained_multiplier is not None else weather_conditioned_risk(row)
    conditioned = base_risk * multiplier if multiplier is not None else base_risk
    # The conditioned amplification can exceed the base scale; clamp to 0..100.
    climate_risk = round(_clamp(conditioned, 0.0, RISK_SCALE_MAX), 2)

    dominant = max(per_hazard, key=lambda key: per_hazard[key]) if per_hazard else None
    return {
        "climate_risk_score": climate_risk,
        "base_hazard_risk": round(base_risk, 2),
        "weather_conditioned_multiplier": multiplier,
        "weather_conditioned_multiplier_low": _to_float(
            row.get("weather_model_multiplier_low")
        ),
        "weather_conditioned_multiplier_high": _to_float(
            row.get("weather_model_multiplier_high")
        ),
        "weather_risk_source": "trained_model" if trained_multiplier is not None else "heuristic_fallback",
        "hazard_weights": weights,
        "per_hazard_component": per_hazard,
        "dominant_hazard": dominant if (dominant and per_hazard[dominant] > 0) else None,
    }


def assess_climate_resilience(
    rows: Sequence[Mapping[str, Any]],
    hazard_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Score a whole network's climate resilience."""
    exposures = ingest_hazard_layer(hazard_records)
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        segment_id = str(row.get("segment_id") or row.get("section_id") or f"row-{index}")
        scored = score_segment_climate_risk(row, exposures.get(segment_id))
        results.append(
            {
                "segment_id": segment_id,
                "latitude": _to_float(row.get("latitude")),
                "longitude": _to_float(row.get("longitude")),
                **scored,
            }
        )
    return results


def _geojson_surface(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A map-ready GeoJSON FeatureCollection the apps/web risk map can render."""
    features = []
    for result in results:
        lat, lon = result.get("latitude"), result.get("longitude")
        if lat is None or lon is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "segment_id": result["segment_id"],
                    "climate_risk_score": result["climate_risk_score"],
                    "dominant_hazard": result["dominant_hazard"],
                    "weather_conditioned_multiplier": result["weather_conditioned_multiplier"],
                    "weather_conditioned_multiplier_low": result.get("weather_conditioned_multiplier_low"),
                    "weather_conditioned_multiplier_high": result.get("weather_conditioned_multiplier_high"),
                    "weather_risk_source": result.get("weather_risk_source"),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


# Data-governance classifications for the new weather/hazard record kinds. These
# are declared here and should be merged into the central registry in
# `data_governance.py`; hazard exposures are publishable, raw provider feeds are
# internal under provider terms.
CLIMATE_FIELD_CLASSIFICATIONS: tuple[FieldClassification, ...] = (
    FieldClassification(
        field_name="hazard_kind",
        record_kind="climate_hazard",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Hazard family (flood/heat/snow_ice/wind); non-personal, safe to publish.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="climate_risk_score",
        record_kind="climate_resilience",
        classification=CLASSIFICATION_PUBLIC,
        rationale="Aggregate segment-level resilience score; the public map surface.",
        publishable_in_aggregate=True,
        role_visibility=("public", "municipality_viewer", "analyst", "data_operator", "admin"),
    ),
    FieldClassification(
        field_name="hazard_intensity_raw",
        record_kind="climate_hazard",
        classification=CLASSIFICATION_INTERNAL,
        rationale="Raw provider hazard-grid intensity; retained internally under provider licensing terms.",
    ),
)


def _summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scores = [r["climate_risk_score"] for r in results if r["climate_risk_score"] is not None]
    dominant_counts: dict[str, int] = {}
    for result in results:
        hazard = result.get("dominant_hazard")
        if hazard:
            dominant_counts[hazard] = dominant_counts.get(hazard, 0) + 1
    high_risk = sum(1 for s in scores if s >= 50.0)
    return {
        "segment_count": len(results),
        "scored_count": len(scores),
        "mean_climate_risk": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "max_climate_risk": max(scores) if scores else 0.0,
        "high_risk_segments": high_risk,
        "dominant_hazard_distribution": dominant_counts,
    }


def run_climate_resilience_assessment(
    *,
    segments_path: str | Path,
    hazards_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Read segment + hazard tables, score climate resilience, and write a
    classification CSV, a map-ready GeoJSON, a summary JSON, and a manifest."""
    segments_file = Path(segments_path)
    hazards_file = Path(hazards_path)
    with segments_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with hazards_file.open("r", encoding="utf-8", newline="") as handle:
        hazard_records = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Segment table is empty.")

    results = assess_climate_resilience(rows, hazard_records)
    summary = _summary(results)
    geojson = _geojson_surface(results)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "climate_resilience.csv"
    geojson_path = output_root / "climate_risk_surface.geojson"
    summary_json = output_root / "climate_resilience.json"
    manifest_path = output_root / "climate_resilience.manifest.json"

    fieldnames = [
        "segment_id",
        "climate_risk_score",
        "base_hazard_risk",
        "weather_conditioned_multiplier",
        "dominant_hazard",
        "latitude",
        "longitude",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    geojson_path.write_text(json.dumps(geojson, indent=2, sort_keys=True), encoding="utf-8")

    payload = {
        "climate_resilience_version": CLIMATE_RESILIENCE_VERSION,
        "hazard_kinds": list(HAZARD_KINDS),
        "hazard_weights": HAZARD_WEIGHTS,
        "summary": summary,
        "governance": [c.to_dict() for c in CLIMATE_FIELD_CLASSIFICATIONS],
        "results": results,
        "lineage": _build_lineage_contract(
            run_record_path=summary_json,
            upstream_inputs=[
                _artifact_reference("climate_segments", segments_file, _sha256(segments_file)),
                _artifact_reference("climate_hazards", hazards_file, _sha256(hazards_file)),
            ],
            publishable_outputs=[
                _artifact_reference("climate_resilience_csv", csv_path, None),
                _artifact_reference("climate_risk_surface_geojson", geojson_path, None),
            ],
        ),
    }
    summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "climate_resilience_version": CLIMATE_RESILIENCE_VERSION,
        "contract": {
            "resource_name": "climate_resilience",
            "public_contract_version": CLIMATE_RESILIENCE_CONTRACT_VERSION,
        },
        "outputs": {
            "classification_csv_path": str(csv_path),
            "classification_csv_sha256": _sha256(csv_path),
            "geojson_path": str(geojson_path),
            "geojson_sha256": _sha256(geojson_path),
            "summary_json_path": str(summary_json),
            "summary_json_sha256": _sha256(summary_json),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "classification_csv_path": str(csv_path),
        "geojson_path": str(geojson_path),
        "summary_json_path": str(summary_json),
        "manifest_path": str(manifest_path),
        "summary": summary,
    }
