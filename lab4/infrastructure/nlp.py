"""Spring token/tree representation adapted to typed immutable records."""

import re
from typing import Any

from lab4.domain.models import Analysis, Sentence, Token, children


class EnglishAnalyzer:
    def __init__(self) -> None:
        self.nlp: Any = None

    def prepare(self) -> dict[str, str]:
        import spacy

        if self.nlp is None:
            try:
                self.nlp = spacy.load("en_core_web_sm", disable=["ner"])
            except OSError as error:
                raise ValueError("Установите en_core_web_sm из lab4/requirements.txt.") from error
        return {"spacy": spacy.__version__, "en_core_web_sm": self.nlp.meta["version"]}

    def analyze(self, text: str) -> Analysis:
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not any(c.isalpha() for c in text):
            raise ValueError("Введите английский текст с буквами.")
        if len(text) > 50_000:
            raise ValueError("Максимум 50 000 символов за один запуск.")
        sentences: list[Sentence] = []
        for paragraph, match in enumerate(re.finditer(r"\S(?:[^\n]|\n(?![ \t]*\n))*", text)):
            document = self.nlp(match.group().rstrip())
            for span in document.sents:
                tokens = tuple(
                    Token(
                        t.i - span.start,
                        t.text,
                        t.lemma_.casefold(),
                        t.pos_,
                        t.tag_,
                        str(t.morph),
                        t.dep_,
                        t.head.i - span.start,
                        match.start() + t.idx,
                        match.start() + t.idx + len(t.text),
                    )
                    for t in span
                )
                sentence = Sentence(len(sentences), paragraph, span.text.strip(), tokens)
                children(sentence)
                sentences.append(sentence)
        return Analysis(text, tuple(sentences))
