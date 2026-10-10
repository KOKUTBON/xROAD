"""Apply normalized signal-phase records to Bari movement objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


MOVEMENT_SIGNAL_PHASE_VERSION = "movement_signal_phase_v1"
MOVEMENT_SIGNAL_PHASE_CONTRACT_VERSION = "movement_signal_phase_public_v1"

PROVIDER_NUMERIC_FIELDS = {
    "cycle_length_s": "movement_phase_cycle_length_s_mean",
    "green_s": "movement_phase_green_s_mean",
    "amber_s": "movement_phase_amber_s_mean",
    "all_red_s": "movement_phase_all_red_s_mean",
    "pedestrian_walk_s": "movement_phase_pedestrian_walk_s_mean",
    "pedestrian_clearance_s": "movement_phase_pedestrian_clearance_s_mean",
}


def _load_geo_stack() -> tuple[Any, Any]:
    try:
        import geopandas as gpd  # type: ignore
        import pandas as pd  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "GeoPandas and pandas are required for movement signal-phase joins. Install geospatial extras with: "
            "python3 -m pip install -e '.[geospatial]'"
        ) from exc
    return gpd, pd


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a JSON object at: {path}")
    return payload


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _resolve_records_path(manifest_path: Path) -> Path:
    manifest = _load_json(manifest_path)
    output_value = manifest.get("outputs", {}).get("records_path")
    if not isinstance(output_value, str) or not output_value.strip():
        raise RuntimeError(f"Manifest does not contain outputs.records_path: {manifest_path}")
    return Path(output_value)


def _load_phase_records(manifest_paths: list[str | Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    source_manifests: list[dict[str, Any]] = []
    for manifest_path_value in manifest_paths:
        manifest_path = Path(manifest_path_value)
        manifest = _load_json(manifest_path)
        records_path = _resolve_records_path(manifest_path)
        source_manifests.append(
            {
                "manifest_path": str(manifest_path),
                "records_path": str(records_path),
                "profile_id": manifest.get("profile", {}).get("profile_id"),
                "profile_type": manifest.get("profile", {}).get("profile_type"),
            }
        )
        with records_path.open("r", encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows, source_manifests


def _flatten_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        attributes = dict(row.get("attributes", {}))
        flattened.append(
            {
                "signal_phase_record_id": row.get("signal_phase_record_id"),
                "record_kind": row.get("record_kind"),
                "profile_id": row.get("profile_id"),
                "profile_type": row.get("profile_type"),
                "junction_id": row.get("junction_id"),
                "phase_id": row.get("phase_id"),
                "stage_id": row.get("stage_id"),
                "incoming_arm_id": row.get("incoming_arm_id"),
                "movement_turn": row.get("movement_turn"),
                "outgoing_arm_id": row.get("outgoing_arm_id"),
                "protection_state": row.get("protection_state"),
                "pedestrian_stage_flag": row.get("pedestrian_stage_flag"),
                "control_mode": row.get("control_mode"),
                "observed_end_utc": row.get("observed_end_utc"),
                **attributes,
            }
        )
    return flattened


def _aggregate_provider_records(provider_frame: Any, pd: Any) -> tuple[Any, Any]:
    if provider_frame.empty:
        return pd.DataFrame(columns=["junction_id", "junction_phase_provider_available"]), pd.DataFrame(
            columns=["junction_id", "phase_id", "stage_id", "movement_phase_provider_record_count"]
        )

    provider_frame = provider_frame.copy()
    for source_field in PROVIDER_NUMERIC_FIELDS:
        if source_field in provider_frame.columns:
            provider_frame[source_field] = pd.to_numeric(provider_frame[source_field], errors="coerce")

    junction_group = provider_frame.groupby("junction_id", as_index=False)
    junction_aggregate = junction_group.size().rename(
        columns={"size": "junction_phase_provider_record_count"}
    )
    junction_profiles = (
        provider_frame.groupby("junction_id")["profile_id"]
        .agg(lambda values: "|".join(sorted({str(value) for value in values if value})))
        .rename("junction_phase_provider_profiles")
        .reset_index()
    )
    junction_controls = (
        provider_frame.groupby("junction_id")["control_mode"]
        .agg(lambda values: "|".join(sorted({str(value) for value in values if value})))
        .rename("junction_phase_control_modes")
        .reset_index()
    )
    junction_latest = (
        provider_frame.groupby("junction_id")["observed_end_utc"]
        .max()
        .rename("junction_phase_latest_end_utc")
        .reset_index()
    )
    junction_aggregate = junction_aggregate.merge(junction_profiles, on="junction_id", how="left")
    junction_aggregate = junction_aggregate.merge(junction_controls, on="junction_id", how="left")
    junction_aggregate = junction_aggregate.merge(junction_latest, on="junction_id", how="left")
    junction_aggregate["junction_phase_provider_available"] = 1.0

    stage_group = provider_frame.groupby(["junction_id", "phase_id", "stage_id"], dropna=False, as_index=False)
    stage_aggregate = stage_group.size().rename(columns={"size": "movement_phase_provider_record_count"})
    stage_profiles = (
        provider_frame.groupby(["junction_id", "phase_id", "stage_id"], dropna=False)["profile_id"]
        .agg(lambda values: "|".join(sorted({str(value) for value in values if value})))
        .rename("movement_phase_source_profiles")
        .reset_index()
    )
    stage_controls = (
        provider_frame.groupby(["junction_id", "phase_id", "stage_id"], dropna=False)["control_mode"]
        .agg(lambda values: "|".join(sorted({str(value) for value in values if value})))
        .rename("movement_phase_control_modes")
        .reset_index()
    )
    stage_latest = (
        provider_frame.groupby(["junction_id", "phase_id", "stage_id"], dropna=False)["observed_end_utc"]
        .max()
        .rename("movement_phase_latest_end_utc")
        .reset_index()
    )
    stage_aggregate = stage_aggregate.merge(stage_profiles, on=["junction_id", "phase_id", "stage_id"], how="left")
    stage_aggregate = stage_aggregate.merge(stage_controls, on=["junction_id", "phase_id", "stage_id"], how="left")
    stage_aggregate = stage_aggregate.merge(stage_latest, on=["junction_id", "phase_id", "stage_id"], how="left")
    for source_field, target_field in PROVIDER_NUMERIC_FIELDS.items():
        if source_field not in provider_frame.columns:
            continue
        numeric = (
            provider_frame.groupby(["junction_id", "phase_id", "stage_id"], dropna=False)[source_field]
            .mean()
            .rename(target_field)
            .reset_index()
        )
        stage_aggregate = stage_aggregate.merge(numeric, on=["junction_id", "phase_id", "stage_id"], how="left")
    stage_aggregate["movement_phase_timing_available"] = 1.0
    return junction_aggregate, stage_aggregate


def _matches_mapping_row(movement: dict[str, Any], mapping_row: dict[str, Any]) -> bool:
    mapped_node_object_id = _clean_text(mapping_row.get("node_object_id"))
    movement_node_object_id = _clean_text(movement.get("node_object_id"))
    if mapped_node_object_id:
        if mapped_node_object_id != movement_node_object_id:
            return False
        mapped_junction_id = _clean_text(mapping_row.get("junction_id"))
        if mapped_junction_id and mapped_junction_id != _clean_text(movement.get("junction_id")):
            return False
        mapped_turn = _clean_text(mapping_row.get("movement_turn"))
        return not mapped_turn or mapped_turn == _clean_text(movement.get("movement_turn"))
    if _clean_text(movement.get("junction_id")) != _clean_text(mapping_row.get("junction_id")):
        return False
    mapped_turn = _clean_text(mapping_row.get("movement_turn"))
    if mapped_turn and mapped_turn != _clean_text(movement.get("movement_turn")):
        return False
    mapped_incoming = _clean_text(mapping_row.get("incoming_arm_id"))
    movement_incoming = _clean_text(movement.get("incoming_arm_id")) or _clean_text(movement.get("approach_arm_id"))
    if mapped_incoming and mapped_incoming != movement_incoming:
        return False
    mapped_outgoing = _clean_text(mapping_row.get("outgoing_arm_id"))
    movement_outgoing = _clean_text(movement.get("outgoing_arm_id"))
    if mapped_outgoing and movement_outgoing and mapped_outgoing != movement_outgoing:
        return False
    return True


def _summarize_mapping_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    phase_ids = sorted({_clean_text(row.get("phase_id")) for row in rows if _clean_text(row.get("phase_id"))})
    stage_ids = sorted({_clean_text(row.get("stage_id")) for row in rows if _clean_text(row.get("stage_id"))})
    protection_states = sorted(
        {_clean_text(row.get("protection_state")) for row in rows if _clean_text(row.get("protection_state"))}
    )
    pedestrian_flags = [bool(row.get("pedestrian_stage_flag")) for row in rows if row.get("pedestrian_stage_flag") is not None]
    return {
        "movement_phase_mapping_available": 1.0,
        "movement_phase_mapping_count": len(rows),
        "movement_phase_id_catalog": " | ".join(phase_ids) or None,
        "movement_stage_id_catalog": " | ".join(stage_ids) or None,
        "movement_protection_state_catalog": " | ".join(protection_states) or None,
        "movement_pedestrian_stage_flag": 1.0 if any(pedestrian_flags) else 0.0,
        "movement_phase_join_resolution": "exact_movement_mapping",
    }


def apply_signal_phase_to_movements(
    movement_objects_path: str | Path,
    phase_manifest_paths: list[str | Path],
    output_dir: str | Path,
) -> dict[str, Any]:
    if not phase_manifest_paths:
        raise RuntimeError("At least one signal-phase manifest path is required.")

    gpd, pd = _load_geo_stack()
    movements_input = Path(movement_objects_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    enriched_path = output_root / "road_movement_objects_signal_phase.geojson"
    manifest_path = output_root / "road_movement_objects_signal_phase.manifest.json"

    movements = gpd.read_file(movements_input)
    if "node_object_id" not in movements.columns:
        raise RuntimeError(f"Movement file does not contain required 'node_object_id' column: {movements_input}")
    movements["node_object_id"] = movements["node_object_id"].astype(str)

    phase_rows, source_manifests = _load_phase_records(phase_manifest_paths)
    if not phase_rows:
        raise RuntimeError("Signal-phase manifests did not contain any rows.")
    frame = pd.DataFrame(_flatten_records(phase_rows))
    provider_frame = frame[frame["record_kind"] == "signal_control_observation"].copy()
    mapping_frame = frame[frame["record_kind"] == "movement_phase_mapping"].copy()

    junction_provider, stage_provider = _aggregate_provider_records(provider_frame, pd)
    enriched = movements.copy()

    if not junction_provider.empty:
        enriched = enriched.merge(junction_provider, on="junction_id", how="left")

    movement_records = movements.drop(columns=["geometry"]).to_dict(orient="records")
    mapping_rows = mapping_frame.to_dict(orient="records")
    movement_mapping_rows: list[dict[str, Any]] = []
    for movement in movement_records:
        matched_rows = [row for row in mapping_rows if _matches_mapping_row(movement, row)]
        summary = {"node_object_id": movement["node_object_id"]}
        if matched_rows:
            summary.update(_summarize_mapping_rows(matched_rows))
        movement_mapping_rows.append(summary)
    mapping_summary_frame = pd.DataFrame(movement_mapping_rows)
    enriched = enriched.merge(mapping_summary_frame, on="node_object_id", how="left")

    phase_stage_rows = []
    for row in movement_mapping_rows:
        node_object_id = row["node_object_id"]
        phase_catalog = _clean_text(row.get("movement_phase_id_catalog"))
        stage_catalog = _clean_text(row.get("movement_stage_id_catalog"))
        junction_id = None
        if phase_catalog and stage_catalog:
            movement_row = enriched.loc[enriched["node_object_id"] == node_object_id].iloc[0]
            junction_id = _clean_text(movement_row.get("junction_id"))
            for phase_id in [part.strip() for part in phase_catalog.split("|") if part.strip()]:
                for stage_id in [part.strip() for part in stage_catalog.split("|") if part.strip()]:
                    phase_stage_rows.append(
                        {
                            "node_object_id": node_object_id,
                            "junction_id": junction_id,
                            "phase_id": phase_id,
                            "stage_id": stage_id,
                        }
                    )
    phase_stage_frame = pd.DataFrame(phase_stage_rows)
    if not phase_stage_frame.empty and not stage_provider.empty:
        stage_joined = phase_stage_frame.merge(stage_provider, on=["junction_id", "phase_id", "stage_id"], how="left")
        stage_grouped = (
            stage_joined.groupby("node_object_id", as_index=False)
            .agg(
                movement_phase_provider_record_count=("movement_phase_provider_record_count", "sum"),
                movement_phase_source_profiles=("movement_phase_source_profiles", lambda values: "|".join(sorted({str(value) for value in values if _clean_text(value)}))),
                movement_phase_control_modes=("movement_phase_control_modes", lambda values: "|".join(sorted({str(value) for value in values if _clean_text(value)}))),
                movement_phase_latest_end_utc=("movement_phase_latest_end_utc", "max"),
                movement_phase_cycle_length_s_mean=("movement_phase_cycle_length_s_mean", "mean"),
                movement_phase_green_s_mean=("movement_phase_green_s_mean", "mean"),
                movement_phase_amber_s_mean=("movement_phase_amber_s_mean", "mean"),
                movement_phase_all_red_s_mean=("movement_phase_all_red_s_mean", "mean"),
                movement_phase_pedestrian_walk_s_mean=("movement_phase_pedestrian_walk_s_mean", "mean"),
                movement_phase_pedestrian_clearance_s_mean=("movement_phase_pedestrian_clearance_s_mean", "mean"),
                movement_phase_timing_available=("movement_phase_timing_available", "max"),
            )
        )
        enriched = enriched.merge(stage_grouped, on="node_object_id", how="left")

    for field in [
        "junction_phase_provider_available",
        "movement_phase_mapping_available",
        "movement_pedestrian_stage_flag",
        "movement_phase_timing_available",
    ]:
        if field not in enriched.columns:
            enriched[field] = 0.0
        enriched[field] = pd.to_numeric(enriched[field], errors="coerce").fillna(0.0)

    for field in [
        "junction_phase_provider_record_count",
        "movement_phase_mapping_count",
        "movement_phase_provider_record_count",
    ]:
        if field not in enriched.columns:
            enriched[field] = 0
        enriched[field] = pd.to_numeric(enriched[field], errors="coerce").fillna(0).astype(int)

    enriched["movement_signal_phase_version"] = MOVEMENT_SIGNAL_PHASE_VERSION
    enriched.to_file(enriched_path, driver="GeoJSON")

    signalized_mask = enriched["movement_role"].astype(str) == "signalized_turn_movement"
    manifest = {
        "movement_signal_phase_version": MOVEMENT_SIGNAL_PHASE_VERSION,
        "inputs": {
            "movement_objects_path": str(movements_input),
            "movement_objects_sha256": _sha256(movements_input),
            "phase_manifest_paths": [str(Path(path)) for path in phase_manifest_paths],
            "phase_manifest_sha256": {str(Path(path)): _sha256(Path(path)) for path in phase_manifest_paths},
        },
        "outputs": {
            "geojson_path": str(enriched_path),
            "geojson_sha256": _sha256(enriched_path),
            "manifest_path": str(manifest_path),
        },
        "contract": {
            "resource_name": "movement_signal_phase_layer",
            "public_contract_version": MOVEMENT_SIGNAL_PHASE_CONTRACT_VERSION,
            "movement_signal_phase_version": MOVEMENT_SIGNAL_PHASE_VERSION,
        },
        "stats": {
            "movement_count": int(len(enriched)),
            "signalized_movement_count": int(signalized_mask.sum()),
            "input_signal_phase_manifest_count": len(source_manifests),
            "input_signal_phase_record_count": int(len(frame)),
            "provider_record_count": int(len(provider_frame)),
            "mapping_record_count": int(len(mapping_frame)),
            "junctions_with_provider_data": int(
                enriched.loc[pd.to_numeric(enriched["junction_phase_provider_available"], errors="coerce").fillna(0.0) > 0.0, "junction_id"].nunique()
            ),
            "movements_with_phase_mapping": int(
                pd.to_numeric(enriched["movement_phase_mapping_available"], errors="coerce").fillna(0.0).gt(0.0).sum()
            ),
            "movements_with_phase_timing": int(
                pd.to_numeric(enriched["movement_phase_timing_available"], errors="coerce").fillna(0.0).gt(0.0).sum()
            ),
            "signalized_movements_with_phase_timing": int(
                (
                    signalized_mask
                    & pd.to_numeric(enriched["movement_phase_timing_available"], errors="coerce").fillna(0.0).gt(0.0)
                ).sum()
            ),
        },
        "lineage": _build_lineage_contract(
            run_record_path=manifest_path,
            upstream_inputs=[
                _artifact_reference("movement_objects_geojson", movements_input, _sha256(movements_input)),
                *[
                    _artifact_reference("signal_phase_manifest", Path(path), _sha256(Path(path)))
                    for path in phase_manifest_paths
                ],
            ],
            publishable_outputs=[
                _artifact_reference("movement_signal_phase_geojson", enriched_path, _sha256(enriched_path)),
            ],
            supporting_outputs=[],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "movement_signal_phase_version": MOVEMENT_SIGNAL_PHASE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": manifest["stats"],
    }
