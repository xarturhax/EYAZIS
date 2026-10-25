"""Структурные интерфейсы; реализации подключает composition root."""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from lab1.ir_system.domain.models import (
    CorpusSnapshot,
    DemoCollection,
    Document,
    DocumentDraft,
    EvaluationReport,
    IndexedDocument,
)


class DocumentReader(Protocol):
    def documents(self) -> tuple[Document, ...]: ...
    def get_document(self, document_id: int) -> Document: ...
    def snapshot(self) -> CorpusSnapshot: ...


class DocumentWriter(Protocol):
    def save_document(self, document: IndexedDocument) -> int: ...
    def delete_document(self, document_id: int) -> None: ...


class JudgmentStore(Protocol):
    def queries(self) -> tuple[str, ...]: ...
    def judgments(self, query: str) -> dict[int, int]: ...
    def save_judgment(self, query: str, document_id: int, grade: int) -> None: ...


class TransactionManager(Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...


class DocumentFetcher(Protocol):
    def fetch(self, url: str) -> DocumentDraft: ...


class CollectionSource(Protocol):
    def load(self) -> DemoCollection: ...


class ReportExporter(Protocol):
    def export(self, report: EvaluationReport, directory: Path) -> Path: ...
