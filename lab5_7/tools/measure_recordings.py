"""Objective measurements of detected regions; labels follow the declared reading order."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from lab5_7.application.project import ROOT
from lab5_7.domain.audio import crop
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.wav import load


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotation-dir", type=Path, default=ROOT / "reports/local/annotation_v2")
    args = parser.parse_args()
    sources = json.loads((args.annotation_dir / "sources.json").read_text(encoding="utf-8"))
    destination = args.annotation_dir / "measurements"
    destination.mkdir(exist_ok=False)
    results: list[dict[str, Any]] = []
    for name, source in sources.items():
        audio, metadata = load(ROOT / "data/raw" / (name + ".wav"))
        if metadata["sha256"] != source["metadata"]["sha256"]:
            raise ValueError("Recording changed: " + name)
        for index, region in enumerate(source["regions"]):
            # Use the full proposal for phrases, stable central area for sustained vowels.
            start, end = float(region["start"]), float(region["end"])
            stable = name in {"vowels", "other_vowels"}
            if stable:
                margin = min(0.2, (end - start) * 0.15)
                start, end = start + margin, end - margin
            measured = analyze(crop(audio, start, end))
            voiced = np.asarray([f for f in measured["f0_hz"] if f is not None])
            row = {
                "file": name + ".wav",
                "source_sha256": metadata["sha256"],
                "index": index,
                "label_by_reading_order": region["label"],
                "start": start,
                "end": end,
                "window": "central_vowel" if stable else "whole_activity_region",
                "duration": end - start,
                "peak": measured["peak"],
                "rms": measured["rms"],
                "rms_dbfs": float(20 * np.log10(measured["rms"])) if measured["rms"] else None,
                "f0_median_hz": measured["f0_median_hz"],
                "f0_p10_hz": float(np.percentile(voiced, 10)) if voiced.size else None,
                "f0_p90_hz": float(np.percentile(voiced, 90)) if voiced.size else None,
                "voiced_fraction": measured["voiced_fraction"],
                "status": "MEASURED_AUTOMATIC_REGION_PHONETIC_LABEL_NOT_REVIEWED",
            }
            results.append(row)
    payload = {
        "status": "PRELIMINARY_OBJECTIVE_MEASUREMENTS",
        "note": "Activity intervals are automatic. Labels follow user-declared whole-list cycles; phonetic boundaries and subjective effects are not confirmed. F0 uses Praat AC, 60-500 Hz; high isolated estimates may be octave errors. RMS dBFS is not dB SPL.",
        "annotation_manifest_sha256": hashlib.sha256(
            (args.annotation_dir / "candidates.json").read_bytes()
        ).hexdigest(),
        "results": results,
    }
    (destination / "regions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    with (destination / "regions.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(11, 6), constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 2)
    vowel_labels = ["a", "o", "u", "e", "y", "i"]
    for name, color, caption in [
        ("vowels.wav", "#2458ae", "Speaker 1"),
        ("other_vowels.wav", "#b34615", "Speaker 2"),
    ]:
        medians = []
        spreads = []
        for label in vowel_labels:
            values = [
                r["f0_median_hz"]
                for r in results
                if r["file"] == name
                and r["label_by_reading_order"] == label
                and r["f0_median_hz"] is not None
            ]
            medians.append(float(np.mean(values)))
            spreads.append(float(np.ptp(values)) / 2)
        axes[0].errorbar(
            vowel_labels, medians, yerr=spreads, marker="o", label=caption, color=color, capsize=3
        )
    axes[0].set(
        title="F0 of sustained vowels: mean of 2 medians",
        ylabel="Hz",
        xlabel="Labels by reading order",
    )
    axes[0].legend()
    names = ["neutral", "joy", "sad", "proud"]
    values = [
        float(
            np.mean(
                [
                    r["f0_median_hz"]
                    for r in results
                    if r["file"] == "emotion.wav"
                    and r["label_by_reading_order"] == name
                    and r["f0_median_hz"] is not None
                ]
            )
        )
        for name in names
    ]
    axes[1].bar(names, values, color="#5279b0")
    axes[1].set(title="Intended emotions: measured F0 only", ylabel="Median F0, Hz")
    figure.savefig(destination / "preliminary_comparison.png", dpi=140)
    print(len(results), "activity-region measurements; labels/boundaries remain unreviewed")
    print(destination)


if __name__ == "__main__":
    main()
