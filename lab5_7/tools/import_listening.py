"""Import human lab6 ratings without changing the experiment or filling missing scores."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from lab5_7.application.project import ROOT

FIELDS = ("intelligibility_1_5", "naturalness_1_5", "heard_focus", "heard_intonation", "comment")


def validate_listening(
    data: dict[str, Any], results: list[dict[str, Any]], manifest: str
) -> list[dict[str, Any]]:
    if (
        data.get("schema") != 1
        or data.get("assessment_kind") != "LAB6_EXPERIMENT_LISTENING"
        or data.get("manifest_sha256") != manifest
    ):
        raise ValueError("Listening assessment does not match the experiment manifest.")
    rows = data.get("results")
    if not isinstance(rows, list) or len(rows) != len(results):
        raise ValueError("Expected one assessment entry per experiment result.")
    expected = {row["id"]: row for row in results}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("id") not in expected or row["id"] in seen:
            raise ValueError("Unknown or duplicate result.")
        seen.add(row["id"])
        original = expected[row["id"]]
        if row.get("sha256") != original["sha256"] or type(row.get("completed")) is not bool:
            raise ValueError("Audio hash or explicit completion status is invalid.")
        if not isinstance(row.get("comment", ""), str):
            raise ValueError("Comments must be text.")
        focuses = (
            {"student", "pisal", "referat"}
            if original["category"] == "prosody"
            else {"sasha", "kushal", "kashu"}
        ) | {"none", "unclear"}
        for key in FIELDS[:4]:
            value = row.get(key)
            if not row["completed"] and value in (None, ""):
                continue
            if key.endswith("_1_5"):
                valid = type(value) is int and 1 <= value <= 5
            else:
                choices = (
                    focuses
                    if key == "heard_focus"
                    else {"statement", "question", "other", "unclear"}
                )
                valid = isinstance(value, str) and value in choices
            if not valid:
                raise ValueError("Invalid or missing rating: " + key + " for " + row["id"])
    return rows


def summarize(rows: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {r["id"]: r for r in results}
    completed = [r | {"experiment": by_id[r["id"]]} for r in rows if r["completed"]]
    groups: dict[str, Any] = {}
    for method in ("psola", "coupled_contour"):
        for stage in (None, 1, 2, 3):
            selected = [
                r
                for r in completed
                if r["experiment"].get("method") == method
                and (stage is None or r["experiment"]["stage"] == stage)
            ]
            if not selected:
                continue
            key = method if stage is None else f"{method}_stage{stage}"
            groups[key] = {
                "count": len(selected),
                **{k: sum(r[k] for r in selected) / len(selected) for k in FIELDS[:2]},
                "focus_matches_intent": sum(
                    r["heard_focus"] == ("student", "pisal", "referat")[r["experiment"]["focus"]]
                    for r in selected
                ),
                "intonation_matches_intent": sum(
                    r["heard_intonation"]
                    == ("question" if r["experiment"]["question_intended"] else "statement")
                    for r in selected
                ),
            }
    return {
        "completed": len(completed),
        "pending": len(rows) - len(completed),
        "completed_by_category": {
            category: sum(r["experiment"]["category"] == category for r in completed)
            for category in ("prosody", "permutation")
        },
        "groups": groups,
        "scope": "One listener; descriptive statistics for this experiment only.",
    }


def import_listening(path: Path, folder: Path) -> Path:
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Listening JSON exceeds 2 MiB.")
    canonical = (folder / "results.json").read_bytes()
    model = json.loads(canonical)
    data = json.loads(raw.decode("utf-8-sig"))
    rows = validate_listening(data, model["results"], hashlib.sha256(canonical).hexdigest())
    base = folder.resolve()
    for result in model["results"]:
        audio = (base / result["wav"]).resolve()
        if (
            not audio.is_relative_to(base)
            or hashlib.sha256(audio.read_bytes()).hexdigest() != result["sha256"]
        ):
            raise ValueError("Experiment audio changed: " + result["id"])
    receipt = folder / ("listening_import-" + hashlib.sha256(raw).hexdigest()[:16])
    if receipt.exists():
        if (receipt / "listening.json").read_bytes() != raw:
            raise ValueError("Existing import receipt conflicts with this assessment.")
        return receipt
    receipt.mkdir()
    (receipt / "listening.json").write_bytes(raw)
    (receipt / "summary.json").write_text(
        json.dumps(summarize(rows, model["results"]), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    by_id = {r["id"]: r for r in model["results"]}
    with (receipt / "ratings.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("id", "category", "title", "completed", *FIELDS))
        writer.writerows(
            (
                r["id"],
                by_id[r["id"]]["category"],
                by_id[r["id"]]["title"],
                r["completed"],
                *(r.get(k, "") for k in FIELDS),
            )
            for r in rows
        )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--experiment-dir", type=Path, default=ROOT / "reports/local/lab6_experiments_v1"
    )
    args = parser.parse_args()
    receipt = import_listening(args.input, args.experiment_dir)
    summary = json.loads((receipt / "summary.json").read_text(encoding="utf-8"))
    model = json.loads((args.experiment_dir / "results.json").read_text(encoding="utf-8"))
    assessment = json.loads((receipt / "listening.json").read_text(encoding="utf-8-sig"))
    pending = {r["id"] for r in assessment["results"] if not r["completed"]}
    resume_category = next(
        (r["category"] for r in model["results"] if r["id"] in pending),
        model["results"][0]["category"],
    )
    model.update(
        manifest_sha256=assessment["manifest_sha256"],
        saved_assessment=assessment,
        resume_category=resume_category,
    )
    template = (ROOT / "presentation/experiment_listening.html").read_text(encoding="utf-8")
    page = args.experiment_dir / (
        "resume-" + receipt.name.removeprefix("listening_import-") + ".html"
    )
    page.write_text(
        template.replace("__MODEL__", json.dumps(model, ensure_ascii=False).replace("</", "<\\/")),
        encoding="utf-8",
    )
    print("Imported human ratings:", summary["completed"], "; pending:", summary["pending"])
    print("Receipt:", receipt)
    print("Resume page:", page)


if __name__ == "__main__":
    main()
