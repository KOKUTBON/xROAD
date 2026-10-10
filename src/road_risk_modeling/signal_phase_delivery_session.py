"""Run validated signal-phase deliveries through ingestion and movement-phase joins."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_delivery_uplift import build_bari_signal_phase_delivery_uplift_report
from .signal_phase_ingestion import ingest_signal_phase_extract
from .signal_phase_join import apply_signal_phase_to_movements


SIGNAL_PHASE_DELIVERY_SESSION_VERSION = "signal_phase_delivery_session_v1"
SIGNAL_PHASE_DELIVERY_SESSION_CONTRACT_VERSION = "signal_phase_delivery_session_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return None if text == "" else text


def _session_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Signal-Phase Delivery Session",
        "",
        f"As of {payload['generated_at_utc']}, the validated deliveries have been processed through normalized ingestion and movement-phase joining.",
        "",
        "## Summary",
        "",
        f"- Validation manifests supplied: `{payload['stats']['validation_manifest_count']}`",
        f"- Accepted validations: `{payload['stats']['accepted_validation_count']}`",
        f"- Skipped validations: `{payload['stats']['skipped_validation_count']}`",
        f"- Ingested record manifests: `{payload['stats']['ingested_manifest_count']}`",
        f"- Joined movement count: `{payload['stats']['movement_count']}`",
        f"- Movements with phase timing: `{payload['stats']['movements_with_phase_timing']}`",
        f"- Movements with phase mapping: `{payload['stats']['movements_with_phase_mapping']}`",
        f"- Delivery uplift report generated: `{payload['stats']['delivery_uplift_report_generated']}`",
        "",
        "## Accepted Deliveries",
        "",
    ]
    for row in payload["accepted_deliveries"]:
        lines.append(
            f"- `{row['profile_id']}` `{row['validation_outcome']}` from `{row['validation_manifest_path']}`"
        )
    if payload["skipped_deliveries"]:
        lines.extend(["", "## Skipped Deliveries", ""])
        for row in payload["skipped_deliveries"]:
            lines.append(
                f"- `{row['profile_id']}` skipped with outcome `{row['validation_outcome']}` from `{row['validation_manifest_path']}`"
            )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Session report: `{payload['outputs']['session_json_path']}`",
            f"- Joined movement layer: `{payload['outputs']['movement_signal_phase_manifest_path']}`",
            f"- Delivery uplift report: `{payload['outputs']['delivery_uplift_manifest_path'] or 'not_generated'}`",
            "",
        ]
    )
    return "\n".join(lines)


def apply_validated_signal_phase_deliveries(
    movement_objects_path: str | Path,
    validation_manifest_paths: list[str | Path],
    output_dir: str | Path,
    *,
    matched_records_path: str | Path | None = None,
    target_request_queue_path: str | Path | None = None,
    baseline_movement_objects_path: str | Path | None = None,
) -> dict[str, Any]:
    if not validation_manifest_paths:
        raise RuntimeError("At least one validation manifest path is required.")

    movement_objects_input = Path(movement_objects_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    ingested_root = output_root / "ingested_records"
    joined_root = output_root / "movement_layer"
    ingested_root.mkdir(parents=True, exist_ok=True)
    joined_root.mkdir(parents=True, exist_ok=True)

    accepted_deliveries: list[dict[str, Any]] = []
    skipped_deliveries: list[dict[str, Any]] = []
    ingested_manifest_paths: list[str] = []

    for raw_manifest_path in validation_manifest_paths:
        manifest_path = Path(raw_manifest_path)
        manifest = _load_json(manifest_path)
        profile = manifest.get("profile", {})
        profile_id = str(profile.get("profile_id") or "unknown_profile")
        outcome = str(manifest.get("stats", {}).get("validation_outcome") or "unknown")
        record = {
            "validation_manifest_path": str(manifest_path),
            "profile_id": profile_id,
            "validation_outcome": outcome,
        }
        if outcome != "accepted_for_ingestion":
            skipped_deliveries.append(record)
            continue

        input_csv_path = Path(manifest["inputs"]["input_csv_path"]["path"])
        mapping_stub_path = Path(manifest["inputs"]["mapping_stub_path"]["path"])
        ingest_output_dir = ingested_root / _slugify(manifest_path.parent.name)
        ingest_result = ingest_signal_phase_extract(
            input_csv_path,
            mapping_stub_path,
            ingest_output_dir,
        )
        ingested_manifest_path = str(ingest_result["manifest_path"])
        accepted_deliveries.append(
            {
                **record,
                "input_csv_path": str(input_csv_path),
                "mapping_stub_path": str(mapping_stub_path),
                "ingested_manifest_path": ingested_manifest_path,
            }
        )
        ingested_manifest_paths.append(ingested_manifest_path)

    if not ingested_manifest_paths:
        raise RuntimeError("No validation manifests were accepted for ingestion.")

    join_result = apply_signal_phase_to_movements(
        movement_objects_input,
        ingested_manifest_paths,
        joined_root,
    )
    movement_signal_phase_manifest_path = str(join_result["manifest_path"])
    movement_signal_phase_manifest = _load_json(Path(movement_signal_phase_manifest_path))
    movement_signal_phase_geojson_path = str(movement_signal_phase_manifest["outputs"]["geojson_path"])

    session_json_path = output_root / "signal_phase_delivery_session.json"
    session_md_path = output_root / "signal_phase_delivery_session.md"
    manifest_path = output_root / "signal_phase_delivery_session.manifest.json"
    uplift_output_dir = output_root / "delivery_uplift"

    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "validation_manifest_count": len(validation_manifest_paths),
        "accepted_validation_count": len(accepted_deliveries),
        "skipped_validation_count": len(skipped_deliveries),
        "ingested_manifest_count": len(ingested_manifest_paths),
        "movement_count": join_result["stats"]["movement_count"],
        "movements_with_phase_timing": join_result["stats"]["movements_with_phase_timing"],
        "movements_with_phase_mapping": join_result["stats"]["movements_with_phase_mapping"],
        "provider_record_count": join_result["stats"]["provider_record_count"],
        "mapping_record_count": join_result["stats"]["mapping_record_count"],
        "delivery_uplift_report_generated": False,
    }
    payload = {
        "signal_phase_delivery_session_version": SIGNAL_PHASE_DELIVERY_SESSION_VERSION,
        "signal_phase_delivery_session_contract_version": SIGNAL_PHASE_DELIVERY_SESSION_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "source": {
            "adapter": "validated_signal_phase_delivery_session_runner",
        },
        "stats": stats,
        "accepted_deliveries": accepted_deliveries,
        "skipped_deliveries": skipped_deliveries,
        "inputs": {
            "movement_objects_path": {
                "path": str(movement_objects_input),
                "role": "movement_objects",
                "sha256": _sha256(movement_objects_input),
            },
            "validation_manifest_paths": [
                {
                    "path": str(Path(path)),
                    "role": "signal_phase_delivery_validation",
                    "sha256": _sha256(Path(path)),
                }
                for path in validation_manifest_paths
            ],
        },
        "outputs": {
            "session_json_path": str(session_json_path),
            "session_md_path": str(session_md_path),
            "manifest_path": str(manifest_path),
            "ingested_root": str(ingested_root),
            "ingested_manifest_paths": ingested_manifest_paths,
            "movement_signal_phase_manifest_path": movement_signal_phase_manifest_path,
            "movement_signal_phase_geojson_path": movement_signal_phase_geojson_path,
            "delivery_uplift_manifest_path": None,
        },
    }

    uplift_result: dict[str, Any] | None = None
    if matched_records_path is not None:
        uplift_result = build_bari_signal_phase_delivery_uplift_report(
            uplift_output_dir,
            baseline_movement_objects_path=baseline_movement_objects_path or movement_objects_input,
            updated_movement_objects_path=movement_signal_phase_geojson_path,
            matched_records_path=matched_records_path,
            target_request_queue_path=target_request_queue_path,
            delivery_session_manifest_path=manifest_path,
        )
        uplift_manifest_path = str(uplift_result["manifest_path"])
        uplift_manifest = _load_json(Path(uplift_manifest_path))
        uplift_stats = uplift_manifest["stats"]
        stats.update(
            {
                "delivery_uplift_report_generated": True,
                "uplift_movements_with_phase_timing": int(
                    uplift_stats["movements_with_phase_timing_after"]
                    - uplift_stats["movements_with_phase_timing_before"]
                ),
                "uplift_movements_with_phase_mapping": int(
                    uplift_stats["movements_with_phase_mapping_after"]
                    - uplift_stats["movements_with_phase_mapping_before"]
                ),
                "uplift_matched_signalized_crashes_on_timed_movements": int(
                    uplift_stats["matched_signalized_crashes_on_timed_movements_after"]
                    - uplift_stats["matched_signalized_crashes_on_timed_movements_before"]
                ),
                "uplift_matched_signalized_crashes_on_mapped_movements": int(
                    uplift_stats["matched_signalized_crashes_on_mapped_movements_after"]
                    - uplift_stats["matched_signalized_crashes_on_mapped_movements_before"]
                ),
            }
        )
        payload["outputs"]["delivery_uplift_manifest_path"] = uplift_manifest_path

    session_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    session_md_path.write_text(_session_markdown(payload), encoding="utf-8")

    supporting_outputs = [
        _artifact_reference("signal_phase_ingested_manifest", Path(path), _sha256(Path(path)))
        for path in ingested_manifest_paths
    ]
    if uplift_result is not None:
        supporting_outputs.append(
            _artifact_reference(
                "signal_phase_delivery_uplift_report",
                Path(str(uplift_result["manifest_path"])),
                _sha256(Path(str(uplift_result["manifest_path"]))),
            )
        )

    manifest = {
        "signal_phase_delivery_session_version": SIGNAL_PHASE_DELIVERY_SESSION_VERSION,
        "contract": {
            "resource_name": "signal_phase_delivery_session",
            "public_contract_version": SIGNAL_PHASE_DELIVERY_SESSION_CONTRACT_VERSION,
            "signal_phase_delivery_session_version": SIGNAL_PHASE_DELIVERY_SESSION_VERSION,
        },
        "source": {
            "adapter": "validated_signal_phase_delivery_session_runner",
        },
        "stats": stats,
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "session_json_path": str(session_json_path),
            "session_json_sha256": _sha256(session_json_path),
            "session_md_path": str(session_md_path),
            "session_md_sha256": _sha256(session_md_path),
            "movement_signal_phase_manifest_path": movement_signal_phase_manifest_path,
            "movement_signal_phase_geojson_path": movement_signal_phase_geojson_path,
            "delivery_uplift_manifest_path": payload["outputs"]["delivery_uplift_manifest_path"],
            "ingested_manifest_paths": ingested_manifest_paths,
        },
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("movement_objects", movement_objects_input, _sha256(movement_objects_input)),
            ]
            + [
                _artifact_reference("signal_phase_delivery_validation", Path(path), _sha256(Path(path)))
                for path in validation_manifest_paths
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference(
                    "signal_phase_delivery_session_report",
                    session_json_path,
                    _sha256(session_json_path),
                ),
                _artifact_reference(
                    "signal_phase_delivery_session_markdown",
                    session_md_path,
                    _sha256(session_md_path),
                ),
                _artifact_reference(
                    "movement_signal_phase_manifest",
                    Path(movement_signal_phase_manifest_path),
                    _sha256(Path(movement_signal_phase_manifest_path)),
                ),
            ],
            supporting_outputs=supporting_outputs,
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_phase_delivery_session_version": SIGNAL_PHASE_DELIVERY_SESSION_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": stats,
        "outputs": {
            "movement_signal_phase_manifest_path": movement_signal_phase_manifest_path,
            "movement_signal_phase_geojson_path": movement_signal_phase_geojson_path,
            "delivery_uplift_manifest_path": str(uplift_result["manifest_path"]) if uplift_result else None,
        },
    }
