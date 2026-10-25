"""Tk interface; model inference in the existing queued worker, playback on Windows."""

import logging
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from uuid import uuid4

from lab2.presentation.tasks import TaskRunner

from lab8.application.ports import Player
from lab8.bootstrap import ROOT, build_service
from lab8.domain.models import CancelledError, Result, Settings
from lab8.infrastructure.export import export
from lab8.infrastructure.player import WindowsPlayer
from lab8.tools.download_voices import VOICES

HELP = """Лабораторная №8 · Вариант 8

Французский язык, сочинения по литературе.
Введите текст, откройте UTF-8 TXT или нажмите «Вставить из буфера».
Кнопки примеров содержат короткие оригинальные французские сочинения.

Выберите Siwis или Tom, темп (0.5–2.0×) и громкость (0–100%).
«Читать» синтезирует WAV в фоне, затем воспроизводит его.
«Стоп» отменяет ожидающие фрагменты и останавливает воспроизведение.
Текущий фрагмент модели завершится перед отменой.
«Повторить» воспроизводит готовый результат.
«Сохранить WAV» сохраняет также текст, параметры и HTML для прослушивания/печати.

Темп — относительный коэффициент, не слова в минуту.
Громкость 0% создаёт тишину намеренно.
Изменение текста/настроек сбрасывает устаревший результат и останавливает чтение.
Длинные тексты разбиваются на фрагменты без потери слов, максимум 5000 символов.

После установки моделей всё работает локально. Микрофон не нужен.
Если голоса отсутствуют: python -m lab8.tools.download_voices.
Произношение имён, сокращений и выразительность оцениваются прослушиванием.
F1 открывает эту справку.
"""


class Application:
    def __init__(self, root: tk.Tk, player: Player | None = None) -> None:
        self.root = root
        root.title("ЕЯЗиС · Лабораторная 8 · Français")
        root.geometry("1050x760")
        root.minsize(800, 560)
        self.service = build_service()
        self.player = player or WindowsPlayer()
        self.runner = TaskRunner(root)
        self.result: Result | None = None
        self.autoplay = False
        self.playback_after: str | None = None
        self.voice = tk.StringVar(value=VOICES["siwis"])
        self.speed = tk.DoubleVar(value=1)
        self.volume = tk.DoubleVar(value=0.8)
        self.speed_label = tk.StringVar(value="1.00×")
        self.volume_label = tk.StringVar(value="80%")
        self.status = tk.StringVar(value="Введите французский текст или выберите пример.")
        self.count = tk.StringVar()
        self.controls: list[tuple[ttk.Widget, str]] = []
        self._build()
        self.voice.trace_add("write", self.changed)
        self.speed.trace_add("write", self.changed)
        self.volume.trace_add("write", self.changed)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F1>", lambda _: self.help())
        self.demo("essai_hugo")

    def button(self, frame: ttk.Frame, label: str, command: Callable[[], None]) -> ttk.Button:
        widget = ttk.Button(frame, text=label, command=command)
        widget.pack(side="left", padx=4, pady=4)
        self.controls.append((widget, "normal"))
        return widget

    def _build(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")
        self.button(toolbar, "Открыть TXT", self.open_text)
        self.button(toolbar, "Вставить из буфера", self.paste)
        self.button(toolbar, "Пример: Hugo", lambda: self.demo("essai_hugo"))
        self.button(toolbar, "Пример: fable", lambda: self.demo("essai_fable"))
        self.button(toolbar, "Справка · F1", self.help)
        settings = ttk.LabelFrame(self.root, text="Французский голос и параметры", padding=12)
        settings.pack(fill="x", padx=12, pady=4)
        combo = ttk.Combobox(
            settings,
            textvariable=self.voice,
            values=list(VOICES.values()),
            state="readonly",
            width=30,
        )
        combo.grid(row=0, column=0, rowspan=2, padx=10, sticky="w")
        self.controls.append((combo, "readonly"))
        ttk.Label(settings, text="Темп").grid(row=0, column=1)
        speed = ttk.Scale(settings, from_=0.5, to=2, variable=self.speed, length=250)
        speed.grid(row=0, column=2, padx=8)
        ttk.Label(settings, textvariable=self.speed_label, width=7).grid(row=0, column=3)
        ttk.Label(settings, text="Громкость").grid(row=1, column=1)
        volume = ttk.Scale(settings, from_=0, to=1, variable=self.volume, length=250)
        volume.grid(row=1, column=2, padx=8)
        ttk.Label(settings, textvariable=self.volume_label, width=7).grid(row=1, column=3)
        self.controls.extend([(speed, "normal"), (volume, "normal")])
        ttk.Label(self.root, text="Texte français · сочинение по литературе", padding=8).pack(
            anchor="w"
        )
        self.input = ScrolledText(self.root, wrap="word", font=("Segoe UI", 13), undo=True)
        self.input.pack(fill="both", expand=True, padx=12)
        self.input.bind("<<Modified>>", self.modified)
        ttk.Label(self.root, textvariable=self.count, padding=5).pack(anchor="e")
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill="x")
        self.button(bar, "▶ Читать", self.read)
        self.stop_button = ttk.Button(bar, text="■ Стоп", command=self.stop)
        self.stop_button.pack(side="left", padx=4)
        self.replay_button = self.button(bar, "Повторить", self.replay)
        self.save_button = self.button(bar, "Сохранить WAV", self.save)
        ttk.Label(self.root, textvariable=self.status, padding=10, wraplength=980).pack(fill="x")
        self.replay_button.configure(state="disabled")
        self.save_button.configure(state="disabled")

    def stop(self) -> None:
        self.autoplay = False
        self.runner.cancelled.set()
        if self.playback_after is not None:
            self.root.after_cancel(self.playback_after)
            self.playback_after = None
        try:
            self.player.stop()
        except (OSError, RuntimeError) as error:
            logging.getLogger("lab8").warning("Playback stop failed: %s", error)
        self.status.set(
            "Остановлено." if not self.runner.busy else "Отмена после текущего фрагмента…"
        )

    def invalidate(self) -> None:
        self.stop()
        self.result = None
        self.replay_button.configure(state="disabled")
        self.save_button.configure(state="disabled")

    def changed(self, *_: object) -> None:
        self.speed_label.set(f"{self.speed.get():.2f}×")
        self.volume_label.set(f"{self.volume.get():.0%}")
        self.invalidate()

    def modified(self, _: object = None) -> None:
        if self.input.edit_modified():
            self.invalidate()
            self.count.set(f"{len(self.input.get('1.0', 'end-1c'))} / 5000 символов")
            self.input.edit_modified(False)

    def set_text(self, text: str) -> None:
        self.invalidate()
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.input.edit_modified(False)
        self.count.set(f"{len(text)} / 5000 символов")
        self.status.set("Текст готов. Нажмите «Читать».")

    def demo(self, name: str) -> None:
        self.set_text((ROOT / "data" / f"{name}.txt").read_text(encoding="utf-8"))

    def open_text(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("Unicode TXT", "*.txt")])
        if value:
            try:
                path = Path(value)
                if path.stat().st_size > 1024 * 1024:
                    raise ValueError("TXT больше 1 МиБ.")
                self.set_text(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as error:
                self.error(error)

    def paste(self) -> None:
        try:
            self.set_text(self.root.clipboard_get())
        except tk.TclError:
            self.error(ValueError("В буфере нет доступного текста."))

    def busy(self, value: bool) -> None:
        for widget, state in self.controls:
            widget.configure({"state": "disabled" if value else state})
        self.input.configure(state="disabled" if value else "normal")
        if not value and self.result is None:
            self.replay_button.configure(state="disabled")
            self.save_button.configure(state="disabled")

    def read(self) -> None:
        if self.runner.busy:
            return
        try:
            voice = next(key for key, label in VOICES.items() if label == self.voice.get())
            settings = Settings(voice, self.speed.get(), self.volume.get())
            text = self.input.get("1.0", "end-1c")
        except ValueError as error:
            self.error(error)
            return
        self.invalidate()
        self.autoplay = True
        self.busy(True)
        target = ROOT / "work" / f"speech-{uuid4().hex}.wav"
        self.runner.start(
            lambda progress, cancelled: self.service.render(
                text, settings, target, progress, cancelled
            ),
            self.receive,
            self.failure,
            self.status.set,
        )

    def receive(self, value: object) -> None:
        assert isinstance(value, Result)
        self.result = value
        self.busy(False)
        self.replay_button.configure(state="normal")
        self.save_button.configure(state="normal")
        self.status.set(
            f"Готово: {value.duration:.1f} с, {value.sample_rate} Гц; "
            f"синтез {value.synthesis_seconds:.2f} с."
        )
        if self.autoplay and not self.runner.cancelled.is_set():
            self.replay()

    def replay(self) -> None:
        if self.result is None:
            return
        result = self.result
        self.stop()
        try:
            self.player.play(str(result.wav_path.resolve()))
        except (OSError, RuntimeError) as error:
            self.error(error)
            return
        self.status.set("Чтение… Нажмите «Стоп» для остановки.")

        def finished() -> None:
            self.playback_after = None
            self.status.set("Воспроизведение завершено.")

        self.playback_after = self.root.after(round(result.duration * 1000) + 100, finished)

    def save_to(self, path: Path) -> None:
        if self.result is None:
            return
        self.stop()
        export(self.result, path)
        self.status.set(f"WAV, текст и отчёт сохранены: {path}")

    def save(self) -> None:
        if self.result is None:
            return
        value = filedialog.asksaveasfilename(
            defaultextension=".wav", confirmoverwrite=False, filetypes=[("WAV PCM 16-bit", "*.wav")]
        )
        if value:
            try:
                self.save_to(Path(value))
            except (OSError, ValueError) as error:
                self.error(error)

    def failure(self, error: Exception) -> None:
        self.busy(False)
        self.error(error)

    def error(self, error: Exception) -> None:
        self.status.set(str(error))
        if isinstance(error, CancelledError):
            return
        logging.getLogger("lab8").error("%s", error, exc_info=error)
        messagebox.showerror("Лабораторная 8", str(error), parent=self.root)

    def help(self) -> None:
        messagebox.showinfo("Справка", HELP, parent=self.root)

    def close(self) -> None:
        self.stop()
        self.runner.close()
        self.root.destroy()


def launch() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()
