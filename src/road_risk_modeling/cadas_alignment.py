"""CADaS / CARE alignment for the canonical crash schema (Issue HE-04).

This module maps the :class:`CanonicalCrashRecord` to the EU **Common Accident
Data Set (CADaS)** used to feed the **CARE** Community road-accident database,
so that canonical records can be exported in an EU-standard-aligned form and
the divergences are explicitly catalogued.

CADaS groups variables into Accident (``A``), Road (``R``), Traffic-unit /
vehicle (``U``) and Person (``P``) blocks. This platform models at the
*accident* level with aggregate casualty counts, so the mapping is densest for
the ``A`` block; ``U``/``P`` person-level detail is largely out of scope and is
recorded as a documented gap.

.. note::
   CADaS variable identifiers follow the EC CADaS glossary. Numeric IDs differ
   slightly between glossary versions; the identifiers here target the
   high-level variable set and **must be validated against the CADaS glossary
   version in force** before any formal CARE submission. The ``cadas_group``
   prefixes and variable names are stable across versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import csv
import json
from pathlib import Path
from typing import Any

from .canonical_schema import CanonicalCrashRecord
from .modeling import _artifact_reference, _sha256

CADAS_ALIGNMENT_VERSION = "cadas_alignment_v1"
CADAS_GLOSSARY_TARGET = "CADaS high-level variable set (validate numeric IDs against the glossary in force)"

# Mapping levels mirror CADaS' distinction between high-level (core) and
# optional variables.
LEVEL_MANDATORY = "mandatory"
LEVEL_RECOMMENDED = "recommended"
LEVEL_OPTIONAL = "optional"

# Per-field mapping status.
STATUS_MAPPED = "mapped"  # produced directly from a canonical field
STATUS_DERIVED = "derived"  # computed from canonical fields
STATUS_SOURCE_DEPENDENT = "source_dependent"  # only present for some sources
STATUS_GAP = "gap"  # required by CADaS but not available in the canonical record


@dataclass(frozen=True, slots=True)
class CadasMapping:
    """One row of the canonical-to-CADaS crosswalk."""

    cadas_variable: str
    cadas_name: str
    cadas_group: str  # "A" accident, "R" road, "U" unit/vehicle, "P" person
    level: str
    canonical_field: str | None
    status: str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "cadas_variable": self.cadas_variable,
            "cadas_name": self.cadas_name,
            "cadas_group": self.cadas_group,
            "level": self.level,
            "canonical_field": self.canonical_field,
            "status": self.status,
            "notes": self.notes,
        }


# The crosswalk. Where one canonical field feeds several CADaS variables (e.g.
# the timestamp), each CADaS target gets its own row.
CADAS_VARIABLE_MAP: tuple[CadasMapping, ...] = (
    CadasMapping("A.1", "Country", "A", LEVEL_MANDATORY, "country_code",
                 STATUS_MAPPED, "ISO country code; CADaS uses the EC country list."),
    CadasMapping("A.2", "Accident identification number", "A", LEVEL_MANDATORY, "crash_id",
                 STATUS_MAPPED, "Synthetic stable crash_id satisfies the unique-id requirement."),
    CadasMapping("A.3", "Date of the accident", "A", LEVEL_MANDATORY, "occurred_at",
                 STATUS_DERIVED, "Derived from occurred_year/month/day or occurred_at."),
    CadasMapping("A.4", "Hour of the accident", "A", LEVEL_MANDATORY, "occurred_hour",
                 STATUS_DERIVED, "Hour bucket; timestamp_precision flags coarse sources."),
    CadasMapping("A.5", "Latitude", "A", LEVEL_RECOMMENDED, "latitude",
                 STATUS_SOURCE_DEPENDENT, "WGS84; restricted personal-data field, kept internal."),
    CadasMapping("A.6", "Longitude", "A", LEVEL_RECOMMENDED, "longitude",
                 STATUS_SOURCE_DEPENDENT, "WGS84; restricted personal-data field, kept internal."),
    CadasMapping("A.7", "NUTS / region code", "A", LEVEL_RECOMMENDED, "region_code",
                 STATUS_SOURCE_DEPENDENT, "ISTAT region today; map to NUTS for cross-border use."),
    CadasMapping("A.8", "Weather conditions", "A", LEVEL_RECOMMENDED, "weather_code",
                 STATUS_SOURCE_DEPENDENT, "Requires a value-set crosswalk to CADaS weather codes."),
    CadasMapping("A.9", "Light conditions", "A", LEVEL_RECOMMENDED, "light_condition",
                 STATUS_SOURCE_DEPENDENT, "Requires a value-set crosswalk to CADaS light codes."),
    CadasMapping("A.10", "Number of persons killed", "A", LEVEL_MANDATORY, "fatalities",
                 STATUS_MAPPED, "Aggregate count; CADaS death horizon is 30 days."),
    CadasMapping("A.11", "Number of persons injured", "A", LEVEL_MANDATORY, "injuries",
                 STATUS_MAPPED, "Aggregate count; serious/slight split not separated in canonical."),
    CadasMapping("R.1", "Road type / carriageway", "R", LEVEL_RECOMMENDED, "roadway_type",
                 STATUS_SOURCE_DEPENDENT, "Crosswalk to CADaS road-type value set."),
    CadasMapping("R.2", "Junction / intersection", "R", LEVEL_RECOMMENDED, "intersection_type",
                 STATUS_SOURCE_DEPENDENT, "Crosswalk to CADaS junction value set."),
    # Documented gaps: CADaS variables this accident-level platform does not yet
    # produce. Recorded so the divergence is explicit, not silent.
    CadasMapping("A.12", "Type of area (urban/rural)", "A", LEVEL_RECOMMENDED, None,
                 STATUS_GAP, "Derivable from jurisdiction/road class; planned with rural work (#224)."),
    CadasMapping("P.x", "Person-level casualty detail (age, sex, severity, road-user type)", "P",
                 LEVEL_RECOMMENDED, None, STATUS_GAP,
                 "Platform is accident-level with aggregate counts; person-level not modelled."),
    CadasMapping("U.x", "Traffic-unit / vehicle detail", "U", LEVEL_RECOMMENDED, None,
                 STATUS_GAP, "Vehicle-level attributes not in the canonical record."),
)


def to_cadas_record(record: CanonicalCrashRecord | dict[str, Any]) -> dict[str, Any]:
    """Map one canonical crash record to a CADaS-keyed dict.

    Only directly mappable / derivable variables are emitted; gaps are omitted
    here and catalogued by :func:`cadas_coverage_gaps`.
    """

    data = record.to_dict() if isinstance(record, CanonicalCrashRecord) else dict(record)

    def _date() -> str | None:
        if data.get("occurred_at"):
            return str(data["occurred_at"])[:10]
        y, m, d = data.get("occurred_year"), data.get("occurred_month"), data.get("occurred_day")
        if y and m and d:
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        return None

    out: dict[str, Any] = {
        "A.1": data.get("country_code"),
        "A.2": data.get("crash_id"),
        "A.3": _date(),
        "A.4": data.get("occurred_hour"),
        "A.5": data.get("latitude"),
        "A.6": data.get("longitude"),
        "A.7": data.get("region_code"),
        "A.8": data.get("weather_code"),
        "A.9": data.get("light_condition"),
        "A.10": data.get("fatalities"),
        "A.11": data.get("injuries"),
        "R.1": data.get("roadway_type"),
        "R.2": data.get("intersection_type"),
    }
    return out


def cadas_coverage_gaps() -> list[dict[str, Any]]:
    """CADaS variables in the map that the canonical record cannot fill."""

    return [m.as_dict() for m in CADAS_VARIABLE_MAP if m.status == STATUS_GAP]


def _coverage_stats() -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_level: dict[str, int] = {}
    for m in CADAS_VARIABLE_MAP:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        by_level[m.level] = by_level.get(m.level, 0) + 1
    mandatory = [m for m in CADAS_VARIABLE_MAP if m.level == LEVEL_MANDATORY]
    mandatory_covered = [m for m in mandatory if m.status != STATUS_GAP]
    return {
        "variables_total": len(CADAS_VARIABLE_MAP),
        "by_status": by_status,
        "by_level": by_level,
        "mandatory_total": len(mandatory),
        "mandatory_covered": len(mandatory_covered),
    }


def _render_markdown(stats: dict[str, Any]) -> str:
    lines = [
        "# CADaS / CARE Alignment Crosswalk",
        "",
        f"Version: `{CADAS_ALIGNMENT_VERSION}`.",
        f"Target: {CADAS_GLOSSARY_TARGET}.",
        "",
        "This crosswalk maps the canonical crash schema to the EU Common "
        "Accident Data Set (CADaS) that feeds CARE. It is generated by "
        "`road-risk build-cadas-alignment`.",
        "",
        f"- Variables in crosswalk: **{stats['variables_total']}**",
        f"- Mandatory covered: **{stats['mandatory_covered']}/{stats['mandatory_total']}**",
        f"- By status: {stats['by_status']}",
        "",
        "| CADaS | Name | Group | Level | Canonical field | Status | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in CADAS_VARIABLE_MAP:
        lines.append(
            f"| {m.cadas_variable} | {m.cadas_name} | {m.cadas_group} | {m.level} "
            f"| {m.canonical_field or '—'} | {m.status} | {m.notes} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_cadas_alignment_bundle(
    *,
    output_dir: str | Path = "data/governance/cadas_alignment",
) -> dict[str, Any]:
    """Materialize the CADaS crosswalk, gap list, and a manifest."""

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    mapping_csv_path = output_root / "cadas_variable_map.csv"
    bundle_json_path = output_root / "cadas_alignment_bundle.json"
    gaps_json_path = output_root / "cadas_coverage_gaps.json"
    markdown_path = output_root / "cadas_alignment.md"
    manifest_path = output_root / "cadas_alignment_bundle.manifest.json"

    stats = _coverage_stats()
    rows = [m.as_dict() for m in CADAS_VARIABLE_MAP]

    fieldnames = ["cadas_variable", "cadas_name", "cadas_group", "level",
                  "canonical_field", "status", "notes"]
    with mapping_csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row[k] is None else row[k]) for k in fieldnames})

    payload = {
        "cadas_alignment_version": CADAS_ALIGNMENT_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "cadas_glossary_target": CADAS_GLOSSARY_TARGET,
        "coverage": stats,
        "variable_map": rows,
        "coverage_gaps": cadas_coverage_gaps(),
    }
    bundle_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    gaps_json_path.write_text(json.dumps(payload["coverage_gaps"], indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(stats), encoding="utf-8")

    manifest = {
        "cadas_alignment_version": CADAS_ALIGNMENT_VERSION,
        "generated_at_utc": payload["generated_at_utc"],
        "outputs": [
            _artifact_reference("variable_map_csv", mapping_csv_path, _sha256(mapping_csv_path)),
            _artifact_reference("bundle_json", bundle_json_path, _sha256(bundle_json_path)),
            _artifact_reference("coverage_gaps_json", gaps_json_path, _sha256(gaps_json_path)),
            _artifact_reference("markdown", markdown_path, _sha256(markdown_path)),
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    payload["manifest_path"] = str(manifest_path)
    return payload


def export_canonical_to_cadas(
    *,
    canonical_path: str | Path,
    output_dir: str | Path = "data/staging/cadas_export",
) -> dict[str, Any]:
    """Export a canonical JSONL crash file to CADaS-aligned JSONL + CSV.

    This is the round-trip deliverable: canonical records become EU-standard
    CADaS-keyed rows that can be staged for a CARE-aligned submission.
    """

    input_path = Path(canonical_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    cadas_jsonl_path = output_root / "crashes_cadas.jsonl"
    cadas_csv_path = output_root / "crashes_cadas.csv"
    manifest_path = output_root / "cadas_export.manifest.json"

    cadas_keys = list(to_cadas_record(_EMPTY_CANONICAL).keys())
    count = 0
    with (
        input_path.open("r", encoding="utf-8") as src,
        cadas_jsonl_path.open("w", encoding="utf-8") as jsonl_out,
        cadas_csv_path.open("w", newline="", encoding="utf-8") as csv_out,
    ):
        writer = csv.DictWriter(csv_out, fieldnames=cadas_keys)
        writer.writeheader()
        for line in src:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            cadas_row = to_cadas_record(record)
            jsonl_out.write(json.dumps(cadas_row) + "\n")
            writer.writerow({k: ("" if cadas_row.get(k) is None else cadas_row[k]) for k in cadas_keys})
            count += 1

    payload = {
        "cadas_alignment_version": CADAS_ALIGNMENT_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_canonical_path": str(input_path),
        "records_exported": count,
        "cadas_variables": cadas_keys,
    }
    manifest = {
        "cadas_alignment_version": CADAS_ALIGNMENT_VERSION,
        "generated_at_utc": payload["generated_at_utc"],
        "records_exported": count,
        "outputs": [
            _artifact_reference("cadas_jsonl", cadas_jsonl_path, _sha256(cadas_jsonl_path)),
            _artifact_reference("cadas_csv", cadas_csv_path, _sha256(cadas_csv_path)),
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    payload["manifest_path"] = str(manifest_path)
    return payload


# A neutral canonical record used only to derive the stable CADaS key order.
_EMPTY_CANONICAL: dict[str, Any] = {
    "crash_id": None, "country_code": None, "occurred_at": None,
    "occurred_year": None, "occurred_month": None, "occurred_day": None,
    "occurred_hour": None, "latitude": None, "longitude": None,
    "region_code": None, "weather_code": None, "light_condition": None,
    "fatalities": None, "injuries": None, "roadway_type": None,
    "intersection_type": None,
}
