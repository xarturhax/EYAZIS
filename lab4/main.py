"""Самостоятельное окно лабораторной. Запуск: python lab4/main.py."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from tkinter import filedialog, messagebox, simpledialog, ttk

from lab4.logic import ROOT, build_service, children, tag_descriptions
from lab4.report import export_report


class App:
    def __init__(self, root, database=None):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №4 — перевод EN → FR · вариант 12")
        root.geometry("1200x850")
        self.service, self.lexicon = build_service(database)
        self.domain = tk.StringVar(value="medicine")
        self.sentence = tk.StringVar()
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        ttk.Combobox(
            bar, textvariable=self.domain, values=("medicine", "art"), state="readonly", width=12
        ).pack(side="left")
        for name, action in (
            ("Пример: медицина", lambda: self.example("medicine")),
            ("Пример: искусство", lambda: self.example("art")),
            ("Открыть TXT", self.open_text),
            ("Перевести и разобрать", self.calculate),
            ("Отмена", self.cancel.set),
            ("Сохранить отчёт", self.save),
        ):
            ttk.Button(bar, text=name, command=action).pack(side="left", padx=3)
        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8)
        self.source, self.target = (
            tk.Text(panes, wrap="word", height=12),
            tk.Text(panes, wrap="word", height=12),
        )
        panes.add(self.source, weight=1)
        panes.add(self.target, weight=1)
        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=8, pady=6)
        dictionary, grammar = ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(dictionary, text="Частотный словарь — двойной щелчок для правки")
        tabs.add(grammar, text="Дерево зависимостей и грамматика")
        columns = ("lemma", "translation", "freq", "pos", "forms", "tags", "morph", "origin")
        self.dictionary = ttk.Treeview(dictionary, columns=columns, show="headings", height=9)
        for key, name in zip(
            columns,
            (
                "Лемма",
                "Перевод",
                "Частота",
                "Часть речи",
                "Словоформы",
                "Теги",
                "Морфология",
                "Источник",
            ),
        ):
            self.dictionary.heading(key, text=name)
            self.dictionary.column(key, width=120)
        self.dictionary.pack(fill="both", expand=True)
        self.dictionary.bind("<Double-1>", self.correct)
        self.sentences = ttk.Combobox(grammar, textvariable=self.sentence, state="readonly")
        self.sentences.pack(fill="x", pady=4)
        self.sentences.bind("<<ComboboxSelected>>", self.show_tree)
        self.tree = ttk.Treeview(
            grammar, columns=("pos", "tag", "dep", "morph"), show="tree headings", height=9
        )
        self.tree.heading("#0", text="Слово → зависимые слова")
        for col, name in (
            ("pos", "Часть речи"),
            ("tag", "Penn tag"),
            ("dep", "Связь"),
            ("morph", "Морфология"),
        ):
            self.tree.heading(col, text=name)
        self.tree.pack(fill="both", expand=True)
        ttk.Label(root, textvariable=self.status, padding=8, wraplength=1150).pack(fill="x")
        self.example("medicine")

    def example(self, domain):
        self.domain.set(domain)
        path = ROOT / "data/demo" / f"source_{domain}.txt"
        if not path.exists():
            path = ROOT / "data/demo" / f"{domain}.txt"
        self.source.delete("1.0", "end")
        self.source.insert("1.0", path.read_text(encoding="utf-8"))
        self.result = None

    def open_text(self):
        path = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")], parent=self.root)
        if path:
            self.source.delete("1.0", "end")
            self.source.insert("1.0", Path(path).read_text(encoding="utf-8-sig"))
            self.result = None

    def calculate(self):
        text, domain = self.source.get("1.0", "end-1c"), self.domain.get()
        self.active_domain = domain
        self.start(lambda: self.service.run(text, domain, self.events.put, self.cancel.is_set))

    def show_result(self):
        self.target.delete("1.0", "end")
        self.target.insert("1.0", self.result.translation)
        self.dictionary.delete(*self.dictionary.get_children())
        for i, e in enumerate(self.result.entries):
            self.dictionary.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    e.lemma,
                    e.translation,
                    e.frequency,
                    e.pos,
                    ", ".join(f"{f}: {n}" for f, n in e.forms),
                    tag_descriptions(e.tags),
                    "; ".join(e.morphology),
                    e.origin,
                ),
            )
        self.sentences.configure(
            values=[f"{i + 1}. {s.text}" for i, s in enumerate(self.result.analysis.sentences)]
        )
        if self.result.analysis.sentences:
            self.sentences.current(0)
            self.show_tree()
        self.status.set(
            f"Исходных слов: {self.result.source_words}; покрыто словарём: {self.result.translated_source_words}; слов перевода: {self.result.target_words}. Покрытие не является точностью перевода."
        )

    def show_tree(self, _=None):
        if not self.result or self.sentences.current() < 0:
            return
        sentence = self.result.analysis.sentences[self.sentences.current()]
        root, branches = children(sentence)
        tokens = {t.index: t for t in sentence.tokens}
        self.tree.delete(*self.tree.get_children())

        def add(ident, parent=""):
            t = tokens[ident]
            node = self.tree.insert(
                parent,
                "end",
                text=t.text,
                values=(t.pos, t.tag, t.dependency, t.morphology),
                open=True,
            )
            for child in branches.get(ident, []):
                add(child, node)

        add(root)

    def correct(self, _=None):
        if not self.result or not self.dictionary.selection():
            return
        index = int(self.dictionary.selection()[0])
        e = self.result.entries[index]
        text = simpledialog.askstring(
            "Правка словаря", e.lemma, initialvalue=e.translation, parent=self.root
        )
        if text is not None:
            try:
                model = self.result.versions["model"] + "@" + self.result.versions["revision"]
                self.lexicon.correct(e.lemma, e.pos, self.active_domain, model, text)
                entries = list(self.result.entries)
                entries[index] = replace(e, translation=text.strip(), origin="manual")
                self.result = replace(
                    self.result,
                    entries=tuple(entries),
                    translated_source_words=sum(e.frequency for e in entries if e.covered),
                )
                self.show_result()
            except Exception as error:
                messagebox.showerror("Правка", str(error), parent=self.root)

    def save(self):
        if self.result:
            folder = filedialog.askdirectory(parent=self.root)
            if folder:
                webbrowser.open(
                    export_report(
                        self.result, Path(folder), max(0, self.sentences.current())
                    ).as_uri()
                )

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
