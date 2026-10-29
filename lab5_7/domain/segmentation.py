"""Energy-based proposals, never phonetic ground truth."""

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_closing

from lab5_7.domain.audio import Audio


@dataclass(frozen=True)
class Interval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def activity(audio: Audio, *, phrases: bool = False, short_stops: bool = False) -> list[Interval]:
    hop = round(audio.rate * 0.005)
    frames = audio.samples[: len(audio.samples) // hop * hop].reshape(-1, hop)
    if not len(frames):
        return []
    rms = np.sqrt(np.mean(frames**2, axis=1))
    threshold = max(
        0.0015 if phrases else 0.0008, float(np.percentile(rms, 10)) * (8 if phrases else 6)
    )
    gap = 0.65 if phrases else 0.12
    mask = binary_closing(rms > threshold, structure=np.ones(round(gap / 0.005)))
    starts = np.flatnonzero(mask & ~np.r_[False, mask[:-1]])
    ends = np.flatnonzero(mask & ~np.r_[mask[1:], False]) + 1
    minimum = 0.5 if phrases else (0.08 if short_stops else 0.25)
    peak = 0.004 if phrases else max(0.002, float(np.percentile(rms, 95)) * 0.1)
    return [
        Interval(float(a * hop / audio.rate), float(b * hop / audio.rate))
        for a, b in zip(starts, ends, strict=True)
        if (b - a) * hop / audio.rate >= minimum and rms[a:b].max() >= peak
    ]


def onset_candidate(audio: Audio, interval: Interval) -> Interval:
    """Propose a consonant prefix of a CV syllable; human correction is required."""
    # A reproducible initial cursor, not an asserted C/V acoustic boundary.
    return Interval(
        max(0, interval.start - 0.01), interval.start + min(0.18, interval.duration * 0.35)
    )
