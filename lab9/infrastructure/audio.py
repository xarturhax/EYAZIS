import hashlib
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def load_pcm(path: Path) -> tuple[bytes, dict[str, object]]:
    if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Нет WAV или размер больше 50 МиБ.")
    info = sf.info(path)
    if info.format != "WAV" or not 0 < info.duration <= 180:
        raise ValueError("Нужен WAV длительностью до 3 минут.")
    samples, rate = sf.read(path, dtype="float64", always_2d=True)
    values = samples[:, 0]
    if not np.isfinite(values).all():
        raise ValueError("Некорректные аудиоотсчёты.")
    if rate != 16000:
        divisor = gcd(rate, 16000)
        values = resample_poly(values, 16000 // divisor, rate // divisor)
    pcm = np.round(np.clip(values, -1, 1) * 32767).astype("<i2").tobytes()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return pcm, {
        "source": str(path.resolve()),
        "sha256": digest,
        "original_rate": rate,
        "original_channels": info.channels,
        "selected_channel": 1,
        "decoder_rate": 16000,
        "duration": len(pcm) / 32000,
    }
