"""Самостоятельное окно лабораторной. Запуск: python lab3/main.py."""

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

from lab3.files import load_corpus, read_manifest
from lab3.logic import DEMO, METHOD_LABELS, Source, build_summarizer
from lab3.report import export_report


class App:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №3 — реферирование EN/ES · вариант 27")
        root.geometry("1150x820")
        self.sources = read_manifest(DEMO)
        self.language, self.domain = tk.StringVar(value="en"), tk.StringVar(value="medicine")
        self.sentences, self.keywords = tk.IntVar(value=10), tk.IntVar(value=10)
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        for title, action in (
            ("Демо", self.demo),
            ("Манифест", self.manifest),
            ("Добавить TXT/PDF", self.add),
            ("Удалить", self.remove),
        ):
            ttk.Button(bar, text=title, command=action).pack(side="left", padx=3)
        ttk.Combobox(
            bar, textvariable=self.language, values=("en", "es"), width=5, state="readonly"
        ).pack(side="left", padx=8)
        ttk.Combobox(
            bar, textvariable=self.domain, values=("medicine", "art"), width=12, state="readonly"
        ).pack(side="left")
        self.documents = ttk.Treeview(
            root, columns=("title", "lang", "domain"), show="headings", height=7
        )
        for col, title in zip(("title", "lang", "domain"), ("Документ", "Язык", "Область")):
            self.documents.heading(col, text=title)
        self.documents.pack(fill="x", padx=8)
        self.documents.bind("<<TreeviewSelect>>", self.show_document)
        settings = ttk.Frame(root, padding=8)
        settings.pack(fill="x")
        for title, value in (("Предложений", self.sentences), ("Ключевых слов", self.keywords)):
            ttk.Label(settings, text=title).pack(side="left", padx=4)
            ttk.Spinbox(settings, textvariable=value, from_=1, to=100, width=5).pack(side="left")
        ttk.Button(settings, text="Создать и сравнить", command=self.calculate).pack(
            side="left", padx=8
        )
        ttk.Button(settings, text="Отмена", command=self.cancel.set).pack(side="left")
        ttk.Button(settings, text="Сохранить отчёт", command=self.save).pack(side="left", padx=8)
        self.summary = []
        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)
        for name in ("TF-IDF × позиции", "TextRank"):
            frame = ttk.Labelframe(panes, text=name, padding=5)
            panes.add(frame, weight=1)
            text = tk.Text(frame, wrap="word", height=14)
            text.pack(fill="both", expand=True)
            self.summary.append(text)
        self.scores = ttk.Treeview(
            root, columns=("number", "text", "position", "textrank"), show="headings", height=6
        )
        for col, name in zip(
            ("number", "text", "position", "textrank"),
            ("№", "Предложение", "TF-IDF × позиции", "TextRank"),
        ):
            self.scores.heading(col, text=name)
        self.scores.column("number", width=40, stretch=False)
        self.scores.column("text", width=650)
        self.scores.pack(fill="x", padx=8, pady=4)
        ttk.Label(root, textvariable=self.status, padding=8, wraplength=1100).pack(fill="x")
        self.refresh()

    def refresh(self):
        self.result = None
        self.documents.delete(*self.documents.get_children())
        for i, source in enumerate(self.sources):
            self.documents.insert(
                "", "end", iid=str(i), values=(source.title, source.language, source.domain)
            )
        self.status.set(
            f"В корпусе {len(self.sources)} документов. IDF рассчитывается отдельно для каждого языка."
        )

    def demo(self):
        self.sources = read_manifest(DEMO)
        self.refresh()

    def manifest(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], parent=self.root)
        if path:
            try:
                self.sources = read_manifest(Path(path))
                self.refresh()
            except Exception as error:
                messagebox.showerror("Манифест", str(error), parent=self.root)

    def add(self):
        for name in filedialog.askopenfilenames(
            filetypes=[("Документы", "*.txt *.pdf")], parent=self.root
        ):
            path = Path(name)
            self.sources.append(Source(path, self.language.get(), self.domain.get(), path.stem))
        self.refresh()

    def remove(self):
        selected = {int(i) for i in self.documents.selection()}
        self.sources = [s for i, s in enumerate(self.sources) if i not in selected]
        self.refresh()

    def calculate(self):
        try:
            sources, sentences, keywords = (
                tuple(self.sources),
                self.sentences.get(),
                self.keywords.get(),
            )
            self.start(
                lambda: build_summarizer().run(
                    load_corpus(list(sources)),
                    sentences,
                    keywords,
                    self.events.put,
                    self.cancel.is_set,
                )
            )
        except Exception as error:
            messagebox.showerror("Параметры", str(error), parent=self.root)

    def show_result(self):
        if self.result.documents:
            self.documents.selection_set("0")
            self.show_document()
        self.status.set("Готово. Выберите документ, чтобы сравнить рефераты и веса предложений.")

    def show_document(self, _=None):
        if not self.result or not self.documents.selection():
            return
        d = self.result.documents[int(self.documents.selection()[0])]
        for text, summary in zip(self.summary, d.summaries):
            text.delete("1.0", "end")
            text.insert(
                "end",
                f"{METHOD_LABELS[summary.method]} · {summary.ranking_seconds:.4f} с\nКлючевые слова: "
                + ", ".join(f"{w} ({v:.3f})" for w, v in summary.keywords)
                + "\n\n",
            )
            text.insert("end", "\n\n".join(d.analyzed.sentences[i].text for i in summary.selected))
            text.insert("end", "\n\n" + "\n".join(summary.warnings))
        self.scores.delete(*self.scores.get_children())
        for i, sentence in enumerate(d.analyzed.sentences):
            self.scores.insert(
                "",
                "end",
                values=(
                    i + 1,
                    sentence.text,
                    f"{d.summaries[0].scores[i]:.4f}",
                    f"{d.summaries[1].scores[i]:.4f}",
                ),
            )
        self.status.set(
            f"Совпадение выбранных предложений (Jaccard): {d.agreement:.3f}. Это сходство методов, не точность реферирования."
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
