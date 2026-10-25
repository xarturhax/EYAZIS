"""Connections stay in the calling thread; manual corrections survive automatic updates."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SqliteLexicon:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS entries(
                    lemma TEXT NOT NULL, pos TEXT NOT NULL, domain TEXT NOT NULL,
                    model TEXT NOT NULL, translation TEXT NOT NULL,
                    origin TEXT NOT NULL CHECK(origin IN ('auto','manual')),
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(lemma,pos,domain,model))
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=20)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, lemma: str, pos: str, domain: str, model: str) -> tuple[str, str]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT translation,origin FROM entries WHERE lemma=? AND pos=? AND domain=? AND model=?",
                (lemma, pos, domain, model),
            ).fetchone()
        return (str(row[0]), str(row[1])) if row else ("", "missing")

    def store_auto(self, rows: list[tuple[str, str, str]], domain: str, model: str) -> None:
        if any(not translation.strip() for _, _, translation in rows):
            raise ValueError("Пустой автоперевод не сохраняется в словаре.")
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO entries(lemma,pos,domain,model,translation,origin)
                VALUES(?,?,?,?,?,'auto')
                ON CONFLICT(lemma,pos,domain,model) DO UPDATE SET
                translation=excluded.translation, updated_at=CURRENT_TIMESTAMP
                WHERE entries.origin!='manual'
            """,
                [(lemma, pos, domain, model, value.strip()) for lemma, pos, value in rows],
            )

    def correct(self, lemma: str, pos: str, domain: str, model: str, translation: str) -> None:
        if not translation.strip() or len(translation) > 500:
            raise ValueError("Перевод должен содержать от 1 до 500 символов.")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO entries(lemma,pos,domain,model,translation,origin)
                VALUES(?,?,?,?,?,'manual')
                ON CONFLICT(lemma,pos,domain,model) DO UPDATE SET
                translation=excluded.translation,origin='manual',updated_at=CURRENT_TIMESTAMP
            """,
                (lemma, pos, domain, model, translation.strip()),
            )

    def reset(self, lemma: str, pos: str, domain: str, model: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM entries WHERE lemma=? AND pos=? AND domain=? AND model=?",
                (lemma, pos, domain, model),
            )
