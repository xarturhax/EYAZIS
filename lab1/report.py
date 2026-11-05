"""График качества и сохранение результатов в HTML/JSON/CSV."""

import csv
import html
import json
from pathlib import Path

from matplotlib.figure import Figure


def figure(report):
    result = Figure(figsize=(9, 4), constrained_layout=True)
    axes = result.subplots(1, 2)
    values = report["averages"]
    axes[0].barh(list(values), list(values.values()))
    axes[0].set(xlim=(0, 1.05), title="Средние показатели")
    axes[1].plot([i / 10 for i in range(11)], report["mean_interpolated"], "o-")
    axes[1].set(
        xlabel="Полнота", ylabel="Точность", xlim=(0, 1), ylim=(0, 1.05), title="11 точек TREC"
    )
    axes[1].grid(True, alpha=0.3)
    return result


def export(report, folder):
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rows = [{"query": r["query"], **r["metrics"]} for r in report["rows"]]
    with (folder / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    chart = figure(report)
    FigureCanvasAgg(chart)
    chart.savefig(folder / "metrics.png", dpi=150)
    chart.savefig(folder / "metrics.svg")
    chart.clear()
    heads = "".join(f"<th>{html.escape(k)}</th>" for k in rows[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row.values()) + "</tr>"
        for row in rows
    )
    summary = "; ".join(f"{name}: {value:.4f}" for name, value in report["averages"].items())
    target = folder / "report.html"
    target.write_text(
        f'<!doctype html><html lang="ru"><meta charset="utf-8"><title>Качество поиска</title>'
        f"<style>body{{font:16px serif;margin:30px}}td,th{{border:1px solid;padding:6px}}"
        f"table{{border-collapse:collapse}}img{{max-width:100%}}</style>"
        f"<h1>Лабораторная №1. Вариант 36</h1><p>{html.escape(summary)}</p>"
        f'<table><tr>{heads}</tr>{body}</table><img src="metrics.png" alt="Метрики">'
        "<p>Оценки 1 и 2 считаются релевантными. P@5/P@10 делятся на 5/10; "
        "запросы с R=0 исключены из средних. MAP — среднее AP.</p></html>",
        encoding="utf-8",
    )
    return target
