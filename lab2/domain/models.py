"""Контракты эксперимента, без зависимостей от GUI/PDF/ML."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

Language = Literal["en", "es"]
Split = Literal["train", "test"]
LANGUAGES: tuple[Language, ...] = ("en", "es")
LANGUAGE_NAMES = {"en": "Английский", "es": "Испанский", "?": "Не определён"}
METHOD_NAMES = {
    "short_words": "Короткие слова",
    "alphabet": "Алфавитный",
    "neural": "Нейросетевой",
}


class LabError(Exception):
    """Ожидаемая ошибка, которую можно показать пользователю."""


class Cancelled(LabError):
    pass


@dataclass(frozen=True)
class Settings:
    max_word_length: int = 5
    min_word_frequency: int = 4
    smoothing: float = 0.5
    seed: int = 36
    repetitions: int = 5
    neural_features: int = 3000
    neural_hidden: int = 32
    neural_iterations: int = 300
    chunk_words: int = 80

    def __post_init__(self) -> None:
        import math

        for name in (
            "max_word_length",
            "min_word_frequency",
            "repetitions",
            "neural_features",
            "neural_hidden",
            "neural_iterations",
            "chunk_words",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise LabError(f"{name}: требуется положительное целое число")
        if not math.isfinite(self.smoothing) or self.smoothing <= 0:
            raise LabError("Сглаживание должно быть конечным положительным числом")
        if not isinstance(self.seed, int) or not 0 <= self.seed < 2**32:
            raise LabError("Seed должен быть целым числом от 0 до 2**32 - 1")


@dataclass(frozen=True)
class CorpusEntry:
    path: Path
    split: Split
    language: Language | None
    source_id: str = ""
    source_url: str = ""
    title: str = ""

    def __post_init__(self) -> None:
        if self.split not in ("train", "test") or self.language not in (*LANGUAGES, None):
            raise LabError("Неверная роль документа или язык")
        if self.split == "train" and self.language is None:
            raise LabError("Для обучающего PDF нужно указать язык")


@dataclass(frozen=True)
class Document:
    entry: CorpusEntry
    text: str
    pages: int
    sha256: str
    warnings: tuple[str, ...] = ()

    @property
    def utf8_bytes(self) -> int:
        return len(self.text.encode("utf-8"))


@dataclass(frozen=True)
class Prediction:
    language: Language | None
    scores: dict[str, float]
    score_kind: str
    explanation: str


@dataclass(frozen=True)
class ResultRow:
    path: str
    title: str
    source_url: str
    expected: Language | None
    characters: int
    pages: int
    predictions: dict[str, Prediction]
    milliseconds: dict[str, float]
    warnings: tuple[str, ...]


class ClassMetrics(TypedDict):
    precision: float
    recall: float
    f1: float


class MethodMetrics(TypedDict):
    labeled: int
    correct: int
    accuracy: float | None
    macro_f1: float | None
    abstentions: int
    mean_ms: float
    confusion: dict[str, dict[str, int]]
    per_class: dict[str, ClassMetrics]


@dataclass(frozen=True)
class ExperimentReport:
    created_at: str
    settings: dict[str, object]
    training: tuple[dict[str, object], ...]
    training_bytes: dict[str, int]
    training_seconds: dict[str, float]
    parsing_seconds: float
    rows: tuple[ResultRow, ...]
    metrics: dict[str, MethodMetrics]
    profiles: dict[str, dict[str, object]]
    versions: dict[str, str]
    warnings: tuple[str, ...] = field(default_factory=tuple)
