import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from lab4.application.translation import CancelledError, TranslationService
from lab4.domain.models import Analysis, Sentence, Token, children, dictionary
from lab4.infrastructure.lexicon import SqliteLexicon
from lab4.infrastructure.marian import MarianTranslator, split_ranges


def token(index, text, lemma, pos, head=0):
    return Token(
        index,
        text,
        lemma,
        pos,
        "NN" if pos == "NOUN" else "VB",
        "Number=Sing",
        "ROOT" if index == head else "dep",
        head,
        index,
        index + len(text),
    )


def analysis():
    return Analysis(
        "They record a record.",
        (
            Sentence(
                0,
                0,
                "They record a record.",
                (
                    token(0, "They", "they", "PRON", 1),
                    token(1, "record", "record", "VERB", 1),
                    token(2, "a", "a", "DET", 3),
                    token(3, "record", "record", "NOUN", 1),
                    token(4, ".", ".", "PUNCT", 1),
                ),
            ),
        ),
    )


class FakeAnalyzer:
    def prepare(self):
        return {"analyzer": "fake"}

    def analyze(self, text):
        return analysis()


class FakeTranslator:
    def __init__(self):
        self.calls = []

    def prepare(self):
        return {"model": "test", "revision": "1"}

    def translate(self, texts):
        self.calls.extend(texts)
        return ["texte français" for _ in texts]


class DomainTests(unittest.TestCase):
    def test_same_spelling_different_pos_remains_separate(self):
        entries = dictionary(analysis())
        records = [e for e in entries if e.lemma == "record"]
        self.assertEqual({e.pos for e in records}, {"NOUN", "VERB"})
        self.assertEqual(sum(e.frequency for e in entries), 4)

    def test_wordforms_frequencies_sorting_and_morphology(self):
        a = analysis()
        extra = replace(a.sentences[0].tokens[3], text="records")
        second = replace(a.sentences[0], index=1, tokens=(replace(extra, index=0, head=0),))
        entries = dictionary(replace(a, sentences=a.sentences + (second,)))
        self.assertEqual(entries[0].lemma, "record")
        self.assertEqual(entries[0].pos, "NOUN")
        self.assertEqual(entries[0].frequency, 2)
        self.assertEqual(entries[0].forms, (("record", 1), ("records", 1)))
        self.assertEqual(entries[0].morphology, ("Number=Sing",))

    def test_tree_keeps_all_tokens_and_local_indices(self):
        sentence = analysis().sentences[0]
        root, mapping = children(sentence)
        self.assertEqual(root, 1)
        self.assertEqual(sum(len(v) for v in mapping.values()), len(sentence.tokens) - 1)
        self.assertIn(2, mapping[3])

    def test_tree_rejects_missing_root_disconnected_cycle_and_outside_head(self):
        base = analysis().sentences[0]
        for tokens in [
            (),
            (token(0, "a", "a", "NOUN"), token(1, "b", "b", "NOUN", 1)),
            (
                token(0, "a", "a", "NOUN"),
                token(1, "b", "b", "NOUN", 2),
                token(2, "c", "c", "NOUN", 1),
            ),
            (token(0, "a", "a", "NOUN"), token(1, "b", "b", "NOUN", 8)),
        ]:
            with self.assertRaises(ValueError):
                children(replace(base, tokens=tokens))

    def test_chunk_ranges_cover_every_token_once(self):
        for size in (0, 1, 383, 384, 385, 1200):
            ranges = split_ranges(size, 384)
            self.assertEqual(
                [i for start, end in ranges for i in range(start, end)], list(range(size))
            )
            self.assertTrue(all(end - start <= 384 for start, end in ranges))


class CoverageTests(unittest.TestCase):
    def test_identical_auto_form_requires_confirmation_but_manual_can_match(self):
        from lab4.domain.models import Entry

        entry = Entry("patient", "NOUN", 3, (("patient", 3),), ("NN",), (), "patient", "auto")
        self.assertFalse(entry.covered)
        self.assertTrue(replace(entry, origin="manual").covered)
        self.assertFalse(replace(entry, translation="", origin="manual").covered)


class LexiconTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lexicon = SqliteLexicon(Path(self.temp.name) / "lexicon.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_manual_value_survives_auto_refresh_and_reopening(self):
        self.lexicon.store_auto([("record", "NOUN", "dossier")], "medicine", "m")
        self.lexicon.correct("record", "NOUN", "medicine", "m", "compte rendu")
        self.lexicon.store_auto([("record", "NOUN", "disque")], "medicine", "m")
        reopened = SqliteLexicon(self.lexicon.path)
        self.assertEqual(
            reopened.get("record", "NOUN", "medicine", "m"), ("compte rendu", "manual")
        )

    def test_domain_model_and_pos_are_independent(self):
        self.lexicon.correct("record", "NOUN", "art", "m", "disque")
        for pos, domain, model in [
            ("VERB", "art", "m"),
            ("NOUN", "medicine", "m"),
            ("NOUN", "art", "other"),
        ]:
            self.assertEqual(self.lexicon.get("record", pos, domain, model), ("", "missing"))

    def test_invalid_auto_batch_writes_nothing(self):
        with self.assertRaises(ValueError):
            self.lexicon.store_auto([("a", "DET", "un"), ("b", "NOUN", "")], "art", "m")
        self.assertEqual(self.lexicon.get("a", "DET", "art", "m"), ("", "missing"))

    def test_reset_and_invalid_manual_correction(self):
        self.lexicon.correct("a", "DET", "art", "m", "un")
        self.lexicon.reset("a", "DET", "art", "m")
        self.assertEqual(self.lexicon.get("a", "DET", "art", "m"), ("", "missing"))
        with self.assertRaises(ValueError):
            self.lexicon.correct("a", "DET", "art", "m", "")

    def test_service_counts_source_coverage_instead_of_target_length(self):
        translator = FakeTranslator()
        service = TranslationService(FakeAnalyzer(), translator, self.lexicon)
        result = service.run("input", "art")
        self.assertEqual(result.source_words, 4)
        self.assertEqual(result.translated_source_words, 4)
        self.assertEqual(result.target_words, 2)
        self.assertEqual([e.frequency for e in result.entries], [1] * 4)

    def test_repeated_analysis_does_not_accumulate_frequency(self):
        service = TranslationService(FakeAnalyzer(), FakeTranslator(), self.lexicon)
        first = service.run("input", "art")
        second = service.run("input", "art")
        self.assertEqual(first.entries, second.entries)

    def test_cancelled_population_has_no_partial_db_writes(self):
        translator = FakeTranslator()
        service = TranslationService(FakeAnalyzer(), translator, self.lexicon)
        with self.assertRaises(CancelledError):
            service.populate(analysis(), "art", "m", False, lambda _: None, lambda: True)
        self.assertEqual(self.lexicon.get("record", "NOUN", "art", "m"), ("", "missing"))

    def test_empty_model_response_and_bad_domain_are_errors(self):
        translator = FakeTranslator()
        translator.translate = lambda texts: ["" for _ in texts]
        service = TranslationService(FakeAnalyzer(), translator, self.lexicon)
        with self.assertRaises(ValueError):
            service.run("input", "art")
        with self.assertRaises(ValueError):
            service.run("input", "other")


class GenerationTests(unittest.TestCase):
    def test_all_encoded_tokens_reach_model_without_truncation(self):
        import torch

        seen = []

        class Tokenizer:
            eos_token_id = 9999

            def encode(self, text, add_special_tokens):
                return list(range(900))

            def decode(self, generated, skip_special_tokens):
                return "traduction"

        class Model:
            def generate(self, input_ids, **kwargs):
                seen.extend(input_ids[0].tolist()[:-1])
                self.assert_limit = len(input_ids[0]) <= 385
                return torch.tensor([[0, 8, 9999]])

        translator = MarianTranslator()
        translator.tokenizer, translator.model = Tokenizer(), Model()
        self.assertEqual(translator.translate(["long"]), ["traduction traduction traduction"])
        self.assertEqual(seen, list(range(900)))

    def test_generation_limit_failure_does_not_return_partial_translation(self):
        import torch

        class Tokenizer:
            eos_token_id = 9

            def encode(self, text, add_special_tokens):
                return [1]

        class Model:
            def generate(self, **kwargs):
                return torch.tensor([[0, 3, 4]])

        translator = MarianTranslator()
        translator.tokenizer, translator.model = Tokenizer(), Model()
        with self.assertRaises(ValueError):
            translator.translate(["text"])
