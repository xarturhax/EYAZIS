"""Small A/B repair experiment on the first phrase; rated baselines stay immutable."""

import argparse
import hashlib
import json
from pathlib import Path

from lab5_7.application.project import ROOT
from lab5_7.application.synthesis_repair import (
    assemble_first_phrase_phones,
    assemble_syllables,
    edge_fade,
)
from lab5_7.domain.audio import Audio
from lab5_7.infrastructure.analysis import analyze, export_analysis
from lab5_7.infrastructure.prosody import manipulate
from lab5_7.infrastructure.wav import load, save


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/local/lab7_repair_v1")
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new output directory.")
    baseline = ROOT / "reports/local/lab7_synthesis_v2"
    old_bytes = (baseline / "results.json").read_bytes()
    old = json.loads(old_bytes)
    by_id = {r["id"]: r for r in old["results"]}
    source_metadata = []
    for row in old["results"]:
        for key, digest in [("wav", "sha256"), ("reference_wav", "reference_sha256")]:
            if hashlib.sha256((baseline / row[key]).read_bytes()).hexdigest() != row[digest]:
                raise ValueError("Rated baseline changed: " + row["id"])
    recipes = json.loads((baseline / "recipes_used.json").read_text(encoding="utf-8"))
    phone_recipe = next(r for r in recipes if r["id"] == "ref1_phones")
    syllable_recipe = next(r for r in recipes if r["id"] == "ref1_syllables")
    reference, ref_metadata = load(baseline / by_id["ref1_phones"]["reference_wav"])
    parts: dict[str, list[Audio]] = {}
    for recipe in [phone_recipe, syllable_recipe]:
        parts[recipe["id"]] = []
        for unit in recipe["units"]:
            audio, metadata = load(baseline / "bank" / (unit + ".wav"))
            source = json.loads((baseline / "bank" / (unit + ".json")).read_text(encoding="utf-8"))
            if source["segment"]["reviewed"] != "yes":
                raise ValueError("Unconfirmed source unit: " + unit)
            parts[recipe["id"]].append(audio)
            source_metadata.append({"unit": unit, "audio": metadata, "segment": source["segment"]})
    phones, phone_ops = assemble_first_phrase_phones(
        parts["ref1_phones"], phone_recipe["units"], reference.duration
    )
    syllables, syllable_ops = assemble_syllables(parts["ref1_syllables"], analyze(reference)["rms"])
    factor = reference.duration / syllables.duration
    if not 0.5 <= factor <= 2:
        raise ValueError("Reference timing outside the bounded PSOLA duration range.")
    timed = edge_fade(manipulate(syllables, [], [(0.0, factor), (syllables.duration, factor)]))
    folder.mkdir(parents=True)
    (folder / "sources.json").write_text(
        json.dumps(source_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for src, target in [
        (baseline / by_id["ref1_phones"]["reference_wav"], "reference.wav"),
        (baseline / by_id["ref1_phones"]["wav"], "baseline_phones.wav"),
        (baseline / by_id["ref1_syllables"]["wav"], "baseline_syllables.wav"),
    ]:
        (folder / target).write_bytes(src.read_bytes())
    results = []
    variants = [
        (
            "phones_timing",
            "Фонемы: короче звуки, мягче стыки",
            "phones",
            phones,
            phone_ops,
            "baseline_phones.wav",
        ),
        (
            "syllables_edges",
            "Слоги: убраны краевые паузы, выровнен уровень",
            "syllables",
            syllables,
            syllable_ops,
            "baseline_syllables.wav",
        ),
        (
            "syllables_timing",
            "Слоги: дополнительно сокращена длительность",
            "syllables",
            timed,
            syllable_ops
            + [{"psola_duration_factor": factor, "pitch_tier": "PRESERVED_NO_NEW_F0_POINTS"}],
            "baseline_syllables.wav",
        ),
    ]
    for ident, title, category, audio, operations, original in variants:
        path = folder / (ident + ".wav")
        save(audio, path)
        measured = export_analysis(path, folder / "analysis" / ident)
        results.append(
            {
                "id": ident,
                "title": title,
                "category": category,
                "wav": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "reference_wav": "reference.wav",
                "reference_sha256": ref_metadata["sha256"],
                "baseline_wav": original,
                "duration": measured["duration"],
                "operations": operations,
                "listening_status": "PENDING_HUMAN_LISTENING",
            }
        )
    model = {
        "schema": 1,
        "status": "REPAIR_CANDIDATES_NOT_YET_ASSESSED",
        "baseline_manifest_sha256": hashlib.sha256(old_bytes).hexdigest(),
        "results": results,
    }
    canonical = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    (folder / "results.json").write_bytes(canonical)
    template = (ROOT / "presentation/synthesis_listening.html").read_text(encoding="utf-8")
    template = template.replace(
        "<h1>Сравнение эталона и компиляционного синтеза</h1>",
        "<h1>Повторный опыт: «Саша кушал кашу»</h1>",
    )
    start = template.index("<p>Прослушайте эталон")
    end = template.index("<header>", start)
    template = (
        template[:start]
        + "<p>Сравните исходный неудачный синтез, новый вариант и эталон. Здесь три кандидата улучшения первой фразы. Убраны паузы между слогами, сокращены растянутые звуки и смягчены стыки. В третьем варианте длительность сокращена через PSOLA с сохранением исходного тонового уровня. Это эксперимент: улучшение нужно проверить на слух.</p><p>Эталон используется только для сравнения и задания общей длительности. Новая фраза собрана из прежних подтверждённых единиц; эталон не подставляется вместо синтеза. Для каждого варианта оцените новую запись, затем скачайте оценки.</p>"
        + template[end:]
    )
    template = template.replace("Прямая склейка для сравнения:", "Прежний синтез для сравнения:")
    template = template.replace("lab7_listening.json", "lab7_repair_listening.json")
    page_model = model | {"manifest_sha256": hashlib.sha256(canonical).hexdigest()}
    (folder / "index.html").write_text(
        template.replace(
            "__MODEL__", json.dumps(page_model, ensure_ascii=False).replace("</", "<\\/")
        ),
        encoding="utf-8",
    )
    print("Built three unassessed repair candidates; rated baselines preserved.")
    print(folder / "index.html")


if __name__ == "__main__":
    main()
