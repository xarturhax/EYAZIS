"""Presentation order from user instructions and candidate bank selection."""

import json
from pathlib import Path
from typing import Any

from lab5_7.application.project import segments
from lab5_7.domain.segmentation import Interval, activity, onset_candidate
from lab5_7.infrastructure.wav import load

LAYOUTS = {
    "vowels": ["a", "o", "u", "e", "y", "i"] * 2,
    "iotated": ["ja", "jo", "ju", "je"] * 2,
    "fricatives": ["f", "s", "sh", "h"] * 2,
    "fricative_syllables": ["fa", "sa", "sha", "ha"] * 2,
    "consonants": ["b", "d", "m", "n"] * 2,
    "hard_syllables": [
        "b",
        "v",
        "g",
        "d",
        "zh",
        "z",
        "k",
        "l",
        "m",
        "n",
        "p",
        "r",
        "s",
        "t",
        "f",
        "h",
        "ts",
        "ch",
        "sh",
        "shch",
    ]
    * 2,
    "soft_syllables": ["b", "v", "g", "d", "z", "k", "l", "m", "n", "p", "r", "s", "t", "f", "h"]
    * 2,
    "words": ["sasha", "kushal", "kashu"] * 2,
    "stress": ["subject", "verb", "object"] * 2,
    "intonation": ["statement", "continuation", "question", "exclamation"] * 2,
    "emotion": ["neutral", "joy", "sad", "proud"] * 2,
    "student": ["phrase"] * 3,
    "references": ["ref_1", "ref_2", "ref_3", "ref_4"],
    "syllable_bank": [
        "sa",
        "sha",
        "ku",
        "shal",
        "ka",
        "shu",
        "a",
        "ma",
        "pi",
        "la",
        "sok",
        "pa",
        "i",
        "li",
    ]
    * 2,
    "other_vowels": ["a", "o", "u", "e", "y", "i"] * 2,
    "other_fricatives": ["f", "s", "sh", "h"] * 2,
}
PHRASES = {"stress", "intonation", "emotion", "student", "references"}


def propose(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    recordings = {}
    detected: dict[str, list[dict[str, Any]]] = {}
    for name, labels in LAYOUTS.items():
        audio, metadata = load(root / "data/raw" / (name + ".wav"))
        regions = activity(audio, phrases=name in PHRASES, short_stops=name == "consonants")
        if len(regions) != len(labels):
            raise ValueError(
                f"{name}: found {len(regions)} regions, expected {len(labels)}; inspect recording before assigning labels."
            )
        recordings[name] = (audio, metadata)
        detected[name] = [
            {"label": label, "start": r.start, "end": r.end}
            for label, r in zip(labels, regions, strict=True)
        ]
    alignment_path = root / "vendor/word_alignment.json"
    alignments = (
        json.loads(alignment_path.read_text(encoding="utf-8")) if alignment_path.exists() else {}
    )
    proposals = []
    for original in segments():
        row = dict(original)
        name = Path(row["file"]).stem
        audio, metadata = recordings[name]
        labels = LAYOUTS[name]
        ident = row["id"]
        if row["kind"] == "phone":
            label = ident.removeprefix("ph_").removesuffix("_soft")
            index = 0 if label == "j" else labels.index(label)
        elif row["kind"] == "syllable":
            index = labels.index(ident.removeprefix("sy_"))
        elif ident.startswith("word_"):
            index = labels.index(ident.removeprefix("word_"))
        elif ident.startswith("ref_"):
            index = labels.index(ident)
        else:
            index = 0
        chosen = detected[name][index]
        parent = Interval(chosen["start"], chosen["end"])
        if ident.startswith("stress"):
            # Whole-phrase context; the word cursor starts at a third, only as a proposal.
            condition = int(ident[6]) - 1
            parent = Interval(detected[name][condition]["start"], detected[name][condition]["end"])
            word = ["sasha", "kushal", "kashu"].index(ident.split("_", 1)[1])
            part = parent.duration / 3
            interval = Interval(parent.start + word * part, parent.start + (word + 1) * part)
            method = "EQUAL_THIRDS_INITIAL_CURSOR_REQUIRES_CORRECTION"
        elif ident.startswith("student_") and ident != "student_phrase":
            word = ["student", "pisal", "referat"].index(ident.removeprefix("student_"))
            part = parent.duration / 3
            interval = Interval(parent.start + word * part, parent.start + (word + 1) * part)
            method = "EQUAL_THIRDS_INITIAL_CURSOR_REQUIRES_CORRECTION"
        elif row["kind"] == "phone":
            if name in {"hard_syllables", "soft_syllables", "iotated"}:
                interval = onset_candidate(audio, parent)
                method = "CONSONANT_PREFIX_INITIAL_CURSOR_REQUIRES_CORRECTION"
            elif ident in {"ph_b", "ph_d"}:
                interval = Interval(
                    max(0, parent.start - 0.015), min(parent.end, parent.start + 0.12)
                )
                method = "STOP_ONSET_CANDIDATE"
            else:
                center = (parent.start + parent.end) / 2
                interval = Interval(center - 0.12, center + 0.12)
                method = "SUSTAINED_CENTER_CANDIDATE"
        else:
            interval = Interval(max(0, parent.start - 0.02), min(audio.duration, parent.end + 0.02))
            method = "ENERGY_REGION_WITH_MARGIN"
        alignment = alignments.get(name, {})
        if name in {"stress", "student"} and alignment.get("eligible"):
            if alignment["source_sha256"] != metadata["sha256"]:
                raise ValueError("Word alignment recording hash changed.")
            offset = (int(ident[6]) - 1) * 3 if name == "stress" else 0
            aligned = alignment["words"][offset : offset + 3]
            if len(aligned) != 3:
                raise ValueError("Incomplete word alignment.")
            parent = Interval(float(aligned[0]["start"]), float(aligned[-1]["end"]))
            if ident == "student_phrase":
                interval = Interval(
                    max(0, parent.start - 0.02), min(audio.duration, parent.end + 0.02)
                )
            else:
                unit = aligned[word]
                interval = Interval(
                    max(0, float(unit["start"]) - 0.015),
                    min(audio.duration, float(unit["end"]) + 0.015),
                )
            method = "VOSK_EXACT_TEXT_WORD_TIMING_NOT_HUMAN_REVIEWED"
        context_start = max(0, min(parent.start, interval.start) - 0.15)
        context_end = min(audio.duration, max(parent.end, interval.end) + 0.15)
        proposals.append(
            row
            | {
                "start": round(interval.start, 6),
                "end": round(interval.end, 6),
                "reviewed": False,
                "source_sha256": metadata["sha256"],
                "source_duration": audio.duration,
                "method": method,
                "context_start": context_start,
                "context_end": context_end,
                "expected_label": ident,
            }
        )
    return proposals, {
        name: {"metadata": item[1], "regions": detected[name]} for name, item in recordings.items()
    }
