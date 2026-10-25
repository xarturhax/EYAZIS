import hashlib
import math
import unittest
from pathlib import Path

from lab2.application.experiment import validate_corpus
from lab2.domain.classifiers import AlphabetClassifier, ShortWordClassifier
from lab2.domain.metrics import evaluate
from lab2.domain.models import CorpusEntry, Document, LabError, Prediction, ResultRow, Settings
from lab2.domain.text import normalize, words


def document(text, language, split="train", source=""):
    return Document(
        CorpusEntry(Path(f"{language}-{split}-{source}.pdf"), split, language, source),
        text,
        1,
        hashlib.sha256(text.encode()).hexdigest(),
    )


class DomainTests(unittest.TestCase):
    def test_unicode_and_line_wrap(self):
        self.assertEqual(normalize("infor-\nmación  española"), "información española")
        self.assertEqual(
            words("EL niño y la nin\u0303a: don't"), ["el", "niño", "y", "la", "niña", "don't"]
        )

    def test_short_words_hand_calculation_and_unknown(self):
        model = ShortWordClassifier(Settings(min_word_frequency=1))
        model.fit([document("the the cat", "en"), document("el el gato", "es")])
        result = model.predict("the the the cat")
        self.assertEqual(result.language, "en")
        denominator = 3 + 0.5 * 5
        expected = -(3 * math.log(2.5 / denominator) + math.log(1.5 / denominator)) / 4
        self.assertAlmostEqual(result.scores["en"], expected)
        self.assertIsNone(model.predict("zzzzz qqqqq vvvvv").language)

    def test_alphabet_uses_frequencies_not_just_accents(self):
        model = AlphabetClassifier(Settings())
        model.fit([document("eeeeeeeeeeaaaa", "en"), document("aaaaaaaaaaeeee", "es")])
        result = model.predict("eeeeeeeeeeaaaa")
        self.assertEqual(result.language, "en")
        self.assertEqual(result.scores["en"], 0)
        self.assertAlmostEqual(result.scores["es"], 12 / 14)

    def test_identical_profiles_abstain(self):
        model = AlphabetClassifier(Settings())
        model.fit([document("abcdefghijklmn", "en"), document("abcdefghijklmn", "es")])
        self.assertIsNone(model.predict("abcdefghijklmn").language)

    def test_untrained_and_unsupported(self):
        model = AlphabetClassifier(Settings())
        with self.assertRaises(LabError):
            model.predict("hello world")
        model.fit([document("the english text", "en"), document("el texto español", "es")])
        for text in ("12345", "русский текст совершенно другой"):
            self.assertIsNone(model.predict(text).language)

    def test_settings_validation(self):
        for params in (
            {"repetitions": 0},
            {"smoothing": float("nan")},
            {"seed": -1},
            {"chunk_words": True},
        ):
            with self.assertRaises(LabError):
                Settings(**params)

    def test_source_and_text_leakage_rejected(self):
        training = [
            document("a" * 20, "en", source="book"),
            document("b" * 20, "es", source="other"),
        ]
        with self.assertRaisesRegex(LabError, "источник"):
            validate_corpus(training + [document("c" * 20, "en", "test", "book")])
        with self.assertRaisesRegex(LabError, "Повтор"):
            validate_corpus(training + [document("a" * 20, "en", "test", "new")])

    def test_unlabeled_excluded_abstentions_counted(self):
        def row(truth, guess):
            predictions = {
                m: Prediction(guess, {}, "", "") for m in ("short_words", "alphabet", "neural")
            }
            return ResultRow(
                "sample.pdf", "", "", truth, 100, 1, predictions, {m: 1.0 for m in predictions}, ()
            )

        metrics = evaluate([row("en", "en"), row("es", None), row(None, "es")])
        for metric in metrics.values():
            self.assertEqual(metric["accuracy"], 0.5)
            self.assertEqual(metric["labeled"], 2)
            self.assertEqual(metric["confusion"]["es"]["?"], 1)
        self.assertIsNone(evaluate([row(None, "en")])["neural"]["accuracy"])
