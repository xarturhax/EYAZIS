import json
import tempfile
import unittest
from pathlib import Path

from lab4.application.translation import TranslationService
from lab4.bootstrap import ROOT
from lab4.domain.models import children, dictionary
from lab4.infrastructure.export import export_report
from lab4.infrastructure.lexicon import SqliteLexicon
from lab4.infrastructure.nlp import EnglishAnalyzer
from lab4.tests.test_core import FakeTranslator


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = EnglishAnalyzer()
        cls.analyzer.prepare()

    def test_real_parse_offsets_and_word_count_agree_with_dictionary(self):
        text = "The doctors study patients. They publish results.\n\nThe painting uses light."
        analyzed = self.analyzer.analyze(text)
        self.assertEqual(len(analyzed.sentences), 3)
        self.assertEqual(analyzed.sentences[2].paragraph, 1)
        for sentence in analyzed.sentences:
            children(sentence)
            for token in sentence.tokens:
                self.assertEqual(analyzed.text[token.start : token.end], token.text)
        self.assertEqual(sum(e.frequency for e in dictionary(analyzed)), 11)
        self.assertTrue(any(e.pos == "VERB" and e.lemma == "study" for e in dictionary(analyzed)))

    def test_invalid_text_and_size(self):
        for text in ("", "123 !", "a" * 50001):
            with self.assertRaises(ValueError):
                self.analyzer.analyze(text)

    def test_unicode_txt_export_includes_full_grammar_and_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            service = TranslationService(
                self.analyzer, FakeTranslator(), SqliteLexicon(base / "lexicon.sqlite3")
            )
            result = service.run("The patient needs treatment.", "medicine")
            report = export_report(result, base / "report")
            text = (base / "report/translation.txt").read_text(encoding="utf-8-sig")
            self.assertIn("texte français", text)
            rows = (base / "report/dictionary.txt").read_text(encoding="utf-8-sig")
            self.assertIn("VBZ", rows)
            self.assertIn("verb, 3rd person singular present", rows)
            self.assertTrue(
                (base / "report/translation.txt").read_bytes().startswith(b"\xef\xbb\xbf")
            )
            self.assertTrue((base / "report/tree.svg").is_file())
            payload = json.loads((base / "report/results.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["source_words"], 4)
            self.assertIn("window.print()", report.read_text(encoding="utf-8"))
            with self.assertRaises(ValueError):
                export_report(result, base / "bad", 10)

    def test_demo_inputs_cover_both_domains(self):
        for domain in ("medicine", "art"):
            self.assertGreater(
                len((ROOT / f"data/demo/{domain}.txt").read_text(encoding="utf-8")), 100
            )
