"""Build Bari signal-phase contact routing bundles from contact drafts."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .modeling import _artifact_reference, _build_lineage_contract, _sha256

SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_VERSION = (
    "signal_phase_contact_resolution_bundle_v1"
)
SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_CONTRACT_VERSION = (
    "signal_phase_contact_resolution_bundle_public_v1"
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object at: {path}")
    return payload


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


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _slugify(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    return "_".join(part for part in "".join(chars).split("_") if part)


def _priority_value(value: Any) -> int:
    parsed = _safe_int(value)
    return parsed if parsed > 0 else 999999


def _infer_channel_type(value: str | None) -> str:
    text = _clean_text(value)
    if not text:
        return "email"
    lowered = text.lower()
    if "@" in text:
        if "pec" in lowered or lowered.endswith(".pec.rupar.puglia.it"):
            return "pec_email"
        return "email"
    if any(char.isdigit() for char in text):
        return "phone"
    return "email"


def _channel_by_value(
    official_channels: list[dict[str, Any]], value: str | None
) -> dict[str, str] | None:
    target = _clean_text(value)
    if not target:
        return None
    target_lower = target.lower()
    for channel in official_channels:
        candidate = _clean_text(channel.get("channel_value"))
        if candidate and candidate.lower() == target_lower:
            return {
                "channel_type": _clean_text(channel.get("channel_type"))
                or _infer_channel_type(candidate),
                "channel_value": candidate,
            }
    return None


def _resolve_channel(
    official_channels: list[dict[str, Any]],
    preferred_value: str | None,
    default_channel: dict[str, str],
) -> dict[str, str]:
    matched_channel = _channel_by_value(official_channels, preferred_value)
    if matched_channel is not None:
        return matched_channel
    preferred = _clean_text(preferred_value)
    if preferred:
        return {
            "channel_type": _infer_channel_type(preferred),
            "channel_value": preferred,
        }
    return {
        "channel_type": default_channel["channel_type"],
        "channel_value": default_channel["channel_value"],
    }


def _resolution_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        f"# Bari Signal-Phase Contact Resolution: {packet['request_id']}",
        "",
        "## Queue Summary",
        "",
        f"- Junction: `{packet['junction_id']}`",
        f"- Signal: `{packet['signal_name']}`",
        f"- Send readiness: `{packet['send_readiness']}`",
        f"- Email subject: `{packet['email_subject']}`",
        f"- Recommended time window: `{packet['recommended_time_window']}`",
        f"- Fallback pilot scope: `{packet['fallback_pilot_scope']}`",
        f"- Unresolved movement burden: `{packet['unresolved_signalized_movement_count']}` movements / `{packet['unresolved_signalized_crash_count']}` crashes",
        f"- Unresolved coverage: `{packet['unresolved_coverage_pct']}`% movements / `{packet['unresolved_crash_coverage_pct']}`% crashes",
        "",
        "## Recommended Routing",
        "",
        f"- Primary channel: `{packet['primary_channel_type']}` `{packet['primary_channel_value']}`",
        f"- Secondary channel: `{packet['secondary_channel_type']}` `{packet['secondary_channel_value']}`",
        f"- Phone escalation: `{packet['phone_escalation_value']}`",
        f"- Routing decision: `{packet['routing_decision'] or 'default_pec_first'}`",
        f"- External blocker: `{packet['external_blocker'] or 'none_reported'}`",
        "",
        "## Action",
        "",
        f"- {packet['recommended_routing_action']}",
        "",
    ]
    return "\n".join(lines)


def _bundle_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Bari Signal-Phase Contact Resolution Bundle",
        "",
        f"As of {payload['generated_at_utc']}, the Bari signal-phase contact queue has been paired with public official routing channels.",
        "",
        "## Summary",
        "",
        f"- targets: `{payload['summary']['target_count']}`",
        f"- direct named contacts available: `{payload['summary']['direct_contact_count']}`",
        f"- routable via official channels: `{payload['summary']['routable_via_official_channels_count']}`",
        f"- official channels catalogued: `{payload['summary']['official_channel_count']}`",
        f"- targets with unresolved movements: `{payload['summary']['targets_with_unresolved_movements']}`",
        f"- unresolved signalized movements across targets: `{payload['summary']['unresolved_signalized_movement_total']}`",
        f"- unresolved signalized crashes across targets: `{payload['summary']['unresolved_signalized_crash_total']}`",
        "",
        "## Queue",
        "",
    ]
    for row in payload["resolution_queue"]:
        blocker_suffix = (
            f", blocker `{row['external_blocker']}`"
            if _clean_text(row.get("external_blocker"))
            else ""
        )
        lines.append(
            f"- `{row['request_id']}` `{row['signal_name']}`: primary `{row['primary_channel_value']}`, "
            f"fallback `{row['phone_escalation_value']}`, unresolved crashes `{row['unresolved_signalized_crash_count']}`, "
            f"readiness `{row['send_readiness']}`{blocker_suffix}"
        )
    lines.append("")
    return "\n".join(lines)


def build_bari_signal_phase_contact_resolution_bundle(
    *,
    output_dir: str | Path = "data/planning/signal_phase_contact_resolution/bari",
    signal_phase_contact_bundle_path: str
    | Path = "data/planning/signal_phase_contact/bari/signal_phase_contact_bundle.json",
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    packet_dir = output_root / "resolution_packets"
    packet_dir.mkdir(parents=True, exist_ok=True)

    contact_bundle_input = Path(signal_phase_contact_bundle_path)
    contact_bundle = _load_json(contact_bundle_input)
    send_queue = contact_bundle.get("send_queue", [])
    if not isinstance(send_queue, list):
        raise RuntimeError(
            "Signal phase contact bundle must include a top-level 'send_queue' list."
        )

    configured_channels = contact_bundle.get("official_channels")
    if not isinstance(configured_channels, list) or len(configured_channels) < 2:
        raise RuntimeError(
            "Provide verified official_channels in the private contact bundle."
        )
    if any(
        not isinstance(row, dict)
        or not row.get("channel_type")
        or not row.get("channel_value")
        for row in configured_channels
    ):
        raise RuntimeError(
            "Each official channel requires channel_type and channel_value."
        )
    official_channels_rows = [dict(row) for row in configured_channels]
    source_observed_as_of = str(contact_bundle.get("source_observed_as_of") or "")
    if not source_observed_as_of:
        raise RuntimeError(
            "Provide source_observed_as_of for verified contact channels."
        )
    phone_channel = next(
        (row for row in official_channels_rows if row["channel_type"] == "phone"), None
    )
    if phone_channel is None:
        raise RuntimeError("Provide a verified phone escalation channel.")
    primary_channel_default = {
        "channel_type": official_channels_rows[0]["channel_type"],
        "channel_value": official_channels_rows[0]["channel_value"],
    }
    secondary_channel_default = {
        "channel_type": official_channels_rows[1]["channel_type"],
        "channel_value": official_channels_rows[1]["channel_value"],
    }

    resolution_queue_rows: list[dict[str, Any]] = []
    packet_paths: list[str] = []

    for row in sorted(
        [item for item in send_queue if isinstance(item, dict)],
        key=lambda item: (
            _priority_value(item.get("priority_rank")),
            str(item.get("junction_id") or ""),
        ),
    ):
        preferred_primary_channel = _clean_text(row.get("preferred_primary_channel"))
        preferred_secondary_channel = _clean_text(
            row.get("preferred_secondary_channel")
        )
        primary_channel = _resolve_channel(
            official_channels_rows,
            preferred_primary_channel,
            primary_channel_default,
        )
        secondary_channel = _resolve_channel(
            official_channels_rows,
            preferred_secondary_channel,
            secondary_channel_default,
        )
        routing_decision = _clean_text(row.get("routing_decision"))
        external_blocker = _clean_text(row.get("external_blocker"))
        queue_row = {
            "request_id": str(row["request_id"]),
            "junction_id": _clean_text(row.get("junction_id")),
            "signal_name": _clean_text(row.get("signal_name")),
            "priority_rank": _safe_int(row.get("priority_rank")),
            "priority_band": _clean_text(row.get("priority_band")),
            "send_readiness": _clean_text(row.get("send_readiness")),
            "contact_name": _clean_text(row.get("contact_name")),
            "contact_email": _clean_text(row.get("contact_email")),
            "preferred_primary_channel": preferred_primary_channel,
            "preferred_secondary_channel": preferred_secondary_channel,
            "routing_decision": routing_decision,
            "external_blocker": external_blocker,
            "email_subject": _clean_text(row.get("email_subject")),
            "recommended_time_window": _clean_text(row.get("recommended_time_window")),
            "preferred_focus_hour_ranges": _clean_text(
                row.get("preferred_focus_hour_ranges")
            ),
            "fallback_pilot_scope": _clean_text(row.get("fallback_pilot_scope")),
            "unresolved_signalized_movement_count": _safe_int(
                row.get("unresolved_signalized_movement_count")
            ),
            "unresolved_signalized_crash_count": _safe_int(
                row.get("unresolved_signalized_crash_count")
            ),
            "unresolved_coverage_pct": round(
                _safe_float(row.get("unresolved_coverage_pct")), 2
            ),
            "unresolved_crash_coverage_pct": round(
                _safe_float(row.get("unresolved_crash_coverage_pct")), 2
            ),
            "primary_channel_type": primary_channel["channel_type"],
            "primary_channel_value": primary_channel["channel_value"],
            "secondary_channel_type": secondary_channel["channel_type"],
            "secondary_channel_value": secondary_channel["channel_value"],
            "phone_escalation_type": phone_channel["channel_type"],
            "phone_escalation_value": phone_channel["channel_value"],
            "source_observed_as_of": source_observed_as_of,
            "recommended_routing_action": routing_decision
            or (
                "Send by PEC or email through the primary mobility/viabilità routing channel, "
                "CC the archivio generale PEC, and call the centralino if routing confirmation is needed."
            ),
        }
        resolution_queue_rows.append(queue_row)

        packet_md_path = packet_dir / f"{_slugify(queue_row['request_id'])}.md"
        packet_json_path = packet_dir / f"{_slugify(queue_row['request_id'])}.json"
        packet_md_path.write_text(
            _resolution_packet_markdown(queue_row), encoding="utf-8"
        )
        packet_json_path.write_text(
            json.dumps(queue_row, indent=2, sort_keys=True), encoding="utf-8"
        )
        packet_paths.extend([str(packet_md_path), str(packet_json_path)])

    official_contact_channels_path = output_root / "official_contact_channels.csv"
    contact_resolution_queue_path = output_root / "contact_resolution_queue.csv"
    bundle_json_path = output_root / "signal_phase_contact_resolution_bundle.json"
    bundle_md_path = output_root / "signal_phase_contact_resolution_bundle.md"
    manifest_path = output_root / "signal_phase_contact_resolution_bundle.manifest.json"

    _write_csv(
        official_contact_channels_path,
        official_channels_rows,
        [
            "channel_id",
            "channel_role",
            "channel_type",
            "channel_value",
            "owner_team",
            "recommended_use",
            "source_title",
            "source_url",
            "source_observed_as_of",
        ],
    )
    _write_csv(
        contact_resolution_queue_path,
        resolution_queue_rows,
        [
            "request_id",
            "junction_id",
            "signal_name",
            "priority_rank",
            "priority_band",
            "send_readiness",
            "contact_name",
            "contact_email",
            "preferred_primary_channel",
            "preferred_secondary_channel",
            "routing_decision",
            "external_blocker",
            "email_subject",
            "recommended_time_window",
            "preferred_focus_hour_ranges",
            "fallback_pilot_scope",
            "unresolved_signalized_movement_count",
            "unresolved_signalized_crash_count",
            "unresolved_coverage_pct",
            "unresolved_crash_coverage_pct",
            "primary_channel_type",
            "primary_channel_value",
            "secondary_channel_type",
            "secondary_channel_value",
            "phone_escalation_type",
            "phone_escalation_value",
            "source_observed_as_of",
            "recommended_routing_action",
        ],
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "target_count": len(resolution_queue_rows),
        "direct_contact_count": sum(
            1 for row in resolution_queue_rows if row["contact_email"]
        ),
        "routable_via_official_channels_count": len(resolution_queue_rows),
        "official_channel_count": len(official_channels_rows),
        "external_blocker_count": sum(
            1
            for row in resolution_queue_rows
            if _clean_text(row.get("external_blocker"))
        ),
        "targets_with_unresolved_movements": sum(
            1
            for row in resolution_queue_rows
            if _safe_int(row["unresolved_signalized_movement_count"]) > 0
        ),
        "unresolved_signalized_movement_total": sum(
            _safe_int(row["unresolved_signalized_movement_count"])
            for row in resolution_queue_rows
        ),
        "unresolved_signalized_crash_total": sum(
            _safe_int(row["unresolved_signalized_crash_count"])
            for row in resolution_queue_rows
        ),
    }

    bundle_payload = {
        "signal_phase_contact_resolution_bundle_version": SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_VERSION,
        "signal_phase_contact_resolution_bundle_contract_version": SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_CONTRACT_VERSION,
        "generated_at_utc": summary["generated_at_utc"],
        "summary": summary,
        "resolution_queue": resolution_queue_rows,
        "official_channels": official_channels_rows,
    }
    bundle_json_path.write_text(
        json.dumps(bundle_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    bundle_md_path.write_text(_bundle_markdown(bundle_payload), encoding="utf-8")

    manifest = {
        "signal_phase_contact_resolution_bundle_version": SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_VERSION,
        "contract": {
            "resource_name": "signal_phase_contact_resolution_bundle",
            "public_contract_version": SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_CONTRACT_VERSION,
            "signal_phase_contact_resolution_bundle_version": SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_VERSION,
        },
        "source": {
            "adapter": "bari_signal_phase_contact_resolution_builder",
        },
        "inputs": {
            "signal_phase_contact_bundle_path": str(contact_bundle_input),
            "source_observed_as_of": source_observed_as_of,
        },
        "outputs": {
            "manifest_path": str(manifest_path),
            "bundle_json_path": str(bundle_json_path),
            "bundle_json_sha256": _sha256(bundle_json_path),
            "bundle_md_path": str(bundle_md_path),
            "bundle_md_sha256": _sha256(bundle_md_path),
            "official_contact_channels_path": str(official_contact_channels_path),
            "official_contact_channels_sha256": _sha256(official_contact_channels_path),
            "contact_resolution_queue_path": str(contact_resolution_queue_path),
            "contact_resolution_queue_sha256": _sha256(contact_resolution_queue_path),
            "packet_dir": str(packet_dir),
            "packet_paths": packet_paths,
        },
        "stats": summary,
    }
    manifest["lineage"] = _build_lineage_contract(
        run_record_path=manifest_path,
        upstream_inputs=[
            _artifact_reference(
                "signal_phase_contact_bundle",
                contact_bundle_input,
                _sha256(contact_bundle_input),
            ),
        ],
        publishable_outputs=[
            _artifact_reference(
                "signal_phase_contact_resolution_bundle_json",
                bundle_json_path,
                _sha256(bundle_json_path),
            ),
            _artifact_reference(
                "signal_phase_contact_resolution_bundle_markdown",
                bundle_md_path,
                _sha256(bundle_md_path),
            ),
        ],
        supporting_outputs=[
            _artifact_reference(
                "signal_phase_official_contact_channels",
                official_contact_channels_path,
                _sha256(official_contact_channels_path),
            ),
            _artifact_reference(
                "signal_phase_contact_resolution_queue",
                contact_resolution_queue_path,
                _sha256(contact_resolution_queue_path),
            ),
        ]
        + [
            _artifact_reference(
                "signal_phase_contact_resolution_packet",
                Path(path),
                _sha256(Path(path)),
            )
            for path in packet_paths
        ],
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return {
        "signal_phase_contact_resolution_bundle_version": SIGNAL_PHASE_CONTACT_RESOLUTION_BUNDLE_VERSION,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "stats": summary,
    }
