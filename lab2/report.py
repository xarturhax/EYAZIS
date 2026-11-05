from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lab2.logic import LANGUAGE_NAMES, METHOD_NAMES, ExperimentReport, LabError

FLOWCHART = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 350" role="img"
aria-label="Алгоритм распознавания языка">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3"
orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#315b83"/></marker></defs>
<g fill="#eef4fa" stroke="#315b83" stroke-width="2">
<rect x="300" y="5" width="400" height="45" rx="8"/>
<rect x="260" y="75" width="480" height="45" rx="8"/>
<rect x="20" y="160" width="280" height="50" rx="8"/>
<rect x="360" y="160" width="280" height="50" rx="8"/>
<rect x="700" y="160" width="280" height="50" rx="8"/>
<rect x="260" y="250" width="480" height="45" rx="8"/>
<path d="M500 50 V72 M500 120 V140 H160 V157 M500 140 V157 M500 140 H840 V157
M160 210 V230 H500 V247 M500 210 V247 M840 210 V230 H500"
fill="none" marker-end="url(#arrow)"/>
</g><g text-anchor="middle" font-family="sans-serif" font-size="16" fill="#172338">
<text x="500" y="33">PDF → текст → проверка train/test</text>
<text x="500" y="103">Языковые профили: обучение только на train</text>
<text x="160" y="190">Короткие слова: log-оценка</text>
<text x="500" y="190">Частоты букв: L1</text>
<text x="840" y="190">Символьный TF-IDF → MLP</text>
<text x="500" y="278">Предсказания на test → метрики → отчёт</text>
<text x="500" y="330">Эталонный язык test используется только для оценки качества</text>
</g></svg>"""

ARCHITECTURE = """<h2>Структура системы и данных</h2>
<p>Окно main.py напрямую запускает Experiment из logic.py. files.py читает PDF и
манифест, models.py описывает данные, report.py сохраняет таблицы и графики.
Длительные вычисления выполняются в рабочем потоке; элементы Tkinter обновляются
в главном потоке. Сервер и промежуточные архитектурные слои отсутствуют.</p>
<p>CorpusEntry: путь, роль, эталонный язык, источник. Document: текст, число страниц,
хеш. Prediction: выбранный язык, оценки и объяснение. ResultRow: результат одного PDF.
ExperimentReport: параметры, профили, времена, метрики и версии библиотек.
JSON-манифест заменяет базу данных для этой небольшой коллекции.</p>
<h2>Схема алгоритма</h2><img src="algorithm.svg" alt="Схема трёх методов">
<h2>Используемые библиотеки</h2>
<p>pypdf извлекает текст; scikit-learn реализует TF-IDF и MLP; NumPy/SciPy выполняют
численные операции; Matplotlib строит диаграммы; ReportLab создаёт учебные PDF.
Tkinter, JSON, CSV и logging обеспечивают интерфейс, хранение и диагностику.</p>
<p>Документация:
<a href="https://pypdf.readthedocs.io/en/stable/user/extract-text.html">pypdf</a>,
<a href="https://scikit-learn.org/stable/modules/neural_networks_supervised.html">MLP</a>.
Исходники демо и лицензии находятся в data/demo/sources, библиография — provenance.json.</p>"""


def charts(report: ExperimentReport) -> Any:
    from matplotlib.figure import Figure

    figure = Figure(figsize=(11, 4), layout="constrained")
    accuracy, time = figure.subplots(1, 2)
    names = list(METHOD_NAMES)
    labels = ["Короткие слова", "Алфавитный", "Нейросеть"]
    values = [report.metrics[m]["accuracy"] for m in names]
    if any(v is not None for v in values):
        accuracy.bar(
            labels,
            [100 * float(v) if v is not None else 0 for v in values],
            color=["#3264a8", "#248570", "#8a5ac2"],
        )
        accuracy.set_ylim(0, 105)
        accuracy.set_ylabel("Точность, %")
    else:
        accuracy.text(0.5, 0.5, "Нет эталонных меток", ha="center")
    accuracy.set_title("Точность на размеченных PDF")
    time.bar(labels, [report.metrics[m]["mean_ms"] for m in names], color="#3264a8")
    time.set_ylabel("Среднее медиан, мс")
    time.set_title("Время распознавания")
    return figure


def _table(headers: list[str], rows: list[list[str]]) -> str:
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{html.escape(v)}</th>" for v in headers)
        + (
            "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows)
            + "</tbody></table>"
        )
    )


def render_html(report: ExperimentReport, chart_name: str = "comparison.svg") -> str:
    esc = html.escape
    summaries = []
    for name, label in METHOD_NAMES.items():
        m = report.metrics[name]
        accuracy = "нет разметки" if m["accuracy"] is None else f"{m['accuracy']:.1%}"
        summaries.append(
            [
                label,
                accuracy,
                str(m["correct"]),
                str(m["labeled"]),
                str(m["abstentions"]),
                f"{m['mean_ms']:.4f}",
                f"{report.training_seconds[name]:.4f}",
            ]
        )
    results = []
    for row in report.rows:
        link = f'<a href="{esc(Path(row.path).as_uri(), quote=True)}">{esc(row.title)}</a>'
        if row.source_url.startswith(("http://", "https://")):
            link += f' <a href="{esc(row.source_url, quote=True)}">источник</a>'
        results.append(
            [
                link,
                LANGUAGE_NAMES[row.expected or "?"],
                *[LANGUAGE_NAMES[row.predictions[m].language or "?"] for m in METHOD_NAMES],
                str(row.characters),
                str(row.pages),
            ]
        )
    confusion = ""
    for method, label in METHOD_NAMES.items():
        matrix = report.metrics[method]["confusion"]
        confusion += (
            "<h3>"
            + label
            + "</h3>"
            + _table(
                ["Эталон / предсказание", "EN", "ES", "Отказ"],
                [
                    [lang, *[str(matrix[lang][p]) for p in ("en", "es", "?")]]
                    for lang in ("en", "es")
                ],
            )
        )
    details = ""
    for row in report.rows:
        details += "<details><summary>" + esc(row.title) + "</summary>"
        for method, prediction in row.predictions.items():
            details += f"<p><b>{METHOD_NAMES[method]}</b>: {esc(prediction.score_kind)}<br>"
            details += esc(json.dumps(prediction.scores, ensure_ascii=False))
            details += "<br>" + esc(prediction.explanation) + "</p>"
        details += "<p>" + esc("; ".join(row.warnings)) + "</p></details>"
    warnings = "".join("<li>" + esc(n) + "</li>" for n in report.warnings)
    sources = _table(
        ["Обучающий PDF", "Язык", "Источник", "UTF-8 байт"],
        [
            [
                esc(Path(str(d["path"])).name),
                esc(str(d["language"])),
                esc(str(d["source_id"])),
                str(d["utf8_bytes"]),
            ]
            for d in report.training
        ],
    )
    # Все внешние строки экранируются; единственный скрипт — системный диалог печати.
    return f"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Лабораторная 2 — вариант 36</title>
<style>
body{{font:16px system-ui,sans-serif;max-width:1150px;margin:32px auto;padding:0 24px;color:#172338}}
h1,h2,h3{{color:#214b78}}table{{border-collapse:collapse;width:100%;margin:18px 0}}
th,td{{border:1px solid #ccd6e0;padding:8px;text-align:left}}th{{background:#edf3fa}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{max-width:100%}}
button{{padding:10px 18px}}details{{margin:12px 0}}
@media print{{button{{display:none}}body{{font-size:10pt;margin:0}}
tr{{break-inside:avoid}}a{{color:inherit}}}}
</style>
<h1>Автоматическое распознавание языка текста</h1>
<p>Лабораторная №2 · Вариант 36 · Английский / испанский · {esc(report.created_at)}</p>
<button onclick="window.print()">Распечатать / сохранить в PDF</button>
{ARCHITECTURE}
<h2>Методика</h2>
<p>Обучение и проверка разделены по исходным документам. Все методы используют один текстовый
слой PDF. Короткие слова: сглаженные вероятности слов длиной до 5 (параметр изменяемый).
Алфавитный метод: L1-расстояние частот одиночных букв. Нейросеть: символьный TF-IDF 2–4
и MLP с одним скрытым слоем. Подробные параметры и профили приведены ниже.</p>
<p>Размер обучения измеряется в байтах нормализованного UTF-8 текста, без PDF-контейнера.
Чтение PDF заняло {report.parsing_seconds:.4f} с. Время распознавания: медиана
{report.settings["repetitions"]} повторов после одного прогрева, затем среднее по документам.
Импорт библиотек, чтение PDF и обучение исключены из времени распознавания.
Обучение измерено отдельным запуском; значения времени зависят от компьютера.</p>
<h2>Сводная статистика</h2>
{_table(["Метод", "Accuracy", "Верно", "Размечено", "Отказов (все)", "Распознавание, мс", "Обучение, с"], summaries)}
<p>Отказы на размеченных документах считаются ошибками. Неразмеченные PDF исключены из
accuracy/F1. EN и ES — единственные классы; надёжного обнаружения любого третьего языка нет.</p>
<img src="{esc(chart_name)}" alt="Сравнение точности и времени">
<h2>Результаты по документам</h2>
{_table(["Документ", "Эталон", "Короткие слова", "Алфавитный", "Нейросеть", "Символов", "Страниц"], results)}
<h2>Матрицы ошибок</h2>{confusion}
<h2>Оценки и объяснения</h2>{details}
<h2>Замечания</h2><ul>{warnings}</ul>
<p>Демонстрационная коллекция состоит из отрывков литературы. Высокая точность на ней
не доказывает переносимость на новости, научные тексты, OCR и короткие сообщения.
Отрывки одной книги статистически зависимы. Оценки моделей не являются
калиброванной вероятностью правильного ответа.</p>
<h2>Обучающая коллекция</h2>{sources}
<h2>Параметры</h2><pre>{esc(json.dumps(report.settings, ensure_ascii=False, indent=2))}</pre>
<h2>Профили и нейросеть</h2><details><summary>Раскрыть полные профили</summary><pre>{esc(json.dumps(report.profiles, ensure_ascii=False, indent=2))}</pre>
</details><h2>Среда</h2><pre>{esc(json.dumps(report.versions, ensure_ascii=False, indent=2))}</pre>
<p>Полные данные: <a href="metrics.json">JSON</a>, <a href="results.csv">результаты CSV</a>,
<a href="summary.csv">сводка CSV</a>.</p></html>"""


def export_report(report: ExperimentReport, directory: Path) -> Path:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".lab2-", dir=directory) as temporary:
            stage = Path(temporary)
            (stage / "algorithm.svg").write_text(FLOWCHART, encoding="utf-8")
            (stage / "metrics.json").write_text(
                json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            with (stage / "results.csv").open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(
                    [
                        "path",
                        "expected",
                        "method",
                        "predicted",
                        "milliseconds",
                        "scores",
                        "explanation",
                    ]
                )
                for row in report.rows:
                    for method, prediction in row.predictions.items():
                        writer.writerow(
                            [
                                row.path,
                                row.expected or "",
                                method,
                                prediction.language or "?",
                                row.milliseconds[method],
                                json.dumps(prediction.scores),
                                prediction.explanation,
                            ]
                        )
            with (stage / "summary.csv").open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(
                    [
                        "method",
                        "accuracy",
                        "macro_f1",
                        "labeled",
                        "correct",
                        "abstentions",
                        "mean_ms",
                        "training_seconds",
                    ]
                )
                for method, m in report.metrics.items():
                    writer.writerow(
                        [
                            method,
                            *[
                                m[k]
                                for k in (
                                    "accuracy",
                                    "macro_f1",
                                    "labeled",
                                    "correct",
                                    "abstentions",
                                    "mean_ms",
                                )
                            ],
                            report.training_seconds[method],
                        ]
                    )
            from matplotlib.backends.backend_agg import FigureCanvasAgg

            figure = charts(report)
            FigureCanvasAgg(figure)
            figure.savefig(stage / "comparison.svg")
            figure.savefig(stage / "comparison.png", dpi=150)
            (stage / "report.html").write_text(render_html(report), encoding="utf-8")
            for item in sorted(stage.iterdir(), key=lambda p: p.name == "report.html"):
                item.replace(directory / item.name)
        return directory / "report.html"
    except (OSError, ValueError) as exc:
        raise LabError(f"Не удалось сохранить отчёт: {exc}") from exc
