"""Файловый экспорт оценок и Figure; предметные формулы остаются в domain."""

import csv
import html
import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from lab1.ir_system.domain.errors import ExportError
from lab1.ir_system.domain.models import EvaluationReport
from lab1.ir_system.reporting import METRIC_DESCRIPTIONS
from lab1.ir_system.visualization import comparison_figure, metrics_figure, precision_recall_figure

from .serialization import report_to_dict


class FileReportExporter:
    def export(self, report: EvaluationReport, directory: Path) -> Path:
        if not report.rows:
            raise ExportError("Отчёт не содержит оценённых запросов")
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".report-", dir=directory) as temporary:
                staging = Path(temporary)
                self._write_files(report, staging)
                # HTML публикуется последним. Замена атомарна для отдельного файла.
                for path in sorted(staging.iterdir(), key=lambda item: item.name == "report.html"):
                    os.replace(path, directory / path.name)
        except OSError as exc:
            raise ExportError(f"Не удалось сохранить отчёт: {exc}") from exc
        return directory / "report.html"

    def _write_files(self, report: EvaluationReport, directory: Path) -> None:
        data = report_to_dict(report)
        (directory / "metrics.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        names = [
            name for name in data["rows"][0] if name not in {"ranking", "curve", "interpolated"}
        ]
        with (directory / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=names, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data["rows"])
        with (directory / "averages.csv").open("w", encoding="utf-8-sig", newline="") as file:
            averages_writer = csv.writer(file)
            averages_writer.writerow(["metric", "value"])
            averages_writer.writerows(data["averages"].items())
        with (directory / "excluded_queries.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as file:
            writer = csv.DictWriter(file, fieldnames=["query", "reason"])
            writer.writeheader()
            writer.writerows(data["excluded_queries"])
        charts = []
        for name, caption, figure in _figures(report):
            try:
                FigureCanvasAgg(figure)
                for extension in ("svg", "png"):
                    figure.savefig(
                        directory / f"{name}.{extension}", dpi=140, metadata={"Title": caption}
                    )
            finally:
                figure.clear()
            charts.append((f"{name}.svg", caption))
        (directory / "report.html").write_text(render_html(data, names, charts), encoding="utf-8")


def _figures(report: EvaluationReport) -> Iterator[tuple[str, str, Figure]]:
    yield (
        "metrics",
        "Арифметическое среднее шести метрик по допустимым запросам",
        metrics_figure(report),
    )
    yield (
        "mean_pr",
        "Средняя 11-точечная кривая полнота–точность TREC",
        precision_recall_figure(report),
    )
    yield (
        "query_metrics",
        "Сравнение всех шести метрик для каждого запроса",
        comparison_figure(report),
    )
    for i, row in enumerate(report.rows, 1):
        yield (
            f"query_{i}_pr",
            f"Полнота–точность для запроса «{row.query}»",
            precision_recall_figure(report, row),
        )


def _cell(value: object) -> str:
    return html.escape(f"{value:.4f}" if isinstance(value, float) else str(value))


def _table(rows: list[dict], names: list[str]) -> str:
    header = "".join(f"<th>{html.escape(name)}</th>" for name in names)
    body = "".join(
        "<tr>" + "".join(f"<td>{_cell(row[name])}</td>" for name in names) + "</tr>" for row in rows
    )
    return f'<div class="scroll"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


def render_html(data: dict, names: list[str], charts: list[tuple[str, str]]) -> str:
    metric_names = ["query", "Precision", "Recall", "AP", "P@5", "P@10", "R-precision"]
    count_names = [name for name in names if name not in metric_names]
    averages = "".join(
        f'<div class="card"><span>{html.escape(name)}</span><strong>{value:.1%}</strong>'
        f"<small>{html.escape(METRIC_DESCRIPTIONS[name])}</small></div>"
        for name, value in data["averages"].items()
    )
    images = "".join(
        f'<figure><img src="{html.escape(name)}" alt="{html.escape(caption, quote=True)}">'
        f"<figcaption>{html.escape(caption)}. "
        f'<a href="{html.escape(name.removesuffix(".svg"))}.png">Скачать PNG</a></figcaption></figure>'
        for name, caption in charts
    )
    exclusions = "".join(
        f"<li><b>{html.escape(item['query'])}</b>: {html.escape(item['reason'])}</li>"
        for item in data["excluded_queries"]
    )
    exclusions = f"<ul>{exclusions}</ul>" if exclusions else "<p>Исключённых запросов нет.</p>"
    glossary = "".join(
        f"<dt>{html.escape(name)}</dt><dd>{html.escape(description)}</dd>"
        for name, description in METRIC_DESCRIPTIONS.items()
    )
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Оценка поиска — РОМИП’2004</title>
<style>
body{{font:16px/1.6 system-ui,sans-serif;color:#172b4d;background:#f4f7fb;margin:0}}
main{{max-width:1120px;margin:auto;padding:32px 24px}}
h1,h2{{line-height:1.3}} h2{{margin-top:36px}} .muted,small,figcaption{{color:#52657d}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:16px}}
.card,figure,.info{{background:white;border:1px solid #dce4ef;border-radius:12px;padding:20px}}
.card span,.card strong,.card small{{display:block}} .card strong{{font-size:32px;color:#2563eb}}
.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;background:white}}
td,th{{padding:10px;border-bottom:1px solid #dce4ef;text-align:right;white-space:nowrap}}
td:first-child,th:first-child{{text-align:left}} th{{background:#eaf0f9}}
figure{{margin:24px 0}}img{{display:block;width:100%;height:auto}}figcaption{{margin-top:12px}}
dt{{font-weight:600}}dd{{margin:0 0 12px}}a{{color:#2563eb}}
</style></head><body><main>
<h1>Качество информационного поиска</h1>
<p class="muted">Вариант 36 · РОМИП’2004, дорожка поиска · BM25:
k1={data["parameters"]["k1"]}, b={data["parameters"]["b"]} ·
Документов: {data["document_count"]} · Оценено запросов: {len(data["rows"])} ·
Исключено: {len(data["excluded_queries"])}</p>
<div class="info"><b>Как читать результаты.</b>
Все шесть метрик лежат в диапазоне 0–1; большее значение означает лучшее качество по этому критерию.
Средние ниже дают каждому допустимому запросу одинаковый вес. MAP — среднее AP.
P@5 и P@10 делятся на фиксированные 5 и 10, даже если результатов меньше.
Например, два релевантных результата без ошибок дают Precision=1, P@5=0.4 и P@10=0.2.</div>
<h2>Средние по запросам</h2><div class="cards">{averages}</div>
<h2>Метрики каждого запроса</h2>{_table(data["rows"], metric_names)}
<h2>Исключённые запросы</h2>
<p>По РОМИП запросы без релевантных документов (R=0) не входят в метрики и среднюю кривую.</p>
{exclusions}
<h2>Графики</h2>
<p>Столбцы показывают отдельные метрики. Цветовая таблица сравнивает запросы.
На кривых горизонтальная ось — полнота, вертикальная — точность.
Синяя линия показывает 11 значений TREC; оранжевая — фактические значения на префиксах выдачи
для одного запроса. Это разные представления, поэтому их значения могут отличаться.</p>
{images}
<h2>Что означают метрики</h2><dl>{glossary}</dl>
<h2>Диагностические количества</h2>{_table(data["rows"], ["query", *count_names])}
<p>retrieved — найдено документов; relevant — релевантных в коллекции;
TP — найдено релевантных; FP — найдено нерелевантных; FN — пропущено релевантных;
TN — не найдено нерелевантных.</p>
<h2>Методика и данные</h2>
<p>Источник: локальный файл 2004_romip_metrix.pdf, стр. 1–3, 5–9.
Экспертная разметка независима от ранга BM25: 0 — нерелевантно, 1 и 2 — релевантно.
AP и Recall используют всю выдачу и всю размеченную коллекцию.
В TREC берётся максимум точности при полноте не ниже каждого порога от 0 до 1 с шагом 0.1;
недостигнутые пороги дают 0. Средняя кривая — среднее этих 11 значений.</p>
<p>RIRES упоминается на стр. 1, но её определение в предоставленном PDF отсутствует:
кривая RIRES не рассчитывается. В документе арифметическое среднее по запросам названо
«микроусреднением» (стр. 5); здесь оно обозначено словами, чтобы избежать путаницы терминов.</p>
<p class="muted">Результаты характеризуют выбранную коллекцию и экспертную разметку.
Ранг BM25 не является вероятностью или метрикой качества.
Машиночитаемые данные: <a href="metrics.json">JSON (версия 2)</a>,
<a href="metrics.csv">CSV по запросам</a>, <a href="averages.csv">средние CSV</a>,
<a href="excluded_queries.csv">исключения CSV</a>.</p>
</main></body></html>"""
