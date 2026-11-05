from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any

from lab4.tools.download_model import MODEL_ID, MODEL_PATH, REVISION


@dataclass(frozen=True)
class Token:
    index: int
    text: str
    lemma: str
    pos: str
    tag: str
    morphology: str
    dependency: str
    head: int
    start: int
    end: int

    @property
    def is_word(self) -> bool:
        return any(c.isalpha() for c in self.text)


@dataclass(frozen=True)
class Sentence:
    index: int
    paragraph: int
    text: str
    tokens: tuple[Token, ...]


@dataclass(frozen=True)
class Analysis:
    text: str
    sentences: tuple[Sentence, ...]


@dataclass(frozen=True)
class Entry:
    lemma: str
    pos: str
    frequency: int
    forms: tuple[tuple[str, int], ...]
    tags: tuple[str, ...]
    morphology: tuple[str, ...]
    translation: str = ""
    origin: str = "missing"

    @property
    def covered(self) -> bool:
        # Shared EN/FR forms can be valid, but require explicit confirmation.
        return bool(self.translation.strip()) and (
            self.origin == "manual" or self.translation.casefold() != self.lemma.casefold()
        )


@dataclass(frozen=True)
class Result:
    analysis: Analysis
    translated_sentences: tuple[str, ...]
    translation: str
    entries: tuple[Entry, ...]
    source_words: int
    translated_source_words: int
    target_words: int
    timings: dict[str, float]
    versions: dict[str, str]
    warnings: tuple[str, ...]


def dictionary(analysis: Analysis) -> tuple[Entry, ...]:
    from collections import Counter, defaultdict

    groups: dict[tuple[str, str], list[Token]] = defaultdict(list)
    for sentence in analysis.sentences:
        for token in sentence.tokens:
            if token.is_word:
                groups[(token.lemma, token.pos)].append(token)
    return tuple(
        sorted(
            (
                Entry(
                    lemma,
                    pos,
                    len(tokens),
                    tuple(sorted(Counter(t.text for t in tokens).items())),
                    tuple(sorted({t.tag for t in tokens})),
                    tuple(sorted({t.morphology for t in tokens if t.morphology})),
                )
                for (lemma, pos), tokens in groups.items()
            ),
            key=lambda entry: (-entry.frequency, entry.lemma, entry.pos),
        )
    )


def children(sentence: Sentence) -> tuple[int, dict[int, list[int]]]:
    """Adapted from spring 3lab/services/dependency.py, with strict tree validation."""
    roots = [t.index for t in sentence.tokens if t.index == t.head]
    if len(roots) != 1 or [t.index for t in sentence.tokens] != list(range(len(sentence.tokens))):
        raise ValueError("Некорректный корень или индексы дерева.")
    mapping: dict[int, list[int]] = {t.index: [] for t in sentence.tokens}
    for token in sentence.tokens:
        if token.head not in mapping:
            raise ValueError("Связь дерева выходит за границы предложения.")
        if token.head != token.index:
            mapping[token.head].append(token.index)
    visited = set()
    pending = [roots[0]]
    while pending:
        node = pending.pop()
        if node in visited:
            raise ValueError("Цикл в дереве зависимостей.")
        visited.add(node)
        pending.extend(mapping[node])
    if len(visited) != len(sentence.tokens):
        raise ValueError("Несвязное дерево зависимостей.")
    return roots[0], mapping


POS = {
    "ADJ": "прилагательное",
    "ADP": "предлог/послелог",
    "ADV": "наречие",
    "AUX": "вспомогательный глагол",
    "CCONJ": "сочинительный союз",
    "DET": "определитель",
    "INTJ": "междометие",
    "NOUN": "существительное",
    "NUM": "числительное",
    "PART": "частица",
    "PRON": "местоимение",
    "PROPN": "имя собственное",
    "PUNCT": "пунктуация",
    "SCONJ": "подчинительный союз",
    "SYM": "символ",
    "VERB": "глагол",
    "X": "прочее",
    "SPACE": "пробел",
}


@lru_cache(maxsize=256)
def explain(tag: str) -> str:
    import spacy

    return POS.get(tag) or spacy.explain(tag) or "нет описания"


def tag_descriptions(tags: tuple[str, ...]) -> str:
    return "; ".join(f"{tag}: {explain(tag)}" for tag in tags)


class EnglishAnalyzer:
    def __init__(self) -> None:
        self.nlp: Any = None

    def prepare(self) -> dict[str, str]:
        import spacy

        if self.nlp is None:
            try:
                self.nlp = spacy.load("en_core_web_sm", disable=["ner"])
            except OSError as error:
                raise ValueError(
                    "Установите en_core_web_sm из requirements.txt в корне проекта."
                ) from error
        return {"spacy": spacy.__version__, "en_core_web_sm": self.nlp.meta["version"]}

    def analyze(self, text: str) -> Analysis:
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not any(c.isalpha() for c in text):
            raise ValueError("Введите английский текст с буквами.")
        if len(text) > 50_000:
            raise ValueError("Максимум 50 000 символов за один запуск.")
        sentences: list[Sentence] = []
        for paragraph, match in enumerate(re.finditer(r"\S(?:[^\n]|\n(?![ \t]*\n))*", text)):
            document = self.nlp(match.group().rstrip())
            for span in document.sents:
                tokens = tuple(
                    Token(
                        t.i - span.start,
                        t.text,
                        t.lemma_.casefold(),
                        t.pos_,
                        t.tag_,
                        str(t.morph),
                        t.dep_,
                        t.head.i - span.start,
                        match.start() + t.idx,
                        match.start() + t.idx + len(t.text),
                    )
                    for t in span
                )
                sentence = Sentence(len(sentences), paragraph, span.text.strip(), tokens)
                children(sentence)
                sentences.append(sentence)
        return Analysis(text, tuple(sentences))


def split_ranges(size: int, limit: int) -> list[tuple[int, int]]:
    return [(start, min(start + limit, size)) for start in range(0, size, limit)]


class MarianTranslator:
    def __init__(self) -> None:
        self.tokenizer: Any = None
        self.model: Any = None

    def prepare(self) -> dict[str, str]:
        import torch
        import transformers
        from transformers import MarianMTModel, MarianTokenizer

        if self.model is None:
            if not (MODEL_PATH / "revision.json").is_file():
                raise ValueError(
                    "Модель отсутствует. Выполните python -m lab4.tools.download_model."
                )
            torch.set_num_threads(2)
            self.tokenizer = MarianTokenizer.from_pretrained(str(MODEL_PATH), local_files_only=True)
            self.model = MarianMTModel.from_pretrained(str(MODEL_PATH), local_files_only=True)
            self.model.eval()
        return {
            "model": MODEL_ID,
            "revision": REVISION,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "device": "cpu",
            "beams": "4",
        }

    def translate(self, texts: list[str]) -> list[str]:
        import torch

        output = []
        for text in texts:
            ids = self.tokenizer.encode(text, add_special_tokens=False)
            if not ids:
                output.append("")
                continue
            translated = []
            # 384 < the model's 512-token context, leaving room for special tokens.
            for start, end in split_ranges(len(ids), 384):
                chunk = ids[start:end] + [self.tokenizer.eos_token_id]
                batch = torch.tensor([chunk], dtype=torch.long)
                with torch.inference_mode():
                    generated = self.model.generate(
                        input_ids=batch,
                        attention_mask=torch.ones_like(batch),
                        num_beams=4,
                        do_sample=False,
                        max_new_tokens=510,
                        max_length=None,
                    )[0].tolist()
                eos = self.tokenizer.eos_token_id
                # The decoder may start with EOS/PAD; only inspect generated tokens.
                if eos not in generated[1:]:
                    raise ValueError(
                        "Перевод достиг лимита генерации; текст не был сохранён частично."
                    )
                value = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
                if not value:
                    raise ValueError("Модель вернула пустой перевод.")
                translated.append(value)
            output.append(" ".join(translated))
        return output


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


class CancelledError(Exception):
    pass


class TranslationService:
    def __init__(self, analyzer: Any, translator: Any, lexicon: Any) -> None:
        self.analyzer, self.translator, self.lexicon = analyzer, translator, lexicon

    def populate(
        self,
        analysis: Analysis,
        domain: str,
        model: str,
        progress: Callable[[str], None],
        cancelled: Callable[[], bool],
    ) -> tuple[Entry, ...]:
        entries = dictionary(analysis)
        pending = []
        for entry in entries:
            value, _ = self.lexicon.get(entry.lemma, entry.pos, domain, model)
            if not value:
                pending.append(entry)
        # Small groups permit cancellation and preserve all-or-nothing DB updates.
        rows: list[tuple[str, str, str]] = []
        for start in range(0, len(pending), 8):
            if cancelled():
                raise CancelledError("Операция отменена; текущая группа завершена.")
            batch = pending[start : start + 8]
            progress(f"Словарь: {start}/{len(pending)} новых эквивалентов")
            values = self.translator.translate([e.lemma for e in batch])
            if len(values) != len(batch) or any(not v.strip() for v in values):
                raise ValueError("Некорректный ответ переводчика для словаря.")
            rows.extend((e.lemma, e.pos, value) for e, value in zip(batch, values, strict=True))
        if cancelled():
            raise CancelledError("Операция отменена.")
        self.lexicon.store_auto(rows, domain, model)
        return tuple(
            replace(e, translation=value, origin=origin)
            for e in entries
            for value, origin in [self.lexicon.get(e.lemma, e.pos, domain, model)]
        )

    def run(
        self,
        text: str,
        domain: str,
        progress: Callable[[str], None] = lambda _: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Result:
        if domain not in {"medicine", "art"}:
            raise ValueError("Выберите medicine или art.")
        if cancelled():
            raise CancelledError("Операция отменена.")
        progress("Загрузка моделей EN→FR…")
        start = perf_counter()
        versions = self.analyzer.prepare() | self.translator.prepare()
        timings = {"initialization": perf_counter() - start}
        start = perf_counter()
        analysis = self.analyzer.analyze(text)
        timings["analysis"] = perf_counter() - start
        translations = []
        start = perf_counter()
        for sentence in analysis.sentences:
            if cancelled():
                raise CancelledError("Операция отменена.")
            progress(f"Перевод предложения {sentence.index + 1}/{len(analysis.sentences)}")
            values = self.translator.translate([sentence.text])
            if len(values) != 1 or not values[0].strip():
                raise ValueError("Пустой перевод предложения.")
            translations.append(values[0])
        timings["translation"] = perf_counter() - start
        start = perf_counter()
        model = versions["model"] + "@" + versions["revision"]
        entries = self.populate(analysis, domain, model, progress, cancelled)
        timings["dictionary"] = perf_counter() - start
        paragraphs: dict[int, list[str]] = {}
        for sentence, translated in zip(analysis.sentences, translations, strict=True):
            paragraphs.setdefault(sentence.paragraph, []).append(translated)
        translation = "\n\n".join(" ".join(parts) for parts in paragraphs.values())
        source_words = sum(e.frequency for e in entries)
        import re

        target_words = len(re.findall(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", translation))
        return Result(
            analysis,
            tuple(translations),
            translation,
            entries,
            source_words,
            sum(e.frequency for e in entries if e.covered),
            target_words,
            timings,
            versions,
            (
                "Автоматические словарные эквиваленты получены изолированно, "
                "требуют проверки и не являются выравниванием полного перевода.",
                "Число переведённых слов — число исходных словоупотреблений с "
                "эквивалентом в словаре; совпавшие с исходником автопереводы требуют ручного подтверждения и не входят в покрытие. Это не оценка качества.",
                "Длинные предложения делятся по 384 токена модели; возможна потеря "
                "контекста на границе. Исходный текст не обрезается.",
            ),
        )


ROOT = Path(__file__).resolve().parent


def build_service(database=None):
    lexicon = SqliteLexicon(database or ROOT / "data/lexicon.sqlite3")
    return TranslationService(EnglishAnalyzer(), MarianTranslator(), lexicon), lexicon
