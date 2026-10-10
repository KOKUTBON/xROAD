"""Legacy ingestion flows that emit canonical records."""

from __future__ import annotations

import csv
from collections import Counter
import io
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from .adapters import map_bari_open_data_row, map_puglia_cleaned_row
from .jurisdictions import load_istat_jurisdiction_lookups
from .legacy_zip import iter_csv_member_rows


DEFAULT_BARI_OPEN_DATA_SOURCES = (
    {
        "year": 2022,
        "label": "incidenti-stradali-anno-2022",
        "url": (
            "https://opendata.comune.bari.it/dataset/e20277fa-b874-4eb0-91f3-6ba9fcc9032d/"
            "resource/3a407f54-8117-4064-b597-202063b940d8/download/elenco-incidenti.csv"
        ),
    },
    {
        "year": 2023,
        "label": "incidenti-stradali-anno-2023",
        "url": (
            "https://opendata.comune.bari.it/dataset/6738d454-744f-456a-a1d8-858d0adeb177/"
            "resource/eeca93bd-96b4-4da6-bdf7-0531f6c8cfa8/download/elenco-incidenti-periodo-2023.csv"
        ),
    },
    {
        "year": 2024,
        "label": "incidenti-stradali-anno-2024",
        "url": (
            "https://opendata.comune.bari.it/dataset/d3a7948a-8a0c-4e4e-b6ca-6f022ae8c376/"
            "resource/20679961-aee8-4b0d-a11a-64ee2dd0d2f8/download/elenco-incidenti-periodo_-anno_2024.csv"
        ),
    },
    {
        "year": 2025,
        "label": "incidenti-stradali-anno-2025",
        "url": (
            "https://opendata.comune.bari.it/dataset/d008a63c-4801-4731-976d-31aaaac28ac5/"
            "resource/c462caff-a8cb-49fc-a10f-fd2efd879bf7/download/elenco-incidenti-periodo_-anno-2025.csv"
        ),
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"}


def _read_remote_bytes(url: str) -> bytes:
    if not _is_url(url):
        raise ValueError("Remote sources must use HTTP or HTTPS.")
    with urlopen(url, timeout=60) as response:  # nosec B310 # scheme checked above
        return response.read()


def _load_text_source(source: str | Path) -> tuple[str, bytes]:
    source_text = str(source)
    if _is_url(source_text):
        return source_text, _read_remote_bytes(source_text)

    path = Path(source_text)
    return str(path), path.read_bytes()


def _sniff_csv_dialect(text: str) -> csv.Dialect:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        if sample.count(";") > sample.count(","):
            return csv.excel()
        return csv.excel()


def _iter_csv_dict_rows(text: str) -> tuple[list[str], list[dict[str, str | None]]]:
    dialect = _sniff_csv_dialect(text)
    delimiter = ";" if text.splitlines() and text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else dialect.delimiter
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = [field or "" for field in (reader.fieldnames or [])]
    rows = [{key or "": value for key, value in row.items()} for row in reader]
    return fieldnames, rows


def _write_raw_source_copy(
    source_label: str,
    source_bytes: bytes,
    raw_dir: Path | None,
) -> dict[str, str] | None:
    if raw_dir is None:
        return None
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{source_label}.csv"
    raw_path.write_bytes(source_bytes)
    return {
        "raw_path": str(raw_path),
        "raw_sha256": _sha256(raw_path),
    }


def ingest_puglia_cleaned_csv(
    zip_path: str | Path,
    member: str,
    output_dir: str | Path,
    limit: int | None = None,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    records_path = output_root / "puglia_cleaned_canonical.jsonl"
    manifest_path = output_root / "puglia_cleaned_canonical.manifest.json"

    severity_counts: Counter[str] = Counter()
    quality_flag_counts: Counter[str] = Counter()
    roadway_type_counts: Counter[str] = Counter()
    coordinate_completeness = 0
    repaired_source_rows = 0
    decoded_city_name_records = 0
    decoded_province_name_records = 0
    total_records = 0

    jurisdiction_lookups = load_istat_jurisdiction_lookups(zip_path, required=False)
    _, csv_rows = iter_csv_member_rows(zip_path, member)

    with records_path.open("w", encoding="utf-8") as output_handle:
        for csv_row in csv_rows:
            if limit is not None and total_records >= limit:
                break

            record = map_puglia_cleaned_row(csv_row, jurisdiction_lookups=jurisdiction_lookups)
            output_handle.write(json.dumps(record.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")

            total_records += 1
            severity_counts[record.severity_level or "unknown"] += 1
            roadway_type_counts[record.roadway_type or "unknown"] += 1
            if record.city_name:
                decoded_city_name_records += 1
            if record.extra.get("jurisdiction", {}).get("province_name"):
                decoded_province_name_records += 1
            if record.latitude is not None and record.longitude is not None:
                coordinate_completeness += 1
            if csv_row.repaired:
                repaired_source_rows += 1
            for flag in record.quality_flags:
                quality_flag_counts[flag] += 1

    manifest = {
        "source": {
            "zip_path": str(Path(zip_path)),
            "member": member,
            "adapter": "puglia_cleaned_csv",
            "jurisdiction_codebooks_loaded": jurisdiction_lookups is not None,
        },
        "outputs": {
            "records_path": str(records_path),
            "records_sha256": _sha256(records_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "total_records": total_records,
            "coordinate_complete_records": coordinate_completeness,
            "repaired_source_rows": repaired_source_rows,
            "decoded_city_name_records": decoded_city_name_records,
            "decoded_province_name_records": decoded_province_name_records,
            "severity_counts": dict(sorted(severity_counts.items())),
            "roadway_type_counts": dict(sorted(roadway_type_counts.items())),
            "quality_flag_counts": dict(sorted(quality_flag_counts.items())),
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def ingest_bari_open_data_crashes(
    output_dir: str | Path,
    *,
    sources: list[dict[str, object]] | None = None,
    raw_dir: str | Path | None = "data/raw/bari_open_data_crashes",
    limit: int | None = None,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    raw_root = Path(raw_dir) if raw_dir is not None else None
    records_path = output_root / "bari_open_data_canonical.jsonl"
    manifest_path = output_root / "bari_open_data_canonical.manifest.json"

    active_sources = sources or [dict(item) for item in DEFAULT_BARI_OPEN_DATA_SOURCES]

    severity_counts: Counter[str] = Counter()
    quality_flag_counts: Counter[str] = Counter()
    roadway_type_counts: Counter[str] = Counter()
    timestamp_precision_counts: Counter[str] = Counter()
    source_year_counts: Counter[str] = Counter()
    total_records = 0
    coordinate_complete_records = 0
    dispatch_time_records = 0
    source_manifests: list[dict[str, object]] = []

    with records_path.open("w", encoding="utf-8") as output_handle:
        for source in active_sources:
            source_year = int(source["year"]) if source.get("year") is not None else None
            source_url = str(source["url"])
            source_label = str(source.get("label") or f"bari_open_data_{source_year or 'unknown'}")
            source_name, source_bytes = _load_text_source(source_url)
            source_text = source_bytes.decode("utf-8-sig")
            fieldnames, rows = _iter_csv_dict_rows(source_text)

            raw_source_payload = _write_raw_source_copy(source_label, source_bytes, raw_root)
            source_record_count = 0

            for row_number, row in enumerate(rows, start=1):
                if limit is not None and total_records >= limit:
                    break

                record = map_bari_open_data_row(
                    row,
                    source_name=source_name,
                    source_row_number=row_number,
                    source_year=source_year,
                )
                output_handle.write(json.dumps(record.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")

                total_records += 1
                source_record_count += 1
                severity_counts[record.severity_level or "unknown"] += 1
                roadway_type_counts[record.roadway_type or "unknown"] += 1
                timestamp_precision_counts[record.timestamp_precision or "unknown"] += 1
                source_year_counts[str(record.occurred_year or source_year or "unknown")] += 1
                if record.latitude is not None and record.longitude is not None:
                    coordinate_complete_records += 1
                if record.occurred_hour is not None and record.occurred_minute is not None:
                    dispatch_time_records += 1
                for flag in record.quality_flags:
                    quality_flag_counts[flag] += 1

            source_manifest = {
                "year": source_year,
                "label": source_label,
                "source_url": source_url,
                "resolved_source": source_name,
                "fieldnames": fieldnames,
                "records_ingested": source_record_count,
            }
            if raw_source_payload:
                source_manifest.update(raw_source_payload)
            source_manifests.append(source_manifest)

            if limit is not None and total_records >= limit:
                break

    manifest = {
        "source": {
            "adapter": "bari_open_data_ckan_csv",
            "catalog_host": "https://opendata.comune.bari.it",
            "source_count": len(source_manifests),
            "sources": source_manifests,
        },
        "outputs": {
            "records_path": str(records_path),
            "records_sha256": _sha256(records_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "total_records": total_records,
            "coordinate_complete_records": coordinate_complete_records,
            "dispatch_time_records": dispatch_time_records,
            "severity_counts": dict(sorted(severity_counts.items())),
            "roadway_type_counts": dict(sorted(roadway_type_counts.items())),
            "timestamp_precision_counts": dict(sorted(timestamp_precision_counts.items())),
            "source_year_counts": dict(sorted(source_year_counts.items())),
            "quality_flag_counts": dict(sorted(quality_flag_counts.items())),
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
