"""Run a repeatable Bari phase-1 exposure pilot cycle (ingest -> join -> readiness)."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .connector_observation_join import apply_connector_observations_to_segments
from .exposure_connector_ingestion import ingest_exposure_connector_extract
from .exposure_provider_adapter import normalize_exposure_provider_extract
from .exposure_readiness import build_exposure_readiness_report
from .modeling import _artifact_reference, _build_lineage_contract, _sha256


EXPOSURE_PILOT_CYCLE_VERSION = "exposure_pilot_cycle_v1"
EXPOSURE_PILOT_CYCLE_CONTRACT_VERSION = "exposure_pilot_cycle_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _require_path(path_value: str | Path, *, label: str) -> Path:
    path = Path(path_value)
    if not path.exists():
        raise RuntimeError(f"{label} does not exist: {path}")
    return path


def _readiness_capability_index(readiness_report_path: Path) -> dict[str, dict[str, Any]]:
    report = _load_json(readiness_report_path)
    datasets = report.get("datasets", [])
    if not datasets:
        raise RuntimeError(f"Readiness report has no datasets: {readiness_report_path}")
    first_dataset = datasets[0]
    capabilities = first_dataset.get("capabilities", [])
    return {
        str(item.get("code")): item
        for item in capabilities
        if isinstance(item, dict) and item.get("code")
    }


def _summary_markdown(payload: dict[str, Any]) -> str:
    stats = payload.get("stats", {})
    readiness_status = stats.get("readiness_status_by_capability", {})
    readiness_share = stats.get("readiness_required_share_by_capability", {})
    lines = [
        "# Bari Phase-1 Exposure Pilot Cycle",
        "",
        "This artifact captures a repeatable pilot run of Bari phase-1 connector ingestion, join, and readiness refresh.",
        "",
        "## Inputs",
        "",
        f"- Segment layer: `{payload['inputs']['segments_path']}`",
        f"- Motorized extract: `{payload['inputs']['motorized_extract_path']}`",
        f"- Motorized mapping stub: `{payload['inputs']['motorized_mapping_stub_path']}`",
        f"- Speed extract: `{payload['inputs']['speed_extract_path']}`",
        f"- Speed mapping stub: `{payload['inputs']['speed_mapping_stub_path']}`",
        "",
        "## Pilot Stats",
        "",
        f"- Motorized normalization rows written: `{stats.get('motorized_normalization_rows_written', 0)}`",
        f"- Speed normalization rows written: `{stats.get('speed_normalization_rows_written', 0)}`",
        f"- Motorized rows written: `{stats.get('motorized_rows_written', 0)}`",
        f"- Speed rows written: `{stats.get('speed_rows_written', 0)}`",
        f"- Matched observations: `{stats.get('joined_matched_observations', 0)}`",
        f"- Matched segments: `{stats.get('joined_matched_segment_count', 0)}`",
        f"- Motorized available segments: `{stats.get('joined_motorized_available_segment_count', 0)}`",
        f"- Speed available segments: `{stats.get('joined_speed_available_segment_count', 0)}`",
        "",
        "## Readiness Refresh",
        "",
        f"- Motorized exposure: `{readiness_status.get('motorized_exposure', 'missing')}` "
        f"(required share: {float(readiness_share.get('motorized_exposure', 0.0)):.0%})",
        f"- Observed speed: `{readiness_status.get('speed_observation', 'missing')}` "
        f"(required share: {float(readiness_share.get('speed_observation', 0.0)):.0%})",
        f"- VRU exposure: `{readiness_status.get('vru_exposure', 'missing')}` "
        f"(required share: {float(readiness_share.get('vru_exposure', 0.0)):.0%})",
        "",
    ]
    return "\n".join(lines)


def run_bari_phase1_exposure_pilot(
    *,
    segments_path: str | Path = "data/processed/segments/bari_context_v2/road_segments_context.geojson",
    motorized_extract_path: str | Path = (
        "data/planning/exposure_connector_intake/sample_templates/"
        "motorized_exposure_connector_v1__municipal_counter_export.csv"
    ),
    motorized_mapping_stub_path: str | Path = (
        "data/planning/exposure_connector_intake/mapping_stubs/"
        "bari_01_motorized_exposure_municipal__municipal_counter_export.json"
    ),
    speed_extract_path: str | Path = (
        "data/planning/exposure_connector_intake/sample_templates/"
        "observed_speed_connector_v1__fixed_speed_counter_export.csv"
    ),
    speed_mapping_stub_path: str | Path = (
        "data/planning/exposure_connector_intake/mapping_stubs/"
        "bari_02_speed_observation_municipal__fixed_speed_counter_export.json"
    ),
    motorized_provider_profile_id: str | None = None,
    speed_provider_profile_id: str | None = None,
    normalize_motorized_provider_extract: bool = False,
    normalize_speed_provider_extract: bool = False,
    mapping_stub_root: str | Path = "data/planning/exposure_connector_intake/mapping_stubs",
    readiness_dataset_label: str = "bari_pilot",
    output_dir: str | Path = "data/planning/exposure_pilot/bari_phase1",
) -> dict[str, Any]:
    segments_input = _require_path(segments_path, label="Segments path")
    motorized_extract_input = _require_path(motorized_extract_path, label="Motorized extract path")
    motorized_mapping_input = _require_path(motorized_mapping_stub_path, label="Motorized mapping stub path")
    speed_extract_input = _require_path(speed_extract_path, label="Speed extract path")
    speed_mapping_input = _require_path(speed_mapping_stub_path, label="Speed mapping stub path")
    mapping_stub_root_input = _require_path(mapping_stub_root, label="Mapping stub root")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    motorized_output_dir = output_root / "motorized_ingestion"
    speed_output_dir = output_root / "speed_ingestion"
    join_output_dir = output_root / "connector_join"
    readiness_output_dir = output_root / "readiness"

    summary_path = output_root / "bari_phase1_exposure_pilot.json"
    summary_markdown_path = output_root / "bari_phase1_exposure_pilot.md"
    manifest_path = output_root / "bari_phase1_exposure_pilot.manifest.json"

    motorized_normalization_payload: dict[str, Any] | None = None
    speed_normalization_payload: dict[str, Any] | None = None
    motorized_ingestion_input = motorized_extract_input
    speed_ingestion_input = speed_extract_input
    should_normalize_motorized = normalize_motorized_provider_extract or bool(motorized_provider_profile_id)
    should_normalize_speed = normalize_speed_provider_extract or bool(speed_provider_profile_id)

    if should_normalize_motorized:
        motorized_normalization_payload = normalize_exposure_provider_extract(
            motorized_extract_input,
            provider_profile_id=motorized_provider_profile_id,
            mapping_stub_path=motorized_mapping_input,
            output_dir=output_root / "motorized_normalization",
        )
        motorized_ingestion_input = Path(motorized_normalization_payload["normalized_csv_path"])

    if should_normalize_speed:
        speed_normalization_payload = normalize_exposure_provider_extract(
            speed_extract_input,
            provider_profile_id=speed_provider_profile_id,
            mapping_stub_path=speed_mapping_input,
            output_dir=output_root / "speed_normalization",
        )
        speed_ingestion_input = Path(speed_normalization_payload["normalized_csv_path"])

    motorized_payload = ingest_exposure_connector_extract(
        input_csv_path=motorized_ingestion_input,
        mapping_stub_path=motorized_mapping_input,
        output_dir=motorized_output_dir,
    )
    speed_payload = ingest_exposure_connector_extract(
        input_csv_path=speed_ingestion_input,
        mapping_stub_path=speed_mapping_input,
        output_dir=speed_output_dir,
    )

    join_payload = apply_connector_observations_to_segments(
        segments_path=segments_input,
        observation_manifest_paths=[
            motorized_payload["manifest_path"],
            speed_payload["manifest_path"],
        ],
        output_dir=join_output_dir,
    )

    join_manifest = _load_json(Path(join_payload["manifest_path"]))
    joined_segments_path_value = join_manifest.get("outputs", {}).get("connector_segments_path")
    if not isinstance(joined_segments_path_value, str) or not joined_segments_path_value.strip():
        raise RuntimeError("Connector join manifest is missing outputs.connector_segments_path")
    joined_segments_path = Path(joined_segments_path_value)

    readiness_payload = build_exposure_readiness_report(
        datasets=[(readiness_dataset_label, str(joined_segments_path))],
        output_dir=readiness_output_dir,
        mapping_stub_root=mapping_stub_root_input,
    )

    readiness_report_path = readiness_output_dir / "exposure_readiness.json"
    readiness_capabilities = _readiness_capability_index(readiness_report_path)

    readiness_status_by_capability = {
        code: str(payload.get("status", "missing"))
        for code, payload in readiness_capabilities.items()
    }
    readiness_required_share_by_capability = {
        code: float(payload.get("required_feature_share", 0.0) or 0.0)
        for code, payload in readiness_capabilities.items()
    }

    summary = {
        "exposure_pilot_cycle_version": EXPOSURE_PILOT_CYCLE_VERSION,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "pilot_label": "bari_phase1",
        "inputs": {
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "motorized_extract_path": str(motorized_extract_input),
            "motorized_extract_sha256": _sha256(motorized_extract_input),
            "motorized_mapping_stub_path": str(motorized_mapping_input),
            "motorized_mapping_stub_sha256": _sha256(motorized_mapping_input),
            "speed_extract_path": str(speed_extract_input),
            "speed_extract_sha256": _sha256(speed_extract_input),
            "speed_mapping_stub_path": str(speed_mapping_input),
            "speed_mapping_stub_sha256": _sha256(speed_mapping_input),
            "motorized_provider_profile_id": motorized_provider_profile_id,
            "speed_provider_profile_id": speed_provider_profile_id,
            "normalize_motorized_provider_extract": should_normalize_motorized,
            "normalize_speed_provider_extract": should_normalize_speed,
            "motorized_resolved_provider_profile_id": (motorized_normalization_payload or {}).get(
                "provider_profile_id"
            ),
            "speed_resolved_provider_profile_id": (speed_normalization_payload or {}).get("provider_profile_id"),
            "mapping_stub_root": str(mapping_stub_root_input),
        },
        "outputs": {
            "motorized_normalization_manifest_path": (
                motorized_normalization_payload["manifest_path"] if motorized_normalization_payload else None
            ),
            "speed_normalization_manifest_path": (
                speed_normalization_payload["manifest_path"] if speed_normalization_payload else None
            ),
            "motorized_manifest_path": motorized_payload["manifest_path"],
            "speed_manifest_path": speed_payload["manifest_path"],
            "connector_join_manifest_path": join_payload["manifest_path"],
            "joined_segments_path": str(joined_segments_path),
            "readiness_manifest_path": readiness_payload["manifest_path"],
            "readiness_report_path": str(readiness_report_path),
            "summary_path": str(summary_path),
            "summary_markdown_path": str(summary_markdown_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "motorized_normalization_rows_written": int(
                (motorized_normalization_payload or {}).get("stats", {}).get("written_rows", 0)
            ),
            "motorized_normalization_rows_rejected": int(
                (motorized_normalization_payload or {}).get("stats", {}).get("rejected_rows", 0)
            ),
            "speed_normalization_rows_written": int(
                (speed_normalization_payload or {}).get("stats", {}).get("written_rows", 0)
            ),
            "speed_normalization_rows_rejected": int(
                (speed_normalization_payload or {}).get("stats", {}).get("rejected_rows", 0)
            ),
            "motorized_rows_written": int(motorized_payload.get("stats", {}).get("written_rows", 0)),
            "motorized_rows_rejected": int(motorized_payload.get("stats", {}).get("rejected_rows", 0)),
            "speed_rows_written": int(speed_payload.get("stats", {}).get("written_rows", 0)),
            "speed_rows_rejected": int(speed_payload.get("stats", {}).get("rejected_rows", 0)),
            "joined_matched_observations": int(join_payload.get("stats", {}).get("matched_observations", 0)),
            "joined_unmatched_observations": int(join_payload.get("stats", {}).get("unmatched_observations", 0)),
            "joined_matched_segment_count": int(join_payload.get("stats", {}).get("matched_segment_count", 0)),
            "joined_motorized_available_segment_count": int(
                join_payload.get("stats", {}).get("motorized_available_segment_count", 0)
            ),
            "joined_speed_available_segment_count": int(
                join_payload.get("stats", {}).get("speed_available_segment_count", 0)
            ),
            "readiness_dataset_count": int(readiness_payload.get("stats", {}).get("dataset_count", 0)),
            "readiness_status_by_capability": readiness_status_by_capability,
            "readiness_required_share_by_capability": readiness_required_share_by_capability,
            "motorized_required_feature_share": readiness_required_share_by_capability.get(
                "motorized_exposure",
                0.0,
            ),
            "speed_required_feature_share": readiness_required_share_by_capability.get(
                "speed_observation",
                0.0,
            ),
        },
    }

    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    summary_markdown_path.write_text(_summary_markdown(summary), encoding="utf-8")

    manifest = {
        "exposure_pilot_cycle_version": EXPOSURE_PILOT_CYCLE_VERSION,
        "inputs": {
            "segments_path": str(segments_input),
            "segments_sha256": _sha256(segments_input),
            "motorized_extract_path": str(motorized_extract_input),
            "motorized_extract_sha256": _sha256(motorized_extract_input),
            "motorized_ingestion_input_path": str(motorized_ingestion_input),
            "motorized_ingestion_input_sha256": _sha256(motorized_ingestion_input),
            "motorized_mapping_stub_path": str(motorized_mapping_input),
            "motorized_mapping_stub_sha256": _sha256(motorized_mapping_input),
            "speed_extract_path": str(speed_extract_input),
            "speed_extract_sha256": _sha256(speed_extract_input),
            "speed_ingestion_input_path": str(speed_ingestion_input),
            "speed_ingestion_input_sha256": _sha256(speed_ingestion_input),
            "speed_mapping_stub_path": str(speed_mapping_input),
            "speed_mapping_stub_sha256": _sha256(speed_mapping_input),
            "motorized_provider_profile_id": motorized_provider_profile_id,
            "speed_provider_profile_id": speed_provider_profile_id,
            "normalize_motorized_provider_extract": should_normalize_motorized,
            "normalize_speed_provider_extract": should_normalize_speed,
            "motorized_resolved_provider_profile_id": (motorized_normalization_payload or {}).get(
                "provider_profile_id"
            ),
            "speed_resolved_provider_profile_id": (speed_normalization_payload or {}).get("provider_profile_id"),
            "mapping_stub_root": str(mapping_stub_root_input),
        },
        "outputs": {
            "summary_path": str(summary_path),
            "summary_sha256": _sha256(summary_path),
            "summary_markdown_path": str(summary_markdown_path),
            "summary_markdown_sha256": _sha256(summary_markdown_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "exposure_pilot_cycle",
            "public_contract_version": EXPOSURE_PILOT_CYCLE_CONTRACT_VERSION,
            "exposure_pilot_cycle_version": EXPOSURE_PILOT_CYCLE_VERSION,
        },
        "stats": summary["stats"],
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("segments_geojson", segments_input, _sha256(segments_input)),
                _artifact_reference("provider_input_csv", motorized_extract_input, _sha256(motorized_extract_input)),
                _artifact_reference("provider_input_csv", speed_extract_input, _sha256(speed_extract_input)),
                _artifact_reference(
                    "connector_mapping_stub_json",
                    motorized_mapping_input,
                    _sha256(motorized_mapping_input),
                ),
                _artifact_reference("connector_mapping_stub_json", speed_mapping_input, _sha256(speed_mapping_input)),
            ],
            publishable_outputs=[
                _artifact_reference("exposure_pilot_summary_json", summary_path, _sha256(summary_path)),
                _artifact_reference(
                    "segment_connector_observations_geojson",
                    joined_segments_path,
                    _sha256(joined_segments_path),
                ),
                _artifact_reference(
                    "exposure_readiness_report_json",
                    readiness_report_path,
                    _sha256(readiness_report_path),
                ),
            ],
            supporting_outputs=[
                *([
                    _artifact_reference(
                        "provider_normalization_manifest",
                        Path(motorized_normalization_payload["manifest_path"]),
                        _sha256(Path(motorized_normalization_payload["manifest_path"])),
                    )
                ] if motorized_normalization_payload else []),
                *([
                    _artifact_reference(
                        "provider_normalization_manifest",
                        Path(speed_normalization_payload["manifest_path"]),
                        _sha256(Path(speed_normalization_payload["manifest_path"])),
                    )
                ] if speed_normalization_payload else []),
                _artifact_reference(
                    "connector_observations_manifest",
                    Path(motorized_payload["manifest_path"]),
                    _sha256(Path(motorized_payload["manifest_path"])),
                ),
                _artifact_reference(
                    "connector_observations_manifest",
                    Path(speed_payload["manifest_path"]),
                    _sha256(Path(speed_payload["manifest_path"])),
                ),
                _artifact_reference(
                    "segment_connector_observations_manifest",
                    Path(join_payload["manifest_path"]),
                    _sha256(Path(join_payload["manifest_path"])),
                ),
                _artifact_reference(
                    "exposure_readiness_manifest",
                    Path(readiness_payload["manifest_path"]),
                    _sha256(Path(readiness_payload["manifest_path"])),
                ),
                _artifact_reference(
                    "exposure_pilot_summary_markdown",
                    summary_markdown_path,
                    _sha256(summary_markdown_path),
                ),
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "exposure_pilot_cycle_version": EXPOSURE_PILOT_CYCLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary["stats"],
    }
