"""Hidden-window integration check; no physical microphone or sound output."""

import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from lab9.bootstrap import DEFAULT_COMMANDS, ROOT
from lab9.domain.commands import Action, Router
from lab9.infrastructure.config import load_policy, save_policy
from lab9.presentation.gui import Application
from lab9.tests.test_commands import phrase


class SilentPlayer:
    def __init__(self):
        self.paths = []
        self.stops = 0

    def play(self, path):
        assert Path(path).is_file()
        self.paths.append(path)

    def stop(self):
        self.stops += 1


def settle(root, runner, seconds=45):
    until = time.monotonic() + seconds
    while runner.busy and time.monotonic() < until:
        root.update()
        time.sleep(0.02)
    root.update()
    assert not runner.busy, "Background task timed out"


def main():
    with tempfile.TemporaryDirectory() as folder:
        config = Path(folder) / "commands.json"
        save_policy(config, load_policy(DEFAULT_COMMANDS))
        root = tk.Tk()
        root.withdraw()
        player = SilentPlayer()
        errors = []
        with patch(
            "lab9.presentation.gui.messagebox.showerror",
            side_effect=lambda *a, **kw: errors.append(a),
        ):
            app = Application(root, config, player)
            try:
                root.update()
                assert not app.live and not app.asr_runner.busy
                assert len(app.command_tree.get_children()) == 7
                app.handle(phrase("lecteur suivant"), "TEST", Router(app.current_policy()), 0, True)
                assert app.reader.position == 1
                app.handle(phrase("lecteur suivant le personnage"), "TEST", app.router, 0, True)
                assert app.reader.position == 1 and app.journal[-1]["status"] == "UNKNOWN"
                app.handle(
                    phrase("lecteur précédent"), "TEST", Router(app.current_policy()), 0, True
                )
                assert app.reader.position == 0
                app.handle(
                    phrase("lecteur plus vite"), "TEST", Router(app.current_policy()), 0, True
                )
                assert app.reader.speed == 1.1

                app.epoch = 10
                app.live = True
                app.events.put((9, phrase("lecteur suivant")))
                root.update()
                # Call poll synchronously without leaving a second timer registered.
                root.after_cancel(app.poll_timer)
                app.poll()
                assert app.reader.position == 0
                app.live = False

                app.new_command()
                app.phrase.set("lecteur encore")
                app.operation.set("repeat")
                app.enabled.set(False)
                app.edit_command()
                app.save_config()
                assert len(load_policy(config).commands) == 15
                assert not load_policy(config).commands[-1].enabled
                app.language.set("en")
                assert len(app.command_tree.get_children()) == 7
                app.language.set("fr")
                assert len(app.command_tree.get_children()) == 8

                # WAV recognition uses real Vosk but must never execute its read command.
                before = len(player.paths)
                app.open_wav(ROOT / "reports/demo/audio/tom_read.wav")
                settle(root, app.asr_runner)
                assert len(player.paths) == before
                assert app.journal[-1]["status"] == "TEST_ONLY"
                assert app.journal[-1]["action"] == "read"

                # Test actual synthesis through the GUI worker, with silent output.
                app.handle(
                    phrase("lecteur commence"), "TEST", Router(app.current_policy()), 2, True
                )
                assert app.tts_runner.busy and app.paused.is_set()
                settle(root, app.tts_runner)
                assert len(player.paths) == before + 1 and app.playing
                assert app.paused.is_set()
                app.duplex.set(True)
                assert not app.paused.is_set()
                app.handle(phrase("lecteur stop"), "TEST", app.router, 3, True)
                assert not app.playing

                # Cancel synthesis before success delivery: playback must not restart.
                before = len(player.paths)
                app.perform(Action.READ)
                app.perform(Action.STOP)
                settle(root, app.tts_runner)
                assert len(player.paths) == before
                assert not app.playing and not app.paused.is_set()
                assert not errors, errors
                print("GUI smoke: PASS (real French WAV + Piper; microphone and playback mocked)")
            finally:
                app.close()


if __name__ == "__main__":
    main()
