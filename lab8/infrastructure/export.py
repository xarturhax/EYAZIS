import json
import shutil
from dataclasses import asdict, replace
from html import escape
from pathlib import Path
from urllib.parse import quote

from lab8.domain.models import Result, output_paths


def metadata(result: Result) -> dict[str, object]:
    data = asdict(result)
    data["wav_path"] = str(result.wav_path)
    data["real_time_factor"] = result.synthesis_seconds / result.duration
    data["auditory_evaluation"] = "PENDING_HUMAN_LISTENING"
    return data


def report(result: Result) -> None:
    target = result.wav_path
    if any(path.exists() for path in output_paths(target)[1:]):
        raise FileExistsError("Report files already exist; choose another name.")
    data = metadata(result)
    target.with_suffix(".json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    target.with_suffix(".txt").write_text(result.text, encoding="utf-8-sig")
    target.with_suffix(".html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        "<title>Лабораторная 8 · Французский синтез</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:950px;margin:30px auto;padding:0 20px}"
        "pre{white-space:pre-wrap} @media print{button,audio{display:none}}</style>"
        '<button onclick="window.print()">Печать</button><h1>Синтез французской речи · вариант 8</h1>'
        f'<audio controls src="{escape(quote(target.name), quote=True)}"></audio>'
        f'<h2>Текст</h2><p lang="fr">{escape(result.text)}</p>'
        f"<h2>Настройки и замеры</h2><pre>{escape(json.dumps(data, ensure_ascii=False, indent=2))}</pre>"
        "<p>Синтез выполнен локально Piper. Темп — относительный коэффициент, "
        "не заявленные слова в минуту. Качество произношения и естественность "
        "требуют прослушивания; автоматической оценки MOS нет.</p></html>",
        encoding="utf-8",
    )


def export(result: Result, target: Path) -> Result:
    if any(path.exists() for path in output_paths(target)):
        raise FileExistsError("Файл уже существует. Выберите новое имя.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with result.wav_path.open("rb") as source, target.open("xb") as output:
        shutil.copyfileobj(source, output)
    saved = replace(result, wav_path=target)
    report(saved)
    return saved
