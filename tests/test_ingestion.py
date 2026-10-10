from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from road_risk_modeling.ingestion import ingest_bari_open_data_crashes, ingest_puglia_cleaned_csv


class IngestionTests(unittest.TestCase):
    def test_ingest_puglia_cleaned_csv_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "legacy.zip"
            output_dir = Path(temp_dir) / "staging"

            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "synthetic_examples/crashes.csv",
                    "ANNO,PROV,COMUNE,LOCINC,NOMESTR,METEO,MORTI,FERITI,NREC,DESCRIZIONE1,CODICE,"
                    "YCOORD_ACI,XCOORD_ACI,ORGRIL,TIPOST,PAVIM,INTNIN,FONDOST,SEGNAL,NATINC,"
                    "TIPOVEIA,TIPOVEIB,TIPOVEIC,KM,METRI,TRONCO,MOR24H,MOR30G\n"
                    "2020,71,2,1,,1,0,1,123,\"Via Roma, 10\",,41.1,16.8,2,2,1,7,1,3,2,1,8.0,,0.0,0.0,12.0,0,0\n"
                    "2021,72,3,8,091,2,1,0,124,Strada Test,SS001,41.2,16.9,2,2,1,8,2,1,10,1,,,0.0,0.0,3.0,1,0\n",
                )

            manifest = ingest_puglia_cleaned_csv(
                zip_path,
                "synthetic_examples/crashes.csv",
                output_dir,
            )

            records_path = Path(manifest["outputs"]["records_path"])
            manifest_path = Path(manifest["outputs"]["manifest_path"])

            self.assertTrue(records_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertEqual(manifest["stats"]["total_records"], 2)
            self.assertEqual(manifest["stats"]["severity_counts"]["fatal"], 1)
            self.assertEqual(manifest["stats"]["severity_counts"]["injury"], 1)

            lines = records_path.read_text(encoding="utf-8").strip().splitlines()
            first_record = json.loads(lines[0])
            self.assertEqual(first_record["crash_id"], "it-puglia-2020:123")
            self.assertEqual(first_record["source_unique_key"], "2020:123")
            self.assertEqual(first_record["timestamp_precision"], "year")

    def test_ingest_bari_open_data_crashes_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "staging"
            raw_dir = root / "raw"
            source_2022 = root / "incidenti_2022.csv"
            source_2025 = root / "incidenti_2025.csv"

            source_2022.write_text(
                "Data incidente;lat;lon;Centro abitato;Tipo di strada;Caratteristiche della strada;"
                "Stato fondo stradale;Tipo pavimentazione;Condizioni meteo;Condizioni traffico;"
                "Danni a cose;Incidente con lesioni;Pattuglia inviata ore;Pattuglia sul posto ore\n"
                "01/01/2022;41.07788;16.87029;Sì;Strada urbana;Incrocio;Asciutto;Asfaltata;"
                "Sereno;Scarso;No;Sì;00:30:00;00:40:00\n",
                encoding="utf-8",
            )
            source_2025.write_text(
                "Data incidente,Latitudine,Longitudine,Centro abitato,Tipo di strada,"
                "Caratteristiche della strada,Stato fondo stradale,Tipo pavimentazione,"
                "Condizioni meteo,Condizioni traffico,Danni a cose,Incidente con lesioni,"
                "Inviata ore,Sul posto ore\n"
                "01/01/2025,4.110.309,1.687.909,si,Strada Urbana,Rettilineo,Asciutto,Asfaltata,"
                "Sereno,Scarso,no,si,20:30,20:45\n",
                encoding="utf-8",
            )

            manifest = ingest_bari_open_data_crashes(
                output_dir,
                raw_dir=raw_dir,
                sources=[
                    {"year": 2022, "label": "bari_2022", "url": str(source_2022)},
                    {"year": 2025, "label": "bari_2025", "url": str(source_2025)},
                ],
            )

            records_path = Path(manifest["outputs"]["records_path"])
            manifest_path = Path(manifest["outputs"]["manifest_path"])

            self.assertTrue(records_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertEqual(manifest["stats"]["total_records"], 2)
            self.assertEqual(manifest["stats"]["coordinate_complete_records"], 2)
            self.assertEqual(manifest["stats"]["dispatch_time_records"], 2)
            self.assertEqual(manifest["stats"]["severity_counts"]["injury"], 2)
            self.assertEqual(manifest["stats"]["source_year_counts"]["2022"], 1)
            self.assertEqual(manifest["stats"]["source_year_counts"]["2025"], 1)
            self.assertEqual(len(manifest["source"]["sources"]), 2)

            first_source = manifest["source"]["sources"][0]
            self.assertTrue(Path(first_source["raw_path"]).exists())

            lines = records_path.read_text(encoding="utf-8").strip().splitlines()
            first_record = json.loads(lines[0])
            second_record = json.loads(lines[1])
            self.assertEqual(first_record["city_name"], "Bari")
            self.assertEqual(first_record["timestamp_precision"], "date_dispatch_time_proxy")
            self.assertEqual(first_record["occurred_year"], 2022)
            self.assertEqual(second_record["occurred_year"], 2025)
