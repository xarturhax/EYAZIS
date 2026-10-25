from collections.abc import Callable
from typing import Protocol

from lab8.domain.models import Audio, Settings


class Synthesizer(Protocol):
    def prepare(self, voice: str) -> dict[str, str]: ...
    def synthesize(self, text: str, settings: Settings, cancelled: Callable[[], bool]) -> Audio: ...


class Player(Protocol):
    def play(self, path: str) -> None: ...
    def stop(self) -> None: ...
