"""Единая политика нормализации документов и запросов."""

import re
from collections import Counter
from urllib.parse import urldefrag, urlsplit

from .errors import ValidationError

STOP_WORDS = frozenset(
    """
a an and are as at be been being but by can could did do does for from had has
have he her hers him his how i if in into is it its may me more most my no nor
not of on or our ours she should so some such than that the their theirs them
then there these they this those to too was we were what when where which who
will with would you your yours
""".split()
)
WORD_PATTERN = re.compile(r"[a-z]+(?:'[a-z]+)?")


class EnglishAnalyzer:
    def tokenize(self, text: str) -> tuple[str, ...]:
        return tuple(word for word in WORD_PATTERN.findall(text.lower()) if word not in STOP_WORDS)

    def frequencies(self, text: str) -> Counter[str]:
        return Counter(self.tokenize(text))

    def query_terms(self, query: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.tokenize(query)))


def normalize_query(query: str) -> str:
    normalized = " ".join(query.split())
    if not normalized:
        raise ValidationError("Запрос не должен быть пустым")
    return normalized


def normalize_url(url: str) -> str:
    try:
        normalized = urldefrag(url.strip())[0]
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Некорректный URL")
        _ = parsed.port  # Проверяет корректность порта.
    except ValueError as exc:
        raise ValidationError("Укажите HTTP(S) URL без логина и пароля") from exc
    return normalized


def validate_positive_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{name} должно быть положительным целым числом")


def validate_grade(grade: int) -> None:
    if isinstance(grade, bool) or not isinstance(grade, int) or grade not in (0, 1, 2):
        raise ValidationError("Оценка должна быть целым числом 0, 1 или 2")
