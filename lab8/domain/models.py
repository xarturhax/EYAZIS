import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


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
