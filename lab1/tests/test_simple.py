"""Контроль расчётов и целостности новой компактной реализации."""

import math
import tempfile
import unittest
from pathlib import Path

from lab1.logic import PageText, SearchEngine, evaluate, words
from lab1.report import export


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = SearchEngine(":memory:")
        self.addCleanup(self.engine.close)

    def test_demo_matches_original_reference(self):
        self.engine.demo()
        result = self.engine.quality(self.engine.queries())
        self.assertEqual(len(self.engine.documents()), 12)
        self.assertEqual(result["averages"]["MAP"], 0.9375)
        self.assertEqual(result["averages"]["Precision"], 0.85)
        self.assertEqual(len(self.engine.search("python programming")), 4)
        self.assertEqual(self.engine.search("program"), [])

    def test_bm25_and_tfidf_by_hand(self):
        a = self.engine.add("https://example.org/a", "Python", "Python tutorial")
        self.engine.add("https://example.org/b", "Java", "Java tutorial")
        score = self.engine.search("python", b=0)[0]["score"]
        expected = math.log(2) * 2 * 2.5 / 3.5
        self.assertAlmostEqual(score, expected)
        index = {r["term"]: r for r in self.engine.index(a)}
        self.assertAlmostEqual(index["python"]["weight"], 2 * math.log(2))
        self.assertEqual(index["tutorial"]["weight"], 0)

    def test_update_delete_and_atomic_grade(self):
        ident = self.engine.add("https://example.org/a", "Python", "Programming")
        self.engine.grade("python", [ident], 2)
        with self.assertRaises(ValueError):
            self.engine.grade("python", [ident, 999], 0)
        self.assertEqual(self.engine.grades("python"), {ident: 2})
        self.engine.add("https://example.org/a", "Python", "Programming")
        self.assertEqual(self.engine.grades("python"), {ident: 2})
        self.engine.add("https://example.org/a", "Water", "River")
        self.assertEqual(self.engine.grades("python"), {})
        self.assertEqual(self.engine.search("python"), [])
        self.engine.delete([ident])
        self.assertEqual(self.engine.documents(), [])

    def test_partial_judgments_are_rejected_and_zero_relevance_excluded(self):
        self.engine.demo()
        ident = self.engine.add("https://example.org/new", "Garden", "Flower")
        with self.assertRaises(ValueError):
            self.engine.quality(self.engine.queries())
        for query in self.engine.queries():
            self.engine.grade(query, [ident], 0)
        self.engine.grade("nothing", [d["id"] for d in self.engine.documents()], 0)
        self.assertIn("nothing", self.engine.quality(self.engine.queries())["excluded"])

    def test_metrics_with_missing_relevant_document(self):
        result = evaluate([1, 2, 3], {1: 2, 2: 0, 3: 1, 4: 2})
        self.assertAlmostEqual(result["metrics"]["AP"], 5 / 9)
        self.assertAlmostEqual(result["metrics"]["Recall"], 2 / 3)
        self.assertEqual(result["metrics"]["P@5"], 0.4)
        self.assertEqual(result["interpolated"][-1], 0)

    def test_html_text_and_normalization(self):
        parser = PageText()
        parser.feed(
            "<html><head><title>A &amp; B</title><style>bad</style></head><body><p>Python</p><script>bad</script><p>Tutorial</p></body></html>"
        )
        self.assertEqual("".join(parser.title), "A & B")
        self.assertNotIn("bad", "".join(parser.body))
        self.assertEqual(
            words("The PYTHON, programming and program!"), ["python", "programming", "program"]
        )

    def test_export_and_persistence(self):
        self.engine.demo()
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            path = export(self.engine.quality(self.engine.queries()), folder)
            self.assertTrue(path.is_file())
            self.assertTrue((folder / "metrics.png").is_file())
            other = SearchEngine(folder / "search.sqlite3")
            other.demo()
            other.close()
            other = SearchEngine(folder / "search.sqlite3")
            self.assertEqual(len(other.documents()), 12)
            other.close()
