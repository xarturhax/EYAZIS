"""Проверка реального Tk, фоновой задачи, таблиц и графика без открытия браузера."""

import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from lab2.presentation.gui import Application


def main():
    root = tk.Tk()
    root.withdraw()
    app = Application(root)
    errors = []
    app.error = errors.append
    try:
        app.load_demo()
        assert len(app.entries) == 48
        app.repetitions.set("1")
        app.analyze()
        deadline = time.monotonic() + 60
        while app.tasks.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        root.update()
        assert not errors, errors
        assert not app.tasks.busy, "Worker timeout"
        assert app.report is not None
        assert len(app.result_tree.get_children()) == 16
        assert app.canvas is not None
        app.result_tree.selection_set("0")
        app.details()
        assert "MLP" in app.details_text.get("1.0", "end")
        with tempfile.TemporaryDirectory() as directory:
            with patch("lab2.presentation.gui.filedialog.askdirectory", return_value=directory):
                with patch("lab2.presentation.gui.webbrowser.open") as opened:
                    app.export()
                    while app.tasks.busy and time.monotonic() < deadline:
                        root.update()
                        time.sleep(0.02)
                    assert app.last_export == Path(directory) / "report.html"
                    assert app.last_export.exists()
                    assert opened.called
        app.seed.set("37")
        assert app.report is None and app.canvas is None
        assert not app.result_tree.get_children()
        print("GUI smoke: OK")
    finally:
        app.close()


if __name__ == "__main__":
    main()
