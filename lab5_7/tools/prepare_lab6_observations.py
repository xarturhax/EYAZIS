"""Natural prosody observations; never infer heard emotion or group counts automatically."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from lab5_7.application.project import ROOT, segments
from lab5_7.domain.audio import crop
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.wav import load, save

INTONATION = [
    ("statement", "Утверждение"),
    ("continuation", "Незавершённость"),
    ("question", "Вопрос"),
    ("exclamation", "Восклицание"),
    ("other", "Другое / различаются повторы"),
    ("unclear", "Не уверен"),
]
EMOTION = [
    ("neutral", "Нейтрально"),
    ("joy", "Радость"),
    ("sad", "Огорчение"),
    ("proud", "Гордость"),
    ("other", "Другое / различаются повторы"),
    ("unclear", "Не уверен"),
]
FOCUS = [
    ("subject", "Саша"),
    ("verb", "кушал"),
    ("object", "кашу"),
    ("none", "Нет явного выделения"),
    ("other", "Различаются повторы"),
    ("unclear", "Не уверен"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/local/lab6_source_observations_v1"
    )
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new observations directory.")
    annotation = ROOT / "reports/local/annotation_v2"
    sources = json.loads((annotation / "sources.json").read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in segments()}
    recordings = {}
    for name in ["intonation", "emotion", "stress", "references"]:
        audio, metadata = load(ROOT / "data/raw" / (name + ".wav"))
        if metadata["sha256"] != sources[name]["metadata"]["sha256"]:
            raise ValueError("Source recording changed: " + name)
        recordings[name] = (audio, metadata)
    folder.mkdir(parents=True)
    (folder / "segments_used.csv").write_bytes((ROOT / "data/segments.csv").read_bytes())
    results: list[dict[str, Any]] = []

    def card(
        ident: str,
        group: str,
        title: str,
        options: list[tuple[str, str]],
        ranges: list[tuple[str, float, float, str]],
        question: str,
        count_groups: bool = False,
    ) -> None:
        name = "references" if group == "reference" else group
        audio, source = recordings[name]
        destination = folder / ident
        destination.mkdir()
        figure = Figure(figsize=(10, 3 * len(ranges)), constrained_layout=True)
        FigureCanvasAgg(figure)
        axes = np.asarray(figure.subplots(len(ranges), 2)).reshape(len(ranges), 2)
        clips = []
        for index, (caption, start, end, boundary_status) in enumerate(ranges):
            piece = crop(audio, start, end)
            path = destination / f"{index + 1}.wav"
            save(piece, path)
            measured = analyze(piece)
            clips.append(
                {
                    "title": caption,
                    "wav": path.relative_to(folder).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source": {
                        "file": name + ".wav",
                        "sha256": source["sha256"],
                        "start": start,
                        "end": end,
                    },
                    "boundary_status": boundary_status,
                    "measurements": measured,
                }
            )
            axes[index, 0].plot(
                measured["f0_time"],
                [v if v is not None else np.nan for v in measured["f0_hz"]],
                ".-",
                ms=2,
            )
            axes[index, 0].set(title=caption, ylabel="F0, Hz", xlabel="Time, s", ylim=(60, 500))
            axes[index, 1].plot(
                measured["rms_time"], [v if v is not None else np.nan for v in measured["rms_dbfs"]]
            )
            axes[index, 1].set(title=caption, ylabel="RMS, dBFS", xlabel="Time, s")
        figure.savefig(destination / "prosody.png", dpi=110)
        results.append(
            {
                "id": ident,
                "group": group,
                "title": title,
                "options": options,
                "question": question,
                "count_groups": count_groups,
                "clips": clips,
                "plot": ident + "/prosody.png",
                "status": "AWAITING_HUMAN_OBSERVATION",
            }
        )

    for name, options in [("intonation", INTONATION), ("emotion", EMOTION)]:
        for label, caption in options[:4]:
            found = [r for r in sources[name]["regions"] if r["label"] == label]
            if len(found) != 2:
                raise ValueError("Expected two whole-list repetitions for " + label)
            ranges = [
                (
                    "Повтор " + str(i + 1),
                    float(r["start"]),
                    float(r["end"]),
                    "AUTO_ACTIVITY_READING_ORDER_LABEL",
                )
                for i, r in enumerate(found)
            ]
            card(
                name + "_" + label,
                name,
                ("Интонация: " if name == "intonation" else "Замысел эмоции: ") + caption,
                options,
                ranges,
                "Как это воспринимается на слух? Где подъём/спад и главное выделение, чем отличаются повторы? Название — замысел, а не готовая оценка.",
            )
    for index, (label, caption) in enumerate(FOCUS[:3], 1):
        components = [rows[f"stress{index}_{word}"] for word in ["sasha", "kushal", "kashu"]]
        if any(r["reviewed"] != "yes" for r in components):
            raise ValueError("Stress components must be confirmed.")
        found = [r for r in sources["stress"]["regions"] if r["label"] == label]
        if len(found) != 2:
            raise ValueError("Expected two stress repetitions.")
        ranges = [
            (
                "Повтор 1, внешние границы по подтверждённым словам",
                min(float(r["start"]) for r in components),
                max(float(r["end"]) for r in components),
                "CONTIGUOUS_RANGE_FROM_CONFIRMED_WORDS",
            ),
            (
                "Повтор 2",
                float(found[1]["start"]),
                float(found[1]["end"]),
                "AUTO_ACTIVITY_READING_ORDER_LABEL",
            ),
        ]
        card(
            "stress_" + label,
            "stress",
            "Фразовое выделение: «" + caption + "»",
            FOCUS,
            ranges,
            "Какое слово выделено? Сколько акцентных групп и синтагм слышно? Если повторы различаются, укажите это в комментарии.",
            True,
        )
    for index in range(1, 5):
        row = rows[f"ref_{index}"]
        if row["reviewed"] != "yes":
            raise ValueError("Reference phrase must be confirmed.")
        card(
            f"reference_{index}",
            "reference",
            f"Эталон {index}" + (" — слово «Мама/Маша» уточняется" if index == 3 else ""),
            INTONATION,
            [
                (
                    "Подтверждённая целая фраза",
                    float(row["start"]),
                    float(row["end"]),
                    "HUMAN_CONFIRMED_PHRASE",
                )
            ],
            "Отметьте интонацию, число акцентных групп и синтагм. Запишите, где проходит разделение, например с символом |.",
            True,
        )
    model = {"schema": 1, "status": "NATURAL_PROSODY_OBSERVATIONS_PENDING", "results": results}
    canonical = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    (folder / "results.json").write_bytes(canonical)
    template = (ROOT / "presentation/source_prosody.html").read_text(encoding="utf-8")
    model["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    (folder / "index.html").write_text(
        template.replace("__MODEL__", json.dumps(model, ensure_ascii=False).replace("</", "<\\/")),
        encoding="utf-8",
    )
    print(
        "Built",
        len(results),
        "natural prosody observation cards; no heard labels or group counts filled.",
    )
    print(folder / "index.html")


if __name__ == "__main__":
    main()
