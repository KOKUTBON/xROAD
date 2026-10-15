from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from road_risk_modeling.legacy_zip import inspect_zip, iter_csv_member_rows, list_csv_members, profile_csv_member


class LegacyZipTests(unittest.TestCase):
    def _build_zip(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        zip_path = Path(temp_dir.name) / "legacy.zip"

        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr(
                "synthetic_examples/crashes.csv",
                "ANNO,YCOORD_ACI,XCOORD_ACI,FERITI\n"
                "2020,41.1,16.8,1\n"
                "2021,,16.9,2\n",
            )
            archive.writestr(
                "synthetic_examples/crashes_broken.csv",
                "ANNO,DESCRIZIONE1,CODICE,YCOORD_ACI,XCOORD_ACI\n"
                "2020,Via Roma, tratto nord,SS1,41.1,16.8\n"
                "2021,Via Napoli,SS2,,16.9\n",
            )
            archive.writestr("ROAD ACCIDENTS RISK MODELING/index.html", "<html></html>")
            archive.writestr("__MACOSX/._ignored", "")

        return zip_path

    def test_inspect_zip_ignores_macosx_entries(self) -> None:
        zip_path = self._build_zip()
        summary = inspect_zip(zip_path)

        self.assertEqual(summary["file_count"], 3)
        self.assertIn(
            "synthetic_examples/crashes.csv",
            summary["csv_members"],
        )

    def test_list_csv_members(self) -> None:
        zip_path = self._build_zip()
        members = list_csv_members(zip_path)
        self.assertEqual(
            members,
            [
                "synthetic_examples/crashes.csv",
                "synthetic_examples/crashes_broken.csv",
            ],
        )

    def test_profile_csv_member(self) -> None:
        zip_path = self._build_zip()
        profile = profile_csv_member(
            zip_path,
            "synthetic_examples/crashes.csv",
        )

        self.assertEqual(profile["row_count"], 2)
        self.assertEqual(profile["column_count"], 4)
        self.assertEqual(profile["year_distribution"], {"2020": 1, "2021": 1})
        self.assertEqual(profile["coordinate_row_count"], 1)
        self.assertEqual(profile["missing_counts"]["YCOORD_ACI"], 1)

    def test_profile_csv_member_repairs_description_commas(self) -> None:
        zip_path = self._build_zip()
        profile = profile_csv_member(
            zip_path,
            "synthetic_examples/crashes_broken.csv",
        )

        self.assertEqual(profile["row_count"], 2)
        self.assertEqual(profile["repaired_row_count"], 1)
        self.assertEqual(profile["coordinate_row_count"], 1)
        self.assertEqual(profile["missing_counts"]["YCOORD_ACI"], 1)

    def test_iter_csv_member_rows_returns_repair_flags(self) -> None:
        zip_path = self._build_zip()
        _, rows = iter_csv_member_rows(
            zip_path,
            "synthetic_examples/crashes_broken.csv",
        )

        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0].repaired)
        self.assertEqual(rows[0].data["DESCRIZIONE1"], "Via Roma, tratto nord")


if __name__ == "__main__":
    unittest.main()
