"""The handout's unsmoothed IDF and positional sentence extraction."""

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from lab3.domain.models import Analyzed, Ranking, Sentence


@dataclass(frozen=True)
class CorpusStatistics:
    count: int
    document_frequency: dict[str, int]

    @classmethod
    def build(cls, documents: Iterable[Analyzed]) -> "CorpusStatistics":
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


class Ranker(Protocol):
    name: str

    def prepare(self) -> None: ...

    def rank(self, document: Analyzed, weights: dict[str, float]) -> Ranking: ...


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
