"""Real hidden Tk smoke check; run explicitly on a desktop system."""

import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from lab3.presentation.gui import Application


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    app = Application(root)
    errors = []
    with patch(
        "lab3.presentation.gui.messagebox.showerror", side_effect=lambda *a, **k: errors.append(a)
    ):
        app.demo()
        assert len(app.sources) == 4
        app.run()
        deadline = time.monotonic() + 45
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert not app.busy, "Background calculation timed out"
        assert not errors, errors
        assert app.result is not None
        assert len(app.score_tree.get_children()) > 50
        assert "КЛАССИЧЕСКИЙ РЕФЕРАТ" in app.summary.get("1.0", "end")
        app.method.set("TextRank")
        app.tree.selection_set("3")
        app.show_result()
        assert "meninas" in app.original.get("1.0", "end").lower()
        assert app.original.tag_ranges("selected")
        with tempfile.TemporaryDirectory() as directory:
            app.save_report(Path(directory))
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
            assert app.report is not None and app.report.exists()
        app.sentences.set("5")
        assert app.result is None and app.report is None
        assert not app.score_tree.get_children()
        app.close()
    print("Tk GUI, background calculation, method switching, export, invalidation: OK")


if __name__ == "__main__":
    main()
