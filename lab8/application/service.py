import wave
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

import numpy as np

from lab8.application.ports import Synthesizer
from lab8.domain.models import CancelledError, Result, Settings, normalize, output_paths, split_text


class SpeechService:
    def __init__(self, engine: Synthesizer) -> None:
        self.engine = engine

    def render(
        self,
        text: str,
        settings: Settings,
        target: Path,
        progress: Callable[[str], None] = lambda _: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Result:
        text = normalize(text)
        parts = split_text(text)
        if any(path.exists() for path in output_paths(target)):
            raise FileExistsError("Файл уже существует. Выберите новое имя WAV.")
        if cancelled():
            raise CancelledError("Синтез отменён.")
        progress("Загрузка французского голоса…")
        started = perf_counter()
        versions = self.engine.prepare(settings.voice)
        initialization = perf_counter() - started
        started = perf_counter()
        blocks = []
        rate = 0
        for index, part in enumerate(parts, 1):
            if cancelled():
                raise CancelledError("Синтез отменён.")
            progress(f"Синтез фрагмента {index}/{len(parts)}")
            audio = self.engine.synthesize(part, settings, cancelled)
            if not rate:
                rate = audio.rate
            if audio.rate != rate or audio.samples.ndim != 1 or not audio.samples.size:
                raise ValueError("Некорректный аудиоформат.")
            if (
                not 8000 <= audio.rate <= 96000
                or not np.isfinite(audio.samples).all()
                or np.max(np.abs(audio.samples)) > 1
            ):
                raise ValueError("Invalid waveform returned by synthesis engine.")
            blocks.append(audio.samples)
        if cancelled():
            raise CancelledError("Синтез отменён.")
        samples = np.concatenate(blocks)
        if len(samples) / rate > 600:
            raise ValueError("Результат превышает 10 минут.")
        duration = len(samples) / rate
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects an existing recording/export.
        with target.open("xb") as stream:
            with wave.open(stream, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                wav.writeframes(np.round(np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
        return Result(
            text,
            settings,
            target,
            duration,
            rate,
            float(np.max(np.abs(samples))),
            float(np.sqrt(np.mean(samples * samples))),
            initialization,
            perf_counter() - started,
            len(parts),
            versions,
        )
