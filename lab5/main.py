"""Самостоятельное окно лабораторной. Запуск: python lab5/main.py."""

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

from lab5.analysis import analyze
from lab5.audio import crop, devices, load, period_bounds, record
from lab5.logic import ROOT as DATA
from lab5.logic import experiment, output_folder, segments, status


class App:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №5 — фонетика и качество WAV")
        root.geometry("1120x940")
        self.source = tk.StringVar(value=str(DATA / "data/raw" / "vowels.wav"))
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
        settings = ttk.Frame(root, padding=6)
        settings.pack(fill="x")
        self.repeats, self.seconds = tk.IntVar(value=50), tk.DoubleVar(value=5)
        self.rate, self.bits = tk.IntVar(value=48000), tk.IntVar(value=16)
        for name, value in (
            ("Начало, с", self.start_time),
            ("Конец, с", self.end),
            ("Повторов", self.repeats),
        ):
            ttk.Label(settings, text=name).pack(side="left", padx=3)
            ttk.Entry(settings, textvariable=value, width=8).pack(side="left")
        for name, action in (
            ("Анализ", self.analyze_source),
            ("Вырезать", lambda: self.calculate("crop")),
            ("Зациклить", lambda: self.calculate("loop")),
            ("Один период", self.select_period),
            ("Сравнить частоты/биты", lambda: self.calculate("quality")),
        ):
            ttk.Button(settings, text=name, command=action).pack(side="left", padx=3)
        capture = ttk.Frame(root, padding=6)
        capture.pack(fill="x")
        ttk.Label(capture, text="Новая запись: секунд").pack(side="left")
        ttk.Entry(capture, textvariable=self.seconds, width=5).pack(side="left", padx=4)
        ttk.Combobox(
            capture,
            textvariable=self.rate,
            values=(4000, 8000, 16000, 32000, 44100, 48000),
            width=7,
            state="readonly",
        ).pack(side="left")
        ttk.Combobox(
            capture, textvariable=self.bits, values=(8, 16), width=4, state="readonly"
        ).pack(side="left", padx=4)
        ttk.Button(capture, text="Записать микрофон", command=self.capture).pack(
            side="left", padx=4
        )
        ttk.Button(capture, text="Список устройств", command=self.device_list).pack(side="left")
        ttk.Button(capture, text="Задания и записи", command=self.recording_summary).pack(
            side="left", padx=4
        )
        self.units = ttk.Treeview(
            root, columns=("id", "file", "start", "end", "kind"), show="headings", height=6
        )
        for key, title in zip(
            ("id", "file", "start", "end", "kind"),
            ("Подтверждённая единица", "Файл", "Начало", "Конец", "Тип"),
        ):
            self.units.heading(key, text=title)
        self.units.pack(fill="x", padx=8)
        self.rows = segments()
        for i, r in enumerate(self.rows):
            self.units.insert(
                "", "end", iid=str(i), values=(r["id"], r["file"], r["start"], r["end"], r["kind"])
            )
        self.units.bind("<<TreeviewSelect>>", self.select_unit)
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

    @staticmethod
    def stop_audio():
        import sounddevice as sd

        sd.stop()

    def select_unit(self, _=None):
        if self.units.selection():
            row = self.rows[int(self.units.selection()[0])]
            self.source.set(str(DATA / "data/raw" / row["file"]))
            self.start_time.set(float(row["start"]))
            self.end.set(float(row["end"]))

    def calculate(self, action):
        try:
            source, start, end, repeats = (
                Path(self.source.get()),
                self.start_time.get(),
                self.end.get(),
                self.repeats.get(),
            )
            self.start(lambda: experiment(source, action, start, end, repeats))
        except Exception as error:
            messagebox.showerror("Параметры", str(error), parent=self.root)

    def select_period(self):
        try:
            audio, _ = load(Path(self.source.get()))
            start = self.start_time.get()
            piece = crop(audio, start, self.end.get())
            frequency = analyze(piece)["f0_median_hz"]
            if frequency is None:
                raise ValueError("F0 не определена. Шумовой участок не считается периодическим.")
            first, last = period_bounds(piece, frequency)
            self.start_time.set(start + first / audio.rate)
            self.end.set(start + last / audio.rate)
            self.status.set(
                f"Выделен локальный период: {(last - first) / audio.rate:.6f} с. Границы CSV не изменены."
            )
        except Exception as error:
            messagebox.showerror("Период", str(error), parent=self.root)

    def capture(self):
        try:
            seconds, rate, bits = self.seconds.get(), self.rate.get(), self.bits.get()

            def task():
                folder = output_folder()
                path = folder / "recording.wav"
                self.events.put(f"Идёт запись: {seconds} с")
                record(path, seconds, rate, bits, None)
                return experiment(path, folder=folder)

            self.start(task)
        except Exception as error:
            messagebox.showerror("Запись", str(error), parent=self.root)

    def device_list(self):
        try:
            messagebox.showinfo("Аудиоустройства", devices(), parent=self.root)
        except Exception as error:
            messagebox.showerror("Устройства", str(error), parent=self.root)

    def recording_summary(self):
        window = tk.Toplevel(self.root)
        window.title("Исходные записи по методичке")
        text = tk.Text(window, wrap="word", width=100, height=25)
        text.pack(fill="both", expand=True)
        for row in status():
            text.insert("end", f"{row['id']}: {row['prompt']}\n{row['note'] or row['state']}\n\n")
        text.configure(state="disabled")

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
