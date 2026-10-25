"""Общий сценарий GUI/CLI: чтение, контроль корпуса, обучение, сравнение."""

from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from statistics import median
from time import perf_counter

from lab2.domain.metrics import evaluate
from lab2.domain.models import (
    LANGUAGES,
    Cancelled,
    CorpusEntry,
    Document,
    ExperimentReport,
    LabError,
    ResultRow,
    Settings,
)

from .ports import Classifier, DocumentReader


def validate_corpus(documents: Sequence[Document]) -> list[str]:
    train = [d for d in documents if d.entry.split == "train"]
    test = [d for d in documents if d.entry.split == "test"]
    if not test or {d.entry.language for d in train} != set(LANGUAGES):
        raise LabError("Нужны обучающие PDF EN и ES и хотя бы один тестовый PDF.")
    seen: set[str] = set()
    for document in documents:
        if document.sha256 in seen:
            raise LabError(f"Повтор текста: {document.entry.path.name}. Удалите дубликат.")
        seen.add(document.sha256)
    train_sources = {d.entry.source_id for d in train if d.entry.source_id}
    test_sources = {d.entry.source_id for d in test if d.entry.source_id}
    if train_sources & test_sources:
        raise LabError("Один источник попал в train и test. Разделите корпус по произведениям.")
    notes = []
    for lang in LANGUAGES:
        size = sum(d.utf8_bytes for d in train if d.entry.language == lang)
        if not 20 * 1024 <= size <= 120 * 1024:
            notes.append(
                f"Обучение {lang}: {size} UTF-8 байт; методичка: 20–120 KiB. "
                "Для сдачи используйте корпус в этом диапазоне."
            )
    sizes = [len(d.text) for d in test]
    if max(sizes) > 1.5 * min(sizes):
        notes.append(
            "Тестовые тексты различаются по длине более чем в 1.5 раза; "
            "сравнение времени может быть некорректным."
        )
    if any(not d.entry.source_id for d in documents):
        notes.append(
            "Не у всех файлов указан source_id: проверены дубликаты текста, "
            "но независимость исходных произведений должна быть проверена вручную."
        )
    if any(d.entry.language is None for d in test):
        notes.append("Неразмеченные тестовые документы не входят в accuracy и F1.")
    return notes


class Experiment:
    def __init__(
        self,
        reader: DocumentReader,
        classifiers: Sequence[Classifier],
        settings: Settings,
        versions: dict[str, str],
    ) -> None:
        self.reader = reader
        self.classifiers = classifiers
        self.settings = settings
        self.versions = versions

    def run(
        self,
        entries: Sequence[CorpusEntry],
        progress: Callable[[str], None] = lambda _: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> ExperimentReport:
        def checkpoint(message: str) -> None:
            if cancelled():
                raise Cancelled("Операция отменена")
            progress(message)

        documents = []
        started = perf_counter()
        for index, entry in enumerate(entries):
            checkpoint(f"Чтение PDF {index + 1}/{len(entries)}: {entry.path.name}")
            documents.append(self.reader.read(entry))
        parsing = perf_counter() - started
        notes = validate_corpus(documents)
        train = [d for d in documents if d.entry.split == "train"]
        test = [d for d in documents if d.entry.split == "test"]
        training_seconds = {}
        for model in self.classifiers:
            checkpoint(f"Обучение: {model.name}")
            started = perf_counter()
            model.fit(train)
            training_seconds[model.name] = perf_counter() - started
        rows = []
        for index, document in enumerate(test):
            predictions, milliseconds = {}, {}
            for model in self.classifiers:
                checkpoint(f"Распознавание {index + 1}/{len(test)}: {model.name}")
                # Прогрев отдельно от измерения; затем одинаковое число повторов для всех методов.
                prediction = model.predict(document.text)
                timings = []
                for _ in range(self.settings.repetitions):
                    if cancelled():
                        raise Cancelled("Операция отменена")
                    started = perf_counter()
                    model.predict(document.text)
                    timings.append((perf_counter() - started) * 1000)
                predictions[model.name] = prediction
                milliseconds[model.name] = median(timings)
            rows.append(
                ResultRow(
                    str(document.entry.path.resolve()),
                    document.entry.title or document.entry.path.stem,
                    document.entry.source_url,
                    document.entry.language,
                    len(document.text),
                    document.pages,
                    predictions,
                    milliseconds,
                    document.warnings,
                )
            )
        profiles = {model.name: model.describe() for model in self.classifiers}
        neural_warnings = profiles.get("neural", {}).get("warnings", [])
        if isinstance(neural_warnings, list):
            for warning in neural_warnings:
                notes.append(f"Neural convergence: {warning}")
        checkpoint("Готово")
        return ExperimentReport(
            created_at=datetime.now(UTC).isoformat(),
            settings=asdict(self.settings),
            training=tuple(
                {
                    "path": str(d.entry.path.resolve()),
                    "language": d.entry.language,
                    "source_id": d.entry.source_id,
                    "source_url": d.entry.source_url,
                    "sha256": d.sha256,
                    "utf8_bytes": d.utf8_bytes,
                    "pages": d.pages,
                    "warnings": list(d.warnings),
                }
                for d in train
            ),
            training_bytes={
                lang: sum(d.utf8_bytes for d in train if d.entry.language == lang)
                for lang in LANGUAGES
            },
            training_seconds=training_seconds,
            parsing_seconds=parsing,
            rows=tuple(rows),
            metrics=evaluate(rows),
            profiles=profiles,
            versions=self.versions,
            warnings=tuple(notes),
        )
