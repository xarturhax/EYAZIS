"""Real-vowel period estimates and nonperiodic fricative windows for listening."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from lab5_7.application.project import ROOT, segment_path, segments
from lab5_7.domain.audio import Audio, crop, loop
from lab5_7.infrastructure.analysis import analyze, export_analysis
from lab5_7.infrastructure.wav import load, save


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/local/lab5_phonetics_v1")
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new directory; existing experiments are preserved.")
    selected = {"ph_" + label for label in ("a", "o", "u", "e", "y", "i", "f", "s", "sh", "h")}
    rows = [r for r in segments() if r["id"] in selected]
    if len(rows) != 10 or any(r["reviewed"].casefold() != "yes" for r in rows):
        raise ValueError("The six vowels and four fricatives must be confirmed first.")
    folder.mkdir(parents=True)
    (folder / "segments_used.csv").write_bytes((ROOT / "data/segments.csv").read_bytes())
    results = []
    for row in rows:
        source, metadata = load(segment_path(row["file"]))
        audio = crop(source, float(row["start"]), float(row["end"]))
        vowel = row["id"] not in {"ph_f", "ph_s", "ph_sh", "ph_h"}
        metrics = analyze(audio)
        if vowel:
            if metrics["f0_median_hz"] is None:
                raise ValueError("No F0 for confirmed vowel " + row["id"])
            first, last = period_bounds(audio, metrics["f0_median_hz"])
        else:
            first = round(len(audio.samples) / 2 - 0.005 * audio.rate)
            last = first + round(0.01 * audio.rate)
        short = Audio(audio.samples[first:last].copy(), audio.rate)
        repeated = loop(short, 200)
        base = folder / row["id"]
        save(audio, base / "original.wav")
        save(short, base / "short.wav")
        save(repeated, base / "loop.wav")
        export_analysis(base / "original.wav", base / "analysis")
        results.append(
            {
                "id": row["id"],
                "kind": "vowel_period_estimate" if vowel else "fricative_window",
                "source": metadata,
                "confirmed_segment": row,
                "original_wav": row["id"] + "/original.wav",
                "short_wav": row["id"] + "/short.wav",
                "loop_wav": row["id"] + "/loop.wav",
                "repetitions": 200,
                "source_short_range": [
                    float(row["start"]) + first / audio.rate,
                    float(row["start"]) + last / audio.rate,
                ],
                "short_duration_s": short.duration,
                "f0_median_hz": metrics["f0_median_hz"],
                "loop_repetition_hz": 1 / short.duration,
                "loop_sha256": hashlib.sha256((base / "loop.wav").read_bytes()).hexdigest(),
                "boundary_status": "DERIVED_PERIOD_ESTIMATE_NOT_HUMAN_CONFIRMED"
                if vowel
                else "ARBITRARY_NONPERIODIC_NOISE_WINDOW",
                "listening_status": "PENDING_HUMAN_LISTENING",
            }
        )
    model = {
        "schema": 1,
        "status": "REAL_PHONETIC_EXPERIMENT_LISTENING_PENDING",
        "results": results,
    }
    canonical = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    (folder / "results.json").write_bytes(canonical)
    template = (ROOT / "presentation/phonetics_listening.html").read_text(encoding="utf-8")
    model["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    (folder / "index.html").write_text(
        template.replace("__MODEL__", json.dumps(model, ensure_ascii=False).replace("</", "<\\/")),
        encoding="utf-8",
    )
    print("Built 6 vowel period estimates and 4 nonperiodic noise-window experiments.")
    print(folder / "index.html")


if __name__ == "__main__":
    main()
