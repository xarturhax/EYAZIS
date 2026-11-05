"""Самостоятельное окно лабораторной. Запуск: python lab2/main.py."""

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

from lab2.files import load_manifest
from lab2.logic import DEMO_MANIFEST, METHOD_NAMES, CorpusEntry, Settings, build_experiment
from lab2.report import charts, export_report


class App:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №2 — определение языка EN/ES · вариант 36")
        root.geometry("1100x800")
        self.entries = load_manifest(DEMO_MANIFEST)
        self.split, self.language = tk.StringVar(value="test"), tk.StringVar(value="en")
        self.length, self.frequency, self.repeats = (
            tk.IntVar(value=5),
            tk.IntVar(value=4),
            tk.IntVar(value=5),
        )
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        for name, action in (
            ("Демо", self.demo),
            ("Открыть манифест", self.manifest),
            ("Сохранить список", self.save_manifest),
        ):
            ttk.Button(bar, text=name, command=action).pack(side="left", padx=3)
        ttk.Combobox(
            bar, textvariable=self.split, values=("train", "test"), state="readonly", width=7
        ).pack(side="left", padx=5)
        ttk.Combobox(
            bar, textvariable=self.language, values=("en", "es", "?"), state="readonly", width=5
        ).pack(side="left")
        ttk.Button(bar, text="Добавить PDF", command=self.add).pack(side="left", padx=4)
        ttk.Button(bar, text="Удалить выбранные", command=self.remove).pack(side="left")
        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=8)
        corpus, results = ttk.Frame(tabs, padding=6), ttk.Frame(tabs, padding=6)
        tabs.add(corpus, text="Корпус PDF")
        tabs.add(results, text="Сравнение методов")
        self.corpus = ttk.Treeview(
            corpus, columns=("file", "split", "language", "source"), show="headings"
        )
        for key, title in zip(
            ("file", "split", "language", "source"), ("PDF", "Роль", "Язык", "Источник")
        ):
            self.corpus.heading(key, text=title)
        self.corpus.pack(fill="both", expand=True)
        ttk.Label(
            corpus,
            text="Метки train используются для обучения; метки test — только для оценки. Не используйте один источник в обеих частях.",
            wraplength=1000,
        ).pack(anchor="w", pady=8)
        settings = ttk.Frame(root, padding=8)
        settings.pack(fill="x")
        for title, value in (
            ("Длина короткого слова", self.length),
            ("Мин. частота", self.frequency),
            ("Повторов времени", self.repeats),
        ):
            ttk.Label(settings, text=title).pack(side="left", padx=4)
            ttk.Spinbox(settings, textvariable=value, from_=1, to=20, width=5).pack(side="left")
        ttk.Button(settings, text="Обучить и сравнить", command=self.calculate).pack(
            side="left", padx=8
        )
        ttk.Button(settings, text="Отмена", command=self.cancel.set).pack(side="left")
        ttk.Button(settings, text="Сохранить отчёт", command=self.save).pack(side="left", padx=8)
        self.rows = ttk.Treeview(
            results,
            columns=("file", "truth", "short", "alphabet", "neural"),
            show="headings",
            height=8,
        )
        for key, title in zip(
            ("file", "truth", "short", "alphabet", "neural"),
            ("Документ", "Эталон", "Короткие слова", "Алфавитный", "Нейросеть"),
        ):
            self.rows.heading(key, text=title)
        self.rows.pack(fill="x")
        self.rows.bind("<<TreeviewSelect>>", self.explain)
        self.details = tk.Text(results, height=7, wrap="word")
        self.details.pack(fill="x", pady=4)
        self.plot = ttk.Frame(results)
        self.plot.pack(fill="both", expand=True)
        ttk.Label(root, textvariable=self.status, padding=8, wraplength=1080).pack(fill="x")
        self.refresh()

    def refresh(self):
        self.result = None
        self.corpus.delete(*self.corpus.get_children())
        for i, e in enumerate(self.entries):
            self.corpus.insert(
                "", "end", iid=str(i), values=(e.path.name, e.split, e.language or "?", e.source_id)
            )
        self.status.set(f"Корпус: {len(self.entries)} PDF. По умолчанию демо: 32 train + 16 test.")

    def demo(self):
        self.entries = load_manifest(DEMO_MANIFEST)
        self.refresh()

    def manifest(self):
        path = filedialog.askopenfilename(filetypes=[("Манифест", "*.json")], parent=self.root)
        if path:
            try:
                self.entries = load_manifest(Path(path))
                self.refresh()
            except Exception as error:
                messagebox.showerror("Манифест", str(error), parent=self.root)

    def save_manifest(self):
        import json
        from dataclasses import asdict

        path = filedialog.asksaveasfilename(defaultextension=".json", parent=self.root)
        if path:
            documents = [asdict(e) | {"path": str(e.path.resolve())} for e in self.entries]
            Path(path).write_text(
                json.dumps({"schema": 1, "documents": documents}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def add(self):
        if self.split.get() == "train" and self.language.get() == "?":
            messagebox.showerror("Корпус", "Для train выберите en или es.", parent=self.root)
            return
        for path in filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")], parent=self.root):
            file = Path(path)
            self.entries.append(
                CorpusEntry(
                    file,
                    self.split.get(),
                    None if self.language.get() == "?" else self.language.get(),
                    file.stem,
                    title=file.stem,
                )
            )
        self.refresh()

    def remove(self):
        selected = {int(i) for i in self.corpus.selection()}
        self.entries = [e for i, e in enumerate(self.entries) if i not in selected]
        self.refresh()

    def calculate(self):
        try:
            settings = Settings(
                max_word_length=self.length.get(),
                min_word_frequency=self.frequency.get(),
                repetitions=self.repeats.get(),
            )
            entries = tuple(self.entries)
            self.start(
                lambda: build_experiment(settings).run(entries, self.events.put, self.cancel.is_set)
            )
        except Exception as error:
            messagebox.showerror("Параметры", str(error), parent=self.root)

    def show_result(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.rows.delete(*self.rows.get_children())
        for i, row in enumerate(self.result.rows):
            labels = [
                row.predictions[m].language or "?" for m in ("short_words", "alphabet", "neural")
            ]
            self.rows.insert(
                "", "end", iid=str(i), values=(row.title, row.expected or "?", *labels)
            )
        self.details.delete("1.0", "end")
        for name, m in self.result.metrics.items():
            self.details.insert(
                "end",
                f"{METHOD_NAMES[name]}: accuracy={m['accuracy']}, F1={m['macro_f1']}, среднее {m['mean_ms']:.3f} мс\n",
            )
        self.details.insert("end", "\n".join(self.result.warnings))
        for widget in self.plot.winfo_children():
            widget.destroy()
        self.canvas = FigureCanvasTkAgg(charts(self.result), master=self.plot)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.status.set("Готово. Выберите строку результата для объяснения каждого метода.")

    def explain(self, _=None):
        if self.result and self.rows.selection():
            row = self.result.rows[int(self.rows.selection()[0])]
            self.details.delete("1.0", "end")
            for method, prediction in row.predictions.items():
                self.details.insert(
                    "end",
                    f"{METHOD_NAMES[method]}: {prediction.explanation}\nОценки: {prediction.scores}\n\n",
                )

    def save(self):
        if self.result:
            folder = filedialog.askdirectory(parent=self.root)
            if folder:
                webbrowser.open(export_report(self.result, Path(folder)).as_uri())

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
