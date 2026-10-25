"""SQLite-адаптер: только persistence, явные транзакции и согласованные снимки."""

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from lab1.ir_system.domain.errors import NotFoundError, StorageError
from lab1.ir_system.domain.models import CorpusSnapshot, Document, IndexedDocument

SCHEMA_VERSION = 1
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS documents ("
    "id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL, "
    "text TEXT NOT NULL, added_at TEXT NOT NULL, length INTEGER NOT NULL CHECK(length >= 0))",
    "CREATE TABLE IF NOT EXISTS postings ("
    "term TEXT NOT NULL, document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, "
    "tf INTEGER NOT NULL CHECK(tf > 0), PRIMARY KEY(term, document_id))",
    "CREATE INDEX IF NOT EXISTS postings_document ON postings(document_id)",
    "CREATE TABLE IF NOT EXISTS queries (id INTEGER PRIMARY KEY, text TEXT NOT NULL UNIQUE)",
    "CREATE TABLE IF NOT EXISTS judgments ("
    "query_id INTEGER NOT NULL REFERENCES queries(id) ON DELETE CASCADE, "
    "document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, "
    "grade INTEGER NOT NULL CHECK(grade IN (0, 1, 2)), PRIMARY KEY(query_id, document_id))",
)


class SQLiteRepository:
    def __init__(self, path: str | Path) -> None:
        self._depth = 0
        try:
            if str(path) != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(path), isolation_level=None)
            self._connection.row_factory = sqlite3.Row
        except (OSError, sqlite3.Error) as exc:
            raise StorageError(f"Не удалось открыть базу данных: {exc}") from exc
        try:
            self._execute("PRAGMA foreign_keys = ON")
            version = self._execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise StorageError(f"Версия базы {version} новее поддерживаемой {SCHEMA_VERSION}")
            with self.transaction():
                for statement in SCHEMA:
                    self._execute(statement)
                self._execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except Exception:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        level = self._depth
        savepoint = f"operation_{level}"
        self._execute("BEGIN" if level == 0 else f"SAVEPOINT {savepoint}")
        self._depth += 1
        try:
            yield
            self._execute("COMMIT" if level == 0 else f"RELEASE SAVEPOINT {savepoint}")
        except BaseException:
            if level == 0:
                self._execute("ROLLBACK")
            else:
                self._execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self._execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        finally:
            self._depth -= 1

    def _execute(self, sql: str, parameters: Sequence[object] = ()) -> sqlite3.Cursor:
        try:
            return self._connection.execute(sql, parameters)
        except sqlite3.Error as exc:
            raise StorageError(f"Ошибка базы данных: {exc}") from exc

    def documents(self) -> tuple[Document, ...]:
        return tuple(
            Document(**dict(row)) for row in self._execute("SELECT * FROM documents ORDER BY id")
        )

    def get_document(self, document_id: int) -> Document:
        row = self._execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"Документ #{document_id} не найден")
        return Document(**dict(row))

    def snapshot(self) -> CorpusSnapshot:
        with self.transaction():
            documents = self.documents()
            postings: dict[str, dict[int, int]] = {}
            for row in self._execute(
                "SELECT term,document_id,tf FROM postings ORDER BY term,document_id"
            ):
                postings.setdefault(row["term"], {})[row["document_id"]] = row["tf"]
        return CorpusSnapshot(documents, postings)

    def save_document(self, document: IndexedDocument) -> int:
        draft = document.draft
        with self.transaction():
            old = self._execute("SELECT * FROM documents WHERE url=?", (draft.url,)).fetchone()
            if old and old["title"] == draft.title and old["text"] == draft.text:
                return old["id"]
            if old:
                document_id = old["id"]
                self._execute(
                    "UPDATE documents SET title=?,text=?,added_at=?,length=? WHERE id=?",
                    (draft.title, draft.text, document.added_at, document.length, document_id),
                )
                self._execute("DELETE FROM postings WHERE document_id=?", (document_id,))
                self._execute("DELETE FROM judgments WHERE document_id=?", (document_id,))
            else:
                cursor = self._execute(
                    "INSERT INTO documents(url,title,text,added_at,length) VALUES(?,?,?,?,?)",
                    (draft.url, draft.title, draft.text, document.added_at, document.length),
                )
                document_id = cursor.lastrowid
                assert document_id is not None
            for term, tf in document.term_frequencies.items():
                self._execute(
                    "INSERT INTO postings(term,document_id,tf) VALUES(?,?,?)",
                    (term, document_id, tf),
                )
        return document_id

    def delete_document(self, document_id: int) -> None:
        self._execute("DELETE FROM documents WHERE id=?", (document_id,))

    def queries(self) -> tuple[str, ...]:
        return tuple(row[0] for row in self._execute("SELECT text FROM queries ORDER BY id"))

    def judgments(self, query: str) -> dict[int, int]:
        return {
            row[0]: row[1]
            for row in self._execute(
                "SELECT document_id,grade FROM judgments JOIN queries ON queries.id=query_id WHERE queries.text=?",
                (query,),
            )
        }

    def save_judgment(self, query: str, document_id: int, grade: int) -> None:
        with self.transaction():
            self._execute("INSERT OR IGNORE INTO queries(text) VALUES(?)", (query,))
            self._execute(
                "INSERT INTO judgments(query_id,document_id,grade) "
                "SELECT id,?,? FROM queries WHERE text=? "
                "ON CONFLICT(query_id,document_id) DO UPDATE SET grade=excluded.grade",
                (document_id, grade, query),
            )
