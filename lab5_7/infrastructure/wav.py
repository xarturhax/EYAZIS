import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf

from lab5_7.domain.audio import Audio


def load(path: Path) -> tuple[Audio, dict[str, object]]:
    if not path.is_file() or path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Нет файла или размер больше 100 МиБ.")
    info = sf.info(path)
    if info.format != "WAV" or info.duration <= 0 or info.duration > 300:
        raise ValueError("Нужен WAV длительностью до 5 минут.")
    samples, rate = sf.read(path, dtype="float64", always_2d=True)
    # Preserve a channel instead of potentially cancelling an out-of-phase stereo pair.
    audio = Audio(np.asarray(samples[:, 0], dtype=np.float64), rate)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return audio, {
        "path": str(path.resolve()),
        "sha256": digest,
        "rate": rate,
        "channels": info.channels,
        "subtype": info.subtype,
        "analysis_channel": 1,
        "duration": audio.duration,
        "channel_note": "Выбран первый канал." if info.channels > 1 else "",
    }


def save(audio: Audio, path: Path, bits: int = 16) -> None:
    if path.exists():
        raise FileExistsError(f"Файл уже существует, исходники не перезаписываются: {path}")
    if bits not in (8, 16):
        raise ValueError("Поддерживаются PCM 8 или 16 бит.")
    if np.max(np.abs(audio.samples)) >= 1:
        raise ValueError("Пик достигает полной шкалы. Уменьшите уровень явно.")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(
        path, audio.samples, audio.rate, format="WAV", subtype="PCM_U8" if bits == 8 else "PCM_16"
    )
