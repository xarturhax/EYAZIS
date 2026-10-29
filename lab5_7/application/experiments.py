import csv
import itertools
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from lab5_7.application.project import ROOT, segment_path, segments
from lab5_7.domain.audio import concatenate, crop, resample
from lab5_7.infrastructure.wav import load, save


def quality(path: Path, output: Path, kind: str) -> None:
    audio, metadata = load(path)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for rate in (4000, 8000, 16000, 32000):
        reference = resample(audio, rate)
        for bits in (8, 16):
            target = output / f"{rate}Hz_{bits}bit.wav"
            save(reference, target, bits)
            restored, _ = load(target)
            error = float(np.mean((restored.samples - reference.samples) ** 2))
            power = float(np.mean(reference.samples**2))
            results.append(
                {
                    "file": target.name,
                    "rate": rate,
                    "bits": bits,
                    "actual_subtype": sf.info(target).subtype,
                    "bytes": target.stat().st_size,
                    "quantization_mse": error,
                    "quantization_snr_db": float(10 * np.log10(power / error))
                    if power > 0 and error > 0
                    else None,
                }
            )
    (output / "experiment.json").write_text(
        json.dumps(
            {
                "source": metadata,
                "source_kind": kind,
                "method": "Digital resampling with anti-aliasing, then WAV PCM quantization; NOT native ADC recordings.",
                "results": results,
                "listening_assessment": "PENDING",
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    with (output / "listening.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "intelligibility_1_5", "quality_1_5", "noise_comment"])
        writer.writerows([r["file"], "", "", ""] for r in results)


def extract_bank(output: Path) -> int:
    count = 0
    missing = []
    for row in segments():
        if not row["start"] or not row["end"] or row["reviewed"].casefold() != "yes":
            missing.append(row["id"])
            continue
        path = segment_path(row["file"])
        audio, metadata = load(path)
        piece = crop(audio, float(row["start"]), float(row["end"]))
        save(piece, output / f"{row['id']}.wav")
        (output / f"{row['id']}.json").write_text(
            json.dumps(
                {"source": metadata, "segment": row, "boundary_review": row["reviewed"]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        count += 1
    output.mkdir(parents=True, exist_ok=True)
    (output / "missing.json").write_text(
        json.dumps(missing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return count


def assemble(recipe_id: str, bank: Path, output: Path, crossfade_ms: float) -> None:
    recipes = json.loads((ROOT / "data/recipes.json").read_text(encoding="utf-8"))
    try:
        recipe = next(r for r in recipes if r["id"] == recipe_id)
    except StopIteration as error:
        raise ValueError("Неизвестный рецепт.") from error
    if recipe.get("status") != "REVIEWED":
        raise ValueError("Сначала проверьте транскрипцию и установите status=REVIEWED.")
    parts, sources = [], []
    for unit in recipe["units"]:
        if not unit.replace("_", "").isalnum():
            raise ValueError("Некорректное имя единицы.")
        audio, metadata = load(bank / f"{unit}.wav")
        parts.append(audio)
        sources.append(metadata)
    result = concatenate(parts, crossfade_ms)
    save(result, output)
    output.with_suffix(".json").write_text(
        json.dumps(
            {
                "recipe": recipe,
                "sources": sources,
                "crossfade_ms": crossfade_ms,
                "duration": result.duration,
                "intelligibility": "PENDING_LISTENING",
                "note": "Reviewed symbolic recipe in a simplified teaching alphabet; reductions and coarticulation are not modeled. No automatic intonation imposed.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def permutations(bank: Path, output: Path, prefix: str = "word") -> None:
    if prefix not in ("word", "stress1", "stress2", "stress3"):
        raise ValueError("Неизвестная группа слов.")
    units = tuple(f"{prefix}_{word}" for word in ("sasha", "kushal", "kashu"))
    for order in itertools.permutations(units):
        result = concatenate([load(bank / f"{unit}.wav")[0] for unit in order])
        save(result, output / ("_".join(unit.removeprefix("word_") for unit in order) + ".wav"))
