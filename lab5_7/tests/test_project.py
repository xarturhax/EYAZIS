import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lab5_7.application.project import ROOT, status, tasks
from lab5_7.infrastructure.textgrid import textgrid
from lab5_7.infrastructure.wav import save
from lab5_7.tests.test_audio import tone


class ProjectTests(unittest.TestCase):
    def test_task_and_recipe_references_are_consistent(self):
        task_ids = [row["id"] for row in tasks()]
        self.assertEqual(len(task_ids), len(set(task_ids)))
        with (ROOT / "data/segments.csv").open(encoding="utf-8-sig", newline="") as stream:
            segments = list(csv.DictReader(stream))
        known = {row["id"] for row in segments}
        self.assertTrue(all(Path(row["file"]).stem in task_ids for row in segments))
        recipes = json.loads((ROOT / "data/recipes.json").read_text(encoding="utf-8"))
        self.assertEqual(len(recipes), 8)
        self.assertTrue(all(set(recipe["units"]) <= known for recipe in recipes))

    def test_missing_recordings_are_reported_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "lab5_7.application.project.recording_path",
                side_effect=lambda identifier: Path(directory) / f"{identifier}.wav",
            ):
                self.assertTrue(all(row["state"] == "MISSING" for row in status()))

    def test_textgrid_roundtrip_uses_real_praat_reader(self):
        import parselmouth
        from parselmouth.praat import call

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "sample.wav"
            save(tone(), source)
            row = dict(id="ph_a", file="sample.wav", start=".1", end=".4", kind="phone")
            with (
                patch("lab5_7.infrastructure.textgrid.segments", return_value=[row]),
                patch("lab5_7.infrastructure.textgrid.segment_path", return_value=source),
            ):
                textgrid(source, base / "sample.TextGrid")
            grid = parselmouth.read(str(base / "sample.TextGrid"))
            self.assertEqual(call(grid, "Get number of tiers"), 1)
            self.assertEqual(call(grid, "Get label of interval", 1, 2), "ph_a")
            self.assertAlmostEqual(call(grid, "Get start time of interval", 1, 2), 0.1)
