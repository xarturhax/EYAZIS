"""Explicit processing of confirmed units; source boundaries are never re-approved."""

from typing import Any

import numpy as np

from lab5_7.domain.audio import Audio, concatenate


def prepare_unit(
    audio: Audio, *, margin_ms: float = 8, gain_db: float = 0
) -> tuple[Audio, dict[str, Any]]:
    if not 2 <= margin_ms <= 20 or not -6 <= gain_db <= 6:
        raise ValueError("Invalid unit margin or bounded gain.")
    hop = max(1, round(audio.rate * 0.005))
    rms = np.array(
        [
            np.sqrt(np.mean(audio.samples[s : s + hop] ** 2))
            for s in range(0, len(audio.samples), hop)
        ]
    )
    active = np.flatnonzero(rms > max(float(rms.max()) * 0.08, 0.00015))
    if not active.size:
        raise ValueError("No active unit samples.")
    margin = round(audio.rate * margin_ms / 1000)
    start = max(0, int(active[0]) * hop - margin)
    end = min(len(audio.samples), (int(active[-1]) + 1) * hop + margin)
    samples = audio.samples[start:end].copy() * 10 ** (gain_db / 20)
    if np.max(np.abs(samples)) >= 1:
        raise ValueError("Unit gain would clip.")
    return Audio(samples, audio.rate), {
        "trim_start_samples": start,
        "trim_end_samples": len(audio.samples) - end,
        "margin_ms": margin_ms,
        "gain_db": gain_db,
    }


def edge_fade(audio: Audio, milliseconds: float = 2) -> Audio:
    if not 0 <= milliseconds <= 5:
        raise ValueError("Edge fade must be 0-5 ms.")
    count = min(round(audio.rate * milliseconds / 1000), len(audio.samples) // 4)
    samples = audio.samples.copy()
    if count:
        ramp = np.sin(np.linspace(0, np.pi / 2, count)) ** 2
        samples[:count] *= ramp
        samples[-count:] *= ramp[::-1]
    return Audio(samples, audio.rate)


def assemble_syllables(
    parts: list[Audio], reference_rms: float
) -> tuple[Audio, list[dict[str, Any]]]:
    processed, operations = [], []
    for audio in parts:
        rms = float(np.sqrt(np.mean(audio.samples**2)))
        # Match only broad level differences, never normalise every syllable without a bound.
        db = (
            float(np.clip(20 * np.log10(reference_rms / rms), -3, 3))
            if rms and reference_rms
            else 0
        )
        unit, operation = prepare_unit(audio, gain_db=db)
        processed.append(edge_fade(unit, 2))
        operations.append(operation)
    return concatenate(processed, crossfade_ms=4), operations


def assemble_first_phrase_phones(
    parts: list[Audio], units: list[str], target_duration: float
) -> tuple[Audio, list[dict[str, Any]]]:
    if len(parts) != len(units) or len(parts) != 13:
        raise ValueError("Expected the 13 confirmed phone units of the first phrase.")
    # Relative durations are explicit trial controls, not measured phone boundaries.
    weights = np.array(
        [0.09, 0.13, 0.10, 0.08, 0.06, 0.13, 0.10, 0.08, 0.07, 0.06, 0.14, 0.10, 0.08]
    )
    # Two 35-ms word pauses; 4-ms crossfades within each word.
    desired = weights * ((target_duration - 0.07 + 0.004 * 10) / float(weights.sum()))
    processed, operations = [], []
    vowel_rms = [
        float(np.sqrt(np.mean(a.samples**2)))
        for a, u in zip(parts, units, strict=True)
        if u in {"ph_a", "ph_u"}
    ]
    target_rms = float(np.median(vowel_rms))
    for audio, unit_id, duration in zip(parts, units, desired, strict=True):
        rms = float(np.sqrt(np.mean(audio.samples**2)))
        db = float(np.clip(20 * np.log10(target_rms / rms), -6, 3)) if rms else 0
        prepared, operation = prepare_unit(audio, margin_ms=6, gain_db=db)
        count = min(len(prepared.samples), max(1, round(duration * audio.rate)))
        # Sustained vowels/noise are cropped centrally. Consonant attacks stay at the front.
        sustained = unit_id in {"ph_a", "ph_u", "ph_s", "ph_sh"}
        first = (len(prepared.samples) - count) // 2 if sustained else 0
        shortened = Audio(prepared.samples[first : first + count].copy(), audio.rate)
        processed.append(edge_fade(shortened, 1.5))
        operation.update(
            unit=unit_id,
            selection_start_in_trimmed=first,
            selected_samples=count,
            duration_target_s=float(duration),
            duration_actual_s=shortened.duration,
            duration_control="heuristic shortening only; no synthetic replacement",
        )
        operations.append(operation)
    words = [concatenate(processed[a:b], 4) for a, b in ((0, 4), (4, 9), (9, 13))]
    pause = Audio(np.zeros(round(parts[0].rate * 0.035)), parts[0].rate)
    return concatenate([words[0], pause, words[1], pause, words[2]]), operations
