"""Jurisdiction codebook parsing and crash profiling utilities."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import html
import json
from dataclasses import dataclass
from pathlib import Path
import re
import zipfile


PROVINCE_CODEBOOK_MEMBER = (
    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/"
    "INCSTRAD_Classificazione_2020_var2.html"
)
MUNICIPALITY_CODEBOOK_MEMBER = (
    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/"
    "INCSTRAD_Classificazione_2020_var3.html"
)

ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
CELL_PATTERN = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_istat_code(value: str | None, width: int) -> str | None:
    text = (value or "").strip()
    digits = "".join(character for character in text if character.isdigit())
    if not digits:
        return None
    return digits.zfill(width)


def _clean_html_cell(value: str) -> str:
    text = TAG_PATTERN.sub("", value)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    return " ".join(text.split())


def _parse_html_table_rows(document: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in ROW_PATTERN.findall(document):
        cells = [_clean_html_cell(cell) for cell in CELL_PATTERN.findall(row_html)]
        if cells:
            rows.append(cells)
    return rows


@dataclass(frozen=True, slots=True)
class IstatJurisdictionLookups:
    province_by_code: dict[str, str]
    municipality_by_key: dict[tuple[str, str], str]

    def province_name_for(self, province_code: str | None) -> str | None:
        normalized = normalize_istat_code(province_code, width=3)
        if normalized is None:
            return None
        return self.province_by_code.get(normalized)

    def municipality_name_for(self, province_code: str | None, city_code: str | None) -> str | None:
        normalized_province = normalize_istat_code(province_code, width=3)
        normalized_city = normalize_istat_code(city_code, width=3)
        if normalized_province is None or normalized_city is None:
            return None
        return self.municipality_by_key.get((normalized_province, normalized_city))


def load_istat_jurisdiction_lookups(
    zip_path: str | Path,
    province_member: str = PROVINCE_CODEBOOK_MEMBER,
    municipality_member: str = MUNICIPALITY_CODEBOOK_MEMBER,
    required: bool = True,
) -> IstatJurisdictionLookups | None:
    zip_input = Path(zip_path)
    try:
        with zipfile.ZipFile(zip_input) as archive:
            province_html = archive.read(province_member).decode("cp1252", errors="replace")
            municipality_html = archive.read(municipality_member).decode("cp1252", errors="replace")
    except KeyError:
        if required:
            raise RuntimeError(
                "Could not find ISTAT province/municipality codebooks in the legacy ZIP archive."
            ) from None
        return None

    province_lookup: dict[str, str] = {}
    for row in _parse_html_table_rows(province_html):
        if len(row) < 2:
            continue
        province_code = normalize_istat_code(row[0], width=3)
        province_name = row[1].strip()
        if province_code is None or not province_name or province_name.lower() == "descrizione":
            continue
        province_lookup[province_code] = province_name

    municipality_lookup: dict[tuple[str, str], str] = {}
    for row in _parse_html_table_rows(municipality_html):
        if len(row) < 3:
            continue
        municipality_code = normalize_istat_code(row[0], width=3)
        municipality_name = row[1].strip()
        province_code = normalize_istat_code(row[2], width=3)
        if (
            municipality_code is None
            or province_code is None
            or not municipality_name
            or municipality_name.lower() == "descrizione"
        ):
            continue
        municipality_lookup[(province_code, municipality_code)] = municipality_name

    if required and (not province_lookup or not municipality_lookup):
        raise RuntimeError("ISTAT jurisdiction codebooks were found but could not be parsed.")

    return IstatJurisdictionLookups(
        province_by_code=province_lookup,
        municipality_by_key=municipality_lookup,
    )


def extract_istat_codebooks(zip_path: str | Path, output_dir: str | Path) -> dict[str, object]:
    zip_input = Path(zip_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    lookups = load_istat_jurisdiction_lookups(zip_input, required=True)
    if lookups is None:
        raise ValueError("Required jurisdiction lookups were not loaded.")

    provinces_path = output_root / "istat_provinces.csv"
    municipalities_path = output_root / "istat_municipalities.csv"
    manifest_path = output_root / "istat_codebooks.manifest.json"

    with provinces_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["province_code", "province_name"])
        writer.writeheader()
        for province_code, province_name in sorted(lookups.province_by_code.items()):
            writer.writerow({"province_code": province_code, "province_name": province_name})

    with municipalities_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["province_code", "province_name", "city_code", "city_name"],
        )
        writer.writeheader()
        for (province_code, city_code), city_name in sorted(lookups.municipality_by_key.items()):
            writer.writerow(
                {
                    "province_code": province_code,
                    "province_name": lookups.province_by_code.get(province_code),
                    "city_code": city_code,
                    "city_name": city_name,
                }
            )

    manifest = {
        "source": {
            "zip_path": str(zip_input),
            "province_member": PROVINCE_CODEBOOK_MEMBER,
            "municipality_member": MUNICIPALITY_CODEBOOK_MEMBER,
        },
        "outputs": {
            "provinces_path": str(provinces_path),
            "provinces_sha256": _sha256(provinces_path),
            "municipalities_path": str(municipalities_path),
            "municipalities_sha256": _sha256(municipalities_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "province_count": len(lookups.province_by_code),
            "municipality_count": len(lookups.municipality_by_key),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def profile_canonical_jurisdictions(
    records_path: str | Path,
    output_dir: str | Path,
    zip_path: str | Path | None = None,
    top_n: int = 20,
) -> dict[str, object]:
    records_input = Path(records_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    lookups = load_istat_jurisdiction_lookups(zip_path, required=False) if zip_path else None

    city_rows: dict[tuple[str | None, str | None], dict[str, object]] = {}
    province_rows: dict[str | None, dict[str, object]] = {}
    total_records = 0
    decoded_city_name_records = 0
    decoded_province_name_records = 0
    missing_city_code_records = 0
    missing_province_code_records = 0

    with records_input.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            total_records += 1

            province_code = normalize_istat_code(record.get("province_code"), width=3)
            city_code = normalize_istat_code(record.get("city_code"), width=3)

            if province_code is None:
                missing_province_code_records += 1
            if city_code is None:
                missing_city_code_records += 1

            city_name = (record.get("city_name") or "").strip() or None
            province_name = None
            if lookups is not None:
                province_name = lookups.province_name_for(province_code) or None
                city_name = city_name or lookups.municipality_name_for(province_code, city_code)

            if city_name is not None:
                decoded_city_name_records += 1
            if province_name is not None:
                decoded_province_name_records += 1

            group_key = (province_code, city_code)
            if group_key not in city_rows:
                city_rows[group_key] = {
                    "province_code": province_code,
                    "province_name": province_name,
                    "city_code": city_code,
                    "city_name": city_name,
                    "crash_count": 0,
                    "fatal_crash_count": 0,
                    "injury_crash_count": 0,
                    "fatalities_total": 0,
                    "injuries_total": 0,
                    "coordinate_complete_records": 0,
                    "years_present": set(),
                }
            city_row = city_rows[group_key]
            city_row["province_name"] = city_row["province_name"] or province_name
            city_row["city_name"] = city_row["city_name"] or city_name
            city_row["crash_count"] += 1
            severity_level = record.get("severity_level")
            if severity_level == "fatal":
                city_row["fatal_crash_count"] += 1
            if severity_level == "injury":
                city_row["injury_crash_count"] += 1
            city_row["fatalities_total"] += int(record.get("fatalities") or 0)
            city_row["injuries_total"] += int(record.get("injuries") or 0)
            if record.get("latitude") is not None and record.get("longitude") is not None:
                city_row["coordinate_complete_records"] += 1
            if record.get("occurred_year") is not None:
                city_row["years_present"].add(int(record["occurred_year"]))

            if province_code not in province_rows:
                province_rows[province_code] = {
                    "province_code": province_code,
                    "province_name": province_name,
                    "crash_count": 0,
                    "fatal_crash_count": 0,
                    "injury_crash_count": 0,
                    "fatalities_total": 0,
                    "injuries_total": 0,
                    "distinct_city_codes": set(),
                }
            province_row = province_rows[province_code]
            province_row["province_name"] = province_row["province_name"] or province_name
            province_row["crash_count"] += 1
            if severity_level == "fatal":
                province_row["fatal_crash_count"] += 1
            if severity_level == "injury":
                province_row["injury_crash_count"] += 1
            province_row["fatalities_total"] += int(record.get("fatalities") or 0)
            province_row["injuries_total"] += int(record.get("injuries") or 0)
            if city_code is not None:
                province_row["distinct_city_codes"].add(city_code)

    city_profile_path = output_root / "jurisdiction_city_profile.csv"
    province_profile_path = output_root / "jurisdiction_province_profile.csv"
    summary_path = output_root / "jurisdiction_profile.json"

    city_profile_rows = []
    for row in city_rows.values():
        years_present = sorted(row["years_present"])
        city_profile_rows.append(
            {
                "province_code": row["province_code"],
                "province_name": row["province_name"],
                "city_code": row["city_code"],
                "city_name": row["city_name"],
                "crash_count": row["crash_count"],
                "fatal_crash_count": row["fatal_crash_count"],
                "injury_crash_count": row["injury_crash_count"],
                "fatalities_total": row["fatalities_total"],
                "injuries_total": row["injuries_total"],
                "coordinate_complete_records": row["coordinate_complete_records"],
                "year_min": years_present[0] if years_present else None,
                "year_max": years_present[-1] if years_present else None,
                "year_count": len(years_present),
                "years_present": ",".join(str(year) for year in years_present),
            }
        )

    city_profile_rows.sort(
        key=lambda row: (
            -int(row["crash_count"]),
            -int(row["fatalities_total"]),
            (row["province_name"] or ""),
            (row["city_name"] or ""),
        )
    )

    with city_profile_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "province_code",
                "province_name",
                "city_code",
                "city_name",
                "crash_count",
                "fatal_crash_count",
                "injury_crash_count",
                "fatalities_total",
                "injuries_total",
                "coordinate_complete_records",
                "year_min",
                "year_max",
                "year_count",
                "years_present",
            ],
        )
        writer.writeheader()
        writer.writerows(city_profile_rows)

    province_profile_rows = []
    for row in province_rows.values():
        province_profile_rows.append(
            {
                "province_code": row["province_code"],
                "province_name": row["province_name"],
                "crash_count": row["crash_count"],
                "fatal_crash_count": row["fatal_crash_count"],
                "injury_crash_count": row["injury_crash_count"],
                "fatalities_total": row["fatalities_total"],
                "injuries_total": row["injuries_total"],
                "distinct_city_count": len(row["distinct_city_codes"]),
            }
        )
    province_profile_rows.sort(
        key=lambda row: (
            -int(row["crash_count"]),
            -int(row["fatalities_total"]),
            (row["province_name"] or ""),
        )
    )

    with province_profile_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "province_code",
                "province_name",
                "crash_count",
                "fatal_crash_count",
                "injury_crash_count",
                "fatalities_total",
                "injuries_total",
                "distinct_city_count",
            ],
        )
        writer.writeheader()
        writer.writerows(province_profile_rows)

    summary = {
        "inputs": {
            "records_path": str(records_input),
            "records_sha256": _sha256(records_input),
            "zip_path": str(Path(zip_path)) if zip_path else None,
        },
        "outputs": {
            "city_profile_path": str(city_profile_path),
            "city_profile_sha256": _sha256(city_profile_path),
            "province_profile_path": str(province_profile_path),
            "province_profile_sha256": _sha256(province_profile_path),
            "summary_path": str(summary_path),
        },
        "stats": {
            "total_records": total_records,
            "decoded_city_name_records": decoded_city_name_records,
            "decoded_province_name_records": decoded_province_name_records,
            "missing_city_code_records": missing_city_code_records,
            "missing_province_code_records": missing_province_code_records,
            "distinct_city_groups": len(city_profile_rows),
            "distinct_province_groups": len(province_profile_rows),
            "top_cities": city_profile_rows[:top_n],
            "top_provinces": province_profile_rows[:top_n],
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def filter_canonical_records_by_jurisdiction(
    records_path: str | Path,
    output_dir: str | Path,
    province_code: str | None = None,
    city_code: str | None = None,
    province_name: str | None = None,
    city_name: str | None = None,
    require_coordinates: bool = False,
) -> dict[str, object]:
    records_input = Path(records_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    normalized_province_code = normalize_istat_code(province_code, width=3)
    normalized_city_code = normalize_istat_code(city_code, width=3)
    normalized_province_name = (province_name or "").strip().casefold() or None
    normalized_city_name = (city_name or "").strip().casefold() or None

    if not any(
        value is not None
        for value in (
            normalized_province_code,
            normalized_city_code,
            normalized_province_name,
            normalized_city_name,
        )
    ):
        raise RuntimeError(
            "At least one jurisdiction filter is required: province_code, city_code, province_name, or city_name."
        )

    subset_path = output_root / "jurisdiction_subset.jsonl"
    manifest_path = output_root / "jurisdiction_subset.manifest.json"

    selected_records = 0
    coordinate_complete_records = 0
    years_present: set[int] = set()
    min_latitude = None
    max_latitude = None
    min_longitude = None
    max_longitude = None
    resolved_province_names: Counter[str] = Counter()
    resolved_city_names: Counter[str] = Counter()

    with records_input.open(encoding="utf-8") as input_handle, subset_path.open("w", encoding="utf-8") as output_handle:
        for line in input_handle:
            if not line.strip():
                continue
            record = json.loads(line)

            record_province_code = normalize_istat_code(record.get("province_code"), width=3)
            record_city_code = normalize_istat_code(record.get("city_code"), width=3)
            record_province_name = (
                (
                    record.get("extra", {})
                    .get("jurisdiction", {})
                    .get("province_name")
                )
                or record.get("province_name")
                or ""
            ).strip()
            record_city_name = (record.get("city_name") or "").strip()

            if normalized_province_code is not None and record_province_code != normalized_province_code:
                continue
            if normalized_city_code is not None and record_city_code != normalized_city_code:
                continue
            if normalized_province_name is not None and record_province_name.casefold() != normalized_province_name:
                continue
            if normalized_city_name is not None and record_city_name.casefold() != normalized_city_name:
                continue
            if require_coordinates and (
                record.get("latitude") is None or record.get("longitude") is None
            ):
                continue

            output_handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
            selected_records += 1

            if record_province_name:
                resolved_province_names[record_province_name] += 1
            if record_city_name:
                resolved_city_names[record_city_name] += 1

            latitude = record.get("latitude")
            longitude = record.get("longitude")
            if latitude is not None and longitude is not None:
                coordinate_complete_records += 1
                latitude = float(latitude)
                longitude = float(longitude)
                min_latitude = latitude if min_latitude is None else min(min_latitude, latitude)
                max_latitude = latitude if max_latitude is None else max(max_latitude, latitude)
                min_longitude = longitude if min_longitude is None else min(min_longitude, longitude)
                max_longitude = longitude if max_longitude is None else max(max_longitude, longitude)
            if record.get("occurred_year") is not None:
                years_present.add(int(record["occurred_year"]))

    manifest = {
        "inputs": {
            "records_path": str(records_input),
            "records_sha256": _sha256(records_input),
        },
        "filters": {
            "province_code": normalized_province_code,
            "city_code": normalized_city_code,
            "province_name": province_name,
            "city_name": city_name,
            "require_coordinates": require_coordinates,
        },
        "outputs": {
            "subset_path": str(subset_path),
            "subset_sha256": _sha256(subset_path),
            "manifest_path": str(manifest_path),
        },
        "stats": {
            "selected_records": selected_records,
            "coordinate_complete_records": coordinate_complete_records,
            "year_min": min(years_present) if years_present else None,
            "year_max": max(years_present) if years_present else None,
            "year_count": len(years_present),
            "resolved_province_name": resolved_province_names.most_common(1)[0][0] if resolved_province_names else None,
            "resolved_city_name": resolved_city_names.most_common(1)[0][0] if resolved_city_names else None,
            "bounds": {
                "min_latitude": min_latitude,
                "max_latitude": max_latitude,
                "min_longitude": min_longitude,
                "max_longitude": max_longitude,
            },
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
