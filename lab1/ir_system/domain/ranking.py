"""Чистые BM25 и TF-IDF: без репозитория, HTTP и интерфейса."""

import math

from .models import BM25Parameters, CorpusSnapshot, Keyword, SearchResult
from .text import validate_positive_integer


class BM25Ranker:
    def __init__(self, parameters: BM25Parameters | None = None) -> None:
        self.parameters = parameters if parameters is not None else BM25Parameters()

    def rank(
        self, snapshot: CorpusSnapshot, terms: tuple[str, ...], limit: int | None = None
    ) -> tuple[SearchResult, ...]:
        if limit is not None:
            validate_positive_integer(limit, "Лимит")
        if not terms or not snapshot.documents:
            return ()
        n = len(snapshot.documents)
        scores: dict[int, float] = {}
        matched: dict[int, list[str]] = {}
        k1, b = self.parameters.k1, self.parameters.b
        for term in dict.fromkeys(terms):
            postings = snapshot.postings.get(term, {})
            df = len(postings)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for document_id, tf in postings.items():
                length = snapshot.by_id[document_id].length
                denominator = tf + k1 * (1 - b + b * length / snapshot.average_length)
                scores[document_id] = (
                    scores.get(document_id, 0.0) + idf * tf * (k1 + 1) / denominator
                )
                matched.setdefault(document_id, []).append(term)
        results = sorted(
            (
                SearchResult(snapshot.by_id[d], score, tuple(matched[d]))
                for d, score in scores.items()
            ),
            key=lambda result: (-result.score, result.document.id),
        )
        return tuple(results if limit is None else results[:limit])


def extract_keywords(
    snapshot: CorpusSnapshot, document_id: int, limit: int = 10
) -> tuple[Keyword, ...]:
    validate_positive_integer(limit, "Лимит")
    n = len(snapshot.documents)
    weighted = [
        Keyword(term, postings[document_id] * math.log(n / len(postings)))
        for term, postings in snapshot.postings.items()
        if document_id in postings
    ]
    return tuple(sorted(weighted, key=lambda item: (-item.weight, item.term))[:limit])
