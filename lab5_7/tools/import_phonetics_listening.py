"""Archive human vowel/noise-loop observations with source and WAV verification."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from lab5_7.application.project import ROOT, segment_path


def validate_observations(
    data: dict[str, Any], results: list[dict[str, Any]], digest: str
) -> list[dict[str, Any]]:
    if (
        data.get("schema") != 1
        or data.get("assessment_kind") != "LAB5_PHONETICS_LISTENING"
        or data.get("manifest_sha256") != digest
    ):
        raise ValueError("Observations do not match the phonetics experiment.")
    rows = data.get("results")
    if not isinstance(rows, list) or len(rows) != len(results):
        raise ValueError("Expected one observation per result.")
    expected = {r["id"]: r for r in results}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Invalid observation entry.")
        ident = row["id"]
        if ident not in expected or ident in seen:
            raise ValueError("Unknown or duplicate observation.")
        seen.add(ident)
        if row.get("loop_sha256") != expected[ident]["loop_sha256"]:
            raise ValueError("Loop audio hash changed.")
        if type(row.get("completed")) is not bool or not isinstance(row.get("comment", ""), str):
            raise ValueError("Explicit completion flag and text comment required.")
        allowed = {"similar", "partly", "different", "unclear"}
        if not row["completed"]:
            allowed.add("")
        if (
            not isinstance(row.get("loop_resemblance"), str)
            or row["loop_resemblance"] not in allowed
        ):
            raise ValueError("Invalid or missing loop comparison.")
    return rows


def import_observations(path: Path, folder: Path) -> Path:
    raw = path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Observations exceed 2 MiB.")
    canonical = (folder / "results.json").read_bytes()
    results = json.loads(canonical)["results"]
    rows = validate_observations(
        json.loads(raw.decode("utf-8-sig")), results, hashlib.sha256(canonical).hexdigest()
    )
    base = folder.resolve()
    for result in results:
        loop = (base / result["loop_wav"]).resolve()
        if (
            not loop.is_relative_to(base)
            or hashlib.sha256(loop.read_bytes()).hexdigest() != result["loop_sha256"]
        ):
            raise ValueError("Loop WAV changed: " + result["id"])
        source = segment_path(result["confirmed_segment"]["file"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != result["source"]["sha256"]:
            raise ValueError("Source recording changed: " + result["id"])
    receipt = folder / ("listening_import-" + hashlib.sha256(raw).hexdigest()[:16])
    if receipt.exists():
        if (receipt / "listening.json").read_bytes() != raw:
            raise ValueError("Conflicting observation receipt.")
        return receipt
    by_id = {r["id"]: r for r in results}
    summary = {
        "completed": sum(r["completed"] for r in rows),
        "total": len(rows),
        "groups": {
            kind: dict(
                Counter(
                    r["loop_resemblance"]
                    for r in rows
                    if r["completed"] and by_id[r["id"]]["kind"] == kind
                )
            )
            for kind in sorted({r["kind"] for r in results})
        },
    }
    receipt.mkdir()
    (receipt / "listening.json").write_bytes(raw)
    (receipt / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (receipt / "observations.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        keys = ("id", "completed", "loop_resemblance", "comment")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(keys)
        writer.writerows([r.get(k, "") for k in keys] for r in rows)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--experiment-dir", type=Path, default=ROOT / "reports/local/lab5_phonetics_v1"
    )
    args = parser.parse_args()
    receipt = import_observations(args.input, args.experiment_dir)
    print((receipt / "summary.json").read_text(encoding="utf-8"))
    print("Receipt:", receipt)


if __name__ == "__main__":
    main()
