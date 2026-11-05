"""Коллекция SQLite, английские слова, BM25 и метрики поиска."""

import json
import math
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
STOP = frozenset(
    "a an and are as at be been being but by can could did do does for from had has have he her hers him his how i if in into is it its may me more most my no nor not of on or our ours she should so some such than that the their theirs them then there these they this those to too was we were what when where which who will with would you your yours".split()
)


def words(text):
    return [w for w in re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower()) if w not in STOP]


def url_value(url):
    value = urldefrag(url.strip())[0]
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Нужен HTTP(S) URL без логина и пароля.")
    _ = parsed.port
    return value


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.body, self.title = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append(tag)
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "article", "td"}:
            self.body.append(" ")

    def handle_endtag(self, tag):
        if tag in self.stack:
            position = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[position:]
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "article", "td"}:
            self.body.append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, text):
        if "title" in self.stack:
            self.title.append(text)
        elif not set(self.stack) & {"script", "style", "noscript", "template", "svg", "head"}:
            self.body.append(text)


def fetch(url):
    request = Request(url_value(url), headers={"User-Agent": "EYAZIS-Lab1"})
    with urlopen(request, timeout=15) as response:
        final = url_value(response.geturl())
        kind = response.headers.get_content_type()
        if kind not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise ValueError("Поддерживаются HTML и обычный текст.")
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("Страница больше 2 МиБ.")
        text = raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    if kind == "text/plain":
        return {"url": final, "title": final, "text": text}
    parser = PageText()
    parser.feed(text)
    return {
        "url": final,
        "title": " ".join("".join(parser.title).split()) or final,
        "text": " ".join("".join(parser.body).split()),
    }


def evaluate(ranking, grades):
    if len(set(ranking)) != len(ranking) or any(i not in grades for i in ranking):
        raise ValueError("Выдача содержит дубли или неоценённые документы.")
    if any(type(g) is not int or g not in (0, 1, 2) for g in grades.values()):
        raise ValueError("Оценки: целые числа 0, 1 или 2.")
    relevant = {i for i, grade in grades.items() if grade > 0}
    count = len(relevant)
    if not count:
        raise ValueError("Нет релевантных документов (R=0).")
    hits, ap, curve = 0, 0.0, []
    for rank, ident in enumerate(ranking, 1):
        if ident in relevant:
            hits += 1
            ap += hits / rank
        curve.append((hits / rank, hits / count))
    metrics = {
        "Precision": hits / len(ranking) if ranking else 0.0,
        "Recall": hits / count,
        "AP": ap / count,
        "P@5": sum(i in relevant for i in ranking[:5]) / 5,
        "P@10": sum(i in relevant for i in ranking[:10]) / 10,
        "R-precision": sum(i in relevant for i in ranking[:count]) / count,
    }
    interpolated = [
        max((p for p, r in curve if r >= level / 10), default=0.0) for level in range(11)
    ]
    return {
        "metrics": metrics,
        "curve": curve,
        "interpolated": interpolated,
        "TP": hits,
        "FP": len(ranking) - hits,
        "FN": count - hits,
        "TN": len(grades) - count - len(ranking) + hits,
    }


class SearchEngine:
    def __init__(self, path=ROOT / "data/search.sqlite3"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS documents(
              id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
              text TEXT NOT NULL, added_at TEXT NOT NULL, length INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS postings(
              term TEXT NOT NULL, document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
              tf INTEGER NOT NULL CHECK(tf>0), PRIMARY KEY(term,document_id));
            CREATE INDEX IF NOT EXISTS postings_document ON postings(document_id);
            CREATE TABLE IF NOT EXISTS queries(id INTEGER PRIMARY KEY,text TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS judgments(
              query_id INTEGER REFERENCES queries(id) ON DELETE CASCADE,
              document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
              grade INTEGER NOT NULL CHECK(grade IN (0,1,2)), PRIMARY KEY(query_id,document_id));
        """)

    def documents(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM documents ORDER BY id")]

    def document(self, ident):
        row = self.db.execute("SELECT * FROM documents WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise ValueError(f"Документ №{ident} не найден.")
        return dict(row)

    def _save(self, url, title, text):
        url = url_value(url)
        if not title.strip() or not text.strip():
            raise ValueError("Заполните заголовок и текст.")
        counts = Counter(words(title + " " + text))
        if not counts:
            raise ValueError("В документе нет английских поисковых слов.")
        old = self.db.execute("SELECT * FROM documents WHERE url=?", (url,)).fetchone()
        if old and old["title"] == title and old["text"] == text:
            return old["id"]
        now = datetime.now(timezone.utc).isoformat()
        if old:
            ident = old["id"]
            self.db.execute(
                "UPDATE documents SET title=?,text=?,added_at=?,length=? WHERE id=?",
                (title, text, now, sum(counts.values()), ident),
            )
            self.db.execute("DELETE FROM postings WHERE document_id=?", (ident,))
            self.db.execute("DELETE FROM judgments WHERE document_id=?", (ident,))
        else:
            ident = self.db.execute(
                "INSERT INTO documents(url,title,text,added_at,length) VALUES(?,?,?,?,?)",
                (url, title, text, now, sum(counts.values())),
            ).lastrowid
        self.db.executemany(
            "INSERT INTO postings VALUES(?,?,?)", [(t, ident, tf) for t, tf in counts.items()]
        )
        return ident

    def add(self, url, title, text):
        with self.db:
            return self._save(url, title, text)

    def demo(self):
        data = json.loads((ROOT / "fixtures/collection.json").read_text(encoding="utf-8"))
        with self.db:
            ids = {d["key"]: self._save(d["url"], d["title"], d["text"]) for d in data["documents"]}
            for query in data["queries"]:
                for key, ident in ids.items():
                    self._grade(query["text"], ident, query["grades"].get(key, 0))

    def delete(self, identifiers):
        with self.db:
            for ident in set(identifiers):
                self.document(ident)
                self.db.execute("DELETE FROM documents WHERE id=?", (ident,))

    def search(self, query, k1=1.5, b=0.75):
        if not math.isfinite(k1) or k1 <= 0 or not math.isfinite(b) or not 0 <= b <= 1:
            raise ValueError("Требуется k1 > 0, 0 ≤ b ≤ 1.")
        documents = {d["id"]: d for d in self.documents()}
        if not documents:
            return []
        average = sum(d["length"] for d in documents.values()) / len(documents)
        scores, matched = {}, {}
        for term in dict.fromkeys(words(query)):
            postings = list(
                self.db.execute("SELECT document_id,tf FROM postings WHERE term=?", (term,))
            )
            idf = math.log(1 + (len(documents) - len(postings) + 0.5) / (len(postings) + 0.5))
            for ident, tf in postings:
                denominator = tf + k1 * (1 - b + b * documents[ident]["length"] / average)
                scores[ident] = scores.get(ident, 0.0) + idf * tf * (k1 + 1) / denominator
                matched.setdefault(ident, []).append(term)
        return [
            documents[i] | {"score": scores[i], "matched_words": matched[i]}
            for i in sorted(scores, key=lambda i: (-scores[i], i))
        ]

    def index(self, ident):
        self.document(ident)
        n = self.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        return [
            dict(row) | {"weight": row["tf"] * math.log(n / row["df"])}
            for row in self.db.execute(
                "SELECT p.term,p.tf,(SELECT COUNT(*) FROM postings WHERE term=p.term) df "
                "FROM postings p WHERE p.document_id=? ORDER BY p.term",
                (ident,),
            )
        ]

    def queries(self):
        return [r[0] for r in self.db.execute("SELECT text FROM queries ORDER BY id")]

    def grades(self, query):
        return dict(
            self.db.execute(
                "SELECT document_id,grade FROM judgments JOIN queries ON queries.id=query_id WHERE queries.text=?",
                (" ".join(query.split()),),
            )
        )

    def _grade(self, query, ident, grade):
        query = " ".join(query.split())
        if not query or type(grade) is not int or grade not in (0, 1, 2):
            raise ValueError("Введите запрос и оценку 0, 1 или 2.")
        self.document(ident)
        self.db.execute("INSERT OR IGNORE INTO queries(text) VALUES(?)", (query,))
        self.db.execute(
            "INSERT INTO judgments SELECT id,?,? FROM queries WHERE text=? "
            "ON CONFLICT(query_id,document_id) DO UPDATE SET grade=excluded.grade",
            (ident, grade, query),
        )

    def grade(self, query, identifiers, grade):
        with self.db:
            for ident in set(identifiers):
                self._grade(query, ident, grade)

    def quality(self, queries, k1=1.5, b=0.75):
        rows, excluded = [], []
        ids = {d["id"] for d in self.documents()}
        if not ids:
            raise ValueError("Коллекция пуста.")
        for query in dict.fromkeys(" ".join(q.split()) for q in queries):
            grades = self.grades(query)
            missing = ids - grades.keys()
            if missing:
                raise ValueError(f"Запрос «{query}»: оцените ещё {len(missing)} документов.")
            if not any(grades.values()):
                excluded.append(query)
                continue
            ranking = [d["id"] for d in self.search(query, k1, b)]
            rows.append({"query": query, "ranking": ranking} | evaluate(ranking, grades))
        if not rows:
            raise ValueError("Нет размеченных запросов с релевантными документами.")
        averages = {
            name: sum(r["metrics"][name] for r in rows) / len(rows) for name in rows[0]["metrics"]
        }
        averages["MAP"] = averages.pop("AP")
        return {
            "document_count": len(ids),
            "parameters": {"k1": k1, "b": b},
            "rows": rows,
            "excluded": excluded,
            "averages": averages,
            "mean_interpolated": [
                sum(r["interpolated"][i] for r in rows) / len(rows) for i in range(11)
            ],
        }

    def close(self):
        self.db.close()
