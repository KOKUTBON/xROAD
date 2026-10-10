"""Per-segment drill-down service (Issue 13).

This service answers "what's behind this segment-score id?" without
loading raw row-level data into the browser. It composes the per-city
published artifacts (intervention shortlist top_segments, score-tile
focus list) into a focused payload keyed by `segment_score_id`.

Two surface variants share the same compositor:

- `build_public_segment_drill_down` returns the public-safe subset
  (banded score, qualitative intervention shortlist, no raw crash
  counts at segment level). The redaction policy mirrors the
  `public_segment_score_map` entry in `data/governance/...` (Issue 01).
- `build_analyst_segment_drill_down` returns the analyst subset (adds
  predicted vs observed counts, contributing intervention candidates,
  containing tile lineage).

Both surfaces enforce their field-visibility policy from the
`segment_score` record-kind classification matrix in
`road_risk_modeling.data_governance`. The redaction policy lives in one
place; adding a new segment-score field there automatically excludes it
from the public payload (default-deny) until its `role_visibility` is
explicitly extended.

Tracked by: docs/implementation-issues.md (Issue 13).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from apps.api.settings import ApiSettings
from road_risk_modeling.data_governance import publishable_fields_for_role


SEGMENT_DRILL_DOWN_PUBLIC_CONTRACT_VERSION = "segment_drill_down_public_v1"
SEGMENT_DRILL_DOWN_ANALYST_CONTRACT_VERSION = "segment_drill_down_analyst_v1"


class SegmentDrillDownError(RuntimeError):
    """Raised when a drill-down request cannot be resolved."""


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _resolve_path(path_value: Path, *, root_dir: Path) -> Path:
    if path_value.is_absolute():
        return path_value
    return (root_dir / path_value).resolve()


def _load_dashboard_summary(settings: ApiSettings) -> dict[str, Any]:
    path = _resolve_path(settings.dashboard_summary_path, root_dir=settings.root_dir)
    if not path.is_file():
        raise SegmentDrillDownError(f"Dashboard summary not found at: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _shortlist_for_city(summary: dict[str, Any], city_key: str) -> dict[str, Any] | None:
    for entry in summary.get("intervention_shortlists") or []:
        if str(entry.get("city_key") or "").strip() == city_key:
            return entry
    return None


def _run_for_city(summary: dict[str, Any], city_key: str) -> dict[str, Any]:
    for run in summary.get("published_runs") or []:
        if str(run.get("city_key") or "").strip() == city_key:
            return run
    available = sorted(
        {str(run.get("city_key") or "").strip() for run in summary.get("published_runs") or []}
    )
    raise SegmentDrillDownError(
        f"City '{city_key}' is not available in the published dashboard summary. "
        f"Available: {available}"
    )


def _hotspot_tiles(shortlist: dict[str, Any] | None) -> list[dict[str, Any]]:
    if shortlist is None:
        return []
    return [tile for tile in shortlist.get("hotspot_tiles") or [] if isinstance(tile, dict)]


def _top_corridors(shortlist: dict[str, Any] | None) -> list[dict[str, Any]]:
    if shortlist is None:
        return []
    return [
        corridor
        for corridor in shortlist.get("top_corridors") or []
        if isinstance(corridor, dict)
    ]


def _segment_from_tile(
    tile: dict[str, Any], segment_score_id: str
) -> dict[str, Any] | None:
    for segment in tile.get("top_segments") or []:
        if not isinstance(segment, dict):
            continue
        if segment.get("segment_score_id") == segment_score_id:
            return segment
    return None


def _segment_from_corridor(
    corridor: dict[str, Any], segment_score_id: str
) -> dict[str, Any] | None:
    for segment in corridor.get("top_segments") or []:
        if not isinstance(segment, dict):
            continue
        if segment.get("segment_score_id") == segment_score_id:
            return segment
    return None


def _locate_segment(
    summary: dict[str, Any], *, city_key: str, segment_score_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Locate the segment record + its containing tiles and corridors.

    Raises `SegmentDrillDownError` if the segment is not found in any
    public artifact for the city.
    """
    shortlist = _shortlist_for_city(summary, city_key)
    matching_tiles: list[dict[str, Any]] = []
    matching_corridors: list[dict[str, Any]] = []
    found_segment: dict[str, Any] | None = None

    for tile in _hotspot_tiles(shortlist):
        focus_ids = list(tile.get("focus_segment_score_ids") or [])
        candidate = _segment_from_tile(tile, segment_score_id)
        if candidate is None and segment_score_id not in focus_ids:
            continue
        matching_tiles.append(tile)
        if candidate is not None and found_segment is None:
            found_segment = candidate

    for corridor in _top_corridors(shortlist):
        focus_ids = list(corridor.get("segment_score_ids") or [])
        candidate = _segment_from_corridor(corridor, segment_score_id)
        if candidate is None and segment_score_id not in focus_ids:
            continue
        matching_corridors.append(corridor)
        if candidate is not None and found_segment is None:
            found_segment = candidate

    if found_segment is None and not matching_tiles and not matching_corridors:
        raise SegmentDrillDownError(
            f"Segment '{segment_score_id}' is not present in the dashboard summary for city "
            f"'{city_key}'."
        )

    return (found_segment or {}, matching_tiles, matching_corridors)


# ---------------------------------------------------------------------
# Public payload (Issue 01 redaction applied)
# ---------------------------------------------------------------------


# Per-field coercion for the `segment_score` matrix. Fields not listed
# here pass through unchanged (string-like fields).
_SEGMENT_FIELD_COERCERS: dict[str, Callable[[Any], Any]] = {
    "public_score_index": _coerce_float,
    "predicted_crash_count": _coerce_float,
    "observed_crash_count": _coerce_float,
    "score_decile": _coerce_int,
    "segment_length_m": _coerce_float,
}


def _segment_row_for_role(segment: dict[str, Any], role: str) -> dict[str, Any]:
    """Return a segment row restricted to fields publishable for `role`.

    The publishable field list comes from the `segment_score` record-kind
    classification matrix in `data_governance` (Issue 01). Adding a new
    segment-score field there automatically gates it through the same
    role check; removing or downgrading a field's `role_visibility`
    propagates here without code changes.
    """
    publishable = set(publishable_fields_for_role("segment_score", role))
    row: dict[str, Any] = {}
    for field_name in publishable:
        raw = segment.get(field_name)
        if raw is None:
            row[field_name] = None
            continue
        coerce = _SEGMENT_FIELD_COERCERS.get(field_name)
        row[field_name] = coerce(raw) if coerce is not None else raw
    return row


def _public_segment_row(segment: dict[str, Any]) -> dict[str, Any]:
    return _segment_row_for_role(segment, "public")


def _public_tile_row(tile: dict[str, Any]) -> dict[str, Any]:
    return {
        "tile_score_id": tile.get("tile_score_id"),
        "tile_public_score_band": tile.get("tile_public_score_band"),
        "tile_max_public_score_index": _coerce_float(tile.get("tile_max_public_score_index")),
        "tile_segment_count": _coerce_int(tile.get("tile_segment_count")),
        "tile_high_band_segment_count": _coerce_int(tile.get("tile_high_band_segment_count")),
        "tile_very_high_band_segment_count": _coerce_int(
            tile.get("tile_very_high_band_segment_count")
        ),
    }


def _public_corridor_row(corridor: dict[str, Any]) -> dict[str, Any]:
    return {
        "corridor_label": corridor.get("corridor_label"),
        "segment_count": _coerce_int(corridor.get("segment_count")),
        "tile_count": _coerce_int(corridor.get("tile_count")),
    }


def build_public_segment_drill_down(
    settings: ApiSettings,
    *,
    city_key: str,
    segment_score_id: str,
) -> dict[str, Any]:
    """Public-safe per-segment drill-down payload.

    Applies the `public_segment_score_map` policy from Issue 01: the
    segment band + index is published, but observed / predicted crash
    counts and other restricted fields are redacted.
    """
    summary = _load_dashboard_summary(settings)
    run = _run_for_city(summary, city_key)
    segment, tiles, corridors = _locate_segment(
        summary, city_key=city_key, segment_score_id=segment_score_id,
    )
    return {
        "contract_version": SEGMENT_DRILL_DOWN_PUBLIC_CONTRACT_VERSION,
        "city": {
            "city_key": run.get("city_key"),
            "display_name": run.get("display_name"),
            "prediction_run_label": run.get("prediction_run_label"),
        },
        "segment": _public_segment_row(segment),
        "containing_tiles": [_public_tile_row(t) for t in tiles],
        "containing_corridors": [_public_corridor_row(c) for c in corridors],
        "redaction_policy_id": "public_segment_score_map",
    }


# ---------------------------------------------------------------------
# Analyst payload (predicted/observed counts surfaced)
# ---------------------------------------------------------------------


def _analyst_segment_row(segment: dict[str, Any]) -> dict[str, Any]:
    return _segment_row_for_role(segment, "analyst")


def _analyst_tile_row(tile: dict[str, Any]) -> dict[str, Any]:
    row = _public_tile_row(tile)
    row.update(
        {
            "intersection_segment_count": _coerce_int(tile.get("intersection_segment_count")),
            "focus_segment_score_ids": list(tile.get("focus_segment_score_ids") or []),
        }
    )
    return row


def _analyst_corridor_row(corridor: dict[str, Any]) -> dict[str, Any]:
    row = _public_corridor_row(corridor)
    row.update(
        {
            "predicted_crash_total": _coerce_float(corridor.get("predicted_crash_total")),
            "observed_crash_total": _coerce_float(corridor.get("observed_crash_total")),
            "segment_score_ids": list(corridor.get("segment_score_ids") or []),
        }
    )
    return row


def build_analyst_segment_drill_down(
    settings: ApiSettings,
    *,
    city_key: str,
    segment_score_id: str,
) -> dict[str, Any]:
    """Analyst per-segment drill-down payload.

    Adds predicted vs observed crash counts, containing tile / corridor
    lineage with focus-set ids, and any directly attached metadata
    needed to drive the analyst drill-down panel.
    """
    summary = _load_dashboard_summary(settings)
    run = _run_for_city(summary, city_key)
    segment, tiles, corridors = _locate_segment(
        summary, city_key=city_key, segment_score_id=segment_score_id,
    )
    return {
        "contract_version": SEGMENT_DRILL_DOWN_ANALYST_CONTRACT_VERSION,
        "city": {
            "city_key": run.get("city_key"),
            "display_name": run.get("display_name"),
            "prediction_run_label": run.get("prediction_run_label"),
        },
        "segment": _analyst_segment_row(segment),
        "containing_tiles": [_analyst_tile_row(t) for t in tiles],
        "containing_corridors": [_analyst_corridor_row(c) for c in corridors],
        "redaction_policy_id": None,
    }


__all__ = [
    "SEGMENT_DRILL_DOWN_ANALYST_CONTRACT_VERSION",
    "SEGMENT_DRILL_DOWN_PUBLIC_CONTRACT_VERSION",
    "SegmentDrillDownError",
    "build_analyst_segment_drill_down",
    "build_public_segment_drill_down",
]
