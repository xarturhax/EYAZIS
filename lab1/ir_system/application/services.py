"""Общие для CLI и GUI сценарии; управление предметными правилами и транзакциями."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from lab1.ir_system.domain.errors import NotFoundError, ValidationError
from lab1.ir_system.domain.metrics import average_metrics, evaluate_ranking
from lab1.ir_system.domain.models import (
    Document,
    DocumentDraft,
    EvaluationReport,
    ExcludedQuery,
    ImportResult,
    IndexedDocument,
    Keyword,
    QueryEvaluation,
    SearchResult,
)
from lab1.ir_system.domain.ranking import BM25Ranker, extract_keywords
from lab1.ir_system.domain.text import (
    EnglishAnalyzer,
    normalize_query,
    validate_grade,
    validate_positive_integer,
)

from .ports import (
    CollectionSource,
    DocumentFetcher,
    DocumentReader,
    DocumentWriter,
    JudgmentStore,
    ReportExporter,
    TransactionManager,
)


class CollectionService:
    def __init__(
        self,
        reader: DocumentReader,
        writer: DocumentWriter,
        transactions: TransactionManager,
        fetcher: DocumentFetcher,
        source: CollectionSource,
        judgments: JudgmentStore,
        analyzer: EnglishAnalyzer,
        clock: Callable[[], str],
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._transactions = transactions
        self._fetcher = fetcher
        self._source = source
        self._judgments = judgments
        self._analyzer = analyzer
        self._clock = clock

    def documents(self) -> tuple[Document, ...]:
        return self._reader.documents()

    def get_document(self, document_id: int) -> Document:
        return self._reader.get_document(document_id)

    def fetch(self, url: str) -> DocumentDraft:
        """Сетевой этап; не обращается к хранилищу, допустим в GUI-worker."""
        return self._fetcher.fetch(url)

    def add(self, draft: DocumentDraft) -> int:
        indexed = self._index(draft)
        with self._transactions.transaction():
            return self._writer.save_document(indexed)

    def delete_many(self, document_ids: Sequence[int]) -> None:
        with self._transactions.transaction():
            for document_id in dict.fromkeys(document_ids):
                self._reader.get_document(document_id)
                self._writer.delete_document(document_id)

    def import_demo(self) -> ImportResult:
        collection = self._source.load()
        indexed = [(item.key, self._index(item.draft)) for item in collection.documents]
        keys = [key for key, _ in indexed]
        if len(set(keys)) != len(keys):
            raise ValidationError("Демо содержит повторяющиеся ключи документов")
        urls = [item.draft.url for _, item in indexed]
        if len(set(urls)) != len(urls):
            raise ValidationError("Демо содержит повторяющиеся URL")
        normalized_queries = []
        for query in collection.queries:
            normalized_queries.append(normalize_query(query.text))
            if query.grades.keys() - set(keys):
                raise ValidationError("В разметке демо указан неизвестный документ")
            for grade in query.grades.values():
                validate_grade(grade)
        if not keys or not normalized_queries:
            raise ValidationError("Демо должно содержать документы и запросы")
        if len(set(normalized_queries)) != len(normalized_queries):
            raise ValidationError("Демо содержит повторяющиеся запросы")
        with self._transactions.transaction():
            ids = {key: self._writer.save_document(item) for key, item in indexed}
            for query, text in zip(collection.queries, normalized_queries, strict=True):
                for key, document_id in ids.items():
                    self._judgments.save_judgment(text, document_id, query.grades.get(key, 0))
        return ImportResult(tuple(ids.values()), tuple(normalized_queries))

    def _index(self, draft: DocumentDraft) -> IndexedDocument:
        return IndexedDocument(
            draft, self._analyzer.frequencies(draft.title + " " + draft.text), self._clock()
        )


class SearchService:
    def __init__(
        self, reader: DocumentReader, ranker: BM25Ranker, analyzer: EnglishAnalyzer
    ) -> None:
        self._reader, self._ranker, self._analyzer = reader, ranker, analyzer

    def search(self, query: str, limit: int | None = None) -> tuple[SearchResult, ...]:
        if limit is not None:
            validate_positive_integer(limit, "Лимит")
        terms = self._analyzer.query_terms(query)
        if not terms:
            return ()
        return self._ranker.rank(self._reader.snapshot(), terms, limit)

    def keywords(self, document_id: int, limit: int = 10) -> tuple[Keyword, ...]:
        snapshot = self._reader.snapshot()
        if document_id not in snapshot.by_id:
            raise NotFoundError(f"Документ #{document_id} не найден")
        return extract_keywords(snapshot, document_id, limit)


class JudgmentService:
    def __init__(
        self, reader: DocumentReader, store: JudgmentStore, transactions: TransactionManager
    ) -> None:
        self._reader, self._store, self._transactions = reader, store, transactions

    def queries(self) -> tuple[str, ...]:
        return self._store.queries()

    def judgments(self, query: str) -> dict[int, int]:
        return self._store.judgments(normalize_query(query))

    def grade_many(self, query: str, document_ids: Sequence[int], grade: int) -> None:
        text = normalize_query(query)
        validate_grade(grade)
        ids = tuple(dict.fromkeys(document_ids))
        if not ids:
            return
        with self._transactions.transaction():
            for document_id in ids:
                self._reader.get_document(document_id)
            for document_id in ids:
                self._store.save_judgment(text, document_id, grade)


class EvaluationService:
    def __init__(
        self,
        reader: DocumentReader,
        judgments: JudgmentStore,
        transactions: TransactionManager,
        ranker: BM25Ranker,
        analyzer: EnglishAnalyzer,
    ) -> None:
        self._reader, self._judgments, self._transactions = reader, judgments, transactions
        self._ranker, self._analyzer = ranker, analyzer

    def evaluate(self, queries: Sequence[str]) -> EvaluationReport:
        texts = tuple(dict.fromkeys(normalize_query(query) for query in queries))
        if not texts:
            raise ValidationError("Нет запросов для оценки")
        with self._transactions.transaction():
            snapshot = self._reader.snapshot()
            judgments = {query: self._judgments.judgments(query) for query in texts}
        if not snapshot.documents:
            raise ValidationError("Коллекция пуста")
        ids = set(snapshot.by_id)
        rows = []
        excluded = []
        for query in texts:
            grades = judgments[query]
            missing = ids - grades.keys()
            if missing:
                raise ValidationError(
                    f"Запрос «{query}»: оцените ещё {len(missing)} документов из полной коллекции"
                )
            corpus_grades = {d: grades[d] for d in ids}
            for grade in corpus_grades.values():
                validate_grade(grade)
            if not any(corpus_grades.values()):
                excluded.append(
                    ExcludedQuery(query, "В коллекции нет релевантных документов (R=0)")
                )
                continue
            results = self._ranker.rank(snapshot, self._analyzer.query_terms(query))
            ranking = tuple(result.document.id for result in results)
            evaluation = evaluate_ranking(ranking, corpus_grades)
            rows.append(QueryEvaluation(query, ranking, evaluation))
        evaluations = [row.evaluation for row in rows]
        if not evaluations:
            raise ValidationError(
                "Все выбранные запросы исключены: в коллекции нет релевантных документов. "
                "По РОМИП они не участвуют в расчёте метрик."
            )
        return EvaluationReport(
            document_count=len(snapshot.documents),
            parameters=self._ranker.parameters,
            rows=tuple(rows),
            excluded_queries=tuple(excluded),
            averages=average_metrics(evaluations),
            mean_interpolated=tuple(
                mean(item.interpolated[i] for item in evaluations) for i in range(11)
            ),
        )


class ReportService:
    def __init__(self, exporter: ReportExporter) -> None:
        self._exporter = exporter

    def export(self, report: EvaluationReport, directory: str | Path) -> Path:
        return self._exporter.export(report, Path(directory))


@dataclass(frozen=True)
class Services:
    collection: CollectionService
    search: SearchService
    judgments: JudgmentService
    evaluation: EvaluationService
    reports: ReportService
