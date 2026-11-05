import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lab5.logic import ROOT, status, tasks


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
                "lab5.logic.recording_path",
                side_effect=lambda identifier: Path(directory) / f"{identifier}.wav",
            ):
                self.assertTrue(all(row["state"] == "MISSING" for row in status()))
