"""Composition root: единственное место сборки конкретных зависимостей."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from lab1.ir_system.application.services import (
    CollectionService,
    EvaluationService,
    JudgmentService,
    ReportService,
    SearchService,
    Services,
)
from lab1.ir_system.config import AppConfig
from lab1.ir_system.domain.ranking import BM25Ranker
from lab1.ir_system.domain.text import EnglishAnalyzer
from lab1.ir_system.infrastructure.fixtures import JsonCollectionSource
from lab1.ir_system.infrastructure.reporting.exporter import FileReportExporter
from lab1.ir_system.infrastructure.sqlite import SQLiteRepository
from lab1.ir_system.infrastructure.web import HttpDocumentFetcher


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def application_runtime(config: AppConfig) -> Iterator[Services]:
    repository = SQLiteRepository(config.database)
    try:
        analyzer = EnglishAnalyzer()
        ranker = BM25Ranker(config.bm25)
        fetcher = HttpDocumentFetcher(config.http_timeout, config.max_page_bytes)
        source = JsonCollectionSource(config.fixture)
        yield Services(
            collection=CollectionService(
                repository, repository, repository, fetcher, source, repository, analyzer, utc_now
            ),
            search=SearchService(repository, ranker, analyzer),
            judgments=JudgmentService(repository, repository, repository),
            evaluation=EvaluationService(repository, repository, repository, ranker, analyzer),
            reports=ReportService(FileReportExporter()),
        )
    finally:
        repository.close()
