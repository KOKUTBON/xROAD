"""Curation utilities to produce model-ready canonical subsets."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_EXCLUDED_FLAGS: tuple[str, ...] = (
    "missing_coordinates",
    "invalid_coordinates",
    "coordinates_outside_expected_country_bounds",
    "coordinates_outside_expected_jurisdiction_bounds",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def curate_canonical_records(
    records_path: str | Path,
    output_path: str | Path | None = None,
    rejected_path: str | Path | None = None,
    excluded_flags: tuple[str, ...] = DEFAULT_EXCLUDED_FLAGS,
) -> dict[str, Any]:
    input_path = Path(records_path)
    curated_path = Path(output_path) if output_path else input_path.with_suffix(".curated.jsonl")
    rejected_output_path = Path(rejected_path) if rejected_path else input_path.with_suffix(".rejected.jsonl")
    manifest_path = curated_path.with_suffix(".manifest.json")

    curated_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_output_path.parent.mkdir(parents=True, exist_ok=True)

    kept_records = 0
    rejected_records = 0
    duplicate_source_unique_key_records = 0
    rejected_flag_counts: Counter[str] = Counter()
    kept_flag_counts: Counter[str] = Counter()
    seen_source_unique_keys: set[str] = set()

    with (
        input_path.open("r", encoding="utf-8") as input_handle,
        curated_path.open("w", encoding="utf-8") as curated_handle,
        rejected_output_path.open("w", encoding="utf-8") as rejected_handle,
    ):
        for line in input_handle:
            record = json.loads(line)
            quality_flags = [str(flag) for flag in (record.get("quality_flags") or [])]
            rejected_reasons = [flag for flag in quality_flags if flag in excluded_flags]

            source_unique_key = record.get("source_unique_key")
            if source_unique_key:
                if source_unique_key in seen_source_unique_keys:
                    rejected_reasons.append("duplicate_source_unique_key")
                    duplicate_source_unique_key_records += 1
                else:
                    seen_source_unique_keys.add(str(source_unique_key))

            if rejected_reasons:
                rejected_records += 1
                for reason in rejected_reasons:
                    rejected_flag_counts[reason] += 1
                rejected_handle.write(
                    json.dumps(
                        {
                            "rejected_reasons": rejected_reasons,
                            "record": record,
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                    + "\n"
                )
                continue

            kept_records += 1
            for flag in quality_flags:
                kept_flag_counts[flag] += 1
            curated_handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")

    manifest = {
        "inputs": {
            "records_path": str(input_path),
            "records_sha256": _sha256(input_path),
        },
        "outputs": {
            "curated_path": str(curated_path),
            "curated_sha256": _sha256(curated_path),
            "rejected_path": str(rejected_output_path),
            "rejected_sha256": _sha256(rejected_output_path),
            "manifest_path": str(manifest_path),
        },
        "policy": {
            "excluded_flags": list(excluded_flags),
        },
        "stats": {
            "kept_records": kept_records,
            "rejected_records": rejected_records,
            "duplicate_source_unique_key_records": duplicate_source_unique_key_records,
            "kept_quality_flag_counts": dict(sorted(kept_flag_counts.items())),
            "rejected_reason_counts": dict(sorted(rejected_flag_counts.items())),
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
