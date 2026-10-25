"""Real hidden Tk + Piper; speaker playback and clipboard are mocked."""

import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from lab8.presentation.gui import Application


class FakePlayer:
    def __init__(self):
        self.played = []
        self.stops = 0

    def play(self, path):
        self.played.append(path)

    def stop(self):
        self.stops += 1


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    player = FakePlayer()
    app = Application(root, player)
    errors = []
    with patch(
        "lab8.presentation.gui.messagebox.showerror", side_effect=lambda *a, **k: errors.append(a)
    ):
        with patch.object(
            root, "clipboard_get", return_value="La littérature révèle nos émotions."
        ):
            app.paste()
        assert "émotions" in app.input.get("1.0", "end")
        app.read()
        deadline = time.monotonic() + 45
        while app.runner.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert not app.runner.busy and not errors, errors
        assert app.result and app.result.duration > 1
        assert len(player.played) == 1
        app.stop()
        assert player.stops > 0
        app.replay()
        assert len(player.played) == 2
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "lecture.wav"
            app.save_to(target)
            assert target.exists() and target.with_suffix(".html").exists()
        app.volume.set(0.4)
        assert app.result is None
        app.input.insert("end", " Une autre phrase.")
        root.update()
        assert app.result is None
        app.close()
    print("Tk + real French Piper: paste, synthesis, play/stop routing, export, invalidation OK")


if __name__ == "__main__":
    main()
