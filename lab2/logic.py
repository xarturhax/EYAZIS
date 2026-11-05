from __future__ import annotations

import math
import platform
import re
import unicodedata
import warnings
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any, Literal, TypedDict

from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from threadpoolctl import threadpool_limits

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


WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
ALPHABET = "abcdefghijklmnopqrstuvwxyzáéíóúüñ"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-[ \t]*\n[ \t]*(?=\w)", "", text)
    return " ".join(text.split())


def words(text: str) -> list[str]:
    return WORD_RE.findall(unicodedata.normalize("NFC", text).casefold().replace("’", "'"))


def letter_counts(text: str) -> Counter[str]:
    return Counter(c for c in unicodedata.normalize("NFC", text).casefold() if c in ALPHABET)


def input_problem(text: str) -> str | None:
    letters = [c for c in unicodedata.normalize("NFC", text).casefold() if c.isalpha()]
    if len(letters) < 10:
        return "Слишком мало букв: требуется не менее 10."
    if sum(c not in ALPHABET for c in letters) / len(letters) > 0.2:
        return "Более 20% букв вне поддерживаемых алфавитов EN/ES."
    return None


def unknown(reason: str) -> Prediction:
    return Prediction(None, {}, "нет оценки", reason)


def choose(scores: dict[str, float], kind: str, explanation: str) -> Prediction:
    ordered = sorted(LANGUAGES, key=lambda language: scores[language])
    if math.isclose(scores[ordered[0]], scores[ordered[1]], rel_tol=1e-10, abs_tol=1e-12):
        return Prediction(None, scores, kind, "Профили дают одинаковую оценку. " + explanation)
    return Prediction(ordered[0], scores, kind, explanation)


class ShortWordClassifier:
    name = "short_words"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.profiles: dict[Language, Counter[str]] = {}
        self.vocabulary: set[str] = set()

    def fit(self, documents: Sequence[Document]) -> None:
        self.profiles = {}
        for language in LANGUAGES:
            counts: Counter[str] = Counter()
            for document in documents:
                if document.entry.language == language:
                    counts.update(
                        w for w in words(document.text) if len(w) <= self.settings.max_word_length
                    )
            counts = Counter(
                {w: n for w, n in counts.items() if n >= self.settings.min_word_frequency}
            )
            if not counts:
                raise LabError(f"Нет частых коротких слов для {language}; увеличьте корпус.")
            self.profiles[language] = counts
        self.vocabulary = set().union(*self.profiles.values())

    def predict(self, text: str) -> Prediction:
        if not self.profiles:
            raise LabError("Сначала обучите классификатор")
        if problem := input_problem(text):
            return unknown(problem)
        tokens = [w for w in words(text) if len(w) <= self.settings.max_word_length]
        known = sum(w in self.vocabulary for w in tokens)
        if not tokens or not known:
            return unknown("Нет коротких слов, известных обучающим профилям.")
        a = self.settings.smoothing
        scores: dict[str, float] = {}
        for language, counts in self.profiles.items():
            denominator = sum(counts.values()) + a * (len(self.vocabulary) + 1)
            scores[language] = -sum(math.log((counts[w] + a) / denominator) for w in tokens) / len(
                tokens
            )
        return choose(
            scores,
            "средняя отрицательная log-вероятность; меньше лучше",
            f"Коротких слов: {len(tokens)}; известных: {known}. "
            "Сглаживание учитывает неизвестные слова; оценки не являются уверенностью.",
        )

    def describe(self) -> dict[str, object]:
        return {
            "vocabulary_size": len(self.vocabulary),
            "profiles": {
                language: dict(counts.most_common()) for language, counts in self.profiles.items()
            },
            "formula": "-mean(log((count(w,L)+alpha)/(N_L+alpha*(|V|+1))))",
        }


class AlphabetClassifier:
    """Статистический алфавитный метод: частоты одиночных букв и L1-расстояние."""

    name = "alphabet"

    def __init__(self, settings: Settings) -> None:
        self.profiles: dict[Language, dict[str, float]] = {}

    def fit(self, documents: Sequence[Document]) -> None:
        self.profiles = {}
        for language in LANGUAGES:
            counts: Counter[str] = Counter()
            for document in documents:
                if document.entry.language == language:
                    counts.update(letter_counts(document.text))
            total = sum(counts.values())
            if not total:
                raise LabError(f"Нет букв в обучающем корпусе {language}")
            self.profiles[language] = {c: counts[c] / total for c in ALPHABET}

    def predict(self, text: str) -> Prediction:
        if not self.profiles:
            raise LabError("Сначала обучите классификатор")
        if problem := input_problem(text):
            return unknown(problem)
        counts = letter_counts(text)
        total = sum(counts.values())
        scores: dict[str, float] = {
            language: sum(abs(counts[c] / total - profile[c]) for c in ALPHABET)
            for language, profile in self.profiles.items()
        }
        return choose(
            scores,
            "L1-расстояние частот букв; меньше лучше",
            "Сравниваются частоты отдельных букв. Общая латиница не различает языки "
            "по одному только наличию букв; короткие тексты ненадёжны.",
        )

    def describe(self) -> dict[str, object]:
        return {
            "alphabet": ALPHABET,
            "profiles": self.profiles,
            "formula": "sum(abs(f_document(c)-f_language(c)))",
        }


def evaluate(rows: Sequence[ResultRow]) -> dict[str, MethodMetrics]:
    result: dict[str, MethodMetrics] = {}
    for method in METHOD_NAMES:
        labeled = [row for row in rows if row.expected is not None]
        matrix: dict[str, dict[str, int]] = {
            truth: {prediction: 0 for prediction in (*LANGUAGES, "?")} for truth in LANGUAGES
        }
        for row in labeled:
            matrix[str(row.expected)][row.predictions[method].language or "?"] += 1
        correct = sum(matrix[lang][lang] for lang in LANGUAGES)
        per_class: dict[str, ClassMetrics] = {}
        for lang in LANGUAGES:
            tp = matrix[lang][lang]
            predicted = sum(matrix[truth][lang] for truth in LANGUAGES)
            actual = sum(matrix[lang].values())
            precision = tp / predicted if predicted else 0.0
            recall = tp / actual if actual else 0.0
            per_class[lang] = {
                "precision": precision,
                "recall": recall,
                "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            }
        result[method] = {
            "labeled": len(labeled),
            "correct": correct,
            "accuracy": correct / len(labeled) if labeled else None,
            "macro_f1": mean(v["f1"] for v in per_class.values()) if labeled else None,
            "abstentions": sum(row.predictions[method].language is None for row in rows),
            "mean_ms": mean(row.milliseconds[method] for row in rows) if rows else 0.0,
            "confusion": matrix,
            "per_class": per_class,
        }
    return result


class NeuralClassifier:
    name = "neural"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            lowercase=True,
            max_features=settings.neural_features,
            sublinear_tf=True,
        )
        self.model = MLPClassifier(
            hidden_layer_sizes=(settings.neural_hidden,),
            solver="lbfgs",
            alpha=0.01,
            max_iter=settings.neural_iterations,
            random_state=settings.seed,
        )
        self.notes: list[str] = []
        self.samples = 0
        self.fitted = False

    def fit(self, documents: Sequence[Document]) -> None:
        self.fitted = False
        texts, labels = [], []
        for document in documents:
            tokens = words(document.text)
            for start in range(0, len(tokens), self.settings.chunk_words):
                chunk = tokens[start : start + self.settings.chunk_words]
                if len(chunk) >= 10:
                    texts.append(" ".join(chunk))
                    labels.append(document.entry.language)
        if len(set(labels)) != 2:
            raise LabError("Для нейросети нужны непустые документы обоих языков")
        features = self.vectorizer.fit_transform(texts)
        with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            self.model.fit(features, labels)
        self.notes = [str(item.message) for item in caught]
        self.samples = len(texts)
        self.fitted = True

    def predict(self, text: str) -> Prediction:
        if not self.fitted:
            raise LabError("Сначала обучите нейросеть")
        if problem := input_problem(text):
            return unknown(problem)
        features = self.vectorizer.transform([" ".join(words(text))])
        if features.nnz == 0:
            return unknown("Ни одного известного символьного признака.")
        with threadpool_limits(limits=1):
            probabilities = self.model.predict_proba(features)[0]
        scores = {
            str(language): float(p)
            for language, p in zip(self.model.classes_, probabilities, strict=True)
        }
        label = self.model.classes_[int(probabilities.argmax())]
        if abs(scores["en"] - scores["es"]) < 1e-10:
            label = None
        return Prediction(
            label,
            scores,
            "оценка MLP; больше лучше",
            "Вероятности модели не калиброваны. Выбор только между EN и ES; "
            "другие языки на латинице могут быть ошибочно отнесены к одному из них.",
        )

    def describe(self) -> dict[str, object]:
        return {
            "features": len(self.vectorizer.vocabulary_),
            "samples": self.samples,
            "hidden_layers": [self.settings.neural_hidden],
            "solver": "lbfgs",
            "iterations": int(self.model.n_iter_),
            "loss": float(self.model.loss_),
            "warnings": self.notes,
            "ngrams": [2, 4],
        }


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
        reader: Any,
        classifiers: Sequence[Any],
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


ROOT = Path(__file__).resolve().parent
DEMO_MANIFEST = ROOT / "data/demo/manifest.json"


def build_experiment(settings):
    from lab2.files import PdfDocumentReader

    versions = {name: version(name) for name in ("pypdf", "scikit-learn", "numpy", "scipy")}
    versions["python"] = platform.python_version()
    return Experiment(
        PdfDocumentReader(),
        [ShortWordClassifier(settings), AlphabetClassifier(settings), NeuralClassifier(settings)],
        settings,
        versions,
    )
