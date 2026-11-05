"""Самостоятельное окно лабораторной. Запуск: python lab8/main.py."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue
import time
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event
from tkinter import filedialog, messagebox, ttk

import sounddevice as sd
import soundfile as sf

from lab8.logic import ROOT, Settings, build_service
from lab8.report import report


class App:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №8 — французский синтез речи · вариант 8")
        root.geometry("1000x650")
        self.service = build_service()
        self.voice, self.speed, self.volume = (
            tk.StringVar(value="siwis"),
            tk.DoubleVar(value=1),
            tk.DoubleVar(value=80),
        )
        self.audio, self.position, self.started = None, 0, None
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        for name, action in (
            ("Пример: Гюго", lambda: self.example("essai_hugo.txt")),
            ("Пример: басня", lambda: self.example("essai_fable.txt")),
            ("Открыть TXT", self.open_text),
        ):
            ttk.Button(bar, text=name, command=action).pack(side="left", padx=4)
        ttk.Label(root, text="Французский текст (до 5000 символов):", padding=8).pack(anchor="w")
        self.text = tk.Text(root, wrap="word", height=18)
        self.text.pack(fill="both", expand=True, padx=8)
        settings = ttk.Frame(root, padding=8)
        settings.pack(fill="x")
        ttk.Label(settings, text="Голос").pack(side="left")
        ttk.Combobox(
            settings, textvariable=self.voice, values=("siwis", "tom"), width=8, state="readonly"
        ).pack(side="left", padx=4)
        ttk.Label(settings, text="Темп").pack(side="left")
        ttk.Spinbox(
            settings, textvariable=self.speed, from_=0.5, to=2, increment=0.1, width=5
        ).pack(side="left", padx=4)
        ttk.Label(settings, text="Громкость %").pack(side="left")
        ttk.Scale(settings, variable=self.volume, from_=0, to=100, length=150).pack(
            side="left", padx=4
        )
        ttk.Button(settings, text="Синтезировать", command=self.calculate).pack(side="left", padx=5)
        ttk.Button(settings, text="Отменить синтез", command=self.cancel.set).pack(side="left")
        playback = ttk.Frame(root, padding=8)
        playback.pack(fill="x")
        for name, action in (
            ("Воспроизвести / продолжить", self.play),
            ("Пауза", self.pause),
            ("Стоп", self.stop),
            ("Сохранить WAV как…", self.save),
            ("Открыть отчёт", self.open_report),
        ):
            ttk.Button(playback, text=name, command=action).pack(side="left", padx=3)
        ttk.Label(root, textvariable=self.status, padding=8, wraplength=950).pack(fill="x")
        self.example("essai_hugo.txt")

    def example(self, name):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", (ROOT / "data" / name).read_text(encoding="utf-8"))

    def open_text(self):
        path = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")], parent=self.root)
        if path:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", Path(path).read_text(encoding="utf-8-sig"))

    def calculate(self):
        try:
            text = self.text.get("1.0", "end-1c")
            settings = Settings(self.voice.get(), self.speed.get(), self.volume.get() / 100)
            target = ROOT / "reports/local" / f"speech_{datetime.now():%Y%m%d_%H%M%S_%f}.wav"
            self.stop()
            self.start(
                lambda: self.service.render(
                    text, settings, target, self.events.put, self.cancel.is_set
                )
            )
        except Exception as error:
            messagebox.showerror("Синтез", str(error), parent=self.root)

    def show_result(self):
        report(self.result)
        self.audio = sf.read(self.result.wav_path, dtype="float32")
        self.position, self.started = 0, None
        self.status.set(
            f"Готово: {self.result.wav_path.name}; {self.result.duration:.2f} с, {self.result.sample_rate} Гц. Воспроизведение запускается кнопкой."
        )

    def play(self):
        if self.audio:
            try:
                samples, rate = self.audio
                if self.started is not None:
                    self.pause()
                if self.position >= len(samples):
                    self.position = 0
                sd.play(samples[self.position :], rate)
                self.started = time.monotonic()
            except Exception as error:
                messagebox.showerror("Воспроизведение", str(error), parent=self.root)

    def pause(self):
        if self.started is not None and self.audio:
            self.position = min(
                len(self.audio[0]),
                self.position + round((time.monotonic() - self.started) * self.audio[1]),
            )
        sd.stop()
        self.started = None

    def stop(self):
        sd.stop()
        self.position, self.started = 0, None

    def save(self):
        if self.result:
            import shutil

            path = filedialog.asksaveasfilename(
                defaultextension=".wav", filetypes=[("WAV", "*.wav")], parent=self.root
            )
            if path and Path(path).resolve() != self.result.wav_path.resolve():
                shutil.copyfile(self.result.wav_path, path)

    def open_report(self):
        if self.result:
            webbrowser.open(self.result.wav_path.with_suffix(".html").as_uri())

    def start(self, function):
        if self.future is not None and not self.future.done():
            return
        self.cancel.clear()
        self.result = None
        self.status.set("Выполняется…")
        self.future = self.pool.submit(function)
        self.root.after(100, self.poll)

    def poll(self):
        try:
            while True:
                self.status.set(self.events.get_nowait())
        except queue.Empty:
            pass
        if not self.future.done():
            self.root.after(100, self.poll)
            return
        try:
            self.result = self.future.result()
            self.show_result()
        except Exception as error:
            self.status.set(str(error))
            messagebox.showerror("Выполнение", str(error), parent=self.root)

    def close(self):
        sd.stop()
        self.cancel.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    App(root)
    root.mainloop()
