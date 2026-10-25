"""Praat overlap-add resynthesis; parameters are explicit and never guessed from text."""

from typing import Any

import numpy as np

from lab5_7.domain.audio import Audio


def manipulate(
    audio: Audio,
    points: list[tuple[float, float]],
    duration_points: list[tuple[float, float]] | None = None,
    floor: float = 60,
    ceiling: float = 500,
) -> Audio:
    import parselmouth
    from parselmouth.praat import call

    if not 40 <= floor < ceiling <= 1200:
        raise ValueError("Проверьте границы F0 (40–1200 Гц).")
    for values, low, high in ((points, floor, ceiling), (duration_points or [], 0.5, 2.0)):
        if any(not 0 <= t <= audio.duration or not low <= v <= high for t, v in values):
            raise ValueError("Точки выходят за длительность или допустимые значения.")
        if any(a[0] >= b[0] for a, b in zip(values, values[1:], strict=False)):
            raise ValueError("Время точек должно строго возрастать.")
    sound = parselmouth.Sound(audio.samples, sampling_frequency=audio.rate)
    manipulation = call(sound, "To Manipulation", 0.01, floor, ceiling)
    if points:
        tier = call(manipulation, "Extract pitch tier")
        if call(tier, "Get number of points") == 0:
            raise ValueError("Не найден голосовой участок: проверьте запись и диапазон F0.")
        call(tier, "Remove points between", 0, audio.duration)
        for time, value in points:
            call(tier, "Add point", time, value)
        call([tier, manipulation], "Replace pitch tier")
    if duration_points:
        tier = call(manipulation, "Extract duration tier")
        call(tier, "Remove points between", 0, audio.duration)
        for time, value in duration_points:
            call(tier, "Add point", time, value)
        call([tier, manipulation], "Replace duration tier")
    output: Any = call(manipulation, "Get resynthesis (overlap-add)")
    return Audio(np.asarray(output.values[0], dtype=np.float64), audio.rate)


def coupled_shift(audio: Audio, semitones: float) -> Audio:
    """Playback-speed analogue: pitch AND duration change together, not PSOLA."""
    from fractions import Fraction

    from scipy.signal import resample_poly

    if not -12 <= semitones <= 12:
        raise ValueError("Сдвиг должен быть в пределах ±12 полутонов.")
    ratio = Fraction(2 ** (-semitones / 12)).limit_denominator(1000)
    output = resample_poly(audio.samples, ratio.numerator, ratio.denominator)
    return Audio(np.asarray(output, dtype=np.float64), audio.rate)


def coupled_contour(audio: Audio, points: list[tuple[float, float]]) -> Audio:
    """Variable playback clock: local pitch changes are coupled to time changes."""
    from scipy.signal import butter, sosfiltfilt

    if len(points) < 2 or abs(points[0][0]) > 1e-8 or abs(points[-1][0] - audio.duration) > 1e-8:
        raise ValueError("Контур скорости должен включать начало 0 и конец записи.")
    if any(not 0 <= t <= audio.duration or not 0.5 <= r <= 2 for t, r in points):
        raise ValueError("Коэффициенты скорости должны быть от 0.5 до 2.")
    if any(a[0] >= b[0] for a, b in zip(points, points[1:], strict=False)):
        raise ValueError("Времена должны возрастать.")
    edges = np.arange(len(audio.samples) + 1) / audio.rate
    rates = np.interp(edges, [t for t, _ in points], [r for _, r in points])
    output_edges = np.concatenate(
        ([0.0], np.cumsum((1 / rates[:-1] + 1 / rates[1:]) / (2 * audio.rate)))
    )
    length = max(1, round(output_edges[-1] * audio.rate))
    input_times = np.interp(np.arange(length) / audio.rate, output_edges, edges)
    samples = audio.samples
    maximum = float(np.max(rates))
    if maximum > 1:
        if len(samples) < 100:
            raise ValueError("Сигнал слишком короткий для антиалиас-фильтра.")
        samples = sosfiltfilt(butter(8, 0.9 / maximum, output="sos"), samples)
    result = np.interp(input_times, np.arange(len(samples)) / audio.rate, samples)
    return Audio(np.asarray(result, dtype=np.float64), audio.rate)
