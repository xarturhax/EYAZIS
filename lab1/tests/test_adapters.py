import json
import sqlite3
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

from lab1.ir_system.config import AppConfig
from lab1.ir_system.domain.errors import ExportError, FetchError, StorageError, ValidationError
from lab1.ir_system.domain.models import DocumentDraft
from lab1.ir_system.infrastructure.fixtures import JsonCollectionSource
from lab1.ir_system.infrastructure.reporting.exporter import FileReportExporter
from lab1.ir_system.infrastructure.sqlite import SQLiteRepository
from lab1.ir_system.infrastructure.web import HTMLTextExtractor, HttpDocumentFetcher

from .support import collection_service


class StorageTests(unittest.TestCase):
    def test_persistence_between_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.sqlite3"
            repo = SQLiteRepository(path)
            document_id = collection_service(repo).add(
                DocumentDraft("https://example.org", "alpha", "beta")
            )
            repo.save_judgment("alpha", document_id, 2)
            repo.close()
            repo = SQLiteRepository(path)
            try:
                self.assertEqual(repo.snapshot().postings["alpha"][document_id], 1)
                self.assertEqual(repo.judgments("alpha"), {document_id: 2})
            finally:
                repo.close()

    def test_nested_transaction_does_not_commit_outer_operation(self):
        repo = SQLiteRepository(":memory:")
        self.addCleanup(repo.close)
        with self.assertRaises(RuntimeError):
            with repo.transaction():
                collection_service(repo).add(DocumentDraft("https://example.org", "alpha", "beta"))
                raise RuntimeError("abort")
        self.assertEqual(repo.documents(), ())

    def test_storage_errors_are_translated(self):
        repo = SQLiteRepository(":memory:")
        repo.close()
        with self.assertRaises(StorageError) as caught:
            repo.documents()
        self.assertIsInstance(caught.exception.__cause__, sqlite3.Error)

    def test_legacy_database_keeps_documents_index_and_judgments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript("""
                CREATE TABLE documents(id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL, text TEXT NOT NULL, added_at TEXT NOT NULL,
                    length INTEGER NOT NULL CHECK(length >= 0));
                CREATE TABLE postings(term TEXT NOT NULL, document_id INTEGER NOT NULL
                    REFERENCES documents(id) ON DELETE CASCADE, tf INTEGER NOT NULL CHECK(tf>0),
                    PRIMARY KEY(term,document_id));
                CREATE TABLE queries(id INTEGER PRIMARY KEY,text TEXT NOT NULL UNIQUE);
                CREATE TABLE judgments(query_id INTEGER NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    grade INTEGER NOT NULL CHECK(grade IN (0,1,2)),PRIMARY KEY(query_id,document_id));
                INSERT INTO documents VALUES(7,'https://example.org','alpha','beta','old-time',2);
                INSERT INTO postings VALUES('alpha',7,1),('beta',7,1);
                INSERT INTO queries VALUES(3,'alpha');
                INSERT INTO judgments VALUES(3,7,2);
            """)
            connection.close()
            repo = SQLiteRepository(path)
            try:
                self.assertEqual(repo.get_document(7).added_at, "old-time")
                self.assertEqual(repo.get_document(7).length, 2)
                self.assertEqual(repo.snapshot().postings["alpha"][7], 1)
                self.assertEqual(repo.judgments("alpha"), {7: 2})
                self.assertEqual(repo.queries(), ("alpha",))
            finally:
                repo.close()
            connection = sqlite3.connect(path)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            connection.close()

    def test_future_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA user_version=99")
            connection.close()
            with self.assertRaisesRegex(StorageError, "новее"):
                SQLiteRepository(path)


class LoaderTests(unittest.TestCase):
    def response(self, body, content_type="text/html; charset=utf-8"):
        headers = Message()
        headers["Content-Type"] = content_type
        response = Mock()
        response.headers = headers
        response.geturl.return_value = "https://example.org/final"
        response.read.side_effect = lambda limit: body[:limit]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)
        return response

    def test_html_extraction(self):
        parser = HTMLTextExtractor()
        parser.feed(
            "<head><title>Python &amp; SQL</title><style>hidden</style></head>"
            "<body><p>Hello <b>world</b>.</p><script>hidden</script><p>Database.</p></body>"
        )
        self.assertEqual(parser.title, "Python & SQL")
        self.assertEqual(parser.text, "Hello world. Database.")

    def test_fetch_redirect_charset_and_plaintext(self):
        opener = Mock(return_value=self.response(b"<title>Test</title><p>English content</p>"))
        document = HttpDocumentFetcher(opener=opener).fetch("https://example.org/start")
        self.assertEqual(document.url, "https://example.org/final")
        self.assertEqual(document.text, "English content")
        opener = Mock(return_value=self.response(b"plain text", "text/plain"))
        self.assertEqual(
            HttpDocumentFetcher(opener=opener).fetch("https://example.org").text, "plain text"
        )

    def test_size_type_encoding_and_network_errors(self):
        for body, kind in (
            (b"x" * 101, "text/html"),
            (b"pdf", "application/pdf"),
            (b"text", "text/plain; charset=invalid-codec"),
        ):
            opener = Mock(return_value=self.response(body, kind))
            with self.assertRaises(FetchError):
                HttpDocumentFetcher(max_bytes=100, opener=opener).fetch("https://example.org")
        with self.assertRaises(FetchError) as caught:
            HttpDocumentFetcher(opener=Mock(side_effect=OSError("offline"))).fetch(
                "https://example.org"
            )
        self.assertIsInstance(caught.exception.__cause__, OSError)


class FixtureTests(unittest.TestCase):
    def test_bad_json_reports_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text('{"documents":', encoding="utf-8")
            with self.assertRaises(ValidationError):
                JsonCollectionSource(path).load()


class ExportTests(unittest.TestCase):
    def report(self):
        from dataclasses import replace

        from lab1.ir_system.bootstrap import application_runtime

        with application_runtime(replace(AppConfig(), database=":memory:")) as services:
            result = services.collection.import_demo()
            return services.evaluation.evaluate(result.queries)

    def test_export_formats_and_charts(self):
        report = self.report()
        with tempfile.TemporaryDirectory() as directory:
            path = FileReportExporter().export(report, Path(directory))
            self.assertTrue(path.is_file())
            self.assertEqual(len(list(Path(directory).glob("*.svg"))), 8)
            self.assertEqual(len(list(Path(directory).glob("*.png"))), 8)
            self.assertTrue(
                (Path(directory) / "metrics.csv")
                .read_text(encoding="utf-8-sig")
                .startswith("query,")
            )
            data = json.loads((Path(directory) / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(data["averages"]["MAP"], 0.9375)
            self.assertEqual(data["averages"]["P@10"], 0.24)
            self.assertEqual(data["schema_version"], 2)
            self.assertNotIn("F1", data["averages"])
            self.assertIn("недостигнутые пороги дают 0", path.read_text(encoding="utf-8").lower())
            self.assertEqual(list(Path(directory).glob(".report-*")), [])

    def test_failed_preparation_preserves_previous_report(self):
        report = self.report()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            path.write_text("previous", encoding="utf-8")
            with patch(
                "ir_system.infrastructure.reporting.exporter.render_html",
                side_effect=OSError("disk"),
            ):
                with self.assertRaises(ExportError):
                    FileReportExporter().export(report, Path(directory))
            self.assertEqual(path.read_text(encoding="utf-8"), "previous")

    def test_export_escapes_query_html(self):
        from dataclasses import replace

        report = self.report()
        row = replace(report.rows[0], query='<script>alert("x")</script>')
        report = replace(report, rows=(row,))
        with tempfile.TemporaryDirectory() as directory:
            page = FileReportExporter().export(report, Path(directory)).read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(", page)
            self.assertIn("&lt;script&gt;", page)
