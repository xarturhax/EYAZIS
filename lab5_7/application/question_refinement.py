"""Explicit second-pass F0 candidates informed by failed question judgements."""

from typing import Any

import numpy as np

from lab5_7.application.prosody_experiment import Phrase, _duration_points, _time_edges
from lab5_7.domain.audio import Audio, gain
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.prosody import manipulate


def nucleus_candidates(phrase: Phrase) -> list[float]:
    measured = analyze(phrase.audio)
    times = np.asarray(measured["rms_time"])
    levels = np.array([v if v is not None else -150 for v in measured["rms_dbfs"]])
    voiced = (
        np.interp(times, measured["f0_time"], [float(v is not None) for v in measured["f0_hz"]])
        > 0.9
    )
    anchors = []
    for word in phrase.words:
        # The three known words have final-syllable lexical stress. This is a search
        # region for a trial anchor, not a confirmed phonetic vowel boundary.
        mask = (
            voiced
            & (times >= word.start + 0.35 * word.duration)
            & (times <= word.end - 0.1 * word.duration)
        )
        if not mask.any():
            raise ValueError("No voiced energy anchor in " + word.label)
        anchors.append(float(times[np.argmax(np.where(mask, levels, -np.inf))]))
    return anchors


def refined_controls(phrase: Phrase, focus: int, contour: str) -> dict[str, Any]:
    if focus not in (0, 1) or contour not in {"nucleus_fall", "terminal_rise"}:
        raise ValueError("Unknown question refinement configuration.")
    measured = analyze(phrase.audio)
    if measured["f0_median_hz"] is None:
        raise ValueError("A voiced phrase is required.")
    base = float(measured["f0_median_hz"])
    anchors = nucleus_candidates(phrase)
    word, anchor = phrase.words[focus], anchors[focus]
    before = max(word.start, anchor - 0.07)
    peak = min(word.end - 0.02, anchor + 0.025)
    after = min(word.end, peak + 0.08)
    if not before < peak < after:
        raise ValueError("Anchor does not allow an ordered local contour.")
    values = {
        0.0: base * 0.92,
        phrase.audio.duration: base * 0.8,
        word.start: base * 0.9,
        before: base * 0.82,
        peak: base * (1.65 if contour == "nucleus_fall" else 1.35),
        after: base * (0.78 if contour == "nucleus_fall" else 0.96),
        word.end: base * (0.78 if contour == "nucleus_fall" else 0.96),
    }
    if contour == "terminal_rise":
        values[max(phrase.words[-1].start, anchors[-1] - 0.11)] = base * 0.94
        values[min(phrase.audio.duration, anchors[-1] + 0.08)] = base * 1.65
        values[phrase.audio.duration] = base * 1.75
    points = sorted((float(t), float(np.clip(v, 60, 500))) for t, v in values.items())
    return {
        "method": "psola",
        "question_intended": True,
        "focus": focus,
        "stage": 1,
        "contour": contour,
        "pitch_points": points,
        "base_f0_hz": base,
        "nucleus_candidates": anchors,
        "anchor_status": "ENERGY_PEAK_ON_VOICED_FRAMES_NOT_HUMAN_CONFIRMED",
        "duration_control": "UNCHANGED",
        "gain_db": 0,
        "note": "Trial controls; question intonation and focus must be judged by a human.",
    }


def reinforce_question(phrase: Phrase, focus: int, stage: int) -> tuple[Audio, dict[str, Any]]:
    if stage not in (2, 3):
        raise ValueError("Focus reinforcement uses stages 2 or 3.")
    controls = refined_controls(phrase, focus, "terminal_rise")
    duration = _duration_points(phrase, focus, 1.15 if stage == 3 else 1.0)
    changed = manipulate(phrase.audio, controls["pitch_points"], duration if stage == 3 else None)
    clock = _time_edges(phrase.audio, duration, False)
    times = np.arange(len(clock)) / phrase.audio.rate
    scale = float(changed.duration / clock[-1])
    spans: list[dict[str, Any]] = [
        {
            "label": w.label,
            "start": max(0.0, float(np.interp(w.start, times, clock) * scale)),
            "end": min(changed.duration, float(np.interp(w.end, times, clock) * scale)),
        }
        for w in phrase.words
    ]
    target = spans[focus]
    changed = gain(changed, float(target["start"]), float(target["end"]), 4.5)
    controls.update(
        stage=stage,
        gain_db=4.5,
        duration_factor_intended=1.15 if stage == 3 else 1.0,
        duration_points=duration if stage == 3 else [],
        output_word_ranges=spans,
        duration_control="FOCUSED_WORD_ONLY_1.15" if stage == 3 else "UNCHANGED",
        gain_timeline="Mapped output word range after a single PSOLA resynthesis",
        time_mapping_endpoint_scale=scale,
    )
    return changed, controls
