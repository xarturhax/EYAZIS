"""Общие построители Figure для Tkinter и файлового экспорта; без pyplot."""

from textwrap import fill

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator, PercentFormatter

from lab1.ir_system.domain.metrics import RECALL_LEVELS
from lab1.ir_system.domain.models import EvaluationReport, QueryEvaluation
from lab1.ir_system.reporting import metric_values

BLUE = "#2563eb"
INK = "#172b4d"
MUTED = "#52657d"


def _figure(title: str, context: str, note: str, height: float = 6.4) -> Figure:
    figure = Figure(figsize=(10.4, height), dpi=100, facecolor="white")
    figure.suptitle(title, x=0.08, y=0.97, ha="left", fontsize=16, color=INK)
    figure.text(
        0.08,
        0.895,
        "\n".join(fill(line, 100) for line in context.splitlines()),
        fontsize=10,
        color=MUTED,
        va="top",
    )
    figure.text(0.08, 0.03, note, fontsize=9, color=MUTED, va="bottom")
    figure.subplots_adjust(left=0.16, right=0.95, bottom=0.20, top=0.80)
    return figure


def _style_axes(axes: Axes) -> None:
    axes.set_axisbelow(True)
    axes.tick_params(colors=MUTED, labelsize=10)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color("#ccd5e2")


def _context(report: EvaluationReport, row: QueryEvaluation | None) -> str:
    if row is not None:
        counts = row.evaluation.counts
        return (
            f"Запрос: {row.query}\n"
            f"Найдено: {counts.retrieved}; релевантных в коллекции: {counts.relevant}; "
            f"найдено релевантных: {counts.tp}."
        )
    return (
        f"Арифметическое среднее по {len(report.rows)} запросам; "
        f"исключено с R=0: {len(report.excluded_queries)}. "
        f"Документов в коллекции: {report.document_count}."
    )


def metrics_figure(report: EvaluationReport, row: QueryEvaluation | None = None) -> Figure:
    values = metric_values(
        row.evaluation.metrics if row else report.averages, aggregate=row is None
    )
    figure = _figure(
        "Средние поисковые метрики" if row is None else "Поисковые метрики запроса",
        _context(report, row),
        "Больше — лучше. Каждая метрика отражает отдельное свойство поиска.\n"
        "P@5 и P@10 делятся на 5 и 10 даже при короткой выдаче.",
    )
    axes = figure.add_subplot()
    names, numbers = list(values), list(values.values())
    bars = axes.barh(
        names, numbers, color=[BLUE, "#0d9488", "#7c3aed", BLUE, BLUE, "#0d9488"], height=0.57
    )
    axes.invert_yaxis()
    axes.set_xlim(0, 1.16)
    axes.set_xticks([level / 5 for level in range(6)])
    axes.xaxis.set_major_formatter(PercentFormatter(1))
    axes.set_xlabel("Значение метрики", color=INK, labelpad=12)
    axes.grid(axis="x", color="#e5eaf2", linewidth=0.8)
    for bar, value in zip(bars, numbers, strict=True):
        axes.text(
            value + 0.018,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1%}",
            va="center",
            fontsize=11,
            color=INK,
        )
    _style_axes(axes)
    return figure


def precision_recall_figure(report: EvaluationReport, row: QueryEvaluation | None = None) -> Figure:
    figure = _figure(
        "Полнота–точность: 11 точек TREC",
        _context(report, row),
        "TREC: в каждом пороге полноты берётся максимальная точность при полноте не ниже порога.\n"
        "Недостигнутые пороги дают 0. Средняя кривая усредняет 11 значений по запросам.",
    )
    figure.subplots_adjust(left=0.12, bottom=0.29)
    axes = figure.add_subplot()
    if row and row.evaluation.curve:
        points = row.evaluation.curve
        axes.plot(
            [p.recall for p in points],
            [p.precision for p in points],
            color="#d97706",
            linestyle="--",
            marker=".",
            linewidth=1.5,
            label="Фактические значения по позициям выдачи",
        )
    values = row.evaluation.interpolated if row else report.mean_interpolated
    axes.plot(
        RECALL_LEVELS,
        values,
        color=BLUE,
        marker="o",
        markersize=5,
        linewidth=2.3,
        label="TREC запроса" if row else "Средняя TREC по запросам",
    )
    axes.set_xlim(-0.02, 1.02)
    axes.set_ylim(-0.03, 1.06)
    axes.xaxis.set_major_locator(MultipleLocator(0.1))
    axes.yaxis.set_major_locator(MultipleLocator(0.2))
    axes.xaxis.set_major_formatter(PercentFormatter(1))
    axes.yaxis.set_major_formatter(PercentFormatter(1))
    axes.set_xlabel(
        "Полнота (Recall): доля найденных релевантных документов", color=INK, labelpad=10
    )
    axes.set_ylabel("Точность (Precision)", color=INK, labelpad=10)
    axes.grid(color="#e5eaf2", linewidth=0.8)
    axes.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), frameon=False, fontsize=9)
    _style_axes(axes)
    return figure


def comparison_figure(report: EvaluationReport) -> Figure:
    values = [metric_values(row.evaluation.metrics) for row in report.rows]
    figure = _figure(
        "Сравнение качества по запросам",
        f"Все {len(report.rows)} допустимых запросов; "
        f"исключено с R=0: {len(report.excluded_queries)}.",
        "Числа — значения метрик; более тёмная ячейка означает большее значение.\n"
        "P@5 и P@10 имеют фиксированный знаменатель и могут быть низкими при малом числе релевантных.",
        height=max(6.4, 0.48 * len(values) + 2.7),
    )
    figure.subplots_adjust(left=0.35, right=0.88, bottom=0.23)
    axes = figure.add_subplot()
    names = list(values[0])
    matrix = [[item[name] for name in names] for item in values]
    image = axes.imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    axes.set_xticks(range(len(names)), labels=names, rotation=25, ha="right")
    axes.set_yticks(range(len(values)), labels=[fill(row.query, 30) for row in report.rows])
    axes.tick_params(axis="both", length=0, labelsize=10)
    axes.set_xlabel("Поисковые метрики", labelpad=12, color=INK)
    for i, line in enumerate(matrix):
        for j, value in enumerate(line):
            axes.text(
                j,
                i,
                f"{value:.1%}",
                ha="center",
                va="center",
                fontsize=10,
                color="white" if value >= 0.6 else INK,
            )
    colorbar = figure.colorbar(image, ax=axes, fraction=0.045, pad=0.04)
    colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1))
    colorbar.set_label("Значение", color=INK)
    for spine in axes.spines.values():
        spine.set_visible(False)
    return figure
