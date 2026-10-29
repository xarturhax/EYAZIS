"""Import perceived natural prosody and explicitly uncertain accent/syntagm counts."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from lab5_7.application.project import ROOT
from lab5_7.tools.import_comparisons import import_comparisons, validate_comparisons

KIND = "LAB6_SOURCE_OBSERVATIONS"
FIELDS = ("heard_label", "accent_groups", "syntagms")


def validate_source_observations(
    data: dict[str, Any], results: list[dict[str, Any]], digest: str
) -> list[dict[str, Any]]:
    rows = validate_comparisons(data, results, digest, KIND)
    by_id = {r["id"]: r for r in results}
    for row in rows:
        original = by_id[row["id"]]
        if any(not isinstance(row.get(k), str) for k in FIELDS):
            raise ValueError("Perceived labels and counts must be explicit strings.")
        options = {o[0] for o in original["options"]}
        if row["heard_label"] not in options | ({""} if not row["completed"] else set()):
            raise ValueError("Invalid or missing perceived label.")
        for key in ("accent_groups", "syntagms"):
            allowed = {"1", "2", "3", "4", "5", "6", "unclear", ""}
            if row["completed"] and original["count_groups"]:
                allowed.remove("")
            if row[key] not in allowed:
                raise ValueError("Invalid or missing group count.")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--experiment-dir", type=Path, default=ROOT / "reports/local/lab6_source_observations_v1"
    )
    args = parser.parse_args()
    raw = args.input.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Observations exceed 2 MiB.")
    canonical = (args.experiment_dir / "results.json").read_bytes()
    results = json.loads(canonical)["results"]
    rows = validate_source_observations(
        json.loads(raw.decode("utf-8-sig")), results, hashlib.sha256(canonical).hexdigest()
    )
    receipt = import_comparisons(
        args.input, args.experiment_dir, assessment_kind=KIND, extra_fields=FIELDS
    )
    by_id = {r["id"]: r for r in results}
    summary = {
        "completed": sum(r["completed"] for r in rows),
        "groups": {
            group: dict(
                Counter(
                    r["heard_label"]
                    for r in rows
                    if r["completed"] and by_id[r["id"]]["group"] == group
                )
            )
            for group in sorted({r["group"] for r in results})
        },
        "counts": {
            r["id"]: {k: r[k] for k in ("accent_groups", "syntagms")}
            for r in rows
            if r["completed"] and by_id[r["id"]]["count_groups"]
        },
    }
    (receipt / "prosody_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print("Receipt:", receipt)


if __name__ == "__main__":
    main()
