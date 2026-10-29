"""Validate and archive human synthesis assessments against immutable WAV hashes."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from lab5_7.application.project import ROOT


def validate_assessment(
    data: dict[str, Any], results: list[dict[str, Any]], digest: str
) -> list[dict[str, Any]]:
    if (
        data.get("schema") != 1
        or data.get("assessment_kind") != "LAB7_SYNTHESIS_LISTENING"
        or data.get("manifest_sha256") != digest
    ):
        raise ValueError("Assessment does not match this synthesis manifest.")
    rows = data.get("results")
    if not isinstance(rows, list) or len(rows) != len(results):
        raise ValueError("Expected one assessment entry per result.")
    by_id = {r["id"]: r for r in results}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Invalid result entry.")
        ident = row["id"]
        if ident not in by_id or ident in seen:
            raise ValueError("Unknown or duplicate result.")
        seen.add(ident)
        if any(row.get(k) != by_id[ident][k] for k in ("sha256", "reference_sha256")):
            raise ValueError("Result or reference audio hash changed.")
        if type(row.get("completed")) is not bool or not isinstance(row.get("comment", ""), str):
            raise ValueError("Explicit completion flag and text comment required.")
        for key in ("intelligibility_1_5", "naturalness_1_5"):
            value = row.get(key)
            if not row["completed"] and value in (None, ""):
                continue
            if type(value) is not int or not 1 <= value <= 5:
                raise ValueError("Invalid or missing score: " + key)
    return rows


def import_assessment(path: Path, folder: Path) -> Path:
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Assessment exceeds 2 MiB.")
    canonical = (folder / "results.json").read_bytes()
    results = json.loads(canonical)["results"]
    rows = validate_assessment(
        json.loads(raw.decode("utf-8-sig")), results, hashlib.sha256(canonical).hexdigest()
    )
    base = folder.resolve()
    for result in results:
        for field, digest in (("wav", "sha256"), ("reference_wav", "reference_sha256")):
            audio = (base / result[field]).resolve()
            if (
                not audio.is_relative_to(base)
                or hashlib.sha256(audio.read_bytes()).hexdigest() != result[digest]
            ):
                raise ValueError("Synthesis or reference WAV changed: " + result["id"])
    receipt = folder / ("listening_import-" + hashlib.sha256(raw).hexdigest()[:16])
    if receipt.exists():
        if (receipt / "listening.json").read_bytes() != raw:
            raise ValueError("Conflicting import receipt.")
        return receipt
    by_id = {r["id"]: r for r in results}
    groups = {}
    for category in sorted({r["category"] for r in results}):
        group = [r for r in rows if r["completed"] and by_id[r["id"]]["category"] == category]
        groups[category] = {
            "count": len(group),
            **{
                key: sum(r[key] for r in group) / len(group) if group else None
                for key in ("intelligibility_1_5", "naturalness_1_5")
            },
        }
    summary = {"completed": sum(r["completed"] for r in rows), "total": len(rows), "groups": groups}
    receipt.mkdir()
    (receipt / "listening.json").write_bytes(raw)
    (receipt / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (receipt / "ratings.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        keys = ("id", "completed", "intelligibility_1_5", "naturalness_1_5", "comment")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(keys)
        writer.writerows([r.get(k, "") for k in keys] for r in rows)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--experiment-dir", type=Path, default=ROOT / "reports/local/lab7_synthesis_v2"
    )
    args = parser.parse_args()
    receipt = import_assessment(args.input, args.experiment_dir)
    print((receipt / "summary.json").read_text(encoding="utf-8"))
    print("Receipt:", receipt)


if __name__ == "__main__":
    main()
