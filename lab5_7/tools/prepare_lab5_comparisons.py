"""Remaining contextual comparisons from existing recordings, without auto-approval."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from lab5_7.application.project import ROOT, segments
from lab5_7.domain.audio import Audio, crop, loop
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.wav import load, save
from lab5_7.tools.build_lab5 import period_bounds

LABELS = {
    "a": "а",
    "o": "о",
    "u": "у",
    "e": "э",
    "y": "ы",
    "i": "и",
    "ja": "я",
    "jo": "ё",
    "ju": "ю",
    "je": "е",
    "f": "ф",
    "s": "с",
    "sh": "ш",
    "h": "х",
    "b": "б",
    "d": "д",
    "m": "м",
    "n": "н",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/local/lab5_comparisons_v1")
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new comparison directory.")
    sources = json.loads(
        (ROOT / "reports/local/annotation_v2/sources.json").read_text(encoding="utf-8")
    )
    rows = {r["id"]: r for r in segments()}
    cache = {}
    for name in [
        "vowels",
        "iotated",
        "fricatives",
        "fricative_syllables",
        "consonants",
        "hard_syllables",
        "other_vowels",
        "other_fricatives",
    ]:
        audio, metadata = load(ROOT / "data/raw" / (name + ".wav"))
        if metadata["sha256"] != sources[name]["metadata"]["sha256"]:
            raise ValueError("Source recording changed: " + name)
        cache[name] = (audio, metadata)
    folder.mkdir(parents=True)
    (folder / "segments_used.csv").write_bytes((ROOT / "data/segments.csv").read_bytes())

    def interval(
        name: str, label: str, *, central: bool = False, prefix: bool = False
    ) -> tuple[Audio, dict[str, Any]]:
        region = next(r for r in sources[name]["regions"] if r["label"] == label)
        start, end = float(region["start"]), float(region["end"])
        if central:
            middle = (start + end) / 2
            start, end = middle - 0.12, middle + 0.12
        if prefix:
            start, end = max(0, start - 0.01), start + min(0.18, (end - start) * 0.35)
        audio, metadata = cache[name]
        return crop(audio, start, end), {
            "file": name + ".wav",
            "source_sha256": metadata["sha256"],
            "start": start,
            "end": end,
            "label_status": "READING_ORDER_LABEL_NOT_HUMAN_CONFIRMED",
        }

    def confirmed(ident: str) -> tuple[Audio, dict[str, Any]]:
        row = rows[ident]
        if row["reviewed"] != "yes":
            raise ValueError("Required unit is not confirmed: " + ident)
        name = Path(row["file"]).stem
        audio, metadata = cache[name]
        return crop(audio, float(row["start"]), float(row["end"])), {
            "file": row["file"],
            "source_sha256": metadata["sha256"],
            "start": float(row["start"]),
            "end": float(row["end"]),
            "label_status": "HUMAN_CONFIRMED_BANK_UNIT",
        }

    results: list[dict[str, Any]] = []

    def card(
        ident: str,
        group: str,
        title: str,
        question: str,
        examples: list[tuple[str, Audio, dict[str, Any]]],
    ) -> None:
        destination = folder / ident
        destination.mkdir()
        figure = Figure(figsize=(10, max(3, 1.6 * len(examples))), constrained_layout=True)
        FigureCanvasAgg(figure)
        axes = np.atleast_1d(figure.subplots(len(examples), 1))
        clips = []
        for index, (caption, audio, binding) in enumerate(examples):
            path = destination / f"{index + 1}.wav"
            save(audio, path)
            clips.append(
                {
                    "title": caption,
                    "wav": path.relative_to(folder).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source": binding,
                    "duration": audio.duration,
                }
            )
            stride = max(1, len(audio.samples) // 10000)
            axes[index].plot(
                np.arange(0, len(audio.samples), stride) / audio.rate,
                audio.samples[::stride],
                lw=0.5,
            )
            axes[index].set(title=caption, ylabel="Amplitude", xlabel="Time, s")
        figure.savefig(destination / "waveforms.png", dpi=100)
        results.append(
            {
                "id": ident,
                "group": group,
                "title": title,
                "question": question,
                "clips": clips,
                "plot": ident + "/waveforms.png",
                "status": "AWAITING_HUMAN_COMPARISON",
            }
        )

    for label, vowel in [("ja", "a"), ("jo", "o"), ("ju", "u"), ("je", "e")]:
        full, binding = interval("iotated", label)
        simple, simple_binding = confirmed("ph_" + vowel)
        card(
            "iotated_" + label,
            "iotated",
            "Звук «" + LABELS[label] + "» и гласный «" + LABELS[vowel] + "»",
            "Что слышно в начале йотированного звука? Похож ли последующий гласный на отдельный? Запишите наблюдение по записи.",
            [
                ("Йотированный звук " + LABELS[label], full, binding),
                ("Гласный " + LABELS[vowel], simple, simple_binding),
            ],
        )
    for group, labels in [
        ("fricative_context", ["f", "s", "sh", "h"]),
        ("consonant_context", ["b", "d", "m", "n"]),
    ]:
        for label in labels:
            separate, separate_binding = confirmed("ph_" + label)
            name = "fricative_syllables" if group == "fricative_context" else "hard_syllables"
            reading_label = label + "a" if group == "fricative_context" else label
            whole, whole_binding = interval(name, reading_label)
            prefix, prefix_binding = interval(name, reading_label, prefix=True)
            examples = [
                ("Отдельно: " + LABELS[label], separate, separate_binding),
                ("Целый слог: " + LABELS[label] + "а", whole, whole_binding),
                ("Начало слога, предварительное выделение", prefix, prefix_binding),
            ]
            if group == "consonant_context":
                f0 = analyze(separate)["f0_median_hz"]
                estimated = f0 is not None and separate.duration >= 5 / f0
                if estimated:
                    first, last = period_bounds(separate, f0)
                else:
                    first = len(separate.samples) // 2
                    last = first + round(separate.rate * 0.01)
                short = Audio(separate.samples[first:last].copy(), separate.rate)
                examples.extend(
                    [
                        (
                            "Короткий участок: "
                            + ("кандидат периода" if estimated else "окно 10 мс"),
                            short,
                            separate_binding
                            | {
                                "derived_selection_samples": [first, last],
                                "period_estimate": estimated,
                            },
                        ),
                        (
                            "Этот участок, 200 повторений",
                            loop(short, 200),
                            separate_binding
                            | {
                                "derived_selection_samples": [first, last],
                                "repetitions": 200,
                                "period_estimate": estimated,
                            },
                        ),
                    ]
                )
            card(
                group + "_" + label,
                group,
                "«" + LABELS[label] + "» отдельно и в слоге",
                "Сравните отдельный звук и начало слога. Слышится ли согласный, остаётся ли гласный? Для б/д/м/н также опишите короткий фрагмент и цикл. Не подставляйте ожидаемый вывод, если в записи слышно другое.",
                examples,
            )
    for kind, labels, second in [
        ("vowels", ["a", "o", "u", "e", "y", "i"], "other_vowels"),
        ("fricatives", ["f", "s", "sh", "h"], "other_fricatives"),
    ]:
        examples = []
        for label in labels:
            speaker_first, first_binding = confirmed("ph_" + label)
            other, other_binding = interval(second, label, central=True)
            examples.extend(
                [
                    ("Диктор 1: " + LABELS[label], speaker_first, first_binding),
                    ("Диктор 2: " + LABELS[label], other, other_binding),
                ]
            )
        card(
            "speakers_" + kind,
            "speakers",
            "Два диктора: " + ("гласные" if kind == "vowels" else "фрикативные"),
            "Сравните пары одноимённых звуков. Что отличается по высоте, тембру, шумности и форме осциллограммы? Уровень записи не калиброван, поэтому по нему нельзя сравнивать физическую громкость дикторов.",
            examples,
        )
    model = {"schema": 1, "status": "COMPARISONS_PREPARED_NOT_HUMAN_REVIEWED", "results": results}
    canonical = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    (folder / "results.json").write_bytes(canonical)
    template = (ROOT / "presentation/comparison_listening.html").read_text(encoding="utf-8")
    model["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    (folder / "index.html").write_text(
        template.replace("__MODEL__", json.dumps(model, ensure_ascii=False).replace("</", "<\\/")),
        encoding="utf-8",
    )
    print(
        "Built", len(results), "comparison cards from existing recordings; no observations filled."
    )
    print(folder / "index.html")


if __name__ == "__main__":
    main()
