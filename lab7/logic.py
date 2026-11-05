from __future__ import annotations

import itertools
import json
from pathlib import Path

from lab5.audio import concatenate, crop, load, save
from lab5.logic import ROOT, segment_path, segments


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


def recipes():
    return json.loads((ROOT / "data/recipes.json").read_text(encoding="utf-8"))


def synthesize(recipe_id, crossfade_ms=0, custom_units=None):
    from datetime import datetime

    from lab5.analysis import export_analysis

    folder = (
        Path(__file__).resolve().parent
        / "reports/local"
        / datetime.now().strftime("desktop_%Y%m%d_%H%M%S_%f")
    )
    folder.mkdir(parents=True)
    bank = folder / "bank"
    extract_bank(bank)
    recipe = next(r for r in recipes() if r["id"] == recipe_id)
    target = folder / "synthesis.wav"
    if custom_units is not None:
        if not custom_units or any(not u.replace("_", "").isalnum() for u in custom_units):
            raise ValueError("Введите идентификаторы единиц банка через пробел.")
        parts = [load(bank / f"{u}.wav")[0] for u in custom_units]
        save(concatenate(parts, crossfade_ms), target)
        (folder / "custom_units.json").write_text(
            json.dumps(
                {"units": custom_units, "crossfade_ms": crossfade_ms, "listening": "NOT_ASSESSED"}
            ),
            encoding="utf-8",
        )
    else:
        assemble(recipe_id, bank, target, crossfade_ms)
    reference = bank / f"{recipe['reference']}.wav"
    metrics = export_analysis(target, folder / "analysis")
    export_analysis(reference, folder / "reference_analysis")
    return {
        "audio": target,
        "original": reference,
        "folder": folder,
        "metrics": metrics,
        "playlist": [],
        "recipe": recipe,
    }
