"""Validate user-reviewed intervals before writing the actual speech bank CSV."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from lab5_7.application.project import ROOT, segment_path, segments


def validate_review(
    data: dict[str, Any], candidates: list[dict[str, Any]], manifest: str
) -> list[dict[str, Any]]:
    if (
        data.get("schema") != 1
        or data.get("assessment_kind") != "BOUNDARY_AND_LABEL_REVIEW"
        or data.get("manifest_sha256") != manifest
    ):
        raise ValueError("Review does not match the annotation manifest.")
    rows = data.get("segments")
    if not isinstance(rows, list) or len(rows) != len(candidates):
        raise ValueError("Expected one review entry per candidate.")
    by_id = {r["id"]: r for r in candidates}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("id") not in by_id or row["id"] in seen:
            raise ValueError("Unknown or duplicate segment.")
        seen.add(row["id"])
        original = by_id[row["id"]]
        if (
            row.get("file") != original["file"]
            or row.get("source_sha256") != original["source_sha256"]
        ):
            raise ValueError("Source file or hash changed.")
        start, end = row.get("start"), row.get("end")
        if type(start) not in (int, float) or type(end) not in (int, float):
            raise ValueError("Numeric boundaries are required.")
        assert isinstance(start, (int, float)) and isinstance(end, (int, float))
        start, end = float(start), float(end)
        if not math.isfinite(start) or not math.isfinite(end):
            raise ValueError("Finite numeric boundaries are required.")
        if not original["context_start"] - 1e-6 <= start < end <= original["context_end"] + 1e-6:
            raise ValueError("Boundaries leave the reviewed context.")
        if type(row.get("reviewed")) is not bool or not isinstance(
            row.get("review_comment", ""), str
        ):
            raise ValueError("Explicit review status and text comment required.")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--manifest-dir", type=Path, default=ROOT / "reports/local/annotation_v2")
    args = parser.parse_args()
    if args.input.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Review JSON exceeds 2 MiB.")
    candidates = json.loads((args.manifest_dir / "candidates.json").read_text(encoding="utf-8"))
    metadata = json.loads((args.manifest_dir / "manifest.json").read_text(encoding="utf-8"))
    canonical = (args.manifest_dir / "candidates.json").read_bytes()
    if hashlib.sha256(canonical).hexdigest() != metadata["manifest_sha256"]:
        raise ValueError("Candidate manifest changed.")
    data = json.loads(args.input.read_text(encoding="utf-8-sig"))
    reviewed = validate_review(data, candidates, metadata["manifest_sha256"])
    for name, digest in metadata["source_hashes"].items():
        if hashlib.sha256(segment_path(name).read_bytes()).hexdigest() != digest:
            raise ValueError("Original recording changed: " + name)
    approved = {r["id"]: r for r in reviewed if r["reviewed"]}
    if not approved:
        raise ValueError("No intervals were confirmed; CSV remains unchanged.")
    rows = segments()
    changed = []
    for row in rows:
        if row["id"] in approved:
            update = approved[row["id"]]
            row["start"], row["end"], row["reviewed"] = (
                str(update["start"]),
                str(update["end"]),
                "yes",
            )
            comment = update.get("review_comment", "")
            row["note"] = "Human-reviewed." + (" " + comment if comment else "")
            changed.append(row["id"])
    # Store a snapshot before changing the authoritative CSV; no silent overwrites.
    receipt = (
        ROOT
        / "reports/local"
        / ("annotation_import-" + hashlib.sha256(args.input.read_bytes()).hexdigest()[:16])
    )
    receipt.mkdir(parents=True, exist_ok=False)
    target = ROOT / "data/segments.csv"
    (receipt / "segments_before.csv").write_bytes(target.read_bytes())
    (receipt / "review.json").write_bytes(args.input.read_bytes())
    temporary = target.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["id", "file", "start", "end", "kind", "reviewed", "note"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(target)
    print("Imported", len(changed), "human-confirmed intervals; others preserved")
    print("Snapshot:", receipt)


if __name__ == "__main__":
    main()
