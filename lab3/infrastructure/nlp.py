"""Language-specific models; paragraph boundaries and offsets remain explicit."""

import re
from time import perf_counter
from typing import Any

from lab3.domain.models import Analyzed, Document, Sentence

MODELS = {"en": "en_core_web_sm", "es": "es_core_news_sm"}


class SpacyAnalyzer:
    def __init__(self) -> None:
        self.models: dict[str, Any] = {}

    def prepare(self, languages: set[str]) -> dict[str, str]:
        import spacy

        versions = {"spacy": spacy.__version__}
        for language in sorted(languages):
            name = MODELS[language]
            if language not in self.models:
                try:
                    self.models[language] = spacy.load(name, disable=["ner"])
                except OSError as error:
                    raise ValueError(
                        f"Не установлена модель {name}. Установите lab3/requirements.txt."
                    ) from error
            versions[name] = self.models[language].meta["version"]
        return versions

    def analyze(self, document: Document) -> Analyzed:
        started = perf_counter()
        model = self.models[document.source.language]
        sentences: list[Sentence] = []
        # Blank lines delimit paragraphs; a lone line break is not a paragraph boundary.
        paragraphs = list(re.finditer(r"\S(?:[^\n]|\n(?![ \t]*\n))*", document.text))
        for match, parsed in zip(
            paragraphs,
            model.pipe((m.group().rstrip() for m in paragraphs), batch_size=16),
            strict=True,
        ):
            paragraph_end = match.start() + len(parsed.text)
            for span in parsed.sents:
                raw = span.text
                left = len(raw) - len(raw.lstrip())
                right = len(raw.rstrip())
                if left == right:
                    continue
                start = match.start() + span.start_char + left
                end = match.start() + span.start_char + right
                terms = tuple(
                    token.lemma_.casefold()
                    for token in span
                    if token.is_alpha and not token.is_stop and token.lemma_.isalpha()
                )
                sentences.append(
                    Sentence(
                        len(sentences),
                        document.text[start:end],
                        start,
                        end,
                        match.start(),
                        paragraph_end,
                        terms,
                        sum(token.is_alpha for token in span),
                    )
                )
                if len(sentences) > 1500:
                    raise ValueError("Слишком много предложений (максимум 1500 для TextRank).")
        if not sentences:
            raise ValueError("Не удалось выделить предложения.")
        return Analyzed(document, tuple(sentences), perf_counter() - started)
