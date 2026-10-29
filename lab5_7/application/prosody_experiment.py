"""Controlled prosody experiment on a phrase derived from confirmed component words."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from lab5_7.domain.audio import Audio, crop, gain
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.prosody import coupled_contour, manipulate


@dataclass(frozen=True)
class WordRange:
    label: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Phrase:
    audio: Audio
    words: tuple[WordRange, ...]
    original_start: float
    original_end: float
    notes: tuple[str, ...]


def derive_phrase(audio: Audio, rows: list[dict[str, str]]) -> Phrase:
    identifiers = ("student_student", "student_pisal", "student_referat")
    by_id = {r["id"]: r for r in rows}
    selected = [by_id[i] for i in identifiers]
    if any(r["reviewed"].casefold() != "yes" or r["file"] != "student.wav" for r in selected):
        raise ValueError("All three student words must be confirmed in the same source.")
    starts = [float(r["start"]) for r in selected]
    ends = [float(r["end"]) for r in selected]
    if any(not np.isfinite(x) for x in starts + ends):
        raise ValueError("Finite component boundaries required.")
    if any(not 0 <= a < b <= audio.duration for a, b in zip(starts, ends, strict=True)):
        raise ValueError("Invalid component range.")
    if starts != sorted(starts) or ends != sorted(ends):
        raise ValueError("Words must follow the original phrase order.")
    # Midpoints partition overlaps/gaps only for time-control measurements.
    # The original contiguous source is cropped; confirmed word WAVs are not altered.
    cuts = [starts[0], (ends[0] + starts[1]) / 2, (ends[1] + starts[2]) / 2, ends[-1]]
    if any(a >= b for a, b in zip(cuts, cuts[1:], strict=False)):
        raise ValueError("Word partitions are not increasing.")
    source = crop(audio, starts[0], ends[-1])
    words = tuple(
        WordRange(
            r["id"].removeprefix("student_"),
            max(0.0, a - starts[0]),
            min(source.duration, b - starts[0]),
        )
        for r, a, b in zip(selected, cuts[:-1], cuts[1:], strict=True)
    )
    notes = tuple(r["note"] for r in selected if r["note"])
    return Phrase(source, words, starts[0], ends[-1], notes)


def _pitch_points(
    phrase: Phrase, focus: int, question: bool, base: float
) -> list[tuple[float, float]]:
    word = phrase.words[focus]
    # An explicit experimental control anchor; not a claimed measured vowel nucleus.
    anchor = word.start + word.duration * (0.72 if question else 0.45)
    values = {
        0.0: base,
        phrase.audio.duration: base * (1.18 if question else 0.85),
        word.start: base,
        anchor: base * (1.5 if question else 1.35),
        word.end: base * (1.15 if question else 0.95),
    }
    values[phrase.audio.duration] = base * (1.18 if question else 0.85)
    return sorted((t, float(np.clip(v, 60, 500))) for t, v in values.items())


def _duration_points(phrase: Phrase, focus: int, factor: float) -> list[tuple[float, float]]:
    word = phrase.words[focus]
    ramp = min(0.01, (word.end - word.start) / 4)
    return sorted(
        {
            0.0: 1.0,
            phrase.audio.duration: 1.0,
            word.start: 1.0,
            word.start + ramp: factor,
            word.end - ramp: factor,
            word.end: 1.0,
        }.items()
    )


def _time_edges(
    audio: Audio, points: list[tuple[float, float]], inverse: bool
) -> NDArray[np.float64]:
    input_edges = np.arange(len(audio.samples) + 1) / audio.rate
    values = np.interp(input_edges, [t for t, _ in points], [v for _, v in points])
    if inverse:
        values = 1 / values
    return np.r_[0.0, np.cumsum((values[:-1] + values[1:]) / (2 * audio.rate))]


def transform(
    phrase: Phrase, method: str, question: bool, focus: int, stage: int
) -> tuple[Audio, dict[str, Any]]:
    if (
        method not in {"psola", "coupled_contour"}
        or focus not in (0, 1, 2)
        or stage not in (1, 2, 3)
    ):
        raise ValueError("Unknown prosody experiment configuration.")
    original = analyze(phrase.audio)
    if original["f0_median_hz"] is None:
        raise ValueError("A voiced phrase is required.")
    base = float(original["f0_median_hz"])
    pitch = _pitch_points(phrase, focus, question, base)
    duration = _duration_points(phrase, focus, 1.25 if stage == 3 else 1.0)
    if method == "psola":
        changed = manipulate(phrase.audio, pitch, duration if stage == 3 else None)
        clock = _time_edges(phrase.audio, duration, False)
        parameters: dict[str, Any] = {
            "pitch_points": pitch,
            "duration_points": duration if stage == 3 else [],
        }
    else:
        knots = sorted({t for t, _ in pitch} | {t for t, _ in duration})
        p = np.interp(knots, [t for t, _ in pitch], [v for _, v in pitch])
        d = np.interp(knots, [t for t, _ in duration], [v for _, v in duration])
        rates = [(t, float(v / base / f)) for t, v, f in zip(knots, p, d, strict=True)]
        changed = coupled_contour(phrase.audio, rates)
        clock = _time_edges(phrase.audio, rates, True)
        parameters = {
            "rate_points": rates,
            "approximate_pitch_points": pitch,
            "note": "Playback-clock changes couple pitch and time; stretching the focused word also lowers its local pitch.",
        }
    # Allow sample rounding/resynthesis endpoint differences, record the scale.
    scale = float(changed.duration / clock[-1])
    mapped = [
        WordRange(
            w.label,
            max(
                0.0,
                float(np.interp(w.start, np.arange(len(clock)) / phrase.audio.rate, clock) * scale),
            ),
            min(
                changed.duration,
                float(np.interp(w.end, np.arange(len(clock)) / phrase.audio.rate, clock) * scale),
            ),
        )
        for w in phrase.words
    ]
    target = mapped[focus]
    if stage >= 2:
        changed = gain(changed, target.start, target.end, 3)
    controls = {
        "status": "READY",
        "method": method,
        "question_intended": question,
        "focus": focus,
        "stage": stage,
        "base_f0_hz": base,
        "parameters": parameters,
        "gain_db": 3 if stage >= 2 else 0,
        "duration_factor_intended": 1.25 if stage == 3 else 1,
        "output_word_ranges": [{"label": w.label, "start": w.start, "end": w.end} for w in mapped],
        "time_mapping_endpoint_scale": scale,
        "gain_timeline": "output after resynthesis/time change",
        "accent_anchor": "heuristic relative position in the partition, not a human-reviewed vowel nucleus",
        "listening_status": "PENDING_HUMAN_LISTENING",
    }
    return changed, controls
