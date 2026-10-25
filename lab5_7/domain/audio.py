from dataclasses import dataclass
from math import gcd

import numpy as np
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
