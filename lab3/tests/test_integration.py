import csv
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pymupdf

from lab3.application.experiment import Summarizer
from lab3.bootstrap import DEMO, ROOT
from lab3.domain.ranking import PositionalRanker
from lab3.infrastructure.documents import load_corpus, normalize, read_document, read_manifest
from lab3.infrastructure.export import export_report, render
from lab3.infrastructure.nlp import SpacyAnalyzer
from lab3.infrastructure.textrank import TextRank
from lab3.tests.helpers import fixture
from lab3.tests.test_ranking import FakeAnalyzer


class InputTests(unittest.TestCase):
    def test_normalization_keeps_paragraphs_and_accents(self):
        self.assertEqual(
            normalize("  me\u0301dico\r\n español.\r\n\r\nSecond line. "),
            "médico español.\n\nSecond line.",
        )

    def test_invalid_format_encoding_empty_text_and_duplicate_corpus(self):
        source = fixture()[0].document.source
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "text.txt"
            path.write_bytes(b"\xff\xff")
            with self.assertRaises(ValueError):
                read_document(replace(source, path=path))
            path.write_text("123 45", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_document(replace(source, path=path))
            path.write_text("Alpha beta.", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_corpus([replace(source, path=path), replace(source, path=path)])
            unknown = Path(directory) / "file.doc"
            unknown.write_text("Alpha.")
            with self.assertRaises(ValueError):
                read_document(replace(source, path=unknown))

    def test_pdf_text_scan_password_and_broken_file(self):
        source = fixture()[0].document.source
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with pymupdf.open() as document:
                page = document.new_page()
                path = base / "blank.pdf"
                document.save(path)
                with self.assertRaises(ValueError):
                    read_document(replace(source, path=path))
                page.insert_text((72, 72), "Medical research. New results.")
                text_path = base / "text.pdf"
                document.save(text_path)
                result = read_document(replace(source, path=text_path))
                self.assertIn("Medical research", result.text)
                self.assertTrue(result.warnings)
                encrypted = base / "encrypted.pdf"
                document.save(
                    encrypted,
                    encryption=pymupdf.PDF_ENCRYPT_AES_256,
                    owner_pw="owner",
                    user_pw="secret",
                )
                with self.assertRaisesRegex(ValueError, "паролем"):
                    read_document(replace(source, path=encrypted))
            path.write_bytes(b"not PDF")
            with self.assertRaises(ValueError):
                read_document(replace(source, path=path))

    def test_manifest_rejects_unknown_language_and_unsafe_source_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            row = dict(path="input.txt", title="Example", language="fr", domain="art")
            path.write_text(json.dumps(dict(schema=1, documents=[row])), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_manifest(path)
            row.update(language="en", url="javascript:alert(1)")
            path.write_text(json.dumps(dict(schema=1, documents=[row])), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_manifest(path)

    def test_demo_snapshots_match_provenance_and_comparable_lengths(self):
        records = json.loads((ROOT / "data/demo/provenance.json").read_text(encoding="utf-8"))
        sources = read_manifest(DEMO)
        self.assertEqual(
            {(s.language, s.domain) for s in sources},
            {("en", "medicine"), ("es", "medicine"), ("en", "art"), ("es", "art")},
        )
        for source, record in zip(sources, records, strict=True):
            self.assertEqual(
                hashlib.sha256(source.path.read_bytes()).hexdigest(), record["text_sha256"]
            )
            original = ROOT / "data/demo/sources" / record["file"]
            self.assertEqual(
                hashlib.sha256(original.read_bytes()).hexdigest(), record["source_sha256"]
            )
        lengths = [len(d.text) for d in load_corpus(sources)]
        self.assertLess(max(lengths) / min(lengths), 1.25)


class NlpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = SpacyAnalyzer()
        cls.analyzer.prepare({"en", "es"})

    def test_offsets_paragraphs_original_sentences_and_numeric_stopword_filter(self):
        text = "The doctors study 12 patients. They publish results.\n\nThe heart works."
        source = fixture()[0].document.source
        result = self.analyzer.analyze(replace(fixture()[0].document, text=text, source=source))
        self.assertEqual(len(result.sentences), 3)
        for sentence in result.sentences:
            self.assertEqual(text[sentence.start : sentence.end], sentence.text)
            self.assertLessEqual(sentence.paragraph_start, sentence.start)
            self.assertGreaterEqual(sentence.paragraph_end, sentence.end)
            self.assertTrue(all(term.isalpha() for term in sentence.terms))
            self.assertNotIn("the", sentence.terms)
        self.assertEqual(result.sentences[2].paragraph_start, text.index("The heart"))
        self.assertIn("doctor", result.sentences[0].terms)

    def test_spanish_lemmas_preserve_accents_and_latin_words(self):
        source = replace(fixture()[0].document.source, language="es")
        document = replace(
            fixture()[0].document,
            source=source,
            text="Los médicos estudian el corazón. Publican resultados.",
        )
        result = self.analyzer.analyze(document)
        terms = [term for sentence in result.sentences for term in sentence.terms]
        self.assertIn("corazón", terms)
        self.assertIn("médico", terms)
        self.assertNotIn("los", terms)


class ExportTests(unittest.TestCase):
    def test_html_escapes_user_text_and_preserves_source_links(self):
        documents = fixture()
        source = replace(
            documents[0].document.source,
            title='<script>alert("x")</script>',
            url="https://example.com/?a=1&b=2",
        )
        documents[0] = replace(documents[0], document=replace(documents[0].document, source=source))
        result = Summarizer(FakeAnalyzer(documents), [PositionalRanker(), TextRank()]).run(
            [d.document for d in documents]
        )
        html = render(result)
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("https://example.com/?a=1&amp;b=2", html)
        self.assertIn('href="sources/document-001.txt"', html)
        self.assertIn("window.print()", html)

    def test_portable_export_round_trip_and_expert_scores_are_preserved(self):
        documents = fixture()
        service = Summarizer(FakeAnalyzer(documents), [PositionalRanker(), TextRank()])
        result = service.run([d.document for d in documents], sentences=1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = export_report(result, output)
            self.assertTrue(report.is_file())
            payload = json.loads((output / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["documents"][0]["summaries"][0]["selected"], [0])
            self.assertEqual(
                (output / "sources/document-001.txt").read_text(encoding="utf-8"),
                documents[0].document.text,
            )
            assessment = next(output.glob("expert_assessment-*.csv"))
            with assessment.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(row["informativeness_1_5"] == "" for row in rows))
            assessment.write_text("expert data must survive", encoding="utf-8")
            export_report(result, output)
            self.assertEqual(assessment.read_text(encoding="utf-8"), "expert data must survive")
            changed = service.run([d.document for d in documents], sentences=2)
            export_report(changed, output)
            self.assertEqual(len(list(output.glob("expert_assessment-*.csv"))), 2)
