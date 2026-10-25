"""Отдельная проверка Tkinter: python -m tests.gui_smoke (нужен GUI/Tcl)."""

import tempfile
import tkinter as tk
from dataclasses import replace
from unittest.mock import patch

from lab1.ir_system.bootstrap import application_runtime
from lab1.ir_system.config import AppConfig
from lab1.ir_system.domain.errors import ValidationError
from lab1.ir_system.presentation.gui.controller import GuiController
from lab1.ir_system.presentation.gui.tasks import TaskRunner
from lab1.ir_system.presentation.gui.window import MainWindow


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    tasks = TaskRunner(root)
    try:
        with application_runtime(replace(AppConfig(), database=":memory:")) as services:
            window = MainWindow(root)
            controller = GuiController(window, services, tasks)
            controller.bind()
            controller.demo()
            window.search.query.insert(0, "python programming")
            controller.search()
            assert len(window.search.table.tree.get_children()) == 4
            controller.evaluate(all_queries=True)
            root.update()
            assert controller.report.averages.average_precision == 0.9375
            assert len(window.quality.chart.canvas.figure.axes[0].patches) == 6
            window.quality.pages.select(window.quality.charts_page)
            # Окно вне экрана: проверяем настоящую компоновку без показа пользователю.
            root.geometry("1150x780+10000+10000")
            root.deiconify()
            root.update()
            assert window.quality.chart.canvas.get_tk_widget().winfo_width() > 900
            assert window.quality.chart.canvas.get_tk_widget().winfo_height() > 400
            window.quality.chart.kind.current(1)
            window.quality.chart.scope.current(1)
            window.quality.chart.draw()
            root.update()
            assert len(window.quality.chart.canvas.figure.axes[0].lines) == 2
            assert "Полнота" in window.quality.chart.canvas.figure.axes[0].get_xlabel()
            window.quality.chart.kind.current(2)
            window.quality.chart.draw()
            root.update()
            assert window.quality.chart.canvas.figure.axes[0].images[0].get_array().shape == (5, 6)
            assert str(window.quality.chart.scope["state"]) == "disabled"
            root.geometry("850x600+10000+10000")
            root.update()
            assert window.quality.chart.canvas.get_tk_widget().winfo_width() > 650
            window.quality.result_scope.current(1)
            window.quality._show_selected_results()
            assert window.quality.metrics.tree.item("P@10", "values")[1] == "0.3000"
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(window, "choose_report_directory", return_value=directory):
                    with patch.object(window, "open_url") as open_url:
                        controller.export()
                        open_url.assert_called_once()
            window.quality.table.tree.selection_set("1")
            controller.grade(1)
            assert services.judgments.judgments("python programming")[1] == 1
            assert controller.report is None
            window.quality.query.set("different query")
            try:
                controller.grade(2)
            except ValidationError:
                pass
            else:
                raise AssertionError("Оценка изменённого запроса должна быть отклонена")
            controller.details(1)
            window.show_help()
            root.update()
    finally:
        tasks.close()
        root.destroy()
    print("GUI smoke: OK (collection, search, metrics, export, grading, dialogs)")


if __name__ == "__main__":
    main()
