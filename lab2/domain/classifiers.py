"""Объяснимые языковые профили. Меньшая оценка означает лучшее совпадение."""

import math
from collections import Counter
from collections.abc import Sequence

from .models import LANGUAGES, Document, LabError, Language, Prediction, Settings
from .text import ALPHABET, input_problem, letter_counts, words


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
