import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from lab2.bootstrap import DEMO_MANIFEST, build_experiment
from lab2.domain.models import Cancelled, CorpusEntry, LabError, Settings
from lab2.infrastructure.corpus import load_manifest, save_manifest
from lab2.infrastructure.export import export_report, render_html
from lab2.infrastructure.neural import NeuralClassifier
from lab2.infrastructure.pdf import PdfDocumentReader
from lab2.tests.test_domain import document
from lab2.tools.build_demo import write_pdf


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = load_manifest(DEMO_MANIFEST)
        cls.report = build_experiment(Settings(repetitions=1)).run(cls.entries)

    def test_demo_split_sizes_and_real_predictions(self):
        self.assertEqual(len(self.report.rows), 16)
        for size in self.report.training_bytes.values():
            self.assertTrue(20 * 1024 <= size <= 120 * 1024)
        for row in self.report.rows:
            self.assertEqual(row.pages, 1)
            self.assertTrue(2300 <= row.characters <= 2450)
        # Регрессионный минимальный уровень на явно указанной учебной коллекции.
        for metrics in self.report.metrics.values():
            self.assertGreaterEqual(metrics["accuracy"], 0.75)
        self.assertEqual(len(self.report.training), 32)

    def test_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "manifest.json"
            save_manifest(self.entries, target)
            self.assertEqual(load_manifest(target), self.entries)

    def test_pdf_unicode_and_scan_and_password(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "accent.pdf"
            original = "El niño está aquí. La información es útil para la población."
            write_pdf(target, original)
            reader = PdfDocumentReader()
            self.assertEqual(reader.read(CorpusEntry(target, "test", "es")).text, original)
            blank = Path(directory) / "scan.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            writer.write(blank)
            with self.assertRaisesRegex(LabError, "OCR"):
                reader.read(CorpusEntry(blank, "test", None))
            writer.encrypt("secret")
            writer.write(blank)
            with self.assertRaisesRegex(LabError, "парол"):
                reader.read(CorpusEntry(blank, "test", None))
            broken = Path(directory) / "broken.pdf"
            broken.write_bytes(b"not pdf")
            with self.assertRaises(LabError):
                reader.read(CorpusEntry(broken, "test", None))

    def test_pdf_reading_error_keeps_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.pdf"
            with self.assertRaises(LabError):
                PdfDocumentReader().read(CorpusEntry(path, "test", None))
            self.assertFalse(path.exists())

    def test_export_and_escaping(self):
        from dataclasses import replace

        row = replace(self.report.rows[0], title="<script>alert(1)</script>")
        report = replace(self.report, rows=(row, *self.report.rows[1:]))
        self.assertIn("&lt;script&gt;", render_html(report))
        with tempfile.TemporaryDirectory() as directory:
            target = export_report(report, Path(directory))
            self.assertTrue(target.exists())
            data = json.loads((Path(directory) / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data["rows"]), 16)
            self.assertIn("window.print()", target.read_text(encoding="utf-8"))
            for name in ("results.csv", "summary.csv", "comparison.svg", "comparison.png"):
                self.assertGreater((Path(directory) / name).stat().st_size, 100)

    def test_cancellation_before_reading(self):
        with self.assertRaises(Cancelled):
            build_experiment(Settings()).run(self.entries, cancelled=lambda: True)

    def test_neural_no_test_vocabulary_leak(self):
        model = NeuralClassifier(Settings(neural_features=100, neural_iterations=100))
        model.fit(
            [
                document(("the book and the house in the town " * 20), "en"),
                document(("el libro y la casa en la ciudad " * 20), "es"),
            ]
        )
        vocabulary = dict(model.vectorizer.vocabulary_)
        model.predict("zzzzuniqueoutsidewordqqqq " * 4)
        self.assertEqual(model.vectorizer.vocabulary_, vocabulary)
        self.assertNotIn("zz", vocabulary)
