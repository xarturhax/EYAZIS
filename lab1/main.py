"""Запуск: python lab1/main.py. Окно → SearchEngine → результат."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

from lab1.logic import SearchEngine, fetch
from lab1.report import export, figure


class App:
    def __init__(self, root, database=None):
        self.root = root
        root.title("Лабораторная №1 — поиск BM25 · вариант 36")
        root.geometry("1100x760")
        self.engine = SearchEngine(database) if database is not None else SearchEngine()
        self.report = None
        self.messages = queue.Queue()
        self.query = tk.StringVar(value="python programming")
        self.k1, self.b = tk.DoubleVar(value=1.5), tk.DoubleVar(value=0.75)
        self.status = tk.StringVar(
            value="Загрузите демо или добавьте документы. Поиск выполняется по сохранённой коллекции."
        )
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        ttk.Label(bar, text="Запрос:").pack(side="left")
        entry = ttk.Entry(bar, textvariable=self.query, width=45)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        entry.bind("<Return>", lambda _: self.search())
        ttk.Label(bar, text="k1").pack(side="left")
        ttk.Spinbox(bar, textvariable=self.k1, from_=0.1, to=10, increment=0.1, width=5).pack(
            side="left"
        )
        ttk.Label(bar, text="b").pack(side="left", padx=(8, 0))
        ttk.Spinbox(bar, textvariable=self.b, from_=0, to=1, increment=0.05, width=5).pack(
            side="left"
        )
        ttk.Button(bar, text="Найти", command=self.search).pack(side="left", padx=5)
        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=8)
        search, collection, quality = [ttk.Frame(tabs, padding=6) for _ in range(3)]
        for frame, title in zip(
            (search, collection, quality), ("Поиск", "Коллекция", "Оценка качества")
        ):
            tabs.add(frame, text=title)
        self.results = self.table(
            search,
            ("title", "score", "matched", "url"),
            ("Документ", "BM25", "Совпали слова", "URL"),
        )
        self.results.bind("<Double-1>", self.show_document)
        ttk.Label(
            search, text="Двойной щелчок по документу — полный текст и индекс с весами TF-IDF."
        ).pack(anchor="w")
        actions = ttk.Frame(collection)
        actions.pack(fill="x")
        for title, command in (
            ("Демо-коллекция", self.demo),
            ("Загрузить URL", self.load_url),
            ("Добавить текст", self.add_text),
            ("Удалить выбранные", self.delete),
        ):
            ttk.Button(actions, text=title, command=command).pack(side="left", padx=3, pady=4)
        self.collection = self.table(
            collection, ("title", "length", "url"), ("Документ", "Слов после обработки", "URL")
        )
        self.collection.bind("<Double-1>", self.show_document)
        actions = ttk.Frame(quality)
        actions.pack(fill="x")
        for grade in (0, 1, 2):
            ttk.Button(actions, text=f"Оценка {grade}", command=lambda g=grade: self.grade(g)).pack(
                side="left", padx=3
            )
        ttk.Button(actions, text="Оценить запрос", command=lambda: self.evaluate(False)).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text="Оценить все", command=lambda: self.evaluate(True)).pack(
            side="left"
        )
        ttk.Button(actions, text="Сохранить отчёт", command=self.save).pack(side="left", padx=8)
        ttk.Label(
            quality,
            text="Выберите строки: 0 — нерелевантен, 1 — частично полезен, 2 — релевантен. Для метрик нужна вся коллекция.",
        ).pack(anchor="w", pady=5)
        self.judgments = self.table(quality, ("title", "grade"), ("Документ", "Оценка"), height=8)
        self.plot = ttk.Frame(quality)
        self.plot.pack(fill="both", expand=True)
        ttk.Label(root, textvariable=self.status, wraplength=1060, padding=8).pack(fill="x")
        self.query.trace_add("write", lambda *_: self.refresh_grades())
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)
        self.refresh()

    @staticmethod
    def table(parent, columns, headings, height=15):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=4)
        tree = ttk.Treeview(
            frame, columns=columns, show="headings", height=height, selectmode="extended"
        )
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=160, minwidth=70)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        return tree

    def safe(self, action):
        try:
            return action()
        except Exception as error:
            messagebox.showerror("Ошибка", str(error), parent=self.root)
            return None

    def refresh(self):
        self.collection.delete(*self.collection.get_children())
        for d in self.engine.documents():
            self.collection.insert(
                "", "end", iid=str(d["id"]), values=(d["title"], d["length"], d["url"])
            )
        self.refresh_grades()

    def refresh_grades(self):
        grades = self.engine.grades(self.query.get())
        self.judgments.delete(*self.judgments.get_children())
        for d in self.engine.documents():
            self.judgments.insert(
                "", "end", iid=str(d["id"]), values=(d["title"], grades.get(d["id"], "Не оценён"))
            )

    def demo(self):
        if self.safe(lambda: (self.engine.demo(), True)):
            self.report = None
            self.refresh()
            self.status.set(
                "Демо загружено: 12 документов, 5 запросов. Положительные оценки 1 и 2 равноправны в метриках."
            )

    def search(self):
        def action():
            rows = self.engine.search(self.query.get(), self.k1.get(), self.b.get())
            self.results.delete(*self.results.get_children())
            for d in rows:
                self.results.insert(
                    "",
                    "end",
                    iid=str(d["id"]),
                    values=(
                        d["title"],
                        f"{d['score']:.4f}",
                        ", ".join(d["matched_words"]),
                        d["url"],
                    ),
                )
            self.status.set(
                f"Найдено: {len(rows)}. Балл BM25 не является вероятностью. program и programming — разные слова."
            )

        self.safe(action)

    def show_document(self, event):
        tree = event.widget
        if not tree.selection():
            return
        d = self.engine.document(int(tree.selection()[0]))
        window = tk.Toplevel(self.root)
        window.title(d["title"])
        window.geometry("800x650")
        ttk.Button(window, text=d["url"], command=lambda: webbrowser.open(d["url"])).pack(fill="x")
        text = tk.Text(window, wrap="word", height=14)
        text.pack(fill="both", expand=True)
        text.insert("1.0", d["text"])
        text.configure(state="disabled")
        table = self.table(
            window, ("term", "tf", "df", "weight"), ("Термин", "TF", "DF", "TF-IDF"), height=10
        )
        for term in self.engine.index(d["id"]):
            table.insert(
                "", "end", values=(term["term"], term["tf"], term["df"], f"{term['weight']:.5f}")
            )

    def load_url(self):
        url = simpledialog.askstring("Интернет-страница", "HTTP(S) URL:", parent=self.root)
        if url:
            self.status.set("Загрузка страницы…")

            def work():
                try:
                    self.messages.put((True, fetch(url)))
                except Exception as error:
                    self.messages.put((False, str(error)))

            threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                ok, data = self.messages.get_nowait()
                if ok:
                    self.safe(lambda: self.engine.add(**data))
                    self.report = None
                    self.refresh()
                    self.status.set("Документ загружен и проиндексирован.")
                else:
                    messagebox.showerror("Загрузка", data, parent=self.root)
                    self.status.set("Не удалось загрузить страницу.")
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def add_text(self):
        window = tk.Toplevel(self.root)
        window.title("Добавить документ")
        values = []
        for label in ("URL", "Заголовок"):
            ttk.Label(window, text=label).pack(anchor="w")
            field = ttk.Entry(window, width=80)
            field.pack(fill="x")
            values.append(field)
        text = tk.Text(window, width=80, height=15, wrap="word")
        text.pack(fill="both", expand=True)

        def add():
            if (
                self.safe(
                    lambda: self.engine.add(
                        values[0].get(), values[1].get(), text.get("1.0", "end-1c")
                    )
                )
                is not None
            ):
                self.report = None
                self.refresh()
                window.destroy()

        ttk.Button(window, text="Добавить", command=add).pack(pady=6)

    def delete(self):
        ids = [int(i) for i in self.collection.selection()]
        if ids and messagebox.askyesno(
            "Удаление", "Удалить документы, индекс и их оценки?", parent=self.root
        ):
            self.safe(lambda: self.engine.delete(ids))
            self.report = None
            self.refresh()

    def grade(self, value):
        self.safe(
            lambda: self.engine.grade(
                self.query.get(), [int(i) for i in self.judgments.selection()], value
            )
        )
        self.report = None
        self.refresh_grades()

    def evaluate(self, all_queries=False):
        def action():
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            queries = self.engine.queries() if all_queries else [self.query.get()]
            self.report = self.engine.quality(queries, self.k1.get(), self.b.get())
            for child in self.plot.winfo_children():
                child.destroy()
            self.canvas = FigureCanvasTkAgg(figure(self.report), master=self.plot)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
            self.status.set("; ".join(f"{k}={v:.4f}" for k, v in self.report["averages"].items()))

        self.safe(action)

    def save(self):
        if not self.report:
            messagebox.showinfo("Отчёт", "Сначала рассчитайте метрики.", parent=self.root)
            return
        folder = filedialog.askdirectory(parent=self.root, title="Папка отчёта")
        if folder:
            self.safe(lambda: webbrowser.open(export(self.report, folder).resolve().as_uri()))

    def close(self):
        self.engine.close()
        self.root.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    App(root)
    root.mainloop()
