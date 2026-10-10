from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from road_risk_modeling.curation import curate_canonical_records


class CurationTests(unittest.TestCase):
    def test_curate_canonical_records_filters_blocking_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "canonical.jsonl"
            input_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "crash_id": "a",
                                "source_unique_key": "2020:1",
                                "quality_flags": [],
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "b",
                                "source_unique_key": "2020:2",
                                "quality_flags": ["coordinates_outside_expected_jurisdiction_bounds"],
                            }
                        ),
                        json.dumps(
                            {
                                "crash_id": "c",
                                "source_unique_key": "2020:1",
                                "quality_flags": [],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = curate_canonical_records(input_path)

            curated_path = Path(manifest["outputs"]["curated_path"])
            rejected_path = Path(manifest["outputs"]["rejected_path"])
            self.assertTrue(curated_path.exists())
            self.assertTrue(rejected_path.exists())
            self.assertEqual(manifest["stats"]["kept_records"], 1)
            self.assertEqual(manifest["stats"]["rejected_records"], 2)
            self.assertEqual(manifest["stats"]["duplicate_source_unique_key_records"], 1)
