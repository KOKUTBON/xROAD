"""Build proxy-backed VRU exposure layers from published runs and movement objects."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .dashboard_summary import _resolve_reference_path
from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .vru_intelligence import (
    DEFAULT_BARI_MOVEMENT_OBJECTS_PATH,
    _build_bundle_for_run,
    _load_feature_collection,
    _load_json,
    _write_csv,
)


VRU_EXPOSURE_BUNDLE_VERSION = "vru_exposure_bundle_v1"
VRU_EXPOSURE_BUNDLE_CONTRACT_VERSION = "vru_exposure_bundle_public_v1"
DEFAULT_VRU_EXPOSURE_OUTPUT_DIR = Path("data/planning/vru_exposure")
DEFAULT_VRU_EXPOSURE_INDEX_PATH = DEFAULT_VRU_EXPOSURE_OUTPUT_DIR / "vru_exposure_index.json"


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _write_geojson(path: Path, features: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(_feature_collection(features), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _sorted_top_rows(
    rows: list[dict[str, Any]],
    *,
    score_key: str,
    id_key: str,
    limit: int = 15,
) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda item: (-float(item.get(score_key) or 0.0), str(item.get(id_key) or "")),
    )[:limit]


def _segment_features(
    *,
    analyst_geojson_path: Path,
    segment_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    analyst_features = _load_feature_collection(analyst_geojson_path)
    rows_by_segment_score_id = {
        str(row.get("segment_score_id") or ""): row
        for row in segment_rows
        if str(row.get("segment_score_id") or "").strip()
    }
    rows_by_segment_id = {
        str(row.get("segment_id") or ""): row
        for row in segment_rows
        if str(row.get("segment_id") or "").strip()
    }

    matched_count = 0
    output_features: list[dict[str, Any]] = []
    for feature in analyst_features:
        properties = dict(feature.get("properties") or {})
        row = rows_by_segment_score_id.get(str(properties.get("segment_score_id") or "").strip())
        if row is None:
            row = rows_by_segment_id.get(str(properties.get("segment_id") or "").strip())
        if row is not None:
            matched_count += 1
            properties.update(row)
        properties["vru_exposure_layer_kind"] = "segment"
        properties["vru_exposure_source"] = "proxy_backed"
        properties["vru_exposure_bundle_version"] = VRU_EXPOSURE_BUNDLE_VERSION
        output_features.append(
            {
                "type": "Feature",
                "geometry": feature.get("geometry"),
                "properties": properties,
            }
        )
    return output_features, matched_count


def _crossing_geometry_index(
    movement_object_features: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    geometry_by_compound_key: dict[tuple[str, str], dict[str, Any]] = {}
    geometry_by_crossing_id: dict[str, dict[str, Any]] = {}
    for feature in movement_object_features:
        properties = dict(feature.get("properties") or {})
        if str(properties.get("movement_role") or "") != "pedestrian_crossing":
            continue
        crossing_id = str(properties.get("node_object_id") or properties.get("junction_id") or "").strip()
        segment_id = str(properties.get("segment_id") or "").strip()
        if not crossing_id:
            continue
        feature_payload = {
            "geometry": feature.get("geometry"),
            "properties": properties,
        }
        geometry_by_compound_key[(crossing_id, segment_id)] = feature_payload
        geometry_by_crossing_id[crossing_id] = feature_payload
    return geometry_by_compound_key, geometry_by_crossing_id


def _crossing_features(
    *,
    crossing_rows: list[dict[str, Any]],
    movement_object_features: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    geometry_by_compound_key, geometry_by_crossing_id = _crossing_geometry_index(movement_object_features)
    matched_count = 0
    output_features: list[dict[str, Any]] = []
    for row in crossing_rows:
        crossing_id = str(row.get("crossing_id") or "").strip()
        segment_id = str(row.get("segment_id") or "").strip()
        source_feature = geometry_by_compound_key.get((crossing_id, segment_id)) or geometry_by_crossing_id.get(
            crossing_id
        )
        properties = dict((source_feature or {}).get("properties") or {})
        if source_feature is not None:
            matched_count += 1
        properties.update(row)
        properties["vru_exposure_layer_kind"] = "crossing"
        properties["vru_exposure_source"] = "proxy_backed"
        properties["vru_exposure_bundle_version"] = VRU_EXPOSURE_BUNDLE_VERSION
        output_features.append(
            {
                "type": "Feature",
                "geometry": (source_feature or {}).get("geometry"),
                "properties": properties,
            }
        )
    return output_features, matched_count


def _bundle_markdown(bundle: dict[str, Any]) -> str:
    summary = bundle.get("planning_summary", {})
    lines = [
        f"# {bundle['display_name']} VRU Exposure Layer",
        "",
        "This bundle materializes proxy-backed VRU exposure layers from the current published run and Bari movement objects.",
        "",
        "## Inputs",
        "",
        f"- Run label: `{bundle['prediction_run_label']}`",
        f"- Dashboard summary: `{bundle['source_dashboard_summary_path']}`",
        f"- Movement objects: `{bundle['source_movement_objects_path']}`",
        "",
        "## Top Exposure Priorities",
        "",
        f"- Top pedestrian segment: `{summary.get('top_pedestrian_segment', {}).get('segment_label')}`",
        f"- Top cyclist segment: `{summary.get('top_cyclist_segment', {}).get('segment_label')}`",
        f"- Top crossing candidate: `{summary.get('top_crossing_candidate', {}).get('crossing_name')}`",
        f"- Top walkability corridor: `{summary.get('top_walkability_corridor', {}).get('corridor_label')}`",
        "",
        "## Coverage",
        "",
        f"- Segment features: `{bundle['stats']['segment_feature_count']}`",
        f"- Crossing features: `{bundle['stats']['crossing_feature_count']}`",
        f"- Corridor profiles: `{bundle['stats']['corridor_profile_count']}`",
        f"- Matched segment geometries: `{bundle['stats']['matched_segment_feature_count']}`",
        f"- Matched crossing geometries: `{bundle['stats']['matched_crossing_feature_count']}`",
        "",
        "## Uncertainty",
        "",
    ]
    for item in bundle.get("uncertainty_notes", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_vru_exposure_bundle(
    *,
    dashboard_summary_path: str | Path = "data/dashboard/dashboard_summary.json",
    output_dir: str | Path = DEFAULT_VRU_EXPOSURE_OUTPUT_DIR,
    prediction_run_labels: list[str] | None = None,
    movement_objects_path: str | Path = DEFAULT_BARI_MOVEMENT_OBJECTS_PATH,
) -> dict[str, Any]:
    dashboard_summary_input = Path(dashboard_summary_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    summary_payload = _load_json(dashboard_summary_input)
    published_runs = list(summary_payload.get("published_runs", []))
    if prediction_run_labels:
        requested = {str(label) for label in prediction_run_labels}
        published_runs = [
            run_record
            for run_record in published_runs
            if str(run_record.get("prediction_run_label")) in requested
        ]
    if not published_runs:
        raise RuntimeError("No published runs matched the requested VRU-exposure filters.")

    movement_objects_input = Path(movement_objects_path)
    movement_object_features = (
        _load_feature_collection(movement_objects_input)
        if movement_objects_input.exists()
        else []
    )

    bundle_outputs: list[dict[str, Any]] = []
    for run_record in published_runs:
        prediction_run_label = str(run_record["prediction_run_label"])
        run_output_dir = output_root / prediction_run_label
        run_output_dir.mkdir(parents=True, exist_ok=True)

        segment_manifest_path = _resolve_reference_path(
            str(run_record["segment_scores"]["manifest_path"]),
            anchor_path=dashboard_summary_input,
        )
        segment_manifest = _load_json(segment_manifest_path)
        analyst_geojson_path = _resolve_reference_path(
            str(segment_manifest["outputs"]["analyst_geojson_path"]),
            anchor_path=segment_manifest_path,
        )

        vru_bundle, segment_rows, crossing_rows, corridor_profiles, upstream_paths = _build_bundle_for_run(
            dashboard_summary_path=dashboard_summary_input,
            run_record=run_record,
            movement_object_features=movement_object_features,
        )

        segment_features, matched_segment_feature_count = _segment_features(
            analyst_geojson_path=analyst_geojson_path,
            segment_rows=segment_rows,
        )
        crossing_features, matched_crossing_feature_count = _crossing_features(
            crossing_rows=crossing_rows,
            movement_object_features=movement_object_features,
        )

        bundle_path = run_output_dir / "vru_exposure_bundle.json"
        markdown_path = run_output_dir / "vru_exposure_bundle.md"
        segment_geojson_path = run_output_dir / "segment_vru_exposure.geojson"
        segment_csv_path = run_output_dir / "segment_vru_exposure.csv"
        crossing_geojson_path = run_output_dir / "crossing_vru_exposure.geojson"
        crossing_csv_path = run_output_dir / "crossing_vru_exposure.csv"
        corridor_profiles_path = run_output_dir / "corridor_vru_exposure.csv"
        manifest_path = run_output_dir / "vru_exposure_bundle.manifest.json"

        bundle = {
            "vru_exposure_bundle_version": VRU_EXPOSURE_BUNDLE_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_dashboard_summary_path": str(dashboard_summary_input),
            "source_movement_objects_path": str(movement_objects_input),
            "city_key": run_record["city_key"],
            "display_name": run_record["display_name"],
            "prediction_run_label": prediction_run_label,
            "layer_status": "proxy_backed",
            "planning_summary": {
                "top_pedestrian_segment": _sorted_top_rows(
                    segment_rows,
                    score_key="pedestrian_priority_score",
                    id_key="segment_score_id",
                    limit=1,
                )[0]
                if segment_rows
                else {},
                "top_cyclist_segment": _sorted_top_rows(
                    segment_rows,
                    score_key="cyclist_priority_score",
                    id_key="segment_score_id",
                    limit=1,
                )[0]
                if segment_rows
                else {},
                "top_crossing_candidate": crossing_rows[0] if crossing_rows else {},
                "top_walkability_corridor": corridor_profiles[0] if corridor_profiles else {},
            },
            "top_segment_rows": {
                "pedestrian": _sorted_top_rows(
                    segment_rows,
                    score_key="pedestrian_priority_score",
                    id_key="segment_score_id",
                ),
                "cyclist": _sorted_top_rows(
                    segment_rows,
                    score_key="cyclist_priority_score",
                    id_key="segment_score_id",
                ),
                "ageing_user": _sorted_top_rows(
                    segment_rows,
                    score_key="ageing_user_priority_score",
                    id_key="segment_score_id",
                ),
                "micromobility": _sorted_top_rows(
                    segment_rows,
                    score_key="micromobility_priority_score",
                    id_key="segment_score_id",
                ),
            },
            "top_crossing_rows": crossing_rows[:25],
            "top_corridor_profiles": corridor_profiles[:25],
            "uncertainty_notes": list(vru_bundle.get("uncertainty_notes", [])),
            "stats": {
                "segment_feature_count": len(segment_features),
                "crossing_feature_count": len(crossing_features),
                "corridor_profile_count": len(corridor_profiles),
                "matched_segment_feature_count": matched_segment_feature_count,
                "matched_crossing_feature_count": matched_crossing_feature_count,
                "school_frontage_segment_count": vru_bundle["stats"]["school_frontage_segment_count"],
                "retail_frontage_segment_count": vru_bundle["stats"]["retail_frontage_segment_count"],
                "transit_access_segment_count": vru_bundle["stats"]["transit_access_segment_count"],
                "micromobility_corridor_segment_count": vru_bundle["stats"]["micromobility_corridor_segment_count"],
            },
        }

        bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(_bundle_markdown(bundle), encoding="utf-8")
        _write_geojson(segment_geojson_path, segment_features)
        _write_csv(segment_csv_path, segment_rows)
        _write_geojson(crossing_geojson_path, crossing_features)
        _write_csv(crossing_csv_path, crossing_rows)
        _write_csv(corridor_profiles_path, corridor_profiles)

        manifest = {
            "vru_exposure_bundle_version": VRU_EXPOSURE_BUNDLE_VERSION,
            "generated_at_utc": bundle["generated_at_utc"],
            "inputs": {
                "dashboard_summary_path": str(dashboard_summary_input),
                "dashboard_summary_sha256": _sha256(dashboard_summary_input),
                "movement_objects_path": str(movement_objects_input),
                "movement_objects_sha256": _sha256(movement_objects_input),
                "segment_manifest_path": str(segment_manifest_path),
                "segment_manifest_sha256": _sha256(segment_manifest_path),
                "analyst_geojson_path": str(analyst_geojson_path),
                "analyst_geojson_sha256": _sha256(analyst_geojson_path),
            },
            "outputs": {
                "bundle_path": str(bundle_path),
                "bundle_sha256": _sha256(bundle_path),
                "markdown_path": str(markdown_path),
                "markdown_sha256": _sha256(markdown_path),
                "segment_geojson_path": str(segment_geojson_path),
                "segment_geojson_sha256": _sha256(segment_geojson_path),
                "segment_csv_path": str(segment_csv_path),
                "segment_csv_sha256": _sha256(segment_csv_path),
                "crossing_geojson_path": str(crossing_geojson_path),
                "crossing_geojson_sha256": _sha256(crossing_geojson_path),
                "crossing_csv_path": str(crossing_csv_path),
                "crossing_csv_sha256": _sha256(crossing_csv_path),
                "corridor_profiles_path": str(corridor_profiles_path),
                "corridor_profiles_sha256": _sha256(corridor_profiles_path),
                "manifest_path": str(manifest_path),
            },
            "contract": {
                "resource_name": "vru_exposure_bundle",
                "public_contract_version": VRU_EXPOSURE_BUNDLE_CONTRACT_VERSION,
                "vru_exposure_bundle_version": VRU_EXPOSURE_BUNDLE_VERSION,
            },
            "stats": bundle["stats"],
            "lineage": _build_lineage_contract(
                run_record_path=manifest_path,
                upstream_inputs=[
                    _artifact_reference("dashboard_summary_json", dashboard_summary_input, _sha256(dashboard_summary_input)),
                    _artifact_reference("movement_objects_geojson", movement_objects_input, _sha256(movement_objects_input)),
                    _artifact_reference("segment_scores_manifest", segment_manifest_path, _sha256(segment_manifest_path)),
                    _artifact_reference("segment_scores_analyst_geojson", analyst_geojson_path, _sha256(analyst_geojson_path)),
                    *[
                        _artifact_reference(path.stem, path, _sha256(path))
                        for path in upstream_paths
                    ],
                ],
                publishable_outputs=[
                    _artifact_reference("vru_exposure_bundle_json", bundle_path, _sha256(bundle_path)),
                    _artifact_reference("vru_exposure_bundle_markdown", markdown_path, _sha256(markdown_path)),
                    _artifact_reference("segment_vru_exposure_geojson", segment_geojson_path, _sha256(segment_geojson_path)),
                    _artifact_reference("segment_vru_exposure_csv", segment_csv_path, _sha256(segment_csv_path)),
                    _artifact_reference("crossing_vru_exposure_geojson", crossing_geojson_path, _sha256(crossing_geojson_path)),
                    _artifact_reference("crossing_vru_exposure_csv", crossing_csv_path, _sha256(crossing_csv_path)),
                    _artifact_reference("corridor_vru_exposure_csv", corridor_profiles_path, _sha256(corridor_profiles_path)),
                ],
                supporting_outputs=[],
            ),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        bundle_outputs.append(
            {
                "city_key": run_record["city_key"],
                "display_name": run_record["display_name"],
                "prediction_run_label": prediction_run_label,
                "bundle_path": str(bundle_path),
                "manifest_path": str(manifest_path),
                "segment_geojson_path": str(segment_geojson_path),
                "crossing_geojson_path": str(crossing_geojson_path),
                "corridor_profiles_path": str(corridor_profiles_path),
                "layer_status": bundle["layer_status"],
                "stats": bundle["stats"],
            }
        )

    bundle_outputs.sort(key=lambda item: (str(item["city_key"]), str(item["prediction_run_label"])))
    index_payload = {
        "vru_exposure_bundle_version": VRU_EXPOSURE_BUNDLE_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "bundles": bundle_outputs,
        "stats": {
            "bundle_count": len(bundle_outputs),
            "city_count": len({str(item["city_key"]) for item in bundle_outputs}),
        },
    }
    index_path = output_root / DEFAULT_VRU_EXPOSURE_INDEX_PATH.name
    index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "vru_exposure_bundle_version": VRU_EXPOSURE_BUNDLE_VERSION,
        "bundle_count": len(bundle_outputs),
        "city_count": index_payload["stats"]["city_count"],
        "index_path": str(index_path),
    }
