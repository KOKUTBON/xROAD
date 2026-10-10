"""Build Bari signal-phase delivery intake bundles from dispatch and checklist artifacts."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256


SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_VERSION = "signal_phase_delivery_intake_bundle_v1"
SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_CONTRACT_VERSION = "signal_phase_delivery_intake_bundle_public_v1"

PROFILE_FILENAME_HINTS = {
    "controller_event_log_export": "controller_event_log_*.csv",
    "signal_stage_plan_export": "signal_stage_plan_*.csv",
    "arm_phase_mapping_sheet": "arm_phase_mapping_*.csv",
    "junction_phase_diagram_support": "junction_phase_diagram_*",
}


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


def _safe_int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _request_packet_markdown(packet: dict[str, Any], delivery_rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# Bari Signal-Phase Delivery Intake Packet: {packet['request_id']}",
        "",
        "## Dispatch Context",
        "",
        f"- Dispatch reference: `{packet['dispatch_reference']}`",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Planned dispatch date: `{packet['planned_dispatch_date']}`",
        f"- First follow-up date: `{packet['first_follow_up_date']}`",
        f"- Escalation date: `{packet['escalation_date']}`",
        "",
        "## Expected Deliveries",
        "",
    ]
    for row in delivery_rows:
        lines.extend(
            [
                f"- `{row['profile_id']}`",
                f"  expected filename pattern: `{row['expected_filename_hint']}`",
                f"  incoming drop zone: `{row['incoming_dropzone_path']}`",
                f"  mapping stub: `{row['mapping_stub_path']}`",
                f"  validation output dir: `{row['validation_output_dir']}`",
                f"  validation command: `{row['validation_command']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Intake Rule",
            "",
            "When the first reply or attachment arrives, save the file in the matching drop zone, update the receipt register, and run the listed validation command before attempting ingestion.",
            "",
        ]
    )
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Delivery Intake Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari dispatch queue has been paired with expected delivery items and validation paths.",
        "",
        "## Summary",
        "",
        f"- dispatch requests: `{payload['summary']['dispatch_request_count']}`",
        f"- expected delivery items: `{payload['summary']['expected_delivery_count']}`",
        f"- distinct profiles: `{payload['summary']['distinct_profile_count']}`",
        f"- intake packets: `{payload['summary']['packet_count']}`",
        "",
        "## Requests",
        "",
    ]
    for row in payload["dispatch_requests"]:
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: `{row['expected_delivery_count']}` delivery items, "
            f"dispatch `{row['planned_dispatch_date']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_delivery_intake_bundle(
    *,
    output_dir: str | Path = "data/planning/signal_phase_delivery_intake/bari",
    signal_phase_dispatch_bundle_path: str | Path = "data/planning/signal_phase_dispatch/bari/signal_phase_dispatch_bundle.json",
    delivery_checklist_path: str | Path = "data/planning/signal_phase_acquisition/bari/delivery_checklist.csv",
    mapping_stub_dir: str | Path = "data/planning/signal_phase_intake/bari/mapping_stubs",
    validation_output_root: str | Path = "data/quality/signal_phase_delivery_validation/bari_live",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "intake_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    inbox_root = output_root / "incoming_dropzones"
    inbox_root.mkdir(parents=True, exist_ok=True)

    dispatch_bundle_input = Path(signal_phase_dispatch_bundle_path)
    delivery_checklist_input = Path(delivery_checklist_path)
    mapping_stub_root = Path(mapping_stub_dir)
    validation_root = Path(validation_output_root)

    dispatch_payload = _load_json(dispatch_bundle_input)
    dispatch_rows = dispatch_payload.get("dispatch_queue", [])
    if not isinstance(dispatch_rows, list):
        raise RuntimeError("Signal phase dispatch bundle must include a top-level 'dispatch_queue' list.")
    delivery_rows = _read_csv_rows(delivery_checklist_input)

    dispatch_rows = [
        row
        for row in dispatch_rows
        if isinstance(row, dict)
    ]
    dispatch_rows.sort(key=lambda item: (_priority_value(item.get("priority_rank")), str(item.get("junction_id") or "")))
    request_ids = {str(row["request_id"]) for row in dispatch_rows}
    relevant_delivery_rows = [
        row
        for row in delivery_rows
        if row.get("request_id") in request_ids
    ]

    expected_delivery_rows: list[dict[str, Any]] = []
    receipt_register_rows: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for dispatch_row in dispatch_rows:
        request_id = str(dispatch_row["request_id"])
        request_delivery_rows = [
            row for row in relevant_delivery_rows if row.get("request_id") == request_id
        ]
        request_delivery_rows.sort(key=lambda item: str(item.get("profile_id") or ""))

        packet_delivery_rows: list[dict[str, Any]] = []
        for row in request_delivery_rows:
            profile_id = str(row["profile_id"])
            incoming_dropzone_path = inbox_root / request_id / profile_id
            incoming_dropzone_path.mkdir(parents=True, exist_ok=True)
            mapping_stub_path = mapping_stub_root / f"{profile_id}_mapping_stub.json"
            validation_output_dir = validation_root / f"{request_id}__{profile_id}"
            filename_hint = PROFILE_FILENAME_HINTS.get(profile_id, "delivery_*")
            validation_command = (
                "PYTHONPATH=src python3 -m road_risk_modeling validate-signal-phase-delivery "
                f"<received_file_path> {mapping_stub_path} "
                f"--output-dir {validation_output_dir} "
                f"--delivery-checklist-path {delivery_checklist_input} "
                f"--request-id {request_id} "
                f"--junction-id {dispatch_row['junction_id']}"
            )
            intake_row = {
                "dispatch_reference": dispatch_row["dispatch_reference"],
                "request_id": request_id,
                "junction_id": dispatch_row["junction_id"],
                "signal_name": dispatch_row["signal_name"],
                "profile_id": profile_id,
                "delivery_item_id": row["delivery_item_id"],
                "delivery_format": row["delivery_format"],
                "requested_window": row["requested_window"],
                "acceptance_gate": row["acceptance_gate"],
                "expected_filename_hint": filename_hint,
                "incoming_dropzone_path": str(incoming_dropzone_path),
                "mapping_stub_path": str(mapping_stub_path),
                "validation_output_dir": str(validation_output_dir),
                "validation_command": validation_command,
            }
            expected_delivery_rows.append(intake_row)
            receipt_register_rows.append(
                {
                    **intake_row,
                    "receipt_status": "awaiting_delivery",
                    "received_date": "",
                    "received_file_path": "",
                    "validation_status": "not_started",
                    "validation_manifest_path": "",
                    "notes": "",
                }
            )
            packet_delivery_rows.append(intake_row)

        packet_summary = {
            "dispatch_reference": dispatch_row["dispatch_reference"],
            "request_id": request_id,
            "junction_id": dispatch_row["junction_id"],
            "signal_name": dispatch_row["signal_name"],
            "planned_dispatch_date": dispatch_row["planned_dispatch_date"],
            "first_follow_up_date": dispatch_row["first_follow_up_date"],
            "escalation_date": dispatch_row["escalation_date"],
        }
        packet_md_path = packet_dir / f"{_slugify(request_id)}.md"
        packet_json_path = packet_dir / f"{_slugify(request_id)}.json"
        packet_md_path.write_text(_request_packet_markdown(packet_summary, packet_delivery_rows), encoding="utf-8")
        packet_json_path.write_text(
            json.dumps({"dispatch": packet_summary, "expected_deliveries": packet_delivery_rows}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        packet_paths.extend([str(packet_md_path), str(packet_json_path)])

    expected_deliveries_path = output_root / "expected_deliveries.csv"
    receipt_register_path = output_root / "delivery_receipt_register.csv"
    bundle_json_path = output_root / "signal_phase_delivery_intake_bundle.json"
    bundle_md_path = output_root / "signal_phase_delivery_intake_bundle.md"
    manifest_path = output_root / "signal_phase_delivery_intake_bundle.manifest.json"

    _write_csv(
        expected_deliveries_path,
        expected_delivery_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "profile_id",
            "delivery_item_id",
            "delivery_format",
            "requested_window",
            "acceptance_gate",
            "expected_filename_hint",
            "incoming_dropzone_path",
            "mapping_stub_path",
            "validation_output_dir",
            "validation_command",
        ],
    )
    _write_csv(
        receipt_register_path,
        receipt_register_rows,
        [
            "dispatch_reference",
            "request_id",
            "junction_id",
            "signal_name",
            "profile_id",
            "delivery_item_id",
            "delivery_format",
            "requested_window",
            "acceptance_gate",
            "expected_filename_hint",
            "incoming_dropzone_path",
            "mapping_stub_path",
            "validation_output_dir",
            "validation_command",
            "receipt_status",
            "received_date",
            "received_file_path",
            "validation_status",
            "validation_manifest_path",
            "notes",
        ],
    )

    dispatch_request_summary = []
    for row in dispatch_rows:
        request_id = str(row["request_id"])
        dispatch_request_summary.append(
            {
                "request_id": request_id,
                "junction_id": row["junction_id"],
                "signal_name": row["signal_name"],
                "planned_dispatch_date": row["planned_dispatch_date"],
                "expected_delivery_count": sum(1 for item in expected_delivery_rows if item["request_id"] == request_id),
            }
        )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "dispatch_request_count": len(dispatch_rows),
        "expected_delivery_count": len(expected_delivery_rows),
        "distinct_profile_count": len({row["profile_id"] for row in expected_delivery_rows}),
        "packet_count": len(dispatch_rows),
    }
    bundle_payload = {
        "signal_phase_delivery_intake_bundle_version": SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_VERSION,
        "signal_phase_delivery_intake_bundle_contract_version": SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "dispatch_requests": dispatch_request_summary,
    }
    bundle_json_path.write_text(json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_md_path.write_text(_bundle_markdown(bundle_payload), encoding="utf-8")

    manifest = {
        "signal_phase_delivery_intake_bundle_version": SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_delivery_intake_bundle",
            "public_contract_version": SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_CONTRACT_VERSION,
            "signal_phase_delivery_intake_bundle_version": SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_delivery_intake_bundle_builder",
        },
        "inputs": {
            "signal_phase_dispatch_bundle_path": str(dispatch_bundle_input),
            "delivery_checklist_path": str(delivery_checklist_input),
            "mapping_stub_dir": str(mapping_stub_root),
            "validation_output_root": str(validation_root),
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "expected_deliveries_path": str(expected_deliveries_path),
            "expected_deliveries_sha256": _sha256(expected_deliveries_path),
            "receipt_register_path": str(receipt_register_path),
            "receipt_register_sha256": _sha256(receipt_register_path),
            "packet_dir": str(packet_dir),
            "packet_paths": packet_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference("signal_phase_dispatch_bundle", dispatch_bundle_input, _sha256(dispatch_bundle_input)),
            _artifact_reference("signal_phase_delivery_checklist", delivery_checklist_input, _sha256(delivery_checklist_input)),
        ],
        publishable_outputs=[
            _artifact_reference("signal_phase_delivery_intake_bundle_json", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("signal_phase_delivery_intake_bundle_markdown", bundle_md_path, _sha256(bundle_md_path)),
        ],
        supporting_outputs=[
            _artifact_reference("signal_phase_expected_deliveries", expected_deliveries_path, _sha256(expected_deliveries_path)),
            _artifact_reference("signal_phase_delivery_receipt_register", receipt_register_path, _sha256(receipt_register_path)),
        ]
        + [
            _artifact_reference("signal_phase_delivery_intake_packet", Path(path), _sha256(Path(path)))
            for path in packet_paths
        ],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "signal_phase_delivery_intake_bundle_version": SIGNAL_PHASE_DELIVERY_INTAKE_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
