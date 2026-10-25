"""Временная сборка для интеграционных тестов; без сетевых запросов."""

from lab1.ir_system.application.services import CollectionService
from lab1.ir_system.config import AppConfig
from lab1.ir_system.domain.text import EnglishAnalyzer
from lab1.ir_system.infrastructure.fixtures import JsonCollectionSource
from lab1.ir_system.infrastructure.sqlite import SQLiteRepository
from lab1.ir_system.infrastructure.web import HttpDocumentFetcher


def collection_service(
    repository: SQLiteRepository, source=None, judgments=None
) -> CollectionService:
    return CollectionService(
        repository,
        repository,
        repository,
        HttpDocumentFetcher(),
        source if source is not None else JsonCollectionSource(AppConfig().fixture),
        judgments if judgments is not None else repository,
        EnglishAnalyzer(),
        lambda: "2026-10-07T00:00:00+00:00",
    )
