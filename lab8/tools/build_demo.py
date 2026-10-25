"""Generate reproducible French TTS examples without playing them on speakers."""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

from lab8.bootstrap import ROOT, build_service
from lab8.domain.models import Settings
from lab8.infrastructure.export import metadata, report
from lab8.tools.download_voices import MODELS

CASES = (
    ("hugo_siwis", "essai_hugo", "siwis", 1.0, 0.8),
    ("fable_siwis", "essai_fable", "siwis", 1.0, 0.8),
    ("hugo_tom", "essai_hugo", "tom", 1.0, 0.8),
    ("fable_tom", "essai_fable", "tom", 1.0, 0.8),
    ("hugo_slow", "essai_hugo", "siwis", 0.75, 0.8),
    ("hugo_fast", "essai_hugo", "siwis", 1.5, 0.8),
    ("hugo_quiet", "essai_hugo", "siwis", 1.0, 0.4),
    ("hugo_muted", "essai_hugo", "siwis", 1.0, 0.0),
)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Generate French TTS examples")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/demo")
    output = parser.parse_args().output
    service = build_service()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for name, text_id, voice, speed, volume in CASES:
        target = output / f"{name}.wav"
        if target.exists():
            raise FileExistsError(
                "Демо уже существует; используйте новую папку или сохраните предыдущие результаты."
            )
        text = (ROOT / "data" / f"{text_id}.txt").read_text(encoding="utf-8")
        result = service.render(
            text,
            Settings(voice, speed, volume),
            target,
            progress=lambda message: print(message, flush=True),
        )
        report(result)
        results.append((name, result))
        print(name, f"{result.duration:.2f}s", flush=True)
    payload = [{"id": name, **metadata(result)} for name, result in results]
    (output / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "id",
        "voice",
        "speed",
        "volume",
        "duration",
        "synthesis_seconds",
        "initialization_seconds",
        "peak",
        "rms",
    ]
    with (output / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, r in results:
            writer.writerow(
                dict(
                    id=name,
                    voice=r.settings.voice,
                    speed=r.settings.speed,
                    volume=r.settings.volume,
                    duration=r.duration,
                    synthesis_seconds=r.synthesis_seconds,
                    initialization_seconds=r.initialization_seconds,
                    peak=r.peak,
                    rms=r.rms,
                )
            )
    assessment = output / "listening.csv"
    if not assessment.exists():
        with assessment.open("w", encoding="utf-8-sig", newline="") as stream:
            assessment_writer = csv.writer(stream)
            assessment_writer.writerow(
                ["id", "intelligibility_1_5", "naturalness_1_5", "proper_names_comment", "reviewer"]
            )
            assessment_writer.writerows((name, "", "", "", "") for name, _ in results)
    cards = output / "voice_cards"
    cards.mkdir(exist_ok=True)
    for name in ("siwis", "tom"):
        shutil.copyfile(MODELS / name / "MODEL_CARD", cards / f"{name}.md")
    rows = "".join(
        f'<tr><td><a href="{name}.html">{name}</a></td><td>{r.settings.voice}</td>'
        f"<td>{r.settings.speed:.2f}×</td><td>{r.settings.volume:.0%}</td>"
        f"<td>{r.duration:.2f}</td><td>{r.synthesis_seconds:.3f}</td>"
        f'<td><audio controls preload="none" src="{name}.wav"></audio></td></tr>'
        for name, r in results
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Лабораторная 8</title>'
        "<style>body{font:16px system-ui;margin:30px;color:#193047}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccd;padding:8px}audio{width:240px} "
        '@media print{audio,button{display:none}}</style><button onclick="window.print()">Печать</button>'
        "<h1>Французский синтез речи · вариант 8</h1>"
        "<p>Оригинальные учебные сочинения по литературе. Синтез выполнен локально Piper."
        " Громкость 0% — намеренная тишина. Слуховые оценки ещё не заполнены.</p>"
        "<table><tr><th>Пример</th><th>Голос</th><th>Темп</th><th>Громкость</th>"
        "<th>Длительность, с</th><th>Синтез, с</th><th>Прослушать</th></tr>"
        + rows
        + "</table><p>Модели загружаются один раз на голос; время инициализации "
        "показано отдельно в JSON. Синтез без динамиков проверен автоматически; "
        "физическая слышимость и субъективное качество требуют проверки пользователем.</p>"
        '<p>Карточки источников: <a href="voice_cards/siwis.md">Siwis</a> · '
        '<a href="voice_cards/tom.md">Tom</a>.</p></html>',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
