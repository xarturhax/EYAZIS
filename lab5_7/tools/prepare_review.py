"""Prepare a local, offline, unreviewed annotation workstation."""

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from lab5_7.application.annotation import propose
from lab5_7.application.project import ROOT
from lab5_7.infrastructure.wav import load

PHONES = dict(
    zip(
        [
            "a",
            "o",
            "u",
            "e",
            "y",
            "i",
            "j",
            "l",
            "m",
            "n",
            "r",
            "p",
            "k",
            "t",
            "v",
            "z",
            "zh",
            "b",
            "d",
            "g",
            "f",
            "s",
            "sh",
            "shch",
            "h",
            "ts",
            "ch",
        ],
        [
            "а",
            "о",
            "у",
            "э",
            "ы",
            "и",
            "й",
            "л",
            "м",
            "н",
            "р",
            "п",
            "к",
            "т",
            "в",
            "з",
            "ж",
            "б",
            "д",
            "г",
            "ф",
            "с",
            "ш",
            "щ",
            "х",
            "ц",
            "ч",
        ],
        strict=True,
    )
)
WORDS = {
    "sasha": "Саша",
    "kushal": "кушал",
    "kashu": "кашу",
    "student": "Студент",
    "pisal": "писал",
    "referat": "реферат",
}
SYLLABLES = dict(
    zip(
        ["sa", "sha", "ku", "shal", "ka", "shu", "a", "ma", "pi", "la", "sok", "pa", "i", "li"],
        ["са", "ша", "ку", "шал", "ка", "шу", "а", "ма", "пи", "ла", "сок", "па", "и", "ли"],
        strict=True,
    )
)


def label(identifier: str) -> str:
    if identifier.startswith("ph_"):
        unit = identifier.removeprefix("ph_")
        return (
            "[" + PHONES[unit.removesuffix("_soft")] + ("’" if unit.endswith("_soft") else "") + "]"
        )
    if identifier.startswith("sy_"):
        return SYLLABLES[identifier.removeprefix("sy_")]
    if identifier.startswith("word_"):
        return WORDS[identifier.removeprefix("word_")]
    if identifier.startswith("stress"):
        return WORDS[identifier.split("_", 1)[1]] + " · выделение №" + identifier[6]
    if identifier.startswith("student_"):
        return (
            "Студент писал реферат"
            if identifier == "student_phrase"
            else WORDS[identifier.removeprefix("student_")]
        )
    return {
        "ref_1": "Саша кушал кашу.",
        "ref_2": "Саша кушал кашу?",
        "ref_3": "Саша кушал кашу, а Маша пила сок.",
        "ref_4": "Мама, папа и Саша пили сок.",
    }[identifier]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "reports/local/annotation_v2")
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new output directory; existing reviews are preserved.")
    candidates, sources = propose(ROOT)
    # Human confirmation is intentionally absent.
    canonical = json.dumps(candidates, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    manifest = hashlib.sha256(canonical).hexdigest()
    folder.mkdir(parents=True)
    (folder / "candidates.json").write_bytes(canonical)
    (folder / "sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    cache = {}
    embedded = []
    for original in candidates:
        row = dict(original)
        if row["file"] not in cache:
            cache[row["file"]] = load(ROOT / "data/raw" / row["file"])[0]
        audio = cache[row["file"]]
        first, last = (
            round(row["context_start"] * audio.rate),
            round(row["context_end"] * audio.rate),
        )
        context = audio.samples[first:last]
        row["context_start"], row["context_end"] = first / audio.rate, last / audio.rate
        stream = io.BytesIO()
        sf.write(stream, context, audio.rate, format="WAV", subtype="PCM_16")
        row["context_wav"] = base64.b64encode(stream.getvalue()).decode("ascii")
        row["envelope"] = [
            [round(float(part.min()), 6), round(float(part.max()), 6)]
            for part in np.array_split(context, min(600, len(context)))
        ]
        embedded.append(row)
    model = {"manifest_sha256": manifest, "segments": embedded}
    template = (ROOT / "presentation/segment_review.html").read_text(encoding="utf-8")
    html = template.replace(
        "__MODEL__", json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    )
    html = html.replace(
        "__LABELS__", json.dumps({r["id"]: label(r["id"]) for r in candidates}, ensure_ascii=False)
    )
    (folder / "index.html").write_text(html, encoding="utf-8")
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_sha256": manifest,
                "status": "AUTO_PROPOSED_NOT_REVIEWED",
                "segments": len(candidates),
                "recordings": len(sources),
                "source_hashes": {n + ".wav": d["metadata"]["sha256"] for n, d in sources.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(folder / "index.html")
    print(len(candidates), "unreviewed proposals; original segments.csv unchanged")


if __name__ == "__main__":
    main()
