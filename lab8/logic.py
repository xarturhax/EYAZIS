from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import wave
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lab8.tools.download_voices import MODELS, REVISION, VOICES


class CancelledError(Exception):
    pass


MAX_CHARACTERS = 5000
MAX_CHUNK = 300


@dataclass(frozen=True)
class Settings:
    voice: str = "siwis"
    speed: float = 1.0
    volume: float = 0.8

    def __post_init__(self) -> None:
        if self.voice not in {"siwis", "tom"}:
            raise ValueError("Выберите французский голос Siwis или Tom.")
        if not math.isfinite(self.speed) or not 0.5 <= self.speed <= 2:
            raise ValueError("Темп должен быть от 0.5 до 2.0.")
        if not math.isfinite(self.volume) or not 0 <= self.volume <= 1:
            raise ValueError("Громкость должна быть от 0 до 1.")


@dataclass(frozen=True)
class Audio:
    samples: NDArray[np.float32]
    rate: int


@dataclass(frozen=True)
class Result:
    text: str
    settings: Settings
    wav_path: Path
    duration: float
    sample_rate: int
    peak: float
    rms: float
    initialization_seconds: float
    synthesis_seconds: float
    chunks: int
    versions: dict[str, str]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")).strip()
    if not any(c.isalpha() for c in text):
        raise ValueError("Введите французский текст с буквами.")
    if len(text) > MAX_CHARACTERS:
        raise ValueError(f"Максимум {MAX_CHARACTERS} символов.")
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise ValueError("Удалите управляющие символы из текста.")
    if any(len(word) > MAX_CHUNK for word in text.split()):
        raise ValueError("В тексте слишком длинное слово; проверьте содержимое.")
    return text


def split_text(text: str) -> tuple[str, ...]:
    """Preserve all words; prefer punctuation, otherwise a whitespace boundary."""
    parts = []
    while len(text) > MAX_CHUNK:
        prefix = text[: MAX_CHUNK + 1]
        boundaries = [m.end() for m in re.finditer(r"[.!?…][»”\"']?\s+", prefix)]
        spaces = [m.start() for m in re.finditer(r"\s+", prefix)]
        end = boundaries[-1] if boundaries else (spaces[-1] if spaces else -1)
        if end <= 0:
            raise ValueError("Не удалось разбить слишком длинное слово.")
        parts.append(text[:end].strip())
        text = text[end:].lstrip()
    if text.strip():
        parts.append(text.strip())
    return tuple(parts)


def output_paths(target: Path) -> tuple[Path, ...]:
    if target.suffix.lower() != ".wav":
        raise ValueError("Выберите имя файла с расширением .wav.")
    return (
        target,
        target.with_suffix(".json"),
        target.with_suffix(".txt"),
        target.with_suffix(".html"),
    )


class PiperSynthesizer:
    """Only one worker uses the models; no synthesis concurrently with another request."""

    def __init__(self) -> None:
        self.models: dict[str, Any] = {}

    def prepare(self, voice: str) -> dict[str, str]:
        from piper import PiperVoice

        if voice not in VOICES:
            raise ValueError("Unknown French voice.")
        if voice not in self.models:
            folder = MODELS / voice
            manifest = folder / "manifest.json"
            if not manifest.is_file():
                raise ValueError(
                    "Французский голос не установлен. Выполните python -m lab8.tools.download_voices."
                )
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            if metadata["revision"] != REVISION:
                raise ValueError("Ревизия голоса не соответствует приложению.")
            for name, digest in metadata["sha256"].items():
                path = folder / name
                if path.resolve().parent != folder.resolve():
                    raise ValueError("Некорректный путь в манифесте голоса.")
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                        raise ValueError(
                            "Контрольная сумма голоса не совпадает; повторите установку."
                        )
            model = folder / f"fr_FR-{voice}-medium.onnx"
            self.models[voice] = PiperVoice.load(model, use_cuda=False)
            if self.models[voice].config.espeak_voice not in {"fr", "fr-fr", "fr_FR"}:
                del self.models[voice]
                raise ValueError("Загруженный голос не французский.")
        return {
            "piper-tts": version("piper-tts"),
            "onnxruntime": version("onnxruntime"),
            "numpy": version("numpy"),
            "model_revision": REVISION,
            "device": "CPU",
            "voice": voice,
            "normalization": "Piper per sentence; output peak factor 0.98",
            "noise_scale": "0",
            "noise_w_scale": "0",
        }

    def synthesize(self, text: str, settings: Settings, cancelled: Callable[[], bool]) -> Audio:
        from piper import SynthesisConfig

        if cancelled():
            raise CancelledError("Синтез отменён.")
        voice = self.models[settings.voice]
        configuration = SynthesisConfig(
            length_scale=1 / settings.speed,
            noise_scale=0,
            noise_w_scale=0,
            volume=1,
            normalize_audio=True,
        )
        blocks = []
        rate = voice.config.sample_rate
        for chunk in voice.synthesize(text, syn_config=configuration):
            if cancelled():
                raise CancelledError("Синтез отменён.")
            if chunk.sample_rate != rate or chunk.sample_channels != 1:
                raise ValueError("Движок вернул неожиданный аудиоформат.")
            blocks.append(chunk.audio_float_array)
        if not blocks:
            raise ValueError("Движок не создал звук для данного фрагмента.")
        samples = np.concatenate(blocks).astype(np.float32)
        if not np.isfinite(samples).all():
            raise ValueError("Движок вернул некорректные аудиоотсчёты.")
        samples *= settings.volume * 0.98
        return Audio(samples, rate)


class SpeechService:
    def __init__(self, engine: Any) -> None:
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


ROOT = Path(__file__).resolve().parent


def build_service():
    return SpeechService(PiperSynthesizer())
