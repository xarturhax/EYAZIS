"""Four first-pass question candidates; preserve all sixty rated experiments."""

import argparse
import hashlib
import json
from pathlib import Path

from lab5_7.application.project import ROOT, segments
from lab5_7.application.prosody_experiment import derive_phrase
from lab5_7.application.question_refinement import refined_controls, reinforce_question
from lab5_7.infrastructure.analysis import export_analysis
from lab5_7.infrastructure.prosody import manipulate
from lab5_7.infrastructure.wav import load, save
from lab5_7.tools.build_lab6 import record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/local/lab6_question_refinement_v1"
    )
    parser.add_argument("--strengthen-focus", action="store_true")
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new question experiment directory.")
    baseline = ROOT / "reports/local/lab6_experiments_v1"
    canonical_old = (baseline / "results.json").read_bytes()
    old = json.loads(canonical_old)
    comparison_folder = (
        ROOT / "reports/local/lab6_question_refinement_v1" if args.strengthen_focus else baseline
    )
    comparison_bytes = (comparison_folder / "results.json").read_bytes()
    comparison_model = json.loads(comparison_bytes)
    original, source = load(ROOT / "data/raw/student.wav")
    saved_inputs = json.loads((baseline / "inputs.json").read_text(encoding="utf-8"))
    if source["sha256"] != saved_inputs["source"]["sha256"]:
        raise ValueError("Original student recording changed.")
    phrase = derive_phrase(original, segments())
    if phrase.audio.duration != old["original"]["duration"]:
        raise ValueError("Component phrase boundaries changed.")
    folder.mkdir(parents=True)
    save(phrase.audio, folder / "student_original.wav")
    results = []
    for focus in (0, 1):
        old_id = (
            f"focus{focus + 1}_terminal_rise"
            if args.strengthen_focus
            else f"prosody/psola_question_focus{focus + 1}_stage1"
        )
        prior = next(r for r in comparison_model["results"] if r["id"] == old_id)
        old_wav = comparison_folder / prior["wav"]
        if hashlib.sha256(old_wav.read_bytes()).hexdigest() != prior["sha256"]:
            raise ValueError("Rated prior question changed.")
        comparison = folder / f"previous_focus{focus + 1}.wav"
        comparison.write_bytes(old_wav.read_bytes())
        configurations = (
            [("terminal_rise", 2), ("terminal_rise", 3)]
            if args.strengthen_focus
            else [("nucleus_fall", 1), ("terminal_rise", 1)]
        )
        for contour, stage in configurations:
            if stage == 1:
                controls = refined_controls(phrase, focus, contour)
                changed = manipulate(phrase.audio, controls["pitch_points"])
            else:
                changed, controls = reinforce_question(phrase, focus, stage)
            if stage != 3 and abs(changed.duration - phrase.audio.duration) > 0.003:
                raise ValueError("F0-only processing unexpectedly changed duration.")
            ident = (
                f"focus{focus + 1}_stage{stage}"
                if args.strengthen_focus
                else f"focus{focus + 1}_{contour}"
            )
            path = folder / (ident + ".wav")
            save(changed, path)
            controls["source"] = source
            controls["original_source_range"] = [phrase.original_start, phrase.original_end]
            path.with_suffix(".json").write_text(
                json.dumps(controls, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            export_analysis(path, folder / "analysis" / ident)
            caption = (
                "Быстрый подъём на ядре и низкое продолжение"
                if contour == "nucleus_fall"
                else "Выделение слова и подъём в конце"
            )
            if stage > 1:
                caption = "+4.5 дБ на выбранном слове" + (
                    " и растяжение слова ×1.15" if stage == 3 else ""
                )
            results.append(
                record(
                    path,
                    folder,
                    ("«Студент»" if focus == 0 else "«писал»") + " · " + caption,
                    "prosody",
                    method="psola",
                    question_intended=True,
                    focus=focus,
                    stage=stage,
                    baseline_wav=comparison.name,
                    baseline_sha256=prior["sha256"],
                    controls=controls,
                )
            )
    model = {
        "schema": 1,
        "status": "QUESTION_REFINEMENT_HUMAN_LISTENING_PENDING",
        "original_wav": "student_original.wav",
        "original": old["original"],
        "prior_manifest_sha256": hashlib.sha256(comparison_bytes).hexdigest(),
        "results": results,
    }
    canonical = json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    (folder / "results.json").write_bytes(canonical)
    template = (ROOT / "presentation/experiment_listening.html").read_text(encoding="utf-8")
    start, end = template.index("<h1>"), template.index("<header>")
    introduction = "<h1>Уточнение вопросов: четыре варианта</h1><p>В предыдущем опыте вопросы с выделением первого и второго слова воспринимались как утверждения. Здесь два новых контура для каждого слова. Изменён только F0, длительность и усиление не менялись. Опорные точки выбраны по энергии голосовых участков и пока не подтверждены как точные границы ударных гласных. Названия описывают замысел; отметьте, что действительно слышно.</p>"
    if args.strengthen_focus:
        introduction = "<h1>Вопрос с выделением нужного слова</h1><p>Вы уже услышали вопрос, но выделенным стало «реферат». Здесь сохранён тот же вопросительный контур и усилено первое или второе слово на 4.5 дБ. Во втором варианте каждой пары выбранное слово также растянуто в 1.15 раза. Речь пересинтезирована один раз из исходника; прежние записи не перезаписываются. Отметьте, остаётся ли вопрос и какое слово выделено. Название — замысел, а не готовый ответ.</p>"
    template = (
        template[:start]
        + introduction
        + '<p>Исходная фраза: <audio controls preload="none" src="student_original.wav"></audio></p>'
        + template[end:]
    )
    template = template.replace("Просодика: 36 вариантов", "Вопросы: 4 варианта").replace(
        '<option value="permutation">Перестановки: 24 варианта</option>', ""
    )
    template = template.replace(
        "lab6_listening.json",
        "lab6_focus_review.json" if args.strengthen_focus else "lab6_question_review.json",
    )
    page_model = model | {"manifest_sha256": hashlib.sha256(canonical).hexdigest()}
    (folder / "index.html").write_text(
        template.replace(
            "__MODEL__", json.dumps(page_model, ensure_ascii=False).replace("</", "<\\/")
        ),
        encoding="utf-8",
    )
    print("Built 4 unassessed question candidates; prior 60 results preserved.")
    print(folder / "index.html")


if __name__ == "__main__":
    main()
