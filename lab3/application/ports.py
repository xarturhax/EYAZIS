from typing import Protocol

from lab3.domain.models import Analyzed, Document


class Analyzer(Protocol):
    def prepare(self, languages: set[str]) -> dict[str, str]: ...
    def analyze(self, document: Document) -> Analyzed: ...
