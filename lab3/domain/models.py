"""Immutable input and output records shared by the application."""

from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("en", "es")
DOMAINS = ("medicine", "art")
METHODS = ("position", "textrank")
METHOD_LABELS = {"position": "TF-IDF + позиции", "textrank": "TextRank"}


@dataclass(frozen=True)
class Source:
    path: Path
    language: str
    domain: str
    title: str
    url: str = ""
    attribution: str = ""
    license: str = ""

    def __post_init__(self) -> None:
        if self.language not in LANGUAGES or self.domain not in DOMAINS:
            raise ValueError("Допустимы языки en/es и области medicine/art.")


@dataclass(frozen=True)
class Document:
    source: Source
    text: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Sentence:
    index: int
    text: str
    start: int
    end: int
    paragraph_start: int
    paragraph_end: int
    terms: tuple[str, ...]
    word_count: int


@dataclass(frozen=True)
class Analyzed:
    document: Document
    sentences: tuple[Sentence, ...]
    preprocessing_seconds: float


@dataclass(frozen=True)
class Ranking:
    scores: tuple[float, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Summary:
    method: str
    selected: tuple[int, ...]
    scores: tuple[float, ...]
    keywords: tuple[tuple[str, float], ...]
    ranking_seconds: float
    keyword_seconds: float
    sentence_ratio: float
    word_ratio: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DocumentResult:
    analyzed: Analyzed
    summaries: tuple[Summary, ...]
    agreement: float


@dataclass(frozen=True)
class Experiment:
    documents: tuple[DocumentResult, ...]
    requested_sentences: int
    requested_keywords: int
    initialization_seconds: float
    idf_seconds: float
    versions: dict[str, str]
    warnings: tuple[str, ...]
