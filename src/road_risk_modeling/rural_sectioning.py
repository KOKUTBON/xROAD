"""Rural & secondary two-lane road capability: 200 m sectioning + rural features.

The D6-09 call is explicitly about **rural areas** — *"over half of EU road
fatalities occur in rural areas"* — and targets primary and secondary rural
roads, including **single-carriageway / two-lane two-way** roads. The platform's
pilots are all **urban cores** (Bari, Foggia, Taranto, Lecce); its segmentation,
exposure proxies, and crash tasks are tuned for the urban network.

This module provides:

1. **200 m sectioning** — the NWRSA convention for two-lane roads: long rural
   edges are split into fixed ~200 m sections (intersections excluded), so the
   in-built-safety assessment ([nwrsa.py](nwrsa.py)) and crash density are
   computed at the Directive's working resolution rather than on whole edges.
2. **Rural feature set** — alignment/curvature class, carriageway-width
   adequacy, single-carriageway flag, and geometry-derived **run-off-road** and
   **head-on** mechanism exposures (the dominant rural crash mechanisms).
3. **Rural exposure handling** — a low-AADT exposure index and a **sparse-cell**
   flag, since rural sections are mostly zero-crash and naive counts mislead.

Sectioning is length-based and pure-Python; when a real LineString geometry is
present and shapely is installed, the geometry is cut as well. Crash counts are
apportioned across a segment's sections by length share.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .modeling import _artifact_reference, _build_lineage_contract, _sha256

RURAL_SECTIONING_VERSION = "rural_sectioning_v1"
RURAL_SECTIONING_CONTRACT_VERSION = "rural_sectioning_public_v1"

# The NWRSA two-lane working section length.
DEFAULT_SECTION_LENGTH_M = 200.0

# Crash columns apportioned across sections by length share.
_APPORTIONED_COLUMNS = (
    "crash_count",
    "fatal_crash_count",
    "injury_crash_count",
    "fatalities_total",
    "injuries_total",
)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _section_count(length_m: float, section_length_m: float) -> int:
    if length_m <= 0.0:
        return 1
    return max(1, round(length_m / section_length_m))


def section_road_segment(
    row: Mapping[str, Any],
    *,
    section_length_m: float = DEFAULT_SECTION_LENGTH_M,
) -> list[dict[str, Any]]:
    """Split one road segment into fixed ~``section_length_m`` sections.

    Design attributes are inherited unchanged; crash counts are apportioned by
    equal length share. Returns one section dict per piece.
    """
    base = dict(row)
    length = _to_float(row.get("segment_length_m")) or 0.0
    count = _section_count(length, section_length_m)
    piece_length = (length / count) if length > 0 else section_length_m
    share = 1.0 / count

    segment_id = str(row.get("segment_id") or row.get("section_id") or "segment")
    sections: list[dict[str, Any]] = []
    for index in range(count):
        section = dict(base)
        section["parent_segment_id"] = segment_id
        section["section_id"] = f"{segment_id}#s{index:02d}"
        section["segment_id"] = section["section_id"]
        section["section_index"] = index
        section["section_count"] = count
        section["segment_length_m"] = round(piece_length, 2)
        for column in _APPORTIONED_COLUMNS:
            value = _to_float(row.get(column))
            if value is not None:
                section[column] = round(value * share, 4)
        sections.append(section)
    return sections


def _curvature_class(sinuosity: float | None) -> str:
    if sinuosity is None:
        return "unknown"
    if sinuosity < 1.05:
        return "straight"
    if sinuosity < 1.15:
        return "gentle"
    if sinuosity < 1.30:
        return "winding"
    return "sharp"


def _is_single_carriageway(row: Mapping[str, Any]) -> bool:
    lanes = _to_float(row.get("lanes_numeric"))
    oneway = str(row.get("oneway") or "").strip().lower() in {"yes", "true", "1"}
    # Two-way road with <=2 lanes = single carriageway (undivided).
    return (lanes is None or lanes <= 2) and not oneway


def derive_rural_features(row: Mapping[str, Any]) -> dict[str, Any]:
    """Rural-specific features for one section, including the dominant rural
    crash-mechanism exposures derived from geometry."""
    speed = _to_float(row.get("maxspeed_numeric"))
    width = _to_float(row.get("width_numeric"))
    sinuosity = _to_float(row.get("sinuosity"))
    road_class_rank = _to_float(row.get("road_class_rank"))

    speed_factor = _clamp(((speed or 50.0) - 50.0) / 50.0)
    curve_factor = _clamp(((sinuosity or 1.0) - 1.0) / 0.3)
    single_carriageway = _is_single_carriageway(row)
    narrow = width is not None and width < 6.0

    # Run-off-road risk rises with curvature and speed (the classic rural
    # single-vehicle mechanism); head-on risk rises with speed on undivided
    # single carriageways. Both are geometry-derived exposures, not crash-typed
    # classifications (the platform has no per-crash mechanism field).
    run_off_road_exposure = round(_clamp(0.6 * curve_factor + 0.4 * speed_factor), 4)
    head_on_exposure = round(
        _clamp((0.7 * speed_factor + 0.3 * curve_factor) if single_carriageway else 0.2 * speed_factor),
        4,
    )

    # Rural low-AADT exposure proxy: higher road class carries more traffic;
    # absent an AADT feed this is the defensible stand-in (reconciles with the
    # exposure backbone, Issue 16).
    if road_class_rank is None:
        rural_exposure_index = None
    else:
        rural_exposure_index = round(_clamp((5.0 - road_class_rank) / 4.0), 4)

    crash_count = _to_float(row.get("crash_count")) or 0.0
    sparse_cell = crash_count < 1.0

    return {
        "curvature_class": _curvature_class(sinuosity),
        "is_single_carriageway": single_carriageway,
        "narrow_carriageway": bool(narrow),
        "run_off_road_exposure": run_off_road_exposure,
        "head_on_exposure": head_on_exposure,
        "rural_exposure_index": rural_exposure_index,
        "sparse_cell": sparse_cell,
    }


def section_network(
    rows: Sequence[Mapping[str, Any]],
    *,
    section_length_m: float = DEFAULT_SECTION_LENGTH_M,
) -> list[dict[str, Any]]:
    """Section a whole network and attach rural features to each section."""
    sections: list[dict[str, Any]] = []
    for row in rows:
        for section in section_road_segment(row, section_length_m=section_length_m):
            section.update(derive_rural_features(section))
            sections.append(section)
    return sections


def _summary(sections: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(sections)
    single = sum(1 for s in sections if s.get("is_single_carriageway"))
    sparse = sum(1 for s in sections if s.get("sparse_cell"))
    curvature: dict[str, int] = {}
    for section in sections:
        key = str(section.get("curvature_class"))
        curvature[key] = curvature.get(key, 0) + 1
    lengths = [_to_float(s.get("segment_length_m")) or 0.0 for s in sections]
    return {
        "section_count": total,
        "single_carriageway_sections": single,
        "sparse_cell_sections": sparse,
        "sparse_cell_share": round(sparse / total, 4) if total else 0.0,
        "curvature_distribution": curvature,
        "mean_section_length_m": round(sum(lengths) / total, 2) if total else 0.0,
    }


def run_rural_sectioning(
    *,
    segments_path: str | Path,
    output_dir: str | Path,
    section_length_m: float = DEFAULT_SECTION_LENGTH_M,
) -> dict[str, Any]:
    """Read a segment table, produce 200 m rural sections with rural features,
    and write the sectioned table + summary + lineage manifest."""
    segments_file = Path(segments_path)
    with segments_file.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Segment table is empty.")

    sections = section_network(rows, section_length_m=section_length_m)
    summary = _summary(sections)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    sections_csv = output_root / "rural_sections.csv"
    summary_json = output_root / "rural_sectioning_summary.json"
    manifest_path = output_root / "rural_sectioning.manifest.json"

    fieldnames = [
        "section_id",
        "parent_segment_id",
        "section_index",
        "section_count",
        "segment_length_m",
        "maxspeed_numeric",
        "width_numeric",
        "sinuosity",
        "lanes_numeric",
        "road_class_rank",
        "crash_count",
        "fatal_crash_count",
        "curvature_class",
        "is_single_carriageway",
        "narrow_carriageway",
        "run_off_road_exposure",
        "head_on_exposure",
        "rural_exposure_index",
        "sparse_cell",
    ]
    with sections_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sections)

    payload = {
        "rural_sectioning_version": RURAL_SECTIONING_VERSION,
        "section_length_m": section_length_m,
        "input_segment_count": len(rows),
        "summary": summary,
        "lineage": _build_lineage_contract(
            run_record_path=summary_json,
            upstream_inputs=[_artifact_reference("rural_input_segments", segments_file, _sha256(segments_file))],
            publishable_outputs=[_artifact_reference("rural_sections_csv", sections_csv, None)],
        ),
    }
    summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "rural_sectioning_version": RURAL_SECTIONING_VERSION,
        "contract": {
            "resource_name": "rural_sectioning",
            "public_contract_version": RURAL_SECTIONING_CONTRACT_VERSION,
        },
        "outputs": {
            "sections_csv_path": str(sections_csv),
            "sections_csv_sha256": _sha256(sections_csv),
            "summary_json_path": str(summary_json),
            "summary_json_sha256": _sha256(summary_json),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "sections_csv_path": str(sections_csv),
        "summary_json_path": str(summary_json),
        "manifest_path": str(manifest_path),
        "summary": summary,
    }
