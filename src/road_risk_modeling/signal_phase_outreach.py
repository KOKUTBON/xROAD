"""Build Bari signal-phase outreach bundles from acquisition tracking artifacts."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256
from .signal_phase_acquisition import PROFILE_SPECS


SIGNAL_PHASE_OUTREACH_BUNDLE_VERSION = "signal_phase_outreach_bundle_v1"
SIGNAL_PHASE_OUTREACH_BUNDLE_CONTRACT_VERSION = "signal_phase_outreach_bundle_public_v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text or text.lower() == "nan":
        return None
    return text


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _priority_value(priority_band: str) -> int:
    return {"tier_1_immediate": 1, "tier_2_next_wave": 2, "tier_3_monitor": 3}.get(priority_band, 9)


def _template_map(template_paths: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for raw_path in template_paths:
        path = Path(raw_path)
        stem = path.stem
        if stem.endswith("_request"):
            mapping[stem.removesuffix("_request")] = path
    return mapping


def _request_packet_markdown(
    outreach_row: dict[str, str],
    request_row: dict[str, Any],
    delivery_rows: list[dict[str, str]],
    template_text: str | None,
) -> str:
    request_id = outreach_row["request_id"]
    signal_name = outreach_row["signal_name"]
    junction_id = outreach_row["junction_id"]
    recommended_profile = outreach_row["recommended_provider_profile"]
    sample_incoming = _clean_text(request_row.get("sample_incoming_arm_id")) or "not_set"
    sample_turn = _clean_text(request_row.get("sample_movement_turn")) or "not_set"
    sample_outgoing = _clean_text(request_row.get("sample_outgoing_arm_id")) or "not_set"
    lines = [
        f"# Bari Signal-Phase Outreach Packet: {request_id}",
        "",
        "## Request Summary",
        "",
        f"- Junction: `{junction_id}`",
        f"- Signal: `{signal_name}`",
        f"- Priority band: `{outreach_row['priority_band']}`",
        f"- Recommended provider profile: `{recommended_profile}`",
        f"- Acquisition status: `{outreach_row['acquisition_status']}`",
        f"- Owner team: `{outreach_row['owner_team']}`",
        f"- Request window: `{outreach_row['request_window']}`",
        f"- Signalized crashes: `{outreach_row['signalized_crash_total']}`",
        f"- Ambiguous movements: `{outreach_row['ambiguous_movement_count']}`",
        "",
        "## Movement Context",
        "",
        f"- Sample incoming arm: `{sample_incoming}`",
        f"- Sample turn: `{sample_turn}`",
        f"- Sample outgoing arm: `{sample_outgoing}`",
        f"- Sample resolution state: `{_clean_text(request_row.get('sample_resolution_state')) or 'not_set'}`",
        f"- Turn catalog: `{_clean_text(request_row.get('movement_turn_catalog')) or 'not_set'}`",
        f"- Phase groups present: `{_clean_text(request_row.get('phase_groups_present')) or 'not_set'}`",
        "",
        "## Delivery Checklist",
        "",
    ]
    for row in delivery_rows:
        lines.extend(
            [
                f"- `{row['profile_id']}`",
                f"  owner team: `{row['owner_team']}`",
                f"  delivery format: `{row['delivery_format']}`",
                f"  requested window: `{row['requested_window']}`",
                f"  acceptance gate: {row['acceptance_gate']}",
            ]
        )
    if template_text:
        lines.extend(
            [
                "",
                "## Base Request Template",
                "",
                template_text.strip(),
                "",
            ]
        )
    lines.extend(
        [
            "## Send Checklist",
            "",
            "- Fill contact name and email in the outreach tracker before sending.",
            "- Attach or reference the movement identifiers and the current delivery checklist rows for this junction.",
            "- Record the send date and next follow-up date in the outreach tracker after first contact.",
            "",
        ]
    )
    return "\n".join(lines)


def _profile_packet_markdown(
    profile_id: str,
    rows: list[dict[str, str]],
    template_text: str | None,
) -> str:
    spec = PROFILE_SPECS[profile_id]
    lines = [
        f"# Bari Signal-Phase Outreach Packet: {profile_id}",
        "",
        "## Profile Summary",
        "",
        f"- Profile: `{profile_id}`",
        f"- Owner team: `{spec['owner_team']}`",
        f"- Delivery format: `{spec['delivery_format']}`",
        f"- Requested window: `{spec['requested_window']}`",
        f"- Acceptance gate: {spec['acceptance_gate']}",
        f"- Priority note: {spec['priority_note']}",
        "",
        "## Target Junctions",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{row['junction_id']}` `{row['signal_name']}` ({row['priority_band']}, request `{row['request_id']}`)"
        )
    if template_text:
        lines.extend(
            [
                "",
                "## Base Request Template",
                "",
                template_text.strip(),
                "",
            ]
        )
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Outreach Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the acquisition tracker has been converted into send-ready outreach packets.",
        "",
        "## Summary",
        "",
        f"- Target priority band: `{payload['inputs']['priority_band']}`",
        f"- Targeted request rows: `{payload['stats']['target_request_count']}`",
        f"- Targeted delivery rows: `{payload['stats']['target_delivery_item_count']}`",
        f"- Request packets: `{payload['stats']['request_packet_count']}`",
        f"- Profile packets: `{payload['stats']['profile_packet_count']}`",
        "",
        "## Target Queue",
        "",
    ]
    for row in payload["target_requests"]:
        lines.append(
            f"- `{row['junction_id']}` `{row['signal_name']}`: `{row['recommended_provider_profile']}`, "
            f"`{row['signalized_crash_total']}` signalized crashes, `{row['ambiguous_movement_count']}` ambiguous movements"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Target request queue: `{payload['outputs']['target_request_queue_csv_path']}`",
            f"- Target delivery queue: `{payload['outputs']['target_delivery_queue_csv_path']}`",
            f"- Request packet directory: `{payload['outputs']['request_packet_dir']}`",
            f"- Profile packet directory: `{payload['outputs']['profile_packet_dir']}`",
            "",
            "## Immediate Action",
            "",
            "Use the request packets for the first owner contact, then track send dates and responses in the acquisition outreach tracker before validating any received export against the delivery checklist.",
            "",
        ]
    )
    return "\n".join(lines)


def build_bari_signal_phase_outreach_bundle(
    *,
    output_dir: str | Path = "data/planning/signal_phase_outreach/bari",
    acquisition_plan_path: str | Path = "data/planning/signal_phase_acquisition/bari/signal_phase_acquisition_plan.json",
    signal_phase_request_pack_path: str | Path = "data/planning/signal_phase_requests/bari/signal_phase_request_pack.json",
    priority_band: str = "tier_1_immediate",
    max_requests: int | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    acquisition_path = Path(acquisition_plan_path)
    request_pack_path = Path(signal_phase_request_pack_path)
    acquisition_payload = _load_json(acquisition_path)
    request_pack_payload = _load_json(request_pack_path)

    outreach_tracker_path = Path(acquisition_payload["outputs"]["outreach_tracker_csv_path"])
    delivery_checklist_path = Path(acquisition_payload["outputs"]["delivery_checklist_csv_path"])
    outreach_rows = _read_csv_rows(outreach_tracker_path)
    delivery_rows = _read_csv_rows(delivery_checklist_path)

    request_rows_by_id = {
        str(row["request_id"]): row
        for row in request_pack_payload.get("priority_request_rows", [])
        if isinstance(row, dict)
    }
    template_paths = request_pack_payload.get("outputs", {}).get("template_paths", [])
    template_by_profile = _template_map([str(path) for path in template_paths if path])

    target_requests = [
        row
        for row in outreach_rows
        if row.get("priority_band") == priority_band
    ]
    target_requests.sort(
        key=lambda item: (
            _priority_value(item["priority_band"]),
            int(item["priority_rank"]),
            item["junction_id"],
        )
    )
    if max_requests is not None:
        target_requests = target_requests[:max_requests]
    target_request_ids = {row["request_id"] for row in target_requests}
    target_delivery_rows = [row for row in delivery_rows if row.get("request_id") in target_request_ids]

    request_packet_dir = output_root / "request_packets"
    profile_packet_dir = output_root / "profile_packets"
    request_packet_dir.mkdir(parents=True, exist_ok=True)
    profile_packet_dir.mkdir(parents=True, exist_ok=True)

    request_packet_paths: list[str] = []
    for outreach_row in target_requests:
        request_row = request_rows_by_id.get(outreach_row["request_id"], {})
        packet_delivery_rows = [
            row
            for row in target_delivery_rows
            if row.get("request_id") == outreach_row["request_id"]
        ]
        template_path = template_by_profile.get(outreach_row["recommended_provider_profile"])
        template_text = template_path.read_text(encoding="utf-8") if template_path and template_path.exists() else None
        packet_name = f"{outreach_row['request_id']}__{_slugify(outreach_row['junction_id'])}.md"
        packet_path = request_packet_dir / packet_name
        packet_path.write_text(
            _request_packet_markdown(outreach_row, request_row, packet_delivery_rows, template_text),
            encoding="utf-8",
        )
        request_packet_paths.append(str(packet_path))

    profile_rows: dict[str, list[dict[str, str]]] = {}
    for row in target_delivery_rows:
        profile_id = row["profile_id"]
        profile_rows.setdefault(profile_id, []).append(row)

    profile_packet_paths: list[str] = []
    for profile_id, rows in sorted(profile_rows.items()):
        template_path = template_by_profile.get(profile_id)
        template_text = template_path.read_text(encoding="utf-8") if template_path and template_path.exists() else None
        packet_path = profile_packet_dir / f"{profile_id}.md"
        packet_path.write_text(_profile_packet_markdown(profile_id, rows, template_text), encoding="utf-8")
        profile_packet_paths.append(str(packet_path))

    target_request_queue_path = output_root / "target_request_queue.csv"
    target_delivery_queue_path = output_root / "target_delivery_queue.csv"
    bundle_json_path = output_root / "signal_phase_outreach_bundle.json"
    bundle_md_path = output_root / "signal_phase_outreach_bundle.md"
    manifest_path = output_root / "signal_phase_outreach_bundle.manifest.json"

    request_fields = list(target_requests[0].keys()) if target_requests else []
    delivery_fields = list(target_delivery_rows[0].keys()) if target_delivery_rows else []
    _write_csv(target_request_queue_path, target_requests, request_fields)
    _write_csv(target_delivery_queue_path, target_delivery_rows, delivery_fields)

    generated_at_utc = datetime.now(UTC).isoformat()
    stats = {
        "target_request_count": len(target_requests),
        "target_delivery_item_count": len(target_delivery_rows),
        "request_packet_count": len(request_packet_paths),
        "profile_packet_count": len(profile_packet_paths),
        "profile_counts": {
            profile_id: len(rows)
            for profile_id, rows in sorted(profile_rows.items())
        },
    }
    target_request_summaries = [
        {
            "request_id": row["request_id"],
            "junction_id": row["junction_id"],
            "signal_name": row["signal_name"],
            "priority_band": row["priority_band"],
            "recommended_provider_profile": row["recommended_provider_profile"],
            "signalized_crash_total": row["signalized_crash_total"],
            "ambiguous_movement_count": row["ambiguous_movement_count"],
        }
        for row in target_requests
    ]
    payload = {
        "signal_phase_outreach_bundle_version": SIGNAL_PHASE_OUTREACH_BUNDLE_VERSION,
        "signal_phase_outreach_bundle_contract_version": SIGNAL_PHASE_OUTREACH_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": generated_at_utc,
        "source": {
            "adapter": "bari_signal_phase_outreach_bundle_builder",
        },
        "inputs": {
            "priority_band": priority_band,
            "max_requests": max_requests,
            "acquisition_plan_path": {
                "path": str(acquisition_path),
                "role": "signal_phase_acquisition_plan",
                "sha256": _sha256(acquisition_path),
            },
            "signal_phase_request_pack_path": {
                "path": str(request_pack_path),
                "role": "signal_phase_request_pack",
                "sha256": _sha256(request_pack_path),
            },
        },
        "stats": stats,
        "target_requests": target_request_summaries,
        "outputs": {
            "target_request_queue_csv_path": str(target_request_queue_path),
            "target_delivery_queue_csv_path": str(target_delivery_queue_path),
            "request_packet_dir": str(request_packet_dir),
            "request_packet_paths": request_packet_paths,
            "profile_packet_dir": str(profile_packet_dir),
            "profile_packet_paths": profile_packet_paths,
            "bundle_json_path": str(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "manifest_path": str(manifest_path),
        },
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(payload), encoding="utf-8")

    manifest = {
        "signal_phase_outreach_bundle_version": SIGNAL_PHASE_OUTREACH_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_outreach_bundle",
            "public_contract_version": SIGNAL_PHASE_OUTREACH_BUNDLE_CONTRACT_VERSION,
            "signal_phase_outreach_bundle_version": SIGNAL_PHASE_OUTREACH_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_outreach_bundle_builder",
        },
        "stats": stats,
        "inputs": payload["inputs"],
        "outputs": {
            "manifest_path": str(manifest_path),
            "target_request_queue_csv_path": str(target_request_queue_path),
            "target_request_queue_csv_sha256": _sha256(target_request_queue_path),
            "target_delivery_queue_csv_path": str(target_delivery_queue_path),
            "target_delivery_queue_csv_sha256": _sha256(target_delivery_queue_path),
            "request_packet_dir": str(request_packet_dir),
            "request_packet_paths": request_packet_paths,
            "profile_packet_dir": str(profile_packet_dir),
            "profile_packet_paths": profile_packet_paths,
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
        },
        "lineage": _build_lineage_contract(
            upstream_inputs=[
                _artifact_reference("signal_phase_acquisition_plan", acquisition_path, _sha256(acquisition_path)),
                _artifact_reference("signal_phase_request_pack", request_pack_path, _sha256(request_pack_path)),
            ],
            run_record_path=manifest_path,
            publishable_outputs=[
                _artifact_reference("signal_phase_outreach_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
                _artifact_reference("signal_phase_outreach_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
                _artifact_reference("signal_phase_target_request_queue_csv", target_request_queue_path, _sha256(target_request_queue_path)),
                _artifact_reference("signal_phase_target_delivery_queue_csv", target_delivery_queue_path, _sha256(target_delivery_queue_path)),
            ],
            supporting_outputs=[
                _artifact_reference("signal_phase_request_packet_markdown", Path(path), _sha256(Path(path)))
                for path in request_packet_paths
            ] + [
                _artifact_reference("signal_phase_profile_packet_markdown", Path(path), _sha256(Path(path)))
                for path in profile_packet_paths
            ],
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
