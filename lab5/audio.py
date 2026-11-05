from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from numpy.typing import NDArray
from scipy.signal import resample_poly

Samples = NDArray[np.float64]


@dataclass(frozen=True)
class Audio:
    samples: Samples
    rate: int

    def __post_init__(self) -> None:
        if self.samples.ndim != 1 or not self.samples.size:
            raise ValueError("Ожидается непустой моносигнал.")
        if self.rate < 4000 or self.rate > 192000 or not np.isfinite(self.samples).all():
            raise ValueError("Некорректная частота дискретизации или отсчёты.")

    @property
    def duration(self) -> float:
        return len(self.samples) / self.rate


def crop(audio: Audio, start: float, end: float) -> Audio:
    if not 0 <= start < end <= audio.duration:
        raise ValueError("Границы фрагмента должны лежать внутри записи.")
    first, last = round(start * audio.rate), round(end * audio.rate)
    if last <= first:
        raise ValueError("Фрагмент короче одного отсчёта.")
    return Audio(audio.samples[first:last].copy(), audio.rate)


def resample(audio: Audio, rate: int) -> Audio:
    if not 4000 <= rate <= 192000:
        raise ValueError("Частота должна быть от 4000 до 192000 Гц.")
    if rate == audio.rate:
        return Audio(audio.samples.copy(), rate)
    divisor = gcd(rate, audio.rate)
    return Audio(
        np.asarray(
            resample_poly(audio.samples, rate // divisor, audio.rate // divisor), dtype=np.float64
        ),
        rate,
    )


def concatenate(parts: list[Audio], crossfade_ms: float = 0) -> Audio:
    if not parts or not 0 <= crossfade_ms <= 50:
        raise ValueError("Нужны фрагменты; перекрытие — от 0 до 50 мс.")
    rate = parts[0].rate
    if any(p.rate != rate for p in parts):
        raise ValueError("Частоты фрагментов различаются: выполните ресемплинг явно.")
    count = round(crossfade_ms * rate / 1000)
    if count and any(len(p.samples) <= count for p in parts):
        raise ValueError("Перекрытие не должно поглощать весь фрагмент.")
    output = parts[0].samples.copy()
    for part in parts[1:]:
        if count:
            weights = np.linspace(0, 1, count, endpoint=True)
            overlap = output[-count:] * (1 - weights) + part.samples[:count] * weights
            output = np.concatenate((output[:-count], overlap, part.samples[count:]))
        else:
            output = np.concatenate((output, part.samples))
    return Audio(output, rate)


def loop(audio: Audio, repeats: int) -> Audio:
    if not 1 <= repeats <= 2000 or audio.duration * repeats > 120:
        raise ValueError("Повторов 1–2000, длительность результата не более 120 с.")
    return Audio(np.tile(audio.samples, repeats), audio.rate)


def gain(audio: Audio, start: float, end: float, db: float) -> Audio:
    crop(audio, start, end)
    if not -24 <= db <= 24:
        raise ValueError("Изменение уровня: от −24 до +24 дБ.")
    first, last = round(start * audio.rate), round(end * audio.rate)
    output = audio.samples.copy()
    # Short ramps avoid abrupt envelope steps.
    envelope = np.ones(last - first) * 10 ** (db / 20)
    ramp = min(round(0.005 * audio.rate), len(envelope) // 2)
    if ramp:
        envelope[:ramp] = np.linspace(1, envelope[0], ramp)
        envelope[-ramp:] = np.linspace(envelope[-1], 1, ramp)
    output[first:last] *= envelope
    if np.max(np.abs(output)) >= 1:
        raise ValueError("Усиление вызовет клиппинг. Уменьшите число дБ.")
    return Audio(output, audio.rate)


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


def devices() -> str:
    import sounddevice as sd

    try:
        return str(sd.query_devices())
    except sd.PortAudioError as error:
        raise ValueError(f"Не удалось получить устройства: {error}") from error


def record(path: Path, seconds: float, rate: int, bits: int, device: int | None) -> None:
    import sounddevice as sd

    if path.exists():
        raise FileExistsError("Сначала сохраните прежнюю попытку под другим именем.")
    if (
        not 1 <= seconds <= 300
        or rate not in (4000, 8000, 16000, 32000, 44100, 48000)
        or bits not in (8, 16)
    ):
        raise ValueError("Проверьте длительность, частоту и PCM-разрядность.")
    try:
        sd.check_input_settings(device=device, channels=1, samplerate=rate)
        samples = sd.rec(
            round(seconds * rate), samplerate=rate, channels=1, dtype="float64", device=device
        )
        try:
            flags = sd.wait()
        finally:
            sd.stop()
    except sd.PortAudioError as error:
        raise ValueError(f"Микрофон или частота недоступны: {error}") from error
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        sf.write(stream, samples, rate, format="WAV", subtype="PCM_U8" if bits == 8 else "PCM_16")
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source_kind": "recording",
                "requested_rate": rate,
                "stored_bits": bits,
                "device": device,
                "portaudio_status": str(flags),
                "note": "Driver may internally resample; requested rate is not proof of physical ADC rate.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def period_bounds(audio: Audio, f0: float) -> tuple[int, int]:
    if not np.isfinite(f0) or not 60 <= f0 <= 500 or audio.duration < 5 / f0:
        raise ValueError("Need at least five periods and a voiced 60-500 Hz estimate.")
    nominal = audio.rate / f0
    crossings = np.flatnonzero((audio.samples[:-1] <= 0) & (audio.samples[1:] > 0)) + 1
    if not crossings.size:
        raise ValueError("No positive zero crossing in the voiced interval.")
    start = int(crossings[np.argmin(np.abs(crossings - (len(audio.samples) / 2 - nominal)))])
    window = round(2 * nominal)
    candidates = range(round(0.8 * nominal), round(1.2 * nominal) + 1)
    scores = []
    first = audio.samples[start : start + window]
    for lag in candidates:
        second = audio.samples[start + lag : start + lag + window]
        if len(first) != window or len(second) != window:
            continue
        denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
        if denominator:
            scores.append((float(np.dot(first, second)) / denominator, lag))
    if not scores:
        raise ValueError("No complete local period comparison is possible.")
    _, lag = max(scores)
    return start, start + lag
