"""VRU + signal-phase operational product surfaces.

This service exposes the existing analytics artifacts as
analyst-scoped product views:

- VRU exposure bundles (segment, crossing, corridor priorities)
- signal-phase coverage rollup
- signal-phase target dossiers (per-junction request packets)
- signal-phase operator board (ready + hold queues for the request
  lifecycle)

Everything is read-only at this step. Write-side controls (acknowledge
a hold, assign a packet) belong to a follow-on issue.

"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apps.api.settings import ApiSettings


VRU_SUMMARY_CONTRACT_VERSION = "vru_summary_v1"
VRU_DETAIL_CONTRACT_VERSION = "vru_detail_v1"
SIGNAL_PHASE_COVERAGE_CONTRACT_VERSION = "signal_phase_coverage_product_v1"
SIGNAL_PHASE_TARGETS_CONTRACT_VERSION = "signal_phase_targets_product_v1"
SIGNAL_PHASE_OPERATOR_BOARD_CONTRACT_VERSION = "signal_phase_operator_board_product_v1"
TRAFFIC_OPERATIONS_CAPABILITIES_CONTRACT_VERSION = "traffic_operations_capabilities_v1"
SIGNAL_PHASE_OVERVIEW_CONTRACT_VERSION = "signal_phase_overview_v1"

BARI_CITY_KEY = "bari"
BARI_DISPLAY_NAME = "Bari"

DEFAULT_VRU_BUNDLE_RELATIVE_PATH = Path(
    "data/planning/vru_exposure/bari_frequency_baseline_context_v2/vru_exposure_bundle.json"
)
DEFAULT_SIGNAL_PHASE_COVERAGE_RELATIVE_PATH = Path(
    "data/reporting/signal_phase_coverage/bari_sample/signal_phase_coverage.json"
)
DEFAULT_SIGNAL_PHASE_TARGETS_RELATIVE_PATH = Path(
    "data/reporting/signal_phase_targets/bari/signal_phase_target_bundle.json"
)
DEFAULT_SIGNAL_PHASE_OPERATOR_BOARD_RELATIVE_PATH = Path(
    "data/reporting/signal_phase_operator_board/bari/signal_phase_operator_board_bundle.json"
)


class VruSignalsError(RuntimeError):
    """Raised when a VRU or signal-phase request cannot be resolved."""


def _normalize_city_key(city_key: str) -> str:
    return city_key.strip().lower()


def _resolve_path(path_value: Path, *, root_dir: Path) -> Path:
    if path_value.is_absolute():
        return path_value
    return (root_dir / path_value).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise VruSignalsError(f"Missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "available": path.is_file(),
    }


def _vru_bundle_path(settings: ApiSettings, *, city_key: str) -> Path:
    # Foundation step only ships the Bari bundle. Additional cities are
    # added by mapping `city_key` to its bundle path here once they exist.
    if _normalize_city_key(city_key) != BARI_CITY_KEY:
        raise VruSignalsError(
            f"No VRU exposure bundle is registered for city '{city_key}'."
        )
    return _resolve_path(DEFAULT_VRU_BUNDLE_RELATIVE_PATH, root_dir=settings.root_dir)


def _signal_phase_coverage_path(settings: ApiSettings, *, city_key: str) -> Path:
    if _normalize_city_key(city_key) != BARI_CITY_KEY:
        raise VruSignalsError(
            f"No signal-phase coverage report is registered for city '{city_key}'."
        )
    return _resolve_path(DEFAULT_SIGNAL_PHASE_COVERAGE_RELATIVE_PATH, root_dir=settings.root_dir)


def _signal_phase_targets_path(settings: ApiSettings, *, city_key: str) -> Path:
    if _normalize_city_key(city_key) != BARI_CITY_KEY:
        raise VruSignalsError(
            f"No signal-phase target bundle is registered for city '{city_key}'."
        )
    return _resolve_path(DEFAULT_SIGNAL_PHASE_TARGETS_RELATIVE_PATH, root_dir=settings.root_dir)


def _signal_phase_operator_board_path(settings: ApiSettings, *, city_key: str) -> Path:
    if _normalize_city_key(city_key) != BARI_CITY_KEY:
        raise VruSignalsError(
            f"No signal-phase operator board is registered for city '{city_key}'."
        )
    return _resolve_path(
        DEFAULT_SIGNAL_PHASE_OPERATOR_BOARD_RELATIVE_PATH,
        root_dir=settings.root_dir,
    )


def _capability(
    *,
    capability_id: str,
    label: str,
    status: str,
    enabled: bool,
    visibility: str,
    release_stage: str,
    minimum_role: str,
    confidence_label: str,
    governance_label: str,
    reason: str,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "capability_id": capability_id,
        "label": label,
        "status": status,
        "enabled": enabled,
        "visibility": visibility,
        "release_stage": release_stage,
        "minimum_role": minimum_role,
        "confidence_label": confidence_label,
        "governance_label": governance_label,
        "reason": reason,
        "artifacts": artifacts or {},
    }


def build_traffic_operations_capabilities(
    settings: ApiSettings, *, city_key: str,
) -> dict[str, Any]:
    """Describe the v1 production boundary for VRU and signal-phase operations."""
    normalized_city_key = _normalize_city_key(city_key)
    is_bari = normalized_city_key == BARI_CITY_KEY

    vru_artifact = _artifact_status(
        _resolve_path(DEFAULT_VRU_BUNDLE_RELATIVE_PATH, root_dir=settings.root_dir)
    )
    coverage_artifact = _artifact_status(
        _resolve_path(
            DEFAULT_SIGNAL_PHASE_COVERAGE_RELATIVE_PATH,
            root_dir=settings.root_dir,
        )
    )
    targets_artifact = _artifact_status(
        _resolve_path(DEFAULT_SIGNAL_PHASE_TARGETS_RELATIVE_PATH, root_dir=settings.root_dir)
    )
    board_artifact = _artifact_status(
        _resolve_path(
            DEFAULT_SIGNAL_PHASE_OPERATOR_BOARD_RELATIVE_PATH,
            root_dir=settings.root_dir,
        )
    )

    vru_available = is_bari and bool(vru_artifact["available"])
    signal_artifacts_available = is_bari and all(
        bool(item["available"])
        for item in (coverage_artifact, targets_artifact, board_artifact)
    )
    signal_preview_enabled = (
        bool(settings.traffic_operations_signal_preview_enabled)
        and signal_artifacts_available
    )

    unsupported_reason = (
        "V1.0 traffic operations are registered for the Bari pilot only. "
        "This city is planned for v1.5 onboarding once governed VRU and signal-phase artifacts exist."
    )

    if not is_bari:
        vru_status = "unsupported_city"
        signal_status = "unsupported_city"
        city_reason = unsupported_reason
    elif not vru_available and not signal_artifacts_available:
        vru_status = "no_data"
        signal_status = "no_data"
        city_reason = "Bari is in scope, but required VRU and signal-phase artifacts are not available."
    else:
        vru_status = "v1_supported" if vru_available else "no_data"
        if not signal_artifacts_available:
            signal_status = "no_data"
        elif signal_preview_enabled:
            signal_status = "preview"
        else:
            signal_status = "v1_5_gated"
        city_reason = (
            "Bari has the v1.0 VRU operations baseline. Signal-phase operations "
            "are exposed as read-only preview evidence and remain v1.5 for live send/writeback controls."
        )

    vru_reason = (
        "Bari VRU priorities are available as a v1.0 screening workflow with proxy-backed exposure labels."
        if vru_available
        else (
            "The Bari VRU artifact is missing; show a no-data state until the bundle is generated."
            if is_bari
            else unsupported_reason
        )
    )
    signal_reason = (
        "Signal-phase evidence is visible as a read-only v1.5 preview; live dispatch send, delivery writeback, and provider integrations are not enabled in v1.0."
        if signal_preview_enabled
        else (
            "Signal-phase preview is disabled by ROAD_RISK_API_TRAFFIC_OPERATIONS_SIGNAL_PREVIEW_ENABLED."
            if is_bari and signal_artifacts_available
            else (
                "Required Bari signal-phase coverage, target, or operator-board artifacts are missing."
                if is_bari
                else unsupported_reason
            )
        )
    )

    capabilities = [
        _capability(
            capability_id="vru_priority_intelligence",
            label="VRU priority intelligence",
            status=vru_status,
            enabled=vru_available,
            visibility="visible" if vru_available else "empty_state",
            release_stage="v1.0",
            minimum_role="traffic_engineer",
            confidence_label="Medium - proxy exposure, crash, crossing, and corridor signals",
            governance_label="Internal municipal operations; proxy demand assumptions must stay visible",
            reason=vru_reason,
            artifacts={"vru_exposure_bundle": vru_artifact},
        ),
        _capability(
            capability_id="vru_corridor_priorities",
            label="VRU corridor priorities",
            status=vru_status,
            enabled=vru_available,
            visibility="visible" if vru_available else "empty_state",
            release_stage="v1.0",
            minimum_role="traffic_engineer",
            confidence_label="Medium - ranked screening layer, not observed pedestrian counts",
            governance_label="Internal municipal operations; safe for scoped traffic-engineering users",
            reason=vru_reason,
            artifacts={"vru_exposure_bundle": vru_artifact},
        ),
        _capability(
            capability_id="signal_phase_coverage",
            label="Signal-phase coverage evidence",
            status=signal_status,
            enabled=signal_preview_enabled,
            visibility=(
                "preview"
                if signal_preview_enabled
                else "empty_state"
                if is_bari and not signal_artifacts_available
                else "hidden"
            ),
            release_stage="v1.5_preview" if signal_preview_enabled else "v1.5",
            minimum_role="traffic_engineer",
            confidence_label="Low-medium - provider coverage and request lifecycle evidence are incomplete",
            governance_label="Restricted traffic-engineering preview; no public publication",
            reason=signal_reason,
            artifacts={
                "coverage": coverage_artifact,
                "targets": targets_artifact,
            },
        ),
        _capability(
            capability_id="signal_phase_operator_board",
            label="Signal-phase operator board",
            status=signal_status,
            enabled=signal_preview_enabled,
            visibility=(
                "preview_read_only"
                if signal_preview_enabled
                else "empty_state"
                if is_bari and not signal_artifacts_available
                else "hidden"
            ),
            release_stage="v1.5_preview" if signal_preview_enabled else "v1.5",
            minimum_role="traffic_engineer",
            confidence_label="Low - read-only queue over no-send/no-writeback baseline",
            governance_label="Restricted traffic-engineering preview; external send/writeback controls disabled",
            reason=signal_reason,
            artifacts={"operator_board": board_artifact},
        ),
    ]

    return {
        "contract_version": TRAFFIC_OPERATIONS_CAPABILITIES_CONTRACT_VERSION,
        "city": {
            "city_key": normalized_city_key,
            "display_name": BARI_DISPLAY_NAME if is_bari else city_key.strip() or city_key,
        },
        "production_scope": {
            "status": "v1_supported" if vru_available else "not_supported",
            "supported_for_v1": vru_available,
            "reason": city_reason,
        },
        "feature_flags": {
            "signal_phase_preview_enabled": bool(settings.traffic_operations_signal_preview_enabled),
        },
        "ui_policy": {
            "show_operations_board": vru_available or signal_preview_enabled,
            "show_vru_panels": vru_available,
            "fetch_vru_summary": vru_available,
            "fetch_vru_corridors": vru_available,
            "show_signal_phase_preview": signal_preview_enabled,
            "fetch_signal_phase_overview": signal_preview_enabled,
            "show_signal_operator_board": signal_preview_enabled,
            "allow_signal_write_actions": False,
            "unsupported_message": city_reason,
        },
        "release_boundary": {
            "v1_0_included": [
                "Bari VRU planning highlights",
                "Bari top VRU corridor ranking",
                "Bari proxy/confidence/governance labels",
            ],
            "v1_0_preview": [
                "Bari signal-phase coverage evidence",
                "Bari read-only signal-phase operator queues",
            ] if signal_preview_enabled else [],
            "v1_0_excluded": [
                "live signal-phase dispatch send",
                "signal-phase delivery writeback",
                "external signal-controller integrations",
                "multi-city VRU/signal operational onboarding beyond Bari",
            ],
            "v1_5_candidates": [
                "live dispatch and delivery validation UI",
                "provider-backed signal controller ingestion",
                "observed pedestrian, cyclist, and micromobility count ingestion",
                "multi-city operational signal-phase rollout",
            ],
        },
        "capability_count": len(capabilities),
        "capabilities": capabilities,
    }


# ---------------------------------------------------------------------
# VRU exposure
# ---------------------------------------------------------------------


def _top_segment_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": record.get("segment_id"),
        "segment_label": record.get("segment_label") or record.get("corridor_label"),
        "corridor_label": record.get("corridor_label"),
        "predicted_crash_count": record.get("predicted_crash_count"),
        "observed_crash_count": record.get("observed_crash_count"),
        "public_score_index": record.get("public_score_index"),
        "ageing_user_exposure_index": record.get("ageing_user_exposure_index"),
        "micromobility_corridor_index": record.get("micromobility_corridor_index"),
        "transit_access_index": record.get("transit_access_index"),
        "school_frontage_index": record.get("school_frontage_index"),
        "retail_frontage_index": record.get("retail_frontage_index"),
    }


def _top_crossing_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "crossing_id": record.get("crossing_id"),
        "crossing_name": record.get("crossing_name"),
        "corridor_label": record.get("corridor_label"),
        "junction_id": record.get("junction_id"),
        "control_state": record.get("control_state"),
        "crossing_protection_state": record.get("crossing_protection_state"),
        "phase_priority_group": record.get("phase_priority_group"),
        "priority_rule": record.get("priority_rule"),
        "predicted_crash_count": record.get("predicted_crash_count"),
        "observed_crash_count": record.get("observed_crash_count"),
        "pedestrian_crossing_priority_score": record.get("pedestrian_crossing_priority_score"),
        "ageing_crossing_priority_score": record.get("ageing_crossing_priority_score"),
        "crossing_continuity_gap_index": record.get("crossing_continuity_gap_index"),
        "crossing_protection_gap_index": record.get("crossing_protection_gap_index"),
    }


def _top_corridor_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "corridor_label": record.get("corridor_label"),
        "crossing_count": record.get("crossing_count"),
        "protected_crossing_gap_count": record.get("protected_crossing_gap_count"),
        "micromobility_corridor_segment_count": record.get("micromobility_corridor_segment_count"),
        "micromobility_gap_score": record.get("micromobility_gap_score"),
        "predicted_crash_total": record.get("predicted_crash_total"),
    }


def build_vru_summary(settings: ApiSettings, *, city_key: str) -> dict[str, Any]:
    """Compose the VRU exposure summary for one city."""
    bundle = _load_json(_vru_bundle_path(settings, city_key=city_key))
    planning_summary = dict(bundle.get("planning_summary") or {})
    return {
        "contract_version": VRU_SUMMARY_CONTRACT_VERSION,
        "city": {
            "city_key": bundle.get("city_key"),
            "display_name": bundle.get("display_name"),
        },
        "layer_status": bundle.get("layer_status"),
        "generated_at_utc": bundle.get("generated_at_utc"),
        "stats": dict(bundle.get("stats") or {}),
        "planning_highlights": {
            "top_pedestrian_segment": _top_segment_row(
                planning_summary.get("top_pedestrian_segment") or {}
            ),
            "top_cyclist_segment": _top_segment_row(
                planning_summary.get("top_cyclist_segment") or {}
            ),
            "top_crossing_candidate": _top_crossing_row(
                planning_summary.get("top_crossing_candidate") or {}
            ),
        },
    }


def build_vru_top_corridors(
    settings: ApiSettings, *, city_key: str, limit: int | None = None,
) -> dict[str, Any]:
    """Top corridor profiles for VRU planning."""
    bundle = _load_json(_vru_bundle_path(settings, city_key=city_key))
    rows = [_top_corridor_row(r) for r in bundle.get("top_corridor_profiles") or []]
    if limit is not None:
        rows = rows[: max(limit, 0)]
    return {
        "contract_version": VRU_DETAIL_CONTRACT_VERSION,
        "city": {
            "city_key": bundle.get("city_key"),
            "display_name": bundle.get("display_name"),
        },
        "limit": limit,
        "corridor_count": len(rows),
        "corridors": rows,
    }


# ---------------------------------------------------------------------
# Signal-phase operations
# ---------------------------------------------------------------------


def _signal_phase_target_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "junction_id": record.get("junction_id"),
        "junction_label": record.get("junction_label") or record.get("display_name"),
        "coverage_state": record.get("coverage_state"),
        "dominant_day_type": record.get("dominant_day_type"),
        "gap_priority_score": record.get("gap_priority_score"),
        "matched_signalized_crash_count": record.get("matched_signalized_crash_count"),
        "crashes_without_phase_timing": record.get("crashes_without_phase_timing"),
        "movements_with_phase_mapping": record.get("movements_with_phase_mapping"),
        "movements_with_phase_timing": record.get("movements_with_phase_timing"),
        "movements_with_provider_data": record.get("movements_with_provider_data"),
        "movements_without_phase_timing": record.get("movements_without_phase_timing"),
    }


def _operator_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "junction_id": record.get("junction_id"),
        "handoff_reference_key": record.get("handoff_reference_key"),
        "handoff_reference_value": record.get("handoff_reference_value"),
        "handoff_status": record.get("handoff_status"),
        "handoff_target_kind": record.get("handoff_target_kind"),
        "action_category": record.get("action_category"),
        "action_summary": record.get("action_summary"),
        "execution_route": record.get("execution_route"),
        "execution_summary": record.get("execution_summary"),
        "due_date": record.get("due_date"),
        "due_now": record.get("due_now"),
        "dispatch_reference": record.get("dispatch_reference"),
        "packet_available": record.get("packet_available"),
        "handoff_instructions": record.get("handoff_instructions"),
    }


def build_signal_phase_coverage(
    settings: ApiSettings, *, city_key: str,
) -> dict[str, Any]:
    """Composed signal-phase coverage rollup for one city."""
    payload = _load_json(_signal_phase_coverage_path(settings, city_key=city_key))
    summary = dict(payload.get("summary") or {})
    return {
        "contract_version": SIGNAL_PHASE_COVERAGE_CONTRACT_VERSION,
        "city": {"city_key": city_key},
        "generated_at_utc": payload.get("generated_at_utc"),
        "source_contract_version": payload.get("signal_phase_coverage_contract_version"),
        "summary": summary,
    }


def build_signal_phase_targets(
    settings: ApiSettings, *, city_key: str, limit: int | None = None,
) -> dict[str, Any]:
    """Signal-phase target dossiers for one city."""
    payload = _load_json(_signal_phase_targets_path(settings, city_key=city_key))
    targets = [_signal_phase_target_row(t) for t in payload.get("targets") or []]
    if limit is not None:
        targets = targets[: max(limit, 0)]
    return {
        "contract_version": SIGNAL_PHASE_TARGETS_CONTRACT_VERSION,
        "city": {"city_key": city_key},
        "generated_at_utc": payload.get("generated_at_utc"),
        "summary": dict(payload.get("summary") or {}),
        "target_count": len(targets),
        "targets": targets,
    }


def build_signal_phase_operator_board(
    settings: ApiSettings, *, city_key: str,
) -> dict[str, Any]:
    """Signal-phase operator board (ready + hold queues) for one city."""
    payload = _load_json(_signal_phase_operator_board_path(settings, city_key=city_key))
    ready = [_operator_row(r) for r in payload.get("operator_ready_queue") or []]
    holds = [_operator_row(r) for r in payload.get("operator_hold_queue") or []]
    return {
        "contract_version": SIGNAL_PHASE_OPERATOR_BOARD_CONTRACT_VERSION,
        "city": {"city_key": city_key},
        "generated_at_utc": payload.get("generated_at_utc"),
        "totals": {
            "ready_count": len(ready),
            "hold_count": len(holds),
        },
        "ready_queue": ready,
        "hold_queue": holds,
    }


def build_signal_phase_overview(
    settings: ApiSettings, *, city_key: str,
) -> dict[str, Any]:
    """One bundle the operations dashboard can consume in a single call."""
    coverage = build_signal_phase_coverage(settings, city_key=city_key)
    targets = build_signal_phase_targets(settings, city_key=city_key)
    board = build_signal_phase_operator_board(settings, city_key=city_key)
    return {
        "contract_version": SIGNAL_PHASE_OVERVIEW_CONTRACT_VERSION,
        "city": {"city_key": city_key},
        "coverage": coverage,
        "targets_summary": targets["summary"],
        "target_count": targets["target_count"],
        "operator_board": {
            "totals": board["totals"],
            "ready_queue_head": board["ready_queue"][:5],
            "hold_queue_head": board["hold_queue"][:5],
        },
    }


__all__ = [
    "DEFAULT_SIGNAL_PHASE_COVERAGE_RELATIVE_PATH",
    "DEFAULT_SIGNAL_PHASE_OPERATOR_BOARD_RELATIVE_PATH",
    "DEFAULT_SIGNAL_PHASE_TARGETS_RELATIVE_PATH",
    "DEFAULT_VRU_BUNDLE_RELATIVE_PATH",
    "SIGNAL_PHASE_COVERAGE_CONTRACT_VERSION",
    "SIGNAL_PHASE_OPERATOR_BOARD_CONTRACT_VERSION",
    "SIGNAL_PHASE_OVERVIEW_CONTRACT_VERSION",
    "SIGNAL_PHASE_TARGETS_CONTRACT_VERSION",
    "TRAFFIC_OPERATIONS_CAPABILITIES_CONTRACT_VERSION",
    "VRU_DETAIL_CONTRACT_VERSION",
    "VRU_SUMMARY_CONTRACT_VERSION",
    "VruSignalsError",
    "build_traffic_operations_capabilities",
    "build_signal_phase_coverage",
    "build_signal_phase_operator_board",
    "build_signal_phase_overview",
    "build_signal_phase_targets",
    "build_vru_summary",
    "build_vru_top_corridors",
]
