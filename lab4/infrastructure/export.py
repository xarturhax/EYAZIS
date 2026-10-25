import csv
import json
from dataclasses import asdict
from html import escape
from pathlib import Path

from lab4.domain.models import Result, Sentence, children
from lab4.infrastructure.grammar import explain, tag_descriptions

COLUMNS = (
    "lemma",
    "translation",
    "frequency",
    "pos",
    "pos_description",
    "tags",
    "tag_descriptions",
    "wordforms",
    "morphology",
    "origin",
    "status",
)


def dictionary_rows(result: Result) -> list[tuple[str | int, ...]]:
    return [
        (
            e.lemma,
            e.translation,
            e.frequency,
            e.pos,
            explain(e.pos),
            ", ".join(e.tags),
            tag_descriptions(e.tags),
            "; ".join(f"{word}: {count}" for word, count in e.forms),
            "; ".join(e.morphology),
            e.origin,
            "covered" if e.covered else ("review" if e.translation else "missing"),
        )
        for e in result.entries
    ]


def tree_svg(sentence: Sentence) -> str:
    root, mapping = children(sentence)
    layout = []
    pending: list[tuple[int, int, int | None]] = [(root, 0, None)]
    while pending:
        index, depth, parent = pending.pop()
        layout.append((index, depth, parent))
        pending.extend((child, depth + 1, index) for child in reversed(mapping[index]))
    coordinates = {i: (35 + depth * 38, 32 + row * 32) for row, (i, depth, _) in enumerate(layout)}
    width = max(x + 650 for x, _ in coordinates.values())
    height = len(layout) * 32 + 30
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/>'
    ]
    for index, _, parent in layout:
        x, y = coordinates[index]
        if parent is not None:
            px, py = coordinates[parent]
            parts.append(f'<path d="M{px} {py} V{y} H{x}" fill="none" stroke="#7c9baf"/>')
        token = sentence.tokens[index]
        label = f"{index + 1}. {token.text}  [{token.pos}/{token.tag}]  {token.dependency}"
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="3" fill="#17695b"/>'
            f'<text x="{x + 9}" y="{y + 5}" font-family="sans-serif" font-size="15">'
            f"{escape(label)}</text>"
        )
    return "".join(parts) + "</svg>"


def export_report(result: Result, output: Path, selected: int = 0) -> Path:
    if not 0 <= selected < len(result.analysis.sentences):
        raise ValueError("Выберите существующее предложение.")
    output.mkdir(parents=True, exist_ok=True)
    rows = dictionary_rows(result)
    summary = (
        f"Лабораторная №4 · Вариант 12 · EN→FR\n\n"
        f"Исходных слов: {result.source_words}\n"
        f"Переведённых исходных слов (покрытие словарём): {result.translated_source_words}\n"
        f"Слов во французском тексте: {result.target_words}\n\n"
        "ИСХОДНЫЙ ТЕКСТ\n\n"
        + result.analysis.text
        + "\n\nПЕРЕВОД\n\n"
        + result.translation
        + "\n\nПРИМЕЧАНИЯ\n"
        + "\n".join(result.warnings)
    )
    if result.versions.get("source_attribution"):
        summary += "\n\nSOURCE\n" + "\n".join(
            result.versions.get("source_" + key, "")
            for key in ("title", "url", "attribution", "license")
        )
    dictionary_text = (
        "\t".join(COLUMNS)
        + "\n"
        + "\n".join(
            "\t".join(str(value).replace("\t", " ").replace("\n", " ") for value in row)
            for row in rows
        )
    )
    (output / "translation.txt").write_text(summary, encoding="utf-8-sig")
    (output / "dictionary.txt").write_text(dictionary_text, encoding="utf-8-sig")
    with (output / "dictionary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        # Prefix formula-like cells for safe spreadsheet viewing; TXT/JSON stay exact.
        writer.writerows(
            [
                ("'" + v) if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v
                for v in row
            ]
            for row in rows
        )
    (output / "results.json").write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sentence = result.analysis.sentences[selected]
    svg = tree_svg(sentence)
    (output / "tree.svg").write_text(svg, encoding="utf-8")
    details = "".join(
        f"<tr>{''.join('<td>' + escape(str(value)) + '</td>' for value in row)}</tr>"
        for row in rows
    )
    heads = "".join(f"<th>{escape(column)}</th>" for column in COLUMNS)
    html = (
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Лабораторная 4</title>'
        "<style>body{font:15px/1.5 system-ui;margin:25px;color:#193047}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;table-layout:fixed;overflow-wrap:anywhere}"
        "td,th{border:1px solid #ccd6de;padding:5px}svg{max-width:100%;height:auto}"
        "@page{size:A4 landscape;margin:12mm}@media print{button{display:none}table{font-size:9px}}</style><body>"
        '<button onclick="window.print()">Печать / PDF</button>'
        '<p><a href="translation.txt">Unicode TXT: перевод</a> · '
        '<a href="dictionary.txt">Unicode TXT: словарь</a></p>'
        f"<pre>{escape(summary)}</pre><h2>Частотный словарь</h2><table><tr>{heads}</tr>"
        f"{details}</table><h2>Дерево зависимостей предложения {selected + 1}</h2>"
        f"<p>{escape(sentence.text)}</p>{svg}<h2>Параметры</h2>"
        f"<pre>{escape(json.dumps(result.versions | {'timings': result.timings}, ensure_ascii=False, indent=2))}</pre>"
        "</body></html>"
    )
    target = output / "report.html"
    target.write_text(html, encoding="utf-8")
    return target
