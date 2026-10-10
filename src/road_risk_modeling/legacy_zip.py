"""Utilities for inspecting legacy project archives without manual extraction."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
import io
from pathlib import Path
import zipfile


IGNORED_PREFIXES = ("__MACOSX/",)
CSV_NULL_TOKENS = {"", "NA", "N/A", "NULL", "null"}


def _is_relevant_member(name: str) -> bool:
    return not any(name.startswith(prefix) for prefix in IGNORED_PREFIXES)


def _clean_field_name(value: str | None) -> str:
    return (value or "").replace("\ufeff", "").strip()


def _coerce_text(value: str | None) -> str:
    return (value or "").strip()


@dataclass(frozen=True, slots=True)
class CsvMemberRow:
    member: str
    row_number: int
    data: dict[str, str]
    repaired: bool


def _rebalance_row(fieldnames: list[str], row: list[str]) -> tuple[list[str], bool]:
    if len(row) == len(fieldnames):
        return row, False

    if len(row) < len(fieldnames):
        return row + [""] * (len(fieldnames) - len(row)), False

    if "DESCRIZIONE1" not in fieldnames:
        return row[: len(fieldnames)], True

    description_index = fieldnames.index("DESCRIZIONE1")
    suffix_size = len(fieldnames) - description_index - 1
    prefix = row[:description_index]
    suffix = row[-suffix_size:] if suffix_size else []
    description_tokens = row[description_index : len(row) - suffix_size] if suffix_size else row[description_index:]
    repaired = prefix + [",".join(description_tokens)] + suffix
    return repaired[: len(fieldnames)], True


def list_csv_members(zip_path: str | Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            info.filename
            for info in archive.infolist()
            if not info.is_dir()
            and _is_relevant_member(info.filename)
            and info.filename.lower().endswith(".csv")
        ]
    return sorted(members)


def iter_csv_member_rows(zip_path: str | Path, member: str) -> tuple[list[str], list[CsvMemberRow]]:
    rows: list[CsvMemberRow] = []

    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(member, "r") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
            reader = csv.reader(text)
            try:
                header = next(reader)
            except StopIteration:
                header = []
            fieldnames = [_clean_field_name(name) for name in header]

            for row_number, raw_values in enumerate(reader, start=2):
                values, repaired = _rebalance_row(fieldnames, raw_values)
                row = {
                    fieldnames[index]: _coerce_text(values[index]) if index < len(values) else ""
                    for index in range(len(fieldnames))
                }
                rows.append(
                    CsvMemberRow(
                        member=member,
                        row_number=row_number,
                        data=row,
                        repaired=repaired,
                    )
                )

    return fieldnames, rows


def inspect_zip(zip_path: str | Path) -> dict[str, object]:
    zip_file = Path(zip_path)
    with zipfile.ZipFile(zip_file) as archive:
        members = [info for info in archive.infolist() if _is_relevant_member(info.filename)]
        files = [info for info in members if not info.is_dir()]
        directories = [info for info in members if info.is_dir()]

        suffixes = Counter()
        top_level = Counter()
        for info in files:
            suffixes[Path(info.filename).suffix.lower() or "<none>"] += 1
            top_level[info.filename.split("/", 1)[0]] += 1

        largest_files = [
            {"path": info.filename, "size_bytes": info.file_size}
            for info in sorted(files, key=lambda item: item.file_size, reverse=True)[:10]
        ]

        candidate_crash_data = [
            info.filename
            for info in files
            if any(token in info.filename.lower() for token in ("incident", "dataset", "microdati", "crash"))
        ][:20]

    return {
        "zip_path": str(zip_file),
        "file_count": len(files),
        "directory_count": len(directories),
        "top_level_entries": dict(sorted(top_level.items())),
        "suffix_counts": dict(sorted(suffixes.items())),
        "largest_files": largest_files,
        "csv_members": list_csv_members(zip_file),
        "candidate_crash_data": candidate_crash_data,
    }


def profile_csv_member(zip_path: str | Path, member: str, sample_size: int = 3) -> dict[str, object]:
    row_count = 0
    missing_counts: Counter[str] = Counter()
    year_distribution: Counter[str] = Counter()
    sample_rows: list[dict[str, str]] = []
    coordinate_rows = 0
    repaired_row_count = 0

    fieldnames, rows = iter_csv_member_rows(zip_path, member)

    for csv_row in rows:
        row = csv_row.data
        row_count += 1

        if csv_row.repaired:
            repaired_row_count += 1

        if len(sample_rows) < sample_size:
            sample_rows.append(row)

        for field in fieldnames:
            if row.get(field, "") in CSV_NULL_TOKENS:
                missing_counts[field] += 1

        for year_field in ("ANNO", "YEAR", "year"):
            year_value = row.get(year_field)
            if year_value:
                year_distribution[year_value] += 1
                break

        latitude = (
            row.get("YCOORD_ACI")
            if "YCOORD_ACI" in row
            else row.get("latitude") or row.get("lat")
        )
        longitude = (
            row.get("XCOORD_ACI")
            if "XCOORD_ACI" in row
            else row.get("longitude") or row.get("lon")
        )
        if _coerce_text(latitude) not in CSV_NULL_TOKENS and _coerce_text(longitude) not in CSV_NULL_TOKENS:
            coordinate_rows += 1

    missing_summary = {
        field: missing_counts.get(field, 0)
        for field in fieldnames
        if missing_counts.get(field, 0) > 0
    }

    return {
        "member": member,
        "row_count": row_count,
        "column_count": len(fieldnames),
        "columns": fieldnames,
        "missing_counts": missing_summary,
        "year_distribution": dict(sorted(year_distribution.items())),
        "coordinate_row_count": coordinate_rows,
        "repaired_row_count": repaired_row_count,
        "sample_rows": sample_rows,
    }
