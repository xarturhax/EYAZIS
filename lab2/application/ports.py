from collections.abc import Sequence
from typing import Protocol

from lab2.domain.models import CorpusEntry, Document, Prediction


class DocumentReader(Protocol):
    def read(self, entry: CorpusEntry) -> Document: ...


class Classifier(Protocol):
    name: str

    def fit(self, documents: Sequence[Document]) -> None: ...
    def predict(self, text: str) -> Prediction: ...
    def describe(self) -> dict[str, object]: ...
