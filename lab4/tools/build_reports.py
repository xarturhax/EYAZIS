"""Build all four demonstration reports with a fresh temporary dictionary."""

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from lab4.bootstrap import ROOT, build_service
from lab4.infrastructure.export import export_report


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    output = ROOT / "reports/demo"
    output.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((ROOT / "data/demo/provenance.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as temporary:
        service, _ = build_service(Path(temporary) / "lexicon.sqlite3")
        for name, domain in (
            ("medicine", "medicine"),
            ("art", "art"),
            ("source_medicine", "medicine"),
            ("source_art", "art"),
        ):
            source = ROOT / f"data/demo/{name}.txt"
            result = service.run(
                source.read_text(encoding="utf-8"),
                domain,
                progress=lambda message: print(message, flush=True),
            )
            metadata = next((r for r in provenance if r["path"] == source.name), None)
            if metadata:
                result = replace(
                    result,
                    versions=result.versions
                    | {
                        f"source_{key}": str(metadata[key])
                        for key in ("title", "url", "attribution", "license")
                    },
                )
            export_report(result, output / name)
            print(
                name,
                result.source_words,
                result.translated_source_words,
                result.target_words,
                flush=True,
            )
    (output / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        "<title>Лабораторная 4 — примеры</title><h1>Лабораторная 4 · EN→FR</h1>"
        '<p>Короткие учебные примеры: <a href="medicine/report.html">медицина</a> · '
        '<a href="art/report.html">художественная критика</a></p>'
        '<p>Фрагменты реальных источников: <a href="source_medicine/report.html">'
        'медицинская статья</a> · <a href="source_art/report.html">художественная критика</a></p>'
        "<p>В каждом отчёте: перевод, грамматический словарь, дерево, TXT и печать.</p>",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
