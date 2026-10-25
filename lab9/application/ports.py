from collections.abc import Callable
from typing import Protocol

from lab9.domain.commands import Utterance


class Recognizer(Protocol):
    def prepare(self, language: str) -> dict[str, str]: ...
    def decode(
        self, pcm: bytes, rate: int, language: str, cancelled: Callable[[], bool]
    ) -> list[Utterance]: ...
