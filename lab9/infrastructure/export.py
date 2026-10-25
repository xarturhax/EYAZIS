import csv
import json
from html import escape
from pathlib import Path


def export_journal(rows: list[dict[str, object]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "events.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = ["time", "source", "language", "text", "confidence", "status", "action", "message"]
    with (output / "events.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(
            {
                k: (
                    "'" + v
                    if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@"))
                    else v
                )
                for k, v in row.items()
            }
            for row in rows
        )
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(k, '')))}</td>" for k in fields) + "</tr>"
        for row in rows
    )
    (output / "report.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Журнал голосовых команд</title>'
        "<style>body{font:15px system-ui;margin:25px}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccd;padding:6px}@media print{button{display:none}}</style>"
        '<button onclick="window.print()">Печать</button><h1>Журнал распознавания</h1><table><tr>'
        + "".join(f"<th>{escape(k)}</th>" for k in fields)
        + "</tr>"
        + body
        + "</table></html>",
        encoding="utf-8",
    )
