"""Validate human comparison observations without treating negative answers as bad input."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from lab5_7.application.project import ROOT, segment_path


def validate_comparisons(
    data: dict[str, Any],
    results: list[dict[str, Any]],
    digest: str,
    assessment_kind: str = "LAB5_COMPARISON_LISTENING",
) -> list[dict[str, Any]]:
    if (
        data.get("schema") != 1
        or data.get("assessment_kind") != assessment_kind
        or data.get("manifest_sha256") != digest
    ):
        raise ValueError("Comparison observations do not match this manifest.")
    rows = data.get("results")
    if not isinstance(rows, list) or len(rows) != len(results):
        raise ValueError("Expected one observation per comparison.")
    by_id = {r["id"]: r for r in results}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Invalid comparison entry.")
        ident = row["id"]
        if ident not in by_id or ident in seen:
            raise ValueError("Unknown or duplicate comparison.")
        seen.add(ident)
        if row.get("clip_hashes") != [c["sha256"] for c in by_id[ident]["clips"]]:
            raise ValueError("Comparison audio bindings changed.")
        if type(row.get("completed")) is not bool or not isinstance(row.get("comment"), str):
            raise ValueError("Explicit completion status and text observation required.")
        if row.get("labels_match") not in ("", "yes", "no", "unclear"):
            raise ValueError("Invalid label comparison.")
        if row["completed"] and (not row["labels_match"] or len(row["comment"].strip()) < 2):
            raise ValueError("Completed comparisons need a label answer and an observation.")
    return rows


def import_comparisons(
    path: Path,
    folder: Path,
    *,
    assessment_kind: str = "LAB5_COMPARISON_LISTENING",
    extra_fields: tuple[str, ...] = (),
) -> Path:
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Observation file exceeds 2 MiB.")
    canonical = (folder / "results.json").read_bytes()
    results = json.loads(canonical)["results"]
    rows = validate_comparisons(
        json.loads(raw.decode("utf-8-sig")),
        results,
        hashlib.sha256(canonical).hexdigest(),
        assessment_kind,
    )
    base = folder.resolve()
    verified = set()
    for result in results:
        for clip in result["clips"]:
            wav = (base / clip["wav"]).resolve()
            if (
                not wav.is_relative_to(base)
                or hashlib.sha256(wav.read_bytes()).hexdigest() != clip["sha256"]
            ):
                raise ValueError("Comparison WAV changed: " + result["id"])
            source = clip["source"]
            filename = source["file"]
            if filename not in verified:
                if hashlib.sha256(segment_path(filename).read_bytes()).hexdigest() != source.get(
                    "source_sha256", source.get("sha256")
                ):
                    raise ValueError("Source recording changed: " + filename)
                verified.add(filename)
    receipt = folder / ("listening_import-" + hashlib.sha256(raw).hexdigest()[:16])
    if receipt.exists():
        if (receipt / "listening.json").read_bytes() != raw:
            raise ValueError("Conflicting comparison receipt.")
        return receipt
    by_id = {r["id"]: r for r in results}
    summary = {
        "completed": sum(r["completed"] for r in rows),
        "total": len(rows),
        "groups": {
            group: dict(
                Counter(
                    r["labels_match"]
                    for r in rows
                    if r["completed"] and by_id[r["id"]]["group"] == group
                )
            )
            for group in sorted({r["group"] for r in results})
        },
        "negative_answers_preserved": [
            r["id"] for r in rows if r["completed"] and r["labels_match"] == "no"
        ],
    }
    receipt.mkdir()
    (receipt / "listening.json").write_bytes(raw)
    (receipt / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (receipt / "observations.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        keys = ("id", "completed", "labels_match", "comment") + extra_fields
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(keys)
        writer.writerows([r[k] for k in keys] for r in rows)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--experiment-dir", type=Path, default=ROOT / "reports/local/lab5_comparisons_v1"
    )
    args = parser.parse_args()
    receipt = import_comparisons(args.input, args.experiment_dir)
    print((receipt / "summary.json").read_text(encoding="utf-8"))
    print("Receipt:", receipt)


if __name__ == "__main__":
    main()
