import math
import unittest
from dataclasses import replace
from unittest.mock import patch

import networkx as nx

from lab3.application.experiment import CancelledError, Summarizer
from lab3.domain.ranking import CorpusStatistics, PositionalRanker, keywords, position, select
from lab3.infrastructure.textrank import TextRank, similarity
from lab3.tests.helpers import analyzed, fixture


class RankingTests(unittest.TestCase):
    def test_hand_calculation_of_augmented_tf_and_idf(self):
        documents = fixture()
        statistics = CorpusStatistics.build(documents)
        self.assertEqual(statistics.document_frequency, {"alpha": 1, "beta": 2, "common": 3})
        weights = statistics.weights(documents[0])
        self.assertAlmostEqual(weights["alpha"], math.log(3))
        self.assertAlmostEqual(weights["beta"], math.log(3 / 2))
        self.assertEqual(weights["common"], 0)
        # The least-frequent term receives .5*(1+1/2), before IDF.
        other = CorpusStatistics(3, {"alpha": 1, "beta": 2, "common": 1})
        self.assertAlmostEqual(other.weights(documents[0])["common"], 0.75 * math.log(3))

    def test_hand_calculation_of_sentence_product_and_term_repetitions(self):
        document = fixture()[0]
        weights = CorpusStatistics.build(fixture()).weights(document)
        scores = PositionalRanker().rank(document, weights).scores
        self.assertAlmostEqual(scores[0], 2 * math.log(3) + math.log(1.5))
        second = document.sentences[1]
        self.assertAlmostEqual(
            scores[1], math.log(1.5) * (1 - second.start / len(document.document.text))
        )

    def test_paragraph_offset_is_relative_to_paragraph(self):
        sentence = replace(
            fixture()[0].sentences[1], start=25, end=30, paragraph_start=20, paragraph_end=40
        )
        self.assertAlmostEqual(position(sentence, 100), 0.75 * 0.75)

    def test_selection_restores_source_order_and_breaks_ties_by_index(self):
        self.assertEqual(select((3.0, 9.0, 2.0, 9.0), 3), (0, 1, 3))
        self.assertEqual(select((0.0, 0.0), 10), (0, 1))
        with self.assertRaises(ValueError):
            select((1.0,), 0)

    def test_keywords_are_positive_and_deterministic(self):
        self.assertEqual(keywords({"z": 1.0, "a": 1.0, "zero": 0.0}, 10), (("a", 1.0), ("z", 1.0)))

    def test_one_document_unsmoothed_idf_is_zero_with_explicit_warning(self):
        document = fixture()[0]
        weights = CorpusStatistics.build([document]).weights(document)
        ranking = PositionalRanker().rank(document, weights)
        self.assertEqual(ranking.scores, (0.0, 0.0))
        self.assertTrue(ranking.warnings)
        self.assertEqual(keywords(weights, 10), ())

    def test_empty_vocabulary_does_not_divide_by_zero(self):
        document = analyzed([("The and.", ())])
        statistics = CorpusStatistics.build([document])
        self.assertEqual(statistics.weights(document), {})
        self.assertEqual(PositionalRanker().rank(document, {}).scores, (0.0,))

    def test_missing_document_term_and_empty_corpus_fail(self):
        with self.assertRaises(ValueError):
            CorpusStatistics.build([])
        with self.assertRaises(ValueError):
            CorpusStatistics(1, {}).weights(fixture()[0])

    def test_textrank_overlap_formula(self):
        self.assertAlmostEqual(
            similarity(("x", "x", "y"), ("x", "z")), 1 / (math.log(3) + math.log(2))
        )
        self.assertEqual(similarity((), ("x",)), 0)
        self.assertEqual(similarity(("x",), ("x",)), 1)
        self.assertEqual(similarity(("x",), ("y",)), 0)

    def test_graph_central_sentence_wins_and_isolate_is_retained(self):
        document = analyzed(
            [
                ("Alpha.", ("alpha",)),
                ("Alpha beta.", ("alpha", "beta")),
                ("Beta.", ("beta",)),
                ("Gamma.", ("gamma",)),
            ]
        )
        result = TextRank().rank(document, {})
        self.assertGreater(result.scores[1], result.scores[0])
        self.assertGreater(result.scores[0], result.scores[3])
        self.assertAlmostEqual(sum(result.scores), 1)
        self.assertFalse(result.warnings)

    def test_graph_without_edges_uses_documented_positional_fallback(self):
        document = analyzed([("Alpha.", ("alpha",)), ("Beta.", ("beta",))])
        result = TextRank().rank(document, {})
        self.assertGreater(result.scores[0], result.scores[1])
        self.assertTrue(result.warnings)
        single = TextRank().rank(analyzed([("The.", ())]), {})
        self.assertEqual(single.scores, (1.0,))

    def test_graph_nonconvergence_is_not_silent(self):
        document = analyzed([("Alpha.", ("alpha",)), ("Alpha beta.", ("alpha", "beta"))])
        with patch("networkx.pagerank", side_effect=nx.PowerIterationFailedConvergence(200)):
            with self.assertRaisesRegex(ValueError, "200"):
                TextRank().rank(document, {})


class FakeAnalyzer:
    def __init__(self, documents):
        self.documents = {d.document.source.language + d.document.text: d for d in documents}

    def prepare(self, languages):
        return {"analyzer": "test"}

    def analyze(self, document):
        return self.documents[document.source.language + document.text]


class ExperimentTests(unittest.TestCase):
    def service(self, documents):
        return Summarizer(FakeAnalyzer(documents), [PositionalRanker(), TextRank()])

    def test_methods_use_same_sentences_keywords_and_requested_count(self):
        documents = fixture()
        result = self.service(documents).run([d.document for d in documents], 1, 2)
        for item in result.documents:
            first, second = item.summaries
            self.assertEqual(first.keywords, second.keywords)
            self.assertEqual(len(first.selected), 1)
            self.assertEqual(len(second.selected), 1)
            self.assertTrue(0 <= item.agreement <= 1)
            for summary in item.summaries:
                self.assertEqual(len(summary.scores), len(item.analyzed.sentences))
                self.assertTrue(0 <= summary.word_ratio <= 1)

    def test_idf_is_computed_separately_for_languages(self):
        english = fixture()[0]
        spanish = analyzed([("Alpha beta.", ("alpha", "beta"))], language="es")
        result = self.service([english, spanish]).run([english.document, spanish.document])
        for item in result.documents:
            baseline = item.summaries[0]
            self.assertEqual(baseline.keywords, ())
            self.assertFalse(any(baseline.scores))
            self.assertTrue(baseline.warnings)

    def test_invalid_limits_empty_input_and_cancellation(self):
        documents = fixture()
        service = self.service(documents)
        with self.assertRaises(ValueError):
            service.run([])
        with self.assertRaises(ValueError):
            service.run([d.document for d in documents], sentences=0)
        with self.assertRaises(CancelledError):
            service.run([d.document for d in documents], cancelled=lambda: True)
