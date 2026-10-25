"""Виджеты представления: таблица, текст и графики без обращения к сервисам."""

import tkinter as tk
from collections.abc import Iterable, Sequence
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from lab1.ir_system.domain.models import EvaluationReport
from lab1.ir_system.visualization import comparison_figure, metrics_figure, precision_recall_figure


class DataTable(ttk.Frame):
    def __init__(
        self, parent: tk.Misc, columns: Sequence[tuple[str, int]], height: int = 10
    ) -> None:
        super().__init__(parent)
        self.tree = ttk.Treeview(
            self, columns=[name for name, _ in columns], show="headings", height=height
        )
        for name, width in columns:
            self.tree.heading(name, text=name)
            self.tree.column(name, width=width, minwidth=55)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def show_rows(self, rows: Iterable[tuple[str, Sequence[object]]]) -> None:
        self.clear()
        for identifier, values in rows:
            self.tree.insert("", "end", iid=identifier, values=tuple(values))

    def selected_ids(self) -> tuple[int, ...]:
        return tuple(int(identifier) for identifier in self.tree.selection())

    def first_id(self) -> int | None:
        ids = self.selected_ids()
        return ids[0] if ids else None


class TextPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc, height: int = 10) -> None:
        super().__init__(parent)
        self.text = tk.Text(self, wrap="word", height=height, state="disabled", padx=10, pady=10)
        scrollbar = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def show(self, content: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", content)
        self.text.configure(state="disabled")


class ReportChart(ttk.Frame):
    """Полноразмерный график с выбором вида/запроса и прокруткой длинных сравнений."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._report: EvaluationReport | None = None
        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=8)
        ttk.Label(controls, text="График:").pack(side="left")
        self.kind = ttk.Combobox(
            controls,
            state="readonly",
            width=30,
            values=("Метрики", "Полнота–точность (TREC)", "Сравнение запросов"),
        )
        self.kind.current(0)
        self.kind.pack(side="left", padx=8)
        ttk.Label(controls, text="Данные:").pack(side="left")
        self.scope = ttk.Combobox(controls, state="readonly", width=35)
        self.scope.pack(side="left", fill="x", expand=True, padx=8)
        self.kind.bind("<<ComboboxSelected>>", lambda event: self.draw())
        self.scope.bind("<<ComboboxSelected>>", lambda event: self.draw())
        area = ttk.Frame(self)
        area.pack(fill="both", expand=True)
        self._viewport = tk.Canvas(area, background="white", highlightthickness=0)
        scroll = ttk.Scrollbar(area, orient="vertical", command=self._viewport.yview)
        self._viewport.configure(yscrollcommand=scroll.set)
        self._viewport.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._host = ttk.Frame(self._viewport)
        self._host_id = self._viewport.create_window(0, 0, window=self._host, anchor="nw")
        self.canvas = FigureCanvasTkAgg(Figure(figsize=(10.4, 6.4)), master=self._host)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        self.toolbar.pack(fill="x")
        self._viewport.bind("<Configure>", lambda event: self._resize())
        self.show(None)

    def _resize(self) -> None:
        height = max(1, self._viewport.winfo_height())
        if self._report and self.kind.current() == 2 and len(self._report.rows) > 8:
            height = max(height, int((0.48 * len(self._report.rows) + 2.7) * 100))
        width = max(1, self._viewport.winfo_width())
        self._viewport.itemconfigure(self._host_id, width=width, height=height)
        self._viewport.configure(scrollregion=(0, 0, width, height))

    def show(self, report: EvaluationReport | None) -> None:
        self._report = report
        self.scope["values"] = (
            ("Среднее по запросам", *(r.query for r in report.rows)) if report else ()
        )
        self.scope.set("Среднее по запросам" if report else "")
        self.kind.configure(state="readonly" if report else "disabled")
        self.draw()

    def draw(self) -> None:
        report = self._report
        self.scope.configure(
            state="readonly" if report and self.kind.current() != 2 else "disabled"
        )
        if report is None:
            figure = Figure(figsize=(10.4, 6.4), facecolor="white")
            figure.text(
                0.08,
                0.6,
                "Рассчитайте метрики кнопкой «Оценить запрос» или «Оценить все».",
                fontsize=11,
                color="#52657d",
                wrap=True,
            )
        elif self.kind.current() == 2:
            figure = comparison_figure(report)
        else:
            index = self.scope.current() - 1
            row = report.rows[index] if index >= 0 else None
            builder = precision_recall_figure if self.kind.current() == 1 else metrics_figure
            figure = builder(report, row)
        self.canvas.figure.clear()
        self.canvas.figure = figure
        figure.set_canvas(self.canvas)
        self.toolbar.update()
        self._viewport.yview_moveto(0)
        self._resize()
        # При смене Figure Tk-canvas может уже иметь нужный размер: повторного Configure не будет.
        width = self.canvas.get_tk_widget().winfo_width()
        height = self.canvas.get_tk_widget().winfo_height()
        if width > 1 and height > 1:
            figure.set_size_inches(width / figure.dpi, height / figure.dpi, forward=False)
        self.canvas.draw_idle()
