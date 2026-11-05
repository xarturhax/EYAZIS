"""Самостоятельное окно лабораторной. Запуск: python lab6/main.py."""

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
from lab6.logic import ROOT, process, word_permutations


def points(text):
    return [
        tuple(map(float, line.replace(",", ".").split()))
        for line in text.splitlines()
        if line.strip()
    ]


class App:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №6 — просодика и мелодические контуры")
        root.geometry("1120x1000")
        self.source = tk.StringVar(value=str(DATA / "data/raw" / "student.wav"))
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
        self.start_time.set(2.41)
        self.end.set(4.49)
        self.method = tk.StringVar(value="PSOLA")
        self.semitones, self.db = tk.DoubleVar(value=0), tk.DoubleVar(value=0)
        self.gain_start, self.gain_end = tk.DoubleVar(value=0), tk.DoubleVar(value=0.84)
        self.focus, self.intonation = (
            tk.StringVar(value="Студент"),
            tk.StringVar(value="Утверждение"),
        )
        settings = ttk.Frame(root, padding=6)
        settings.pack(fill="x")
        for name, value in (
            ("Начало, с", self.start_time),
            ("Конец, с", self.end),
            ("Полутонов", self.semitones),
        ):
            ttk.Label(settings, text=name).pack(side="left", padx=3)
            ttk.Entry(settings, textvariable=value, width=7).pack(side="left")
        ttk.Combobox(
            settings,
            textvariable=self.method,
            values=("PSOLA", "Сдвиг с изменением темпа", "Контур скорости"),
            state="readonly",
            width=25,
        ).pack(side="left", padx=4)
        ttk.Button(settings, text="Анализ исходника", command=self.analyze_source).pack(side="left")
        preset = ttk.Frame(root, padding=6)
        preset.pack(fill="x")
        ttk.Combobox(
            preset,
            textvariable=self.intonation,
            values=("Утверждение", "Вопрос"),
            state="readonly",
            width=15,
        ).pack(side="left")
        ttk.Combobox(
            preset,
            textvariable=self.focus,
            values=("Студент", "писал", "реферат"),
            state="readonly",
            width=12,
        ).pack(side="left", padx=4)
        ttk.Button(preset, text="Начальный контур", command=self.preset).pack(side="left")
        ttk.Button(preset, text="Открыть один из 6 оценённых опытов", command=self.selected).pack(
            side="left", padx=8
        )
        self.word_group = tk.StringVar(value="word")
        ttk.Combobox(
            preset,
            textvariable=self.word_group,
            values=("word", "stress1", "stress2", "stress3"),
            state="readonly",
            width=8,
        ).pack(side="left", padx=3)
        ttk.Button(preset, text="6 перестановок", command=self.permutations).pack(side="left")
        panes = ttk.Frame(root, padding=6)
        panes.pack(fill="x")
        self.pitch, self.duration, self.speed = [], [], []
        for label, attr in (
            ("F0: время_с частота_Гц", "pitch"),
            ("Длительность: время_с коэффициент", "duration"),
            ("Скорость: время_с коэффициент", "speed"),
        ):
            frame = ttk.Labelframe(panes, text=label)
            frame.pack(side="left", fill="x", expand=True, padx=3)
            field = tk.Text(frame, height=4, width=28)
            field.pack(fill="x")
            setattr(self, attr, field)
        gain = ttk.Frame(root, padding=6)
        gain.pack(fill="x")
        for name, value in (
            ("Усиление, дБ", self.db),
            ("От, с", self.gain_start),
            ("До, с", self.gain_end),
        ):
            ttk.Label(gain, text=name).pack(side="left", padx=3)
            ttk.Entry(gain, textvariable=value, width=6).pack(side="left")
        ttk.Button(gain, text="Применить преобразования", command=self.calculate).pack(
            side="left", padx=8
        )
        ttk.Label(gain, text="Время контуров отсчитывается от начала вырезанной фразы.").pack(
            side="left"
        )
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
        self.preset()

    @staticmethod
    def stop_audio():
        import sounddevice as sd

        sd.stop()

    def preset(self):
        try:
            duration = self.end.get() - self.start_time.get()
            if duration <= 0:
                raise ValueError("Конец должен быть позже начала.")
            focus = {"Студент": 0.2, "писал": 0.52, "реферат": 0.82}[self.focus.get()]
            contour = [
                (0, 150),
                (duration * max(0.05, focus - 0.12), 155),
                (duration * focus, 210),
                (duration * min(0.95, focus + 0.12), 155),
                (duration, 220 if self.intonation.get() == "Вопрос" else 110),
            ]
            self.pitch.delete("1.0", "end")
            self.pitch.insert("1.0", "\n".join(f"{t:.3f} {f}" for t, f in contour))
            self.duration.delete("1.0", "end")
            self.speed.delete("1.0", "end")
            self.speed.insert("1.0", f"0 1\n{duration:.3f} 1")
            self.status.set(
                "Начальный учебный контур; вопрос и выделение проверяются прослушиванием. Готовые оценённые результаты сохранены отдельно."
            )
        except Exception as error:
            messagebox.showerror("Контур", str(error), parent=self.root)

    def calculate(self):
        try:
            args = (
                Path(self.source.get()),
                self.start_time.get(),
                self.end.get(),
                self.method.get(),
                points(self.pitch.get("1.0", "end")),
                points(self.duration.get("1.0", "end")),
                points(self.speed.get("1.0", "end")),
                self.semitones.get(),
                (self.gain_start.get(), self.gain_end.get(), self.db.get())
                if self.db.get()
                else None,
            )
            self.start(lambda: process(*args))
        except Exception as error:
            messagebox.showerror("Параметры", str(error), parent=self.root)

    def selected(self):
        path = filedialog.askopenfilename(
            initialdir=ROOT / "reports/local/lab6_selected_examples",
            filetypes=[("WAV", "*.wav")],
            parent=self.root,
        )
        if path:
            source = Path(path)
            self.source.set(path)
            self.start(lambda: experiment(source))

    def permutations(self):
        prefix = self.word_group.get()
        self.start(lambda: word_permutations(prefix))

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
