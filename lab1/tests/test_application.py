import json
import unittest
from unittest.mock import Mock

from lab1.ir_system.application.services import EvaluationService, JudgmentService, SearchService
from lab1.ir_system.domain.errors import NotFoundError, StorageError, ValidationError
from lab1.ir_system.domain.models import DocumentDraft
from lab1.ir_system.domain.ranking import BM25Ranker
from lab1.ir_system.domain.text import EnglishAnalyzer
from lab1.ir_system.infrastructure.reporting.serialization import report_to_dict
from lab1.ir_system.infrastructure.sqlite import SQLiteRepository

from .support import collection_service


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteRepository(":memory:")
        self.addCleanup(self.repository.close)
        self.collection = collection_service(self.repository)
        self.search = SearchService(self.repository, BM25Ranker(), EnglishAnalyzer())
        self.judgments = JudgmentService(self.repository, self.repository, self.repository)
        self.evaluation = EvaluationService(
            self.repository, self.repository, self.repository, BM25Ranker(), EnglishAnalyzer()
        )

    def add(self, url, title, text):
        return self.collection.add(DocumentDraft(url, title, text))

    def test_empty_unknown_and_stopword_queries(self):
        self.assertEqual(self.search.search("python"), ())
        self.add("https://example.org/1", "python", "programming")
        for query in ("", "the and", "unknown", "русский"):
            self.assertEqual(self.search.search(query), ())

    def test_length_normalization(self):
        short = self.add("https://example.org/short", "note", "alpha")
        self.add("https://example.org/long", "note", "alpha " + "beta " * 40)
        self.assertEqual(self.search.search("alpha")[0].document.id, short)

    def test_update_replaces_postings_and_invalidates_judgments(self):
        doc = self.add("https://example.org/1", "alpha", "alpha")
        self.judgments.grade_many("alpha", [doc], 2)
        self.assertEqual(self.add("https://example.org/1", "alpha", "alpha"), doc)
        self.assertEqual(self.judgments.judgments("alpha"), {doc: 2})
        self.add("https://example.org/1", "beta", "beta")
        self.assertEqual(self.search.search("alpha"), ())
        self.assertEqual(self.judgments.judgments("alpha"), {})
        self.assertEqual(len(self.collection.documents()), 1)
        self.assertTrue(self.search.search("beta"))

    def test_delete_cascades_and_recomputes_idf(self):
        first = self.add("https://example.org/1", "alpha", "alpha")
        second = self.add("https://example.org/2", "beta", "beta")
        self.judgments.grade_many("alpha", [first], 2)
        old_score = self.search.search("alpha")[0].score
        self.collection.delete_many([second])
        self.assertNotEqual(old_score, self.search.search("alpha")[0].score)
        self.collection.delete_many([first])
        self.assertEqual(dict(self.repository.snapshot().postings), {})
        self.assertEqual(self.judgments.judgments("alpha"), {})

    def test_evaluation_requires_full_corpus_judgments(self):
        first = self.add("https://example.org/1", "alpha", "alpha")
        self.add("https://example.org/2", "beta", "beta")
        self.judgments.grade_many("alpha", [first], 2)
        with self.assertRaisesRegex(ValidationError, "ещё 1"):
            self.evaluation.evaluate(["alpha"])

    def test_complete_demo_report_matches_baseline(self):
        from lab1.ir_system.config import PROJECT_ROOT

        result = self.collection.import_demo()
        self.collection.import_demo()
        self.assertEqual(len(self.collection.documents()), 12)
        report = self.evaluation.evaluate(result.queries)
        baseline = json.loads(
            (PROJECT_ROOT / "reports/demo/metrics.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report_to_dict(report), baseline)
        self.assertEqual(report.rows[0].evaluation.counts.fn, 1)
        self.assertEqual(report.rows[0].evaluation.counts.fp, 1)
        self.assertEqual(report.averages.average_precision, 0.9375)
        self.assertEqual(report.averages.precision_at_10, 0.24)

    def test_no_relevant_queries_are_excluded_from_means(self):
        collection = self.collection.import_demo()
        ids = [d.id for d in self.collection.documents()]
        self.judgments.grade_many("excluded query", ids, 0)
        expected = self.evaluation.evaluate(collection.queries)
        report = self.evaluation.evaluate([*collection.queries, "excluded query"])
        self.assertEqual(report.averages, expected.averages)
        self.assertEqual(report.mean_interpolated, expected.mean_interpolated)
        self.assertEqual(len(report.rows), 5)
        self.assertEqual(report.excluded_queries[0].query, "excluded query")
        self.assertIn("R=0", report.excluded_queries[0].reason)

    def test_all_excluded_queries_produce_clear_error(self):
        doc = self.add("https://example.org/1", "alpha", "alpha")
        self.judgments.grade_many("none", [doc], 0)
        with self.assertRaisesRegex(ValidationError, "Все выбранные запросы исключены"):
            self.evaluation.evaluate(["none"])

    def test_partial_zero_judgments_are_not_silently_excluded(self):
        doc = self.add("https://example.org/1", "alpha", "alpha")
        self.add("https://example.org/2", "beta", "beta")
        self.judgments.grade_many("none", [doc], 0)
        with self.assertRaisesRegex(ValidationError, "ещё 1"):
            self.evaluation.evaluate(["none"])

    def test_means_give_equal_weight_to_queries_with_different_relevant_counts(self):
        first = self.add("https://example.org/1", "alpha", "alpha")
        second = self.add("https://example.org/2", "beta", "beta")
        self.judgments.grade_many("alpha", [first], 2)
        self.judgments.grade_many("alpha", [second], 0)
        self.judgments.grade_many("unknown", [first, second], 2)
        report = self.evaluation.evaluate(["alpha", "unknown"])
        self.assertEqual(report.averages.recall, 0.5)
        self.assertEqual(report.averages.average_precision, 0.5)
        self.assertEqual(report.mean_interpolated, (0.5,) * 11)

    def test_evaluation_reads_snapshot_once(self):
        result = self.collection.import_demo()
        reader = Mock(wraps=self.repository)
        service = EvaluationService(
            reader, self.repository, self.repository, BM25Ranker(), EnglishAnalyzer()
        )
        service.evaluate(result.queries)
        self.assertEqual(reader.snapshot.call_count, 1)

    def test_import_rolls_back_documents_and_judgments_on_failure(self):
        store = Mock(wraps=self.repository)
        calls = 0

        def failing_save(query, document_id, grade):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise StorageError("failure")
            self.repository.save_judgment(query, document_id, grade)

        store.save_judgment.side_effect = failing_save
        service = collection_service(self.repository, judgments=store)
        with self.assertRaises(StorageError):
            service.import_demo()
        self.assertEqual(self.collection.documents(), ())
        self.assertEqual(self.repository.queries(), ())
        self.assertEqual(dict(self.repository.snapshot().postings), {})

    def test_group_delete_rolls_back_if_document_missing(self):
        first = self.add("https://example.org/1", "alpha", "alpha")
        with self.assertRaises(NotFoundError):
            self.collection.delete_many([first, 999])
        self.assertEqual(self.collection.get_document(first).title, "alpha")

    def test_group_judgment_does_not_partially_save(self):
        first = self.add("https://example.org/1", "alpha", "alpha")
        with self.assertRaises(NotFoundError):
            self.judgments.grade_many("alpha", [first, 999], 2)
        self.assertEqual(self.judgments.queries(), ())
        self.assertEqual(self.judgments.judgments("alpha"), {})

    def test_query_whitespace_is_normalized_and_empty_selection_has_no_effect(self):
        first = self.add("https://example.org/1", "alpha", "alpha")
        self.judgments.grade_many(" alpha   beta ", [first], 1)
        self.assertEqual(self.judgments.judgments("alpha beta"), {first: 1})
        self.judgments.grade_many("unused", [], 0)
        self.assertEqual(self.judgments.queries(), ("alpha beta",))
