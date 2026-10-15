from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from road_risk_modeling.jurisdictions import (
    extract_istat_codebooks,
    filter_canonical_records_by_jurisdiction,
    load_istat_jurisdiction_lookups,
    profile_canonical_jurisdictions,
)


PROVINCE_HTML = """ELENCO MODALITA' della variabile: provincia (3,0) Anno: 2020<br>
<table border=1>
<tr bgcolor=orange><td>Modalita'</td><td>Descrizione</td><td> Codice aggregazione</td><td>Note</td></tr>
<tr><td>072</td><td>Bari</td><td>&nbsp;</td><td></td></tr>
<tr><td>071</td><td>Foggia</td><td>&nbsp;</td><td></td></tr>
</table>
"""

MUNICIPALITY_HTML = """ELENCO MODALITA' della variabile: comune (6,0) Anno: 2020<br>
<table border=1>
<tr bgcolor=orange><td>Modalita'</td><td>Descrizione</td><td>Codice provincia</td><td>Note</td></tr>
<tr><td>006</td><td>Bari</td><td>072</td><td></td></tr>
<tr><td>027</td><td>Altamura</td><td>072</td><td></td></tr>
<tr><td>017</td><td>Foggia</td><td>071</td><td></td></tr>
</table>
"""


class JurisdictionTests(unittest.TestCase):
    def test_load_and_extract_istat_codebooks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            zip_path = root / "legacy.zip"
            output_dir = root / "codebooks"

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/INCSTRAD_Classificazione_2020_var2.html",
                    PROVINCE_HTML,
                )
                archive.writestr(
                    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/INCSTRAD_Classificazione_2020_var3.html",
                    MUNICIPALITY_HTML,
                )

            lookups = load_istat_jurisdiction_lookups(zip_path)
            self.assertEqual(lookups.province_name_for("72"), "Bari")
            self.assertEqual(lookups.municipality_name_for("72", "6"), "Bari")
            self.assertEqual(lookups.municipality_name_for("72", "27"), "Altamura")

            manifest = extract_istat_codebooks(zip_path, output_dir=output_dir)
            self.assertEqual(manifest["stats"]["province_count"], 2)
            self.assertEqual(manifest["stats"]["municipality_count"], 3)

            with (output_dir / "istat_municipalities.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            city_names = {(row["province_name"], row["city_name"]) for row in rows}
            self.assertIn(("Foggia", "Foggia"), city_names)
            self.assertIn(("Bari", "Altamura"), city_names)

    def test_profile_canonical_jurisdictions_decodes_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            zip_path = root / "legacy.zip"
            records_path = root / "canonical.jsonl"
            output_dir = root / "profiles"

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/INCSTRAD_Classificazione_2020_var2.html",
                    PROVINCE_HTML,
                )
                archive.writestr(
                    "ROAD ACCIDENTS RISK MODELING/Dataset Istat/METADATI/Classificazioni/INCSTRAD_Classificazione_2020_var3.html",
                    MUNICIPALITY_HTML,
                )

            records_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "a",
                                "province_code": "72",
                                "city_code": "6",
                                "fatalities": 0,
                                "injuries": 1,
                                "severity_level": "injury",
                                "latitude": 41.1,
                                "longitude": 16.8,
                                "occurred_year": 2020,
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "b",
                                "province_code": "72",
                                "city_code": "6",
                                "fatalities": 1,
                                "injuries": 0,
                                "severity_level": "fatal",
                                "latitude": 41.1,
                                "longitude": 16.8,
                                "occurred_year": 2021,
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "c",
                                "province_code": "72",
                                "city_code": "27",
                                "fatalities": 0,
                                "injuries": 1,
                                "severity_level": "injury",
                                "latitude": 41.2,
                                "longitude": 16.6,
                                "occurred_year": 2021,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = profile_canonical_jurisdictions(
                records_path,
                output_dir=output_dir,
                zip_path=zip_path,
                top_n=5,
            )

            self.assertEqual(summary["stats"]["decoded_city_name_records"], 3)
            self.assertEqual(summary["stats"]["top_cities"][0]["city_name"], "Bari")
            self.assertEqual(summary["stats"]["top_cities"][0]["crash_count"], 2)

            with (output_dir / "jurisdiction_city_profile.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["city_name"], "Bari")
            self.assertEqual(rows[1]["city_name"], "Altamura")

    def test_filter_canonical_records_by_jurisdiction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records_path = root / "canonical.jsonl"
            output_dir = root / "subset"

            records_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "a",
                                "province_code": "72",
                                "city_code": "6",
                                "city_name": "Bari",
                                "extra": {"jurisdiction": {"province_name": "Bari"}},
                                "latitude": 41.1,
                                "longitude": 16.8,
                                "occurred_year": 2020,
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "b",
                                "province_code": "72",
                                "city_code": "27",
                                "city_name": "Altamura",
                                "extra": {"jurisdiction": {"province_name": "Bari"}},
                                "latitude": 41.0,
                                "longitude": 16.6,
                                "occurred_year": 2021,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = filter_canonical_records_by_jurisdiction(
                records_path,
                output_dir=output_dir,
                province_code="72",
                city_code="6",
                require_coordinates=True,
            )

            self.assertEqual(manifest["stats"]["selected_records"], 1)
            self.assertEqual(manifest["stats"]["resolved_city_name"], "Bari")
            with (output_dir / "jurisdiction_subset.jsonl").open(encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle if line.strip()]
            self.assertEqual(rows[0]["crash_id"], "a")
