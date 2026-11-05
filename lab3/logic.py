from __future__ import annotations

import math
import platform
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from itertools import combinations
from pathlib import Path
from time import perf_counter
from typing import Any

LANGUAGES = ("en", "es")
DOMAINS = ("medicine", "art")
METHODS = ("position", "textrank")
METHOD_LABELS = {"position": "TF-IDF + позиции", "textrank": "TextRank"}


@dataclass(frozen=True)
class Source:
    path: Path
    language: str
    domain: str
    title: str
    url: str = ""
    attribution: str = ""
    license: str = ""

    def __post_init__(self) -> None:
        if self.language not in LANGUAGES or self.domain not in DOMAINS:
            raise ValueError("Допустимы языки en/es и области medicine/art.")


@dataclass(frozen=True)
class Document:
    source: Source
    text: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Sentence:
    index: int
    text: str
    start: int
    end: int
    paragraph_start: int
    paragraph_end: int
    terms: tuple[str, ...]
    word_count: int


@dataclass(frozen=True)
class Analyzed:
    document: Document
    sentences: tuple[Sentence, ...]
    preprocessing_seconds: float


@dataclass(frozen=True)
class Ranking:
    scores: tuple[float, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Summary:
    method: str
    selected: tuple[int, ...]
    scores: tuple[float, ...]
    keywords: tuple[tuple[str, float], ...]
    ranking_seconds: float
    keyword_seconds: float
    sentence_ratio: float
    word_ratio: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DocumentResult:
    analyzed: Analyzed
    summaries: tuple[Summary, ...]
    agreement: float


@dataclass(frozen=True)
class Experiment:
    documents: tuple[DocumentResult, ...]
    requested_sentences: int
    requested_keywords: int
    initialization_seconds: float
    idf_seconds: float
    versions: dict[str, str]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CorpusStatistics:
    count: int
    document_frequency: dict[str, int]

    @classmethod
    def build(cls, documents: Iterable[Analyzed]) -> CorpusStatistics:
        frequency: Counter[str] = Counter()
        count = 0
        for document in documents:
            count += 1
            frequency.update({t for s in document.sentences for t in s.terms})
        if not count:
            raise ValueError("Пустой корпус IDF.")
        return cls(count, dict(frequency))

    def weights(self, document: Analyzed) -> dict[str, float]:
        frequencies = Counter(t for s in document.sentences for t in s.terms)
        maximum = max(frequencies.values(), default=1)
        # The summarized document MUST belong to this language's IDF collection.
        if any(t not in self.document_frequency for t in frequencies):
            raise ValueError("Документ не входит в корпус IDF.")
        return {
            term: 0.5 * (1 + count / maximum) * math.log(self.count / self.document_frequency[term])
            for term, count in frequencies.items()
        }


def position(sentence: Sentence, length: int) -> float:
    return (1 - sentence.start / length) * (
        1
        - (sentence.start - sentence.paragraph_start)
        / (sentence.paragraph_end - sentence.paragraph_start)
    )


class PositionalRanker:
    name = "position"

    def prepare(self) -> None:
        pass

    def rank(self, document: Analyzed, weights: dict[str, float]) -> Ranking:
        scores = tuple(
            sum(weights[t] for t in sentence.terms)
            * position(sentence, len(document.document.text))
            for sentence in document.sentences
        )
        warnings: tuple[str, ...] = ()
        if scores and not any(scores):
            warnings = ("Все веса TF-IDF равны нулю: выбраны первые предложения по порядку.",)
        return Ranking(scores, warnings)


def select(scores: tuple[float, ...], limit: int) -> tuple[int, ...]:
    if limit < 1:
        raise ValueError("Число предложений должно быть положительным.")
    return tuple(sorted(sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:limit]))


def keywords(weights: dict[str, float], limit: int) -> tuple[tuple[str, float], ...]:
    if limit < 1:
        raise ValueError("Число ключевых слов должно быть положительным.")
    return tuple(
        sorted(
            ((term, weight) for term, weight in weights.items() if weight > 0),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
    )


def similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    if not left or not right:
        return 0.0
    denominator = math.log(len(left)) + math.log(len(right))
    # For two single-term sentences the original denominator is zero.
    if denominator == 0:
        return float(left[0] == right[0])
    return len(set(left) & set(right)) / denominator


class TextRank:
    name = "textrank"

    def __init__(self) -> None:
        self.prepared = False

    def prepare(self) -> None:
        if not self.prepared:
            import networkx as nx

            # Load PageRank's numerical dependencies before document timing.
            nx.pagerank(nx.path_graph(2), alpha=0.85)
            self.prepared = True

    def rank(self, document: Analyzed, weights: dict[str, float]) -> Ranking:
        import networkx as nx

        sentences = document.sentences
        graph = nx.Graph()
        graph.add_nodes_from(range(len(sentences)))
        for i, j in combinations(range(len(sentences)), 2):
            weight = similarity(sentences[i].terms, sentences[j].terms)
            if weight > 0:
                graph.add_edge(i, j, weight=weight)
        if not graph.number_of_edges():
            return Ranking(
                tuple(position(s, len(document.document.text)) for s in sentences),
                ("У графа нет рёбер: применено ранжирование по позиции.",),
            )
        try:
            values = nx.pagerank(graph, alpha=0.85, max_iter=200, tol=1e-8, weight="weight")
        except nx.PowerIterationFailedConvergence as error:
            raise ValueError("TextRank не сошёлся за 200 итераций.") from error
        return Ranking(tuple(float(values[i]) for i in range(len(sentences))))


MODELS = {"en": "en_core_web_sm", "es": "es_core_news_sm"}


class SpacyAnalyzer:
    def __init__(self) -> None:
        self.models: dict[str, Any] = {}

    def prepare(self, languages: set[str]) -> dict[str, str]:
        import spacy

        versions = {"spacy": spacy.__version__}
        for language in sorted(languages):
            name = MODELS[language]
            if language not in self.models:
                try:
                    self.models[language] = spacy.load(name, disable=["ner"])
                except OSError as error:
                    raise ValueError(
                        f"Не установлена модель {name}. Установите зависимости из requirements.txt в корне проекта."
                    ) from error
            versions[name] = self.models[language].meta["version"]
        return versions

    def analyze(self, document: Document) -> Analyzed:
        started = perf_counter()
        model = self.models[document.source.language]
        sentences: list[Sentence] = []
        # Blank lines delimit paragraphs; a lone line break is not a paragraph boundary.
        paragraphs = list(re.finditer(r"\S(?:[^\n]|\n(?![ \t]*\n))*", document.text))
        for match, parsed in zip(
            paragraphs,
            model.pipe((m.group().rstrip() for m in paragraphs), batch_size=16),
            strict=True,
        ):
            paragraph_end = match.start() + len(parsed.text)
            for span in parsed.sents:
                raw = span.text
                left = len(raw) - len(raw.lstrip())
                right = len(raw.rstrip())
                if left == right:
                    continue
                start = match.start() + span.start_char + left
                end = match.start() + span.start_char + right
                terms = tuple(
                    token.lemma_.casefold()
                    for token in span
                    if token.is_alpha and not token.is_stop and token.lemma_.isalpha()
                )
                sentences.append(
                    Sentence(
                        len(sentences),
                        document.text[start:end],
                        start,
                        end,
                        match.start(),
                        paragraph_end,
                        terms,
                        sum(token.is_alpha for token in span),
                    )
                )
                if len(sentences) > 1500:
                    raise ValueError("Слишком много предложений (максимум 1500 для TextRank).")
        if not sentences:
            raise ValueError("Не удалось выделить предложения.")
        return Analyzed(document, tuple(sentences), perf_counter() - started)


class CancelledError(Exception):
    pass


class Summarizer:
    def __init__(self, analyzer: Any, rankers: Sequence[Any]) -> None:
        if len(rankers) != 2 or len({r.name for r in rankers}) != 2:
            raise ValueError("Comparison requires two distinct rankers.")
        self.analyzer = analyzer
        self.rankers = rankers

    def run(
        self,
        documents: Sequence[Document],
        sentences: int = 10,
        keyword_count: int = 10,
        progress: Callable[[str], None] = lambda _: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Experiment:
        if not documents:
            raise ValueError("Добавьте документы.")
        if not 1 <= sentences <= 100 or not 1 <= keyword_count <= 100:
            raise ValueError("Число предложений и ключевых слов: от 1 до 100.")

        def checkpoint(message: str) -> None:
            if cancelled():
                raise CancelledError("Выполнение отменено.")
            progress(message)

        checkpoint("Загрузка языковых моделей…")
        started = perf_counter()
        versions = self.analyzer.prepare({d.source.language for d in documents})
        for ranker in self.rankers:
            ranker.prepare()
        initialization_seconds = perf_counter() - started
        versions.update({name: version(name) for name in ("networkx", "numpy", "scipy", "pymupdf")})
        versions["python"] = platform.python_version()
        analyzed = []
        for i, original in enumerate(documents):
            checkpoint(f"Предобработка {i + 1}/{len(documents)}: {original.source.title}")
            analyzed.append(self.analyzer.analyze(original))
        checkpoint("Вычисление IDF отдельно для каждого языка…")
        started = perf_counter()
        statistics = {
            language: CorpusStatistics.build(
                d for d in analyzed if d.document.source.language == language
            )
            for language in {d.source.language for d in documents}
        }
        idf_seconds = perf_counter() - started
        warnings = []
        for language, stats in sorted(statistics.items()):
            if stats.count < 3:
                warnings.append(
                    f"{language}: всего {stats.count} документов в корпусе IDF. "
                    "Для устойчивой оценки добавьте документы обеих областей."
                )
        lengths = [len(d.text) for d in documents]
        if max(lengths) > 1.25 * min(lengths):
            warnings.append("Размеры документов различаются более чем на 25%.")
        results = []
        for document in analyzed:
            started = perf_counter()
            weights = statistics[document.document.source.language].weights(document)
            words = keywords(weights, keyword_count)
            keyword_seconds = perf_counter() - started
            summaries = []
            for ranker in self.rankers:
                checkpoint(f"{ranker.name}: {document.document.source.title}")
                started = perf_counter()
                ranking = ranker.rank(document, weights)
                selected = select(ranking.scores, sentences)
                ranking_seconds = perf_counter() - started
                total_words = sum(s.word_count for s in document.sentences)
                notes = list(document.document.warnings + ranking.warnings)
                if not words:
                    notes.append("Нет ключевых слов с положительным IDF; расширьте корпус.")
                if len(selected) < sentences:
                    notes.append("Предложений меньше заданного размера: включены все.")
                summaries.append(
                    Summary(
                        ranker.name,
                        selected,
                        ranking.scores,
                        words,
                        ranking_seconds,
                        keyword_seconds,
                        len(selected) / len(document.sentences),
                        sum(document.sentences[i].word_count for i in selected)
                        / max(total_words, 1),
                        tuple(notes),
                    )
                )
            first, second = (set(s.selected) for s in summaries)
            agreement = len(first & second) / max(len(first | second), 1)
            results.append(DocumentResult(document, tuple(summaries), agreement))
        checkpoint("Готово.")
        return Experiment(
            tuple(results),
            sentences,
            keyword_count,
            initialization_seconds,
            idf_seconds,
            versions,
            tuple(warnings),
        )


ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "data/demo/manifest.json"


def build_summarizer():
    return Summarizer(SpacyAnalyzer(), [PositionalRanker(), TextRank()])
