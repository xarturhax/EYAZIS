import csv
import json
from pathlib import Path

from lab5_7.infrastructure.wav import load

ROOT = Path(__file__).resolve().parents[1]


def tasks() -> list[dict[str, object]]:
    return json.loads((ROOT / "data/tasks.json").read_text(encoding="utf-8"))


def recording_path(identifier: str) -> Path:
    if identifier not in {t["id"] for t in tasks()}:
        raise ValueError("Неизвестный идентификатор записи.")
    return ROOT / "data/raw" / f"{identifier}.wav"


def status() -> list[dict[str, object]]:
    result = []
    for task in tasks():
        path = recording_path(str(task["id"]))
        state, note = "MISSING", ""
        if path.exists():
            try:
                _, metadata = load(path)
                state = "PRESENT_NOT_REVIEWED"
                note = f"{metadata['rate']} Hz, {metadata['subtype']}"
            except (ValueError, RuntimeError) as error:
                state, note = "INVALID", str(error)
        result.append(task | {"path": str(path), "state": state, "note": note})
    return result


def segments() -> list[dict[str, str]]:
    with (ROOT / "data/segments.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Идентификаторы сегментов должны быть уникальны.")
    return rows


def segment_path(filename: str) -> Path:
    base = (ROOT / "data/raw").resolve()
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Сегменты должны ссылаться на data/raw.")
    return target


def export_status(output: Path) -> None:
    from html import escape

    rows = status()
    output.mkdir(parents=True, exist_ok=True)
    (output / "status.json").write_text(
        json.dumps(
            {"experiment_state": "AWAITING_RECORDINGS_OR_REVIEW", "recordings": rows},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    body = "".join(
        f"<tr><td>{escape(str(r['id']))}</td><td>{escape(str(r['prompt']))}</td>"
        f"<td>{r['state']}</td><td>{escape(str(r['note']))}</td></tr>"
        for r in rows
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        "<title>Лабораторные 5–7: состояние</title>"
        "<style>body{font:16px system-ui;margin:30px}td,th{border:1px solid #ccc;padding:8px}"
        "table{border-collapse:collapse} @media print{button{display:none}}</style>"
        '<button onclick="window.print()">Печать</button><h1>Лабораторные №5–7</h1>'
        "<p>Присутствие WAV не означает завершение эксперимента. Требуются проверка разметки, "
        "прослушивание, измерения и выводы. Синтетические технические примеры не заменяют голос.</p>"
        "<table><tr><th>Файл</th><th>Что записать</th><th>Состояние</th><th>Формат</th></tr>"
        + body
        + "</table></html>",
        encoding="utf-8",
    )
