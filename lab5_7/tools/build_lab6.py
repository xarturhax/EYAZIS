"""Build real lab6 permutations and the full 36-condition prosody experiment."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np

from lab5_7.application.experiments import extract_bank, permutations
from lab5_7.application.project import ROOT, segments
from lab5_7.application.prosody_experiment import derive_phrase, transform
from lab5_7.domain.audio import Audio, crop
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.wav import load, save

WORDS = {
    "sasha": "Саша",
    "kushal": "кушал",
    "kashu": "кашу",
    "student": "Студент",
    "pisal": "писал",
    "referat": "реферат",
}
STAGES = {1: "только F0", 2: "F0 + амплитуда", 3: "F0 + амплитуда + длительность"}


def summary(audio: Audio) -> dict[str, Any]:
    result = analyze(audio)
    voiced = [v for v in result["f0_hz"] if v is not None]
    return {
        k: result[k]
        for k in ["duration", "peak", "rms", "f0_median_hz", "voiced_fraction", "warnings"]
    } | {
        "f0_p10_hz": float(np.percentile(voiced, 10)) if voiced else None,
        "f0_p90_hz": float(np.percentile(voiced, 90)) if voiced else None,
    }


def record(path: Path, folder: Path, title: str, category: str, **metadata: Any) -> dict[str, Any]:
    audio, _ = load(path)
    return {
        "id": path.relative_to(folder).with_suffix("").as_posix(),
        "wav": path.relative_to(folder).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "title": title,
        "category": category,
        "measurements": summary(audio),
        "listening_status": "PENDING_HUMAN_LISTENING",
        **metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/local/lab6_experiments_v1")
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new experiment directory; existing results are preserved.")
    annotation = json.loads(
        (ROOT / "reports/local/annotation_v2/manifest.json").read_text(encoding="utf-8")
    )
    for name, digest in annotation["source_hashes"].items():
        if hashlib.sha256((ROOT / "data/raw" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Source recording changed: " + name)
    rows = segments()
    required = {
        f"{prefix}_{word}"
        for prefix in ["word", "stress1", "stress2", "stress3"]
        for word in ["sasha", "kushal", "kashu"]
    }
    required |= {"student_student", "student_pisal", "student_referat"}
    if not required <= {r["id"] for r in rows if r["reviewed"].casefold() == "yes"}:
        raise ValueError("The 15 component words must be confirmed first.")
    original, source = load(ROOT / "data/raw/student.wav")
    phrase = derive_phrase(original, rows)
    folder.mkdir(parents=True)
    (folder / "segments_used.csv").write_bytes((ROOT / "data/segments.csv").read_bytes())
    (folder / "inputs.json").write_text(
        json.dumps(
            {
                "source": source,
                "phrase_start": phrase.original_start,
                "phrase_end": phrase.original_end,
                "phrase_boundary_status": "DERIVED_FROM_THREE_CONFIRMED_COMPONENTS_NOT_SEPARATELY_CONFIRMED",
                "component_notes": phrase.notes,
                "partition_note": "Adjacent component margins overlap; midpoint partitions are used for controls only. Original source is cropped contiguously; component WAVs are preserved.",
                "annotation_manifest": annotation,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    count = extract_bank(folder / "bank")
    if count < 15:
        raise ValueError("Missing confirmed bank entries.")
    save(phrase.audio, folder / "student_original.wav")
    results = []
    for prefix in ["word", "stress1", "stress2", "stress3"]:
        output = folder / "permutations" / prefix
        permutations(folder / "bank", output, prefix)
        for order in itertools.permutations(["sasha", "kushal", "kashu"]):
            units = [prefix + "_" + word for word in order]
            filename = "_".join(u.removeprefix("word_") for u in units) + ".wav"
            title = " ".join(WORDS[w] for w in order)
            origin = (
                "отдельные слова"
                if prefix == "word"
                else "из фразы с выделением «"
                + ["Саша", "кушал", "кашу"][int(prefix[-1]) - 1]
                + "»"
            )
            result = record(
                output / filename,
                folder,
                title + " · " + origin,
                "permutation",
                prefix=prefix,
                unit_order=units,
                source_kind="CONCATENATED_CONFIRMED_USER_WORDS",
            )
            result["source_word_ranges"] = [r for r in rows if r["id"] in units]
            results.append(result)
    original_metrics = analyze(phrase.audio)
    traces = {}
    for method, question, focus, stage in itertools.product(
        ["psola", "coupled_contour"], [False, True], range(3), [1, 2, 3]
    ):
        audio, controls = transform(phrase, method, question, focus, stage)
        ident = f"{method}_{'question' if question else 'statement'}_focus{focus + 1}_stage{stage}"
        path = folder / "prosody" / (ident + ".wav")
        save(audio, path)
        measured, _ = load(path)
        word_metrics = []
        for span in controls["output_word_ranges"]:
            word_metrics.append(
                {
                    "word": span["label"],
                    "start": span["start"],
                    "end": span["end"],
                    "metrics": summary(
                        crop(measured, span["start"], min(span["end"], measured.duration))
                    ),
                }
            )
        controls["input"] = source
        controls["original_source_range"] = [phrase.original_start, phrase.original_end]
        controls["source_word_partitions"] = [
            {"label": w.label, "start": w.start, "end": w.end} for w in phrase.words
        ]
        path.with_suffix(".json").write_text(
            json.dumps(controls, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        title = (
            ("PSOLA" if method == "psola" else "Связанная скорость")
            + " · "
            + ("вопрос" if question else "утверждение")
            + " · выделение «"
            + WORDS[phrase.words[focus].label]
            + "» · "
            + STAGES[stage]
        )
        row = record(
            path,
            folder,
            title,
            "prosody",
            method=method,
            question_intended=question,
            focus=focus,
            stage=stage,
            source_kind="TRANSFORMED_USER_RECORDING",
            word_metrics=word_metrics,
        )
        results.append(row)
        traces[(method, question, focus, stage)] = analyze(measured)
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    plots = folder / "plots"
    plots.mkdir()
    for method, question, focus in itertools.product(
        ["psola", "coupled_contour"], [False, True], range(3)
    ):
        figure = Figure(figsize=(10, 6), constrained_layout=True)
        FigureCanvasAgg(figure)
        axes = figure.subplots(2, 1)
        for stage in [0, 1, 2, 3]:
            values = original_metrics if stage == 0 else traces[(method, question, focus, stage)]
            label = "original" if stage == 0 else "stage " + str(stage)
            axes[0].plot(
                values["f0_time"],
                [v if v is not None else np.nan for v in values["f0_hz"]],
                ".-",
                ms=2,
                label=label,
            )
            axes[1].plot(
                values["rms_time"],
                [v if v is not None else np.nan for v in values["rms_dbfs"]],
                label=label,
            )
        axes[0].set(
            ylabel="F0, Hz",
            ylim=(60, 500),
            title=f"{method} / {'question' if question else 'statement'} / focus {focus + 1}",
        )
        axes[0].legend()
        axes[1].set(ylabel="RMS, dBFS", xlabel="Output time, s")
        figure.savefig(
            plots / f"{method}_{'question' if question else 'statement'}_focus{focus + 1}.png",
            dpi=120,
        )
    expected = (24, 36)
    actual = (
        sum(r["category"] == "permutation" for r in results),
        sum(r["category"] == "prosody" for r in results),
    )
    if actual != expected:
        raise ValueError("Incomplete experiment matrix.")
    model = {
        "schema": 1,
        "status": "BUILT_OBJECTIVE_MEASUREMENTS_COMPLETE_LISTENING_PENDING",
        "original_wav": "student_original.wav",
        "original": summary(phrase.audio),
        "results": results,
    }
    payload = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False)
    (folder / "results.json").write_text(payload, encoding="utf-8")
    digest = hashlib.sha256((folder / "results.json").read_bytes()).hexdigest()
    template = (ROOT / "presentation/experiment_listening.html").read_text(encoding="utf-8")
    page_model = {"manifest_sha256": digest, **model}
    (folder / "index.html").write_text(
        template.replace(
            "__MODEL__", json.dumps(page_model, ensure_ascii=False).replace("</", "<\\/")
        ),
        encoding="utf-8",
    )
    print(
        "Built",
        actual[0],
        "permutations and",
        actual[1],
        "prosody variants; no subjective ratings generated",
    )
    print(folder / "index.html")


if __name__ == "__main__":
    main()
