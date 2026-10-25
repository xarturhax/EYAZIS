import math
import unittest

from lab1.ir_system.domain.errors import ValidationError
from lab1.ir_system.domain.metrics import evaluate_ranking
from lab1.ir_system.domain.models import BM25Parameters, CorpusSnapshot, Document, DocumentDraft
from lab1.ir_system.domain.ranking import BM25Ranker, extract_keywords
from lab1.ir_system.domain.text import EnglishAnalyzer, normalize_url


class TextTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(
            EnglishAnalyzer().tokenize("The PYTHON, SQL and database!"),
            ("python", "sql", "database"),
        )

    def test_url_validation(self):
        self.assertEqual(normalize_url("https://example.org/a#anchor"), "https://example.org/a")
        for url in (
            "file:///test",
            "ftp://example.org",
            "https://",
            "https://user:pass@example.org",
            "https://example.org:wrong",
        ):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                normalize_url(url)

    def test_draft_validation(self):
        with self.assertRaises(ValidationError):
            DocumentDraft("https://example.org", "title", " ")


class RankingTests(unittest.TestCase):
    def snapshot(self):
        return CorpusSnapshot(
            (
                Document(1, "https://example.org/1", "alpha", "alpha common", "date", 3),
                Document(2, "https://example.org/2", "beta", "common common", "date", 3),
            ),
            {"alpha": {1: 2}, "common": {1: 1, 2: 2}, "beta": {2: 1}},
        )

    def test_bm25_matches_hand_calculation(self):
        result = BM25Ranker().rank(self.snapshot(), ("alpha", "alpha"))[0]
        self.assertEqual(result.document.id, 1)
        self.assertAlmostEqual(result.score, math.log(2) * 2 * 2.5 / (2 + 1.5))
        self.assertEqual(result.matched_words, ("alpha",))

    def test_keywords_formula(self):
        keywords = {item.term: item.weight for item in extract_keywords(self.snapshot(), 1)}
        self.assertAlmostEqual(keywords["alpha"], 2 * math.log(2))
        self.assertEqual(keywords["common"], 0)

    def test_deterministic_tie_order(self):
        snapshot = CorpusSnapshot(self.snapshot().documents, {"alpha": {2: 1, 1: 1}})
        results = BM25Ranker().rank(snapshot, ("alpha",))
        self.assertEqual([result.document.id for result in results], [1, 2])

    def test_parameters_are_validated(self):
        for k1, b in ((0, 0.75), (float("nan"), 0.75), (1.5, 2), (1.5, float("inf"))):
            with self.subTest(k1=k1, b=b), self.assertRaises(ValidationError):
                BM25Parameters(k1, b)

    def test_snapshot_is_immutable_and_detached(self):
        postings = {"alpha": {1: 1}}
        snapshot = CorpusSnapshot(self.snapshot().documents, postings)
        postings["alpha"][1] = 10
        self.assertEqual(snapshot.postings["alpha"][1], 1)
        with self.assertRaises(TypeError):
            snapshot.postings["alpha"][1] = 3


class MetricTests(unittest.TestCase):
    def test_hand_calculation_with_missed_relevant_document(self):
        result = evaluate_ranking([1, 2, 3], {1: 2, 2: 0, 3: 1, 4: 2})
        m = result.metrics
        self.assertAlmostEqual(m.precision, 2 / 3)
        self.assertAlmostEqual(m.recall, 2 / 3)
        self.assertAlmostEqual(m.average_precision, (1 + 2 / 3) / 3)
        self.assertEqual(m.precision_at_5, 2 / 5)
        self.assertEqual(m.precision_at_10, 2 / 10)
        self.assertAlmostEqual(m.r_precision, 2 / 3)
        c = result.counts
        self.assertEqual((c.tp, c.fp, c.fn, c.tn), (2, 1, 1, 0))
        self.assertEqual(result.interpolated[-1], 0)

    def test_romip_pdf_twenty_document_example(self):
        grades = {i: int(i in {1, 2, 4, 15}) for i in range(1, 21)}
        result = evaluate_ranking(list(range(1, 21)), grades)
        self.assertEqual(result.metrics.precision, 4 / 20)
        self.assertEqual(result.metrics.recall, 1)
        self.assertAlmostEqual(result.metrics.average_precision, (1 + 1 + 3 / 4 + 4 / 15) / 4)
        self.assertEqual(result.metrics.precision_at_5, 3 / 5)
        self.assertEqual(result.metrics.precision_at_10, 3 / 10)
        self.assertEqual(result.metrics.r_precision, 3 / 4)
        self.assertEqual(
            result.interpolated, (1, 1, 1, 1, 1, 1, 0.75, 0.75, 4 / 15, 4 / 15, 4 / 15)
        )

    def test_empty_retrieval_with_relevant_documents(self):
        from dataclasses import asdict

        result = evaluate_ranking([], {1: 2})
        self.assertTrue(all(value == 0 for value in asdict(result.metrics).values()))
        self.assertEqual(result.interpolated, (0,) * 11)
        self.assertEqual(result.counts.fn, 1)

    def test_zero_relevance_is_not_a_zero_scored_query(self):
        for ranking, grades in (([1], {1: 0}), ([], {})):
            with self.assertRaisesRegex(ValidationError, "исключается"):
                evaluate_ranking(ranking, grades)

    def test_short_perfect_ranking_has_fixed_cutoff_denominators(self):
        metrics = evaluate_ranking([1, 2], {1: 2, 2: 1}).metrics
        self.assertEqual(metrics.precision, 1)
        self.assertEqual(metrics.average_precision, 1)
        self.assertEqual(metrics.precision_at_5, 0.4)
        self.assertEqual(metrics.precision_at_10, 0.2)

    def test_irrelevant_tail_changes_precision_but_not_ap_or_trec(self):
        grades = {1: 2, 2: 1, 3: 0, 4: 0}
        short = evaluate_ranking([1, 2], grades)
        long = evaluate_ranking([1, 2, 3, 4], grades)
        self.assertEqual(short.metrics.average_precision, long.metrics.average_precision)
        self.assertEqual(short.interpolated, long.interpolated)
        self.assertEqual((short.metrics.precision, long.metrics.precision), (1, 0.5))

    def test_grades_one_and_two_are_equivalent_for_search_metrics(self):
        partial = evaluate_ranking([3, 1, 2], {1: 1, 2: 1, 3: 0})
        full = evaluate_ranking([3, 1, 2], {1: 2, 2: 2, 3: 0})
        self.assertEqual(partial, full)

    def test_invalid_rankings(self):
        for ranking, grades in (([1, 1], {1: 2}), ([2], {1: 2}), ([1], {1: 3}), ([1], {1: True})):
            with self.assertRaises(ValidationError):
                evaluate_ranking(ranking, grades)
