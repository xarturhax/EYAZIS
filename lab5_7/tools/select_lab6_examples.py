"""Collect six already rated examples; never generate or upgrade human ratings."""

import argparse
import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any

from lab5_7.application.project import ROOT
from lab5_7.infrastructure.analysis import export_analysis
from lab5_7.tools.import_listening import validate_listening


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/local/lab6_selected_examples"
    )
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new directory; selected examples are preserved.")
    candidates: list[dict[str, Any]] = []
    for name in ["lab6_experiments_v1", "lab6_question_refinement_v1", "lab6_question_focus_v1"]:
        experiment = ROOT / "reports/local" / name
        canonical = (experiment / "results.json").read_bytes()
        model = json.loads(canonical)
        by_id = {r["id"]: r for r in model["results"]}
        assessments = []
        for path in experiment.glob("listening_import-*/listening.json"):
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            validate_listening(data, model["results"], hashlib.sha256(canonical).hexdigest())
            assessments.append((data.get("created_at", ""), path, data))
        latest: dict[str, tuple[dict[str, Any], Path]] = {}
        for _, path, data in sorted(assessments, key=lambda item: item[0]):
            for rating in data["results"]:
                if rating["completed"]:
                    latest[rating["id"]] = (rating, path)
        for ident, (rating, path) in latest.items():
            result = by_id[ident]
            if result["category"] != "prosody":
                continue
            intended = "question" if result["question_intended"] else "statement"
            if (
                rating["heard_intonation"] != intended
                or rating["heard_focus"] != ["student", "pisal", "referat"][result["focus"]]
            ):
                continue
            candidates.append(
                {
                    "result": result,
                    "rating": rating,
                    "assessment": path,
                    "experiment": experiment,
                    "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
                }
            )
    selected = []
    for question in [False, True]:
        for focus in range(3):
            group = [
                c
                for c in candidates
                if c["result"]["question_intended"] == question and c["result"]["focus"] == focus
            ]
            if not group:
                raise ValueError("Missing a positively rated intention/focus combination.")
            best = max(
                group,
                key=lambda c: (
                    c["rating"]["naturalness_1_5"],
                    c["rating"]["intelligibility_1_5"],
                    -c["result"]["stage"],
                    c["result"]["method"] == "psola",
                ),
            )
            selected.append(best)
    folder.mkdir(parents=True)
    records = []
    body = []
    for item in selected:
        result, rating = item["result"], item["rating"]
        question, focus = result["question_intended"], result["focus"]
        ident = f"{'question' if question else 'statement'}_focus{focus + 1}"
        source = item["experiment"] / result["wav"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != result["sha256"]:
            raise ValueError("Selected source WAV changed.")
        target = folder / (ident + ".wav")
        target.write_bytes(source.read_bytes())
        export_analysis(target, folder / "analysis" / ident)
        title = (
            ("Вопрос" if question else "Утверждение")
            + " · выделение «"
            + ["Студент", "писал", "реферат"][focus]
            + "»"
        )
        records.append(
            {
                "id": ident,
                "title": title,
                "wav": target.name,
                "sha256": result["sha256"],
                "source_experiment": item["experiment"].relative_to(ROOT).as_posix(),
                "source_result_id": result["id"],
                "source_manifest_sha256": item["manifest_sha256"],
                "assessment_file": item["assessment"].relative_to(ROOT).as_posix(),
                "assessment_sha256": hashlib.sha256(item["assessment"].read_bytes()).hexdigest(),
                "human_rating": rating,
                "method": result["method"],
                "stage": result["stage"],
            }
        )
        body.append(
            f'<article><h2>{escape(title)}</h2><audio controls src="{target.name}"></audio>'
            f"<p>Разборчивость {rating['intelligibility_1_5']}/5; естественность {rating['naturalness_1_5']}/5.</p>"
            f'<p>{escape(rating.get("comment", ""))}</p><a href="analysis/{ident}/report.html">Графики и измерения</a></article>'
        )
    (folder / "selection.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "selection_rule": "Correct perceived intention and focus; highest human naturalness, then intelligibility, then lower processing stage.",
                "scope": "Six previously rated examples, one listener, nonblind evaluation. Comments preserved; naturalness is not claimed perfect.",
                "results": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (folder / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Итоговые примеры №6</title>'
        "<style>body{font:18px system-ui;max-width:950px;margin:30px auto;padding:0 18px}article{border:1px solid #ccd;border-radius:8px;margin:18px 0;padding:16px}p{line-height:1.5}audio{max-width:100%}</style>"
        "<h1>Шесть оценённых примеров «Студент писал реферат»</h1><p>Утверждение и вопрос с выделением каждого слова. "
        "Это точные копии уже оценённых WAV. Новые оценки не требуются. Сохранены численные ответы и комментарии, включая замечания о скачках высоты.</p>"
        + "".join(body)
        + "</html>",
        encoding="utf-8",
    )
    print("Selected 6 already rated examples with a complete intention/focus matrix.")
    print(folder / "index.html")


if __name__ == "__main__":
    main()
