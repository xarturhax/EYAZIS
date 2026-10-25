from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from lab9.application.ports import Recognizer
from lab9.domain.commands import Utterance


@dataclass(frozen=True)
class RecognitionResult:
    utterances: tuple[Utterance, ...]
    initialization_seconds: float
    recognition_seconds: float
    versions: dict[str, str]


class RecognitionService:
    def __init__(self, engine: Recognizer) -> None:
        self.engine = engine

    def run(
        self, pcm: bytes, rate: int, language: str, cancelled: Callable[[], bool] = lambda: False
    ) -> RecognitionResult:
        if not pcm or len(pcm) % 2 or not 8000 <= rate <= 96000:
            raise ValueError("Нужен непустой mono PCM16 и частота 8–96 кГц.")
        start = perf_counter()
        versions = self.engine.prepare(language)
        initialization = perf_counter() - start
        start = perf_counter()
        utterances = self.engine.decode(pcm, rate, language, cancelled)
        return RecognitionResult(
            tuple(utterances), initialization, perf_counter() - start, versions
        )
