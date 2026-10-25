import io
import json
import tempfile
import unittest
from pathlib import Path

from lab1.ir_system.presentation.cli import run


class CliTests(unittest.TestCase):
    def test_demo_search_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "search.sqlite3")
            output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(run(["--db", database, "demo"], output, errors), 0)
            output = io.StringIO()
            self.assertEqual(
                run(
                    ["--db", database, "search", "python programming", "--limit", "1"],
                    output,
                    errors,
                ),
                0,
            )
            results = json.loads(output.getvalue())
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["matched_words"], ["python", "programming"])
            self.assertEqual(errors.getvalue(), "")

    def test_isolated_demo_evaluation_does_not_open_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "unused.sqlite3"
            output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(
                run(
                    ["--db", str(database), "evaluate", "--demo", "--output", directory],
                    output,
                    errors,
                ),
                0,
            )
            self.assertFalse(database.exists())
            self.assertTrue((Path(directory) / "report.html").exists())

    def test_open_failure_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            output, errors = io.StringIO(), io.StringIO()
            self.assertEqual(run(["--db", directory, "demo"], output, errors), 1)
            self.assertIn("Ошибка", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())

    def test_invalid_limit_is_not_success(self):
        output, errors = io.StringIO(), io.StringIO()
        self.assertEqual(
            run(["--db", ":memory:", "search", "alpha", "--limit", "0"], output, errors), 1
        )
        self.assertIn("Лимит", errors.getvalue())
