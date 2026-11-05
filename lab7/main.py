"""Самостоятельное окно лабораторной. Запуск: python lab7/main.py."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from tkinter import filedialog, messagebox, ttk

from lab5.audio import load
from lab5.logic import ROOT as DATA
from lab5.logic import experiment
from lab7.logic import recipes, synthesize


class App:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №7 — компиляционный синтез речи")
        root.geometry("1120x900")
        self.source = tk.StringVar(value=str(DATA / "data/raw" / "references.wav"))
        self.start_time, self.end = tk.DoubleVar(value=0), tk.DoubleVar(value=1)
        self.outputs = ttk.Combobox(root, state="readonly", width=100)
        bar = ttk.Frame(root, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Исходный WAV:").pack(side="left")
        ttk.Combobox(
            bar,
            textvariable=self.source,
            values=[str(p) for p in sorted((DATA / "data/raw").glob("*.wav"))],
            width=85,
        ).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(bar, text="Открыть WAV", command=self.choose_source).pack(side="left")
        self.recipes = recipes()
        self.recipe, self.crossfade = tk.StringVar(value="ref1_syllables"), tk.DoubleVar(value=0)
        self.custom = tk.BooleanVar(value=False)
        self.units = tk.StringVar()
        settings = ttk.Frame(root, padding=8)
        settings.pack(fill="x")
        combo = ttk.Combobox(
            settings,
            textvariable=self.recipe,
            values=[r["id"] for r in self.recipes],
            state="readonly",
            width=25,
        )
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", self.select_recipe)
        ttk.Label(settings, text="Перекрытие, мс:").pack(side="left", padx=5)
        ttk.Spinbox(
            settings, textvariable=self.crossfade, from_=0, to=50, increment=1, width=6
        ).pack(side="left")
        ttk.Button(settings, text="Синтезировать из банка", command=self.calculate).pack(
            side="left", padx=8
        )
        self.description = tk.StringVar()
        ttk.Label(root, textvariable=self.description, wraplength=1050, padding=8).pack(fill="x")
        ttk.Checkbutton(
            root, text="Своя последовательность единиц (через пробел)", variable=self.custom
        ).pack(anchor="w", padx=8)
        ttk.Entry(root, textvariable=self.units).pack(fill="x", padx=8, pady=5)
        ttk.Label(
            root,
            text="Банк каждый раз извлекается из 76 подтверждённых границ. Новым WAV не присваиваются прежние слуховые оценки.",
            padding=8,
            wraplength=1050,
        ).pack(fill="x")
        self.outputs.pack(fill="x", padx=8, pady=3)
        playback = ttk.Frame(root, padding=5)
        playback.pack(fill="x")
        for name, action in (
            ("Исходник / эталон", lambda: self.play(True)),
            ("Результат", self.play),
            ("Стоп", self.stop_audio),
            ("Сохранить WAV как…", self.save_audio),
            ("Открыть графики и измерения", self.open_report),
        ):
            ttk.Button(playback, text=name, command=action).pack(side="left", padx=3)
        self.image = ttk.Label(root)
        self.image.pack(fill="both", expand=True, padx=8)
        ttk.Label(root, textvariable=self.status, padding=8, wraplength=1050).pack(fill="x")
        self.select_recipe()

    @staticmethod
    def stop_audio():
        import sounddevice as sd

        sd.stop()

    def select_recipe(self, _=None):
        recipe = next(r for r in self.recipes if r["id"] == self.recipe.get())
        self.description.set(recipe["text"] + " · " + recipe["id"])
        self.units.set(" ".join(recipe["units"]))

    def calculate(self):
        try:
            recipe, crossfade = self.recipe.get(), self.crossfade.get()
            units = self.units.get().split() if self.custom.get() else None
            self.start(lambda: synthesize(recipe, crossfade, units))
        except Exception as error:
            messagebox.showerror("Синтез", str(error), parent=self.root)

    def choose_source(self):
        path = filedialog.askopenfilename(filetypes=[("WAV", "*.wav")], parent=self.root)
        if path:
            self.source.set(path)
            audio, _ = load(Path(path))
            self.end.set(audio.duration)

    def play(self, original=False):
        import sounddevice as sd

        try:
            path = Path(self.source.get()) if original else self.result["audio"]
            if original and self.result and self.result.get("original"):
                path = self.result["original"]
            if not original and self.outputs.get():
                path = Path(self.outputs.get())
            audio, _ = load(path)
            sd.play(audio.samples, audio.rate)
        except Exception as error:
            messagebox.showerror("Аудио", str(error), parent=self.root)

    def analyze_source(self):
        source = Path(self.source.get())
        self.start(lambda: experiment(source))

    def show_result(self):
        from PIL import Image, ImageTk

        picture = Image.open(self.result["folder"] / "analysis/contours.png")
        picture.thumbnail((1050, 500))
        self.photo = ImageTk.PhotoImage(picture)
        self.image.configure(image=self.photo)
        playlist = self.result.get("playlist") or [self.result["audio"]]
        self.outputs.configure(values=[str(p) for p in playlist])
        self.outputs.current(0)
        m = self.result["metrics"]
        self.status.set(
            f"{self.result['audio'].name}: {m['duration']:.3f} с, {m['rate']} Гц; пик {m['peak']:.4f}; F0 медиана {m['f0_median_hz']}. Новые результаты требуют прослушивания."
        )

    def save_audio(self):
        if self.result:
            import shutil

            path = filedialog.asksaveasfilename(
                defaultextension=".wav", filetypes=[("WAV", "*.wav")], parent=self.root
            )
            source = Path(self.outputs.get()) if self.outputs.get() else self.result["audio"]
            if path and Path(path).resolve() != source.resolve():
                shutil.copyfile(source, path)

    def open_report(self):
        if self.result:
            webbrowser.open((self.result["folder"] / "analysis/report.html").as_uri())

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
        self.stop_audio()
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
