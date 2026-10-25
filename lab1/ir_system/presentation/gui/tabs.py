"""Пассивные вкладки: создание виджетов и отображение переданных данных."""

import tkinter as tk
from collections.abc import Mapping, Sequence
from tkinter import ttk

from lab1.ir_system.domain.models import Document, EvaluationReport, SearchResult
from lab1.ir_system.reporting import METRIC_DESCRIPTIONS, metric_values

from .widgets import DataTable, ReportChart, TextPanel


class CollectionTab(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=10)
        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Label(row, text="URL страницы:").pack(side="left")
        self.url = ttk.Entry(row)
        self.url.pack(side="left", fill="x", expand=True, padx=8)
        self.fetch_button = ttk.Button(row, text="Загрузить")
        self.fetch_button.pack(side="left")
        row = ttk.Frame(self)
        row.pack(fill="x", pady=8)
        self.demo_button = ttk.Button(row, text="Загрузить демо (12 документов)")
        self.delete_button = ttk.Button(row, text="Удалить выбранные")
        self.details_button = ttk.Button(row, text="Текст и ключевые слова")
        for button in (self.demo_button, self.delete_button, self.details_button):
            button.pack(side="left", padx=4)
        self.table = DataTable(
            self, (("ID", 60), ("Заголовок", 330), ("Терминов", 90), ("URL", 550))
        )
        self.table.pack(fill="both", expand=True, pady=5)
        ttk.Label(
            self, text="Демо — авторские учебные тексты с тематическими интернет-ссылками."
        ).pack(anchor="w")

    def show_documents(self, documents: Sequence[Document]) -> None:
        self.table.show_rows((str(d.id), (d.id, d.title, d.length, d.url)) for d in documents)

    def set_busy(self, busy: bool) -> None:
        self.fetch_button.configure(state="disabled" if busy else "normal")


class SearchTab(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=10)
        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Label(row, text="English query:").pack(side="left")
        self.query = ttk.Entry(row)
        self.query.pack(side="left", fill="x", expand=True, padx=8)
        self.search_button = ttk.Button(row, text="Найти")
        self.search_button.pack(side="left")
        self.table = DataTable(
            self,
            (("ID", 55), ("Заголовок", 300), ("BM25", 100), ("Слова запроса", 220), ("URL", 400)),
        )
        self.table.pack(fill="both", expand=True, pady=5)
        row = ttk.Frame(self)
        row.pack(fill="x")
        self.open_button = ttk.Button(row, text="Открыть ссылку")
        self.details_button = ttk.Button(row, text="Текст и ключевые слова")
        self.judge_button = ttk.Button(row, text="Разметить этот запрос")
        for button in (self.open_button, self.details_button, self.judge_button):
            button.pack(side="left", padx=4)
        self.snippet = TextPanel(self, height=5)
        self.snippet.pack(fill="x", pady=8)

    def show_results(self, results: Sequence[SearchResult]) -> None:
        self.table.show_rows(
            (
                str(r.document.id),
                (
                    r.document.id,
                    r.document.title,
                    f"{r.score:.4f}",
                    ", ".join(r.matched_words),
                    r.document.url,
                ),
            )
            for r in results
        )
        self.snippet.show("")


class QualityTab(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=10)
        self._report: EvaluationReport | None = None
        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Label(row, text="Запрос для разметки:").pack(side="left")
        self.query_text = tk.StringVar()
        self.query = ttk.Combobox(row, textvariable=self.query_text)
        self.query.pack(side="left", fill="x", expand=True, padx=8)
        self.load_button = ttk.Button(row, text="Разметка")
        self.load_button.pack(side="left")
        row = ttk.Frame(self)
        row.pack(fill="x", pady=8)
        self.evaluate_button = ttk.Button(row, text="Оценить запрос")
        self.all_button = ttk.Button(row, text="Оценить все")
        self.export_button = ttk.Button(row, text="Экспорт отчёта")
        self.evaluate_button.pack(side="left")
        self.all_button.pack(side="left", padx=8)
        self.export_button.pack(side="right")
        self.pages = ttk.Notebook(self)
        self.pages.pack(fill="both", expand=True)
        self.judgments_page = ttk.Frame(self.pages, padding=10)
        self.results_page = ttk.Frame(self.pages, padding=10)
        self.charts_page = ttk.Frame(self.pages, padding=10)
        for page, name in (
            (self.judgments_page, "Разметка"),
            (self.results_page, "Результаты"),
            (self.charts_page, "Графики"),
        ):
            self.pages.add(page, text=name)
        ttk.Label(
            self.judgments_page,
            text="Оцените каждый документ коллекции независимо от его ранга BM25.",
        ).pack(anchor="w")
        self.table = DataTable(
            self.judgments_page, (("ID", 60), ("Документ", 720), ("Оценка", 100)), height=8
        )
        self.table.pack(fill="both", expand=True, pady=8)
        row = ttk.Frame(self.judgments_page)
        row.pack(fill="x")
        self.grade_buttons = {}
        for grade, label in ((0, "0 — нет"), (1, "1 — частично"), (2, "2 — полностью")):
            button = ttk.Button(row, text=label)
            button.pack(side="left", padx=3)
            self.grade_buttons[grade] = button
        self.summary = tk.StringVar(value="Сначала рассчитайте метрики.")
        ttk.Label(self.results_page, textvariable=self.summary, wraplength=950).pack(
            anchor="w", pady=8
        )
        row = ttk.Frame(self.results_page)
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="Показать:").pack(side="left")
        self.result_scope = ttk.Combobox(row, state="disabled")
        self.result_scope.pack(side="left", fill="x", expand=True, padx=8)
        self.result_scope.bind("<<ComboboxSelected>>", lambda event: self._show_selected_results())
        self.metrics = DataTable(
            self.results_page,
            (("Метрика", 150), ("Значение", 100), ("Что измеряет", 670)),
            height=6,
        )
        self.metrics.pack(fill="both", expand=True, pady=8)
        self.details = tk.StringVar()
        ttk.Label(self.results_page, textvariable=self.details, wraplength=950).pack(
            anchor="w", pady=8
        )
        ttk.Label(
            self.results_page,
            wraplength=950,
            text="Каждый допустимый запрос имеет одинаковый вес. MAP — среднее AP. "
            "Оценки 1 и 2 обе считаются релевантными. "
            "P@5 и P@10 делятся на 5 и 10 даже при короткой выдаче.",
        ).pack(anchor="w")
        self.chart = ReportChart(self.charts_page)
        self.chart.pack(fill="both", expand=True)

    def show_judgments(self, documents: Sequence[Document], grades: Mapping[int, int]) -> None:
        self.table.show_rows(
            (str(d.id), (d.id, d.title, grades.get(d.id, "не оценён"))) for d in documents
        )
        self.pages.select(self.judgments_page)

    def show_report(self, report: EvaluationReport | None) -> None:
        self._report = report
        self.result_scope["values"] = (
            ("Среднее по запросам", *(r.query for r in report.rows)) if report else ()
        )
        self.result_scope.configure(state="readonly" if report else "disabled")
        self.result_scope.set("Среднее по запросам" if report else "")
        if report:
            summary = (
                f"Оценено запросов: {len(report.rows)}; документов: {report.document_count}. "
                f"Исключено с R=0: {len(report.excluded_queries)}."
            )
            if report.excluded_queries:
                summary += "\nИсключены: " + "; ".join(r.query for r in report.excluded_queries)
            self.summary.set(summary)
            self.pages.select(self.results_page)
        else:
            self.summary.set("Сначала рассчитайте метрики.")
        self._show_selected_results()
        self.chart.show(report)

    def _show_selected_results(self) -> None:
        report = self._report
        index = self.result_scope.current() - 1
        row = report.rows[index] if report and index >= 0 else None
        values = (
            metric_values(row.evaluation.metrics if row else report.averages, aggregate=row is None)
            if report
            else {}
        )
        self.metrics.show_rows(
            (name, (name, f"{value:.4f}", METRIC_DESCRIPTIONS[name]))
            for name, value in values.items()
        )
        if row:
            counts = row.evaluation.counts
            self.details.set(
                f"Найдено: {counts.retrieved}; релевантных в коллекции: {counts.relevant}; "
                f"TP={counts.tp}, FP={counts.fp}, FN={counts.fn}, TN={counts.tn}."
            )
        else:
            self.details.set("Арифметическое среднее по допустимым запросам." if report else "")
