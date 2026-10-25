"""CSV intervals -> Praat TextGrid, preserving empty gaps and explicit human labels."""

from pathlib import Path

from lab5_7.application.project import segment_path, segments
from lab5_7.infrastructure.wav import load


def textgrid(path: Path, output: Path) -> None:
    audio, _ = load(path)
    rows = [
        r
        for r in segments()
        if segment_path(r["file"]) == path.resolve() and r["start"] and r["end"]
    ]
    tiers: dict[str, list[tuple[float, float, str]]] = {}
    for row in rows:
        tiers.setdefault(row["kind"], []).append(
            (float(row["start"]), float(row["end"]), row["id"])
        )
    if not tiers:
        tiers["segments"] = []
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {audio.duration}",
        "tiers? <exists>",
        f"size = {len(tiers)}",
        "item []:",
    ]
    for index, (name, intervals) in enumerate(sorted(tiers.items()), 1):
        filled = []
        cursor = 0.0
        for start, end, label in sorted(intervals):
            if not 0 <= start < end <= audio.duration or start < cursor:
                raise ValueError("Интервалы одного уровня перекрываются или выходят за WAV.")
            if start > cursor:
                filled.append((cursor, start, ""))
            filled.append((start, end, label))
            cursor = end
        if cursor < audio.duration:
            filled.append((cursor, audio.duration, ""))
        lines.extend(
            [
                f"    item [{index}]:",
                '        class = "IntervalTier"',
                f'        name = "{name}"',
                "        xmin = 0",
                f"        xmax = {audio.duration}",
                f"        intervals: size = {len(filled)}",
            ]
        )
        for j, (start, end, label) in enumerate(filled, 1):
            lines.extend(
                [
                    f"        intervals [{j}]:",
                    f"            xmin = {start}",
                    f"            xmax = {end}",
                    f'            text = "{label.replace(chr(34), chr(34) * 2)}"',
                ]
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("TextGrid уже существует; выберите новое имя.")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
