"""Hidden real Tk check with a real local Marian model."""

import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from lab4.presentation.gui import Application


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        root = tk.Tk()
        root.withdraw()
        app = Application(root, base / "lexicon.sqlite3")
        errors = []

        def wait():
            deadline = time.monotonic() + 90
            while app.runner.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
            assert not app.runner.busy, "Background task timed out"
            assert not errors, errors

        with patch(
            "lab4.presentation.gui.messagebox.showerror",
            side_effect=lambda *a, **k: errors.append(a),
        ):
            app.demo("medicine")
            app.run()
            wait()
            assert app.result is not None and app.result.source_words > 20
            assert "étude" in app.output.get("1.0", "end").casefold()
            assert app.dictionary.get_children()
            assert len(app.syntax.get_children()) == 1
            entry = app.result.entries[0]
            app.correct_value(entry, "équivalent vérifié")
            app.populate()
            wait()
            assert app.result.entries[0].translation == "équivalent vérifié"
            assert app.result.entries[0].origin == "manual"
            app.sentence_combo.current(1)
            app.show_tree()
            assert len(app.syntax.get_children()) == 1
            app.save(base / "report")
            wait()
            assert app.report and app.report.is_file()
            assert (base / "report/dictionary.txt").is_file()
            app.input.insert("end", " More text.")
            root.update()
            assert app.result is None and app.report is None
            app.close()
    print(
        "Real Marian + Tk: translation, dictionary corrections, refresh, tree, export, invalidation OK"
    )


if __name__ == "__main__":
    main()
