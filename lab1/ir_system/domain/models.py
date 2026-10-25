"""Неизменяемые контракты данных между слоями."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .errors import ValidationError
from .text import normalize_url


@dataclass(frozen=True)
class DocumentDraft:
    url: str
    title: str
    text: str

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.text.strip():
            raise ValidationError("Заголовок и текст не должны быть пустыми")
        object.__setattr__(self, "url", normalize_url(self.url))


@dataclass(frozen=True)
class Document:
    id: int
    url: str
    title: str
    text: str
    added_at: str
    length: int


@dataclass(frozen=True)
class IndexedDocument:
    draft: DocumentDraft
    term_frequencies: Mapping[str, int]
    added_at: str

    def __post_init__(self) -> None:
        counts = dict(self.term_frequencies)
        if not counts or any(tf < 1 for tf in counts.values()):
            raise ValidationError("В документе нет английских поисковых терминов")
        object.__setattr__(self, "term_frequencies", MappingProxyType(counts))

    @property
    def length(self) -> int:
        return sum(self.term_frequencies.values())


@dataclass(frozen=True)
class CorpusSnapshot:
    documents: tuple[Document, ...]
    postings: Mapping[str, Mapping[int, int]]
    by_id: Mapping[int, Document] = field(init=False, repr=False)
    average_length: float = field(init=False)

    def __post_init__(self) -> None:
        by_id = {document.id: document for document in self.documents}
        object.__setattr__(self, "by_id", MappingProxyType(by_id))
        object.__setattr__(
            self,
            "postings",
            MappingProxyType(
                {term: MappingProxyType(dict(values)) for term, values in self.postings.items()}
            ),
        )
        average = (
            sum(d.length for d in self.documents) / len(self.documents) if self.documents else 0.0
        )
        object.__setattr__(self, "average_length", average)


@dataclass(frozen=True)
class BM25Parameters:
    k1: float = 1.5
    b: float = 0.75

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.k1)
            or self.k1 <= 0
            or not math.isfinite(self.b)
            or not 0 <= self.b <= 1
        ):
            raise ValidationError("Требуется k1 > 0 и 0 <= b <= 1")


@dataclass(frozen=True)
class SearchResult:
    document: Document
    score: float
    matched_words: tuple[str, ...]

    @property
    def snippet(self) -> str:
        return self.document.text[:300]


@dataclass(frozen=True)
class Keyword:
    term: str
    weight: float


@dataclass(frozen=True)
class PrecisionRecallPoint:
    rank: int
    precision: float
    recall: float


@dataclass(frozen=True)
class RetrievalCounts:
    retrieved: int
    relevant: int
    tp: int
    fp: int
    fn: int
    tn: int


@dataclass(frozen=True)
class MetricValues:
    precision: float
    recall: float
    average_precision: float
    precision_at_5: float
    precision_at_10: float
    r_precision: float


@dataclass(frozen=True)
class RankingEvaluation:
    counts: RetrievalCounts
    metrics: MetricValues
    curve: tuple[PrecisionRecallPoint, ...]
    interpolated: tuple[float, ...]


@dataclass(frozen=True)
class QueryEvaluation:
    query: str
    ranking: tuple[int, ...]
    evaluation: RankingEvaluation


@dataclass(frozen=True)
class ExcludedQuery:
    query: str
    reason: str


@dataclass(frozen=True)
class EvaluationReport:
    document_count: int
    parameters: BM25Parameters
    rows: tuple[QueryEvaluation, ...]
    excluded_queries: tuple[ExcludedQuery, ...]
    averages: MetricValues
    mean_interpolated: tuple[float, ...]


@dataclass(frozen=True)
class DemoDocument:
    key: str
    draft: DocumentDraft


@dataclass(frozen=True)
class DemoQuery:
    text: str
    grades: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "grades", MappingProxyType(dict(self.grades)))


@dataclass(frozen=True)
class DemoCollection:
    documents: tuple[DemoDocument, ...]
    queries: tuple[DemoQuery, ...]


@dataclass(frozen=True)
class ImportResult:
    document_ids: tuple[int, ...]
    queries: tuple[str, ...]
