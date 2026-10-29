"""Build available synthesis recipes using only human-confirmed audio units."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from lab5_7.application.experiments import assemble, extract_bank
from lab5_7.application.project import ROOT, segments
from lab5_7.infrastructure.analysis import export_analysis
from lab5_7.infrastructure.wav import load


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/local/lab7_synthesis_v1")
    parser.add_argument("--manifest-dir", type=Path, default=ROOT / "reports/local/annotation_v2")
    parser.add_argument("--previous-experiment", type=Path)
    parser.add_argument("--only", nargs="+", help="Build only these recipe identifiers.")
    parser.add_argument("--assessment-name", default="lab7_listening.json")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", args.assessment_name):
        raise ValueError("Assessment name must be a simple JSON filename.")
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new output directory; previous results are preserved.")
    annotation = args.manifest_dir
    manifest = json.loads((annotation / "manifest.json").read_text(encoding="utf-8"))
    if (
        hashlib.sha256((annotation / "candidates.json").read_bytes()).hexdigest()
        != manifest["manifest_sha256"]
    ):
        raise ValueError("Annotation manifest changed.")
    for name, digest in manifest["source_hashes"].items():
        if hashlib.sha256((ROOT / "data/raw" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Source recording changed: " + name)
    confirmed = {r["id"] for r in segments() if r["reviewed"].casefold() == "yes"}
    recipes = json.loads((ROOT / "data/recipes.json").read_text(encoding="utf-8"))
    if args.only:
        requested = set(args.only)
        if not requested <= {r["id"] for r in recipes}:
            raise ValueError("Unknown requested recipe.")
        recipes = [r for r in recipes if r["id"] in requested]
    if not any(r["status"] == "REVIEWED" and set(r["units"]) <= confirmed for r in recipes):
        raise ValueError("No reviewed recipe has all its units confirmed.")
    folder.mkdir(parents=True)
    (folder / "segments_used.csv").write_bytes((ROOT / "data/segments.csv").read_bytes())
    (folder / "recipes_used.json").write_bytes((ROOT / "data/recipes.json").read_bytes())
    (folder / "annotation_manifest.json").write_bytes((annotation / "manifest.json").read_bytes())
    extract_bank(folder / "bank")
    results: list[dict[str, Any]] = []
    skipped = []
    for recipe in recipes:
        missing = sorted((set(recipe["units"]) | {recipe["reference"]}) - confirmed)
        if recipe["status"] != "REVIEWED" or missing:
            skipped.append(
                {
                    "id": recipe["id"],
                    "missing_confirmations": missing,
                    "recipe_status": recipe["status"],
                }
            )
            continue
        for smooth in [False, True] if recipe["id"] == "ref1_phones" else [False]:
            ident = recipe["id"] + ("_crossfade3ms" if smooth else "")
            path = folder / "synthesis" / (ident + ".wav")
            assemble(recipe["id"], folder / "bank", path, 3 if smooth else 0)
            metrics = export_analysis(path, folder / "analysis" / ident)
            reference = folder / "bank" / (recipe["reference"] + ".wav")
            _, reference_metadata = load(reference)
            category = (
                "smoothed"
                if smooth
                else ("phones" if recipe["id"].endswith("_phones") else "syllables")
            )
            caption = {
                "phones": "Фонемы",
                "syllables": "Слоги",
                "smoothed": "Фонемы, сглаживание 3 мс",
            }[category]
            results.append(
                {
                    "id": ident,
                    "title": recipe["text"] + " · " + caption,
                    "text": recipe["text"],
                    "category": category,
                    "wav": path.relative_to(folder).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "reference_wav": reference.relative_to(folder).as_posix(),
                    "reference_sha256": reference_metadata["sha256"],
                    "baseline_wav": "synthesis/ref1_phones.wav" if smooth else None,
                    "recipe_id": recipe["id"],
                    "units": recipe["units"],
                    "crossfade_ms": 3 if smooth else 0,
                    "duration": metrics["duration"],
                    "reference_content_status": recipe.get(
                        "reference_content_status", "PLANNED_TEXT_NO_REPORTED_MISMATCH"
                    ),
                    "listening_status": "PENDING_HUMAN_LISTENING",
                }
            )
    model = {
        "schema": 1,
        "status": "SYNTHESIS_BUILT_LISTENING_PENDING",
        "results": results,
        "skipped": skipped,
        "reference_note": (
            "Текст третьего эталона подтверждён: «Саша кушал кашу, а Мама пила сок». "
            "Эти два новых варианта пересобраны с «Мама». Старые оценки варианта с «Маша» к ним не переносятся."
        )
        if any(r.get("reference_content_status") == "HUMAN_CONFIRMED_MAMA_TEXT" for r in recipes)
        else "",
    }
    if args.previous_experiment:
        previous_bytes = (args.previous_experiment / "results.json").read_bytes()
        previous = json.loads(previous_bytes)
        current = {r["id"]: r for r in results}
        bindings = []
        for prior in previous["results"]:
            if prior["id"] not in current or any(
                prior[key] != current[prior["id"]][key] for key in ("sha256", "reference_sha256")
            ):
                raise ValueError("Previous assessment audio changed: " + prior["id"])
            bindings.append({key: prior[key] for key in ("id", "sha256", "reference_sha256")})
        model["previous_assessment"] = {
            "manifest_sha256": hashlib.sha256(previous_bytes).hexdigest(),
            "results": bindings,
        }
    canonical = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    (folder / "results.json").write_bytes(canonical)
    template = (ROOT / "presentation/synthesis_listening.html").read_text(encoding="utf-8")
    if args.only:
        first, last = template.index("<h1>"), template.index("<header>")
        template = (
            template[:first]
            + '<h1>Сравнение исправленной третьей фразы</h1><p>Прослушайте эталон и два новых варианта с тем же текстом: фонемный и слоговый. Оцените разборчивость и естественность по шкале 1–5. Прежние оценки записей с другим словом сохранены отдельно.</p><p id="referenceNote" class="warning"></p>'
            + template[last:]
        )
    template = template.replace("lab7_listening.json", args.assessment_name)
    page_model = model | {"manifest_sha256": hashlib.sha256(canonical).hexdigest()}
    (folder / "index.html").write_text(
        template.replace(
            "__MODEL__", json.dumps(page_model, ensure_ascii=False).replace("</", "<\\/")
        ),
        encoding="utf-8",
    )
    print("Built", len(results), "synthesis results; skipped", len(skipped), "unavailable recipes.")
    print(folder / "index.html")


if __name__ == "__main__":
    main()
