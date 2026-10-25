"""One preprocessing pass and one language-specific IDF for both rankers."""

import platform
from collections.abc import Callable, Sequence
from importlib.metadata import version
from time import perf_counter

from lab3.application.ports import Analyzer
from lab3.domain.models import Document, DocumentResult, Experiment, Summary
from lab3.domain.ranking import CorpusStatistics, Ranker, keywords, select


class CancelledError(Exception):
    pass


class Summarizer:
    def __init__(self, analyzer: Analyzer, rankers: Sequence[Ranker]) -> None:
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
