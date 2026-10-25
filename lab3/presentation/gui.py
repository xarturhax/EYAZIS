"""Tk widgets only run on the main thread; a daemon worker reports through a queue."""

import logging
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from lab3.application.experiment import CancelledError
from lab3.bootstrap import DEMO, ROOT, build_summarizer
from lab3.domain.models import METHOD_LABELS, Experiment, Source
from lab3.infrastructure.documents import load_corpus, read_manifest, save_manifest, source_url
from lab3.infrastructure.export import export_report

HELP = """Лабораторная №3 · вариант 27

1. «Демо» загружает четыре документа EN/ES по медицине и искусству.
   Для своего корпуса выберите язык и область и добавьте TXT/PDF.
   TXT: UTF-8, пустая строка между абзацами.
2. Укажите размер реферата (по умолчанию 10) и число ключевых слов.
3. «Сравнить» выполняет оба метода. Модели загружаются при первом запуске.
4. Выберите документ в таблице и метод просмотра.
   Вкладки показывают исходный текст, реферат, ключевые слова и веса.
5. «Сохранить отчёт» создаёт HTML, JSON, CSV и копии входного текста.
   «Печать» открывает отчёт с кнопкой печати / сохранения PDF.

IDF считается по всем документам выбранного языка, включая текущий.
Один документ даёт нулевой IDF: добавьте несколько разных текстов.
Латинские слова сохраняются; числа и стоп-слова исключаются из признаков.
Исходные предложения не перефразируются. PDF-блоки могут отличаться
от настоящих абзацев: для точных позиций используйте подготовленный TXT.

TextRank заменяет необязательный OSTIS как сравнительный алгоритм.
Совпадение предложений не является точностью. В экспертной CSV-форме
оценки 1–5 заполняет человек после чтения текста; автоматических оценок нет.
Отмена срабатывает между этапами: текущая обработка документа завершается.
"""


class Application:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("ЕЯЗиС · Лабораторная 3 · Вариант 27")
        root.geometry("1220x820")
        root.minsize(960, 640)
        self.sources: list[Source] = []
        self.result: Experiment | None = None
        self.report: Path | None = None
        self.service = build_summarizer()
        self.busy = False
        self.closed = False
        self.cancelled = Event()
        self.events: Queue[tuple[str, object]] = Queue()
        self.poll_id: str | None = None
        self.status = tk.StringVar(value="Загрузите демо или добавьте документы.")
        self.language = tk.StringVar(value="en")
        self.domain = tk.StringVar(value="medicine")
        self.url = tk.StringVar()
        self.sentences = tk.StringVar(value="10")
        self.keyword_count = tk.StringVar(value="10")
        self.method = tk.StringVar(value=METHOD_LABELS["position"])
        self.controls: list[tuple[ttk.Widget, str]] = []
        self._build()
        self.sentences.trace_add("write", self.invalidate)
        self.keyword_count.trace_add("write", self.invalidate)
        self.method.trace_add("write", lambda *_: self.show_result())
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F1>", lambda _: self.help())

    def button(self, parent: ttk.Frame, label: str, command: Callable[[], None]) -> ttk.Button:
        widget = ttk.Button(parent, text=label, command=command)
        widget.pack(side="left", padx=3, pady=4)
        self.controls.append((widget, "normal"))
        return widget

    def _build(self) -> None:
        bar = ttk.Frame(self.root, padding=6)
        bar.pack(fill="x")
        self.button(bar, "Демо", self.demo)
        self.button(bar, "Открыть корпус", self.open_manifest)
        self.button(bar, "Сохранить корпус", self.save_corpus)
        self.button(bar, "Удалить", self.remove)
        self.button(bar, "Справка · F1", self.help)
        add = ttk.Frame(self.root, padding=6)
        add.pack(fill="x")
        for label, variable, values in [
            ("Язык", self.language, ("en", "es")),
            ("Область", self.domain, ("medicine", "art")),
        ]:
            ttk.Label(add, text=label).pack(side="left")
            combo = ttk.Combobox(
                add, textvariable=variable, values=values, width=12, state="readonly"
            )
            combo.pack(side="left", padx=4)
            self.controls.append((combo, "readonly"))
        ttk.Label(add, text="Ссылка (необязательно)").pack(side="left", padx=5)
        entry = ttk.Entry(add, textvariable=self.url, width=35)
        entry.pack(side="left", fill="x", expand=True)
        self.controls.append((entry, "normal"))
        self.button(add, "Добавить TXT/PDF", self.add)
        self.tree = ttk.Treeview(
            self.root,
            columns=("language", "domain", "title"),
            show="headings",
            height=5,
            selectmode="extended",
        )
        for name, title, width in [
            ("language", "Язык", 65),
            ("domain", "Область", 100),
            ("title", "Документ", 760),
        ]:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width)
        self.tree.pack(fill="x", padx=10)
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.show_result())
        action = ttk.Frame(self.root, padding=6)
        action.pack(fill="x")
        for label, variable in [
            ("Предложений", self.sentences),
            ("Ключевых слов", self.keyword_count),
        ]:
            ttk.Label(action, text=label).pack(side="left", padx=4)
            spin = ttk.Spinbox(action, from_=1, to=100, textvariable=variable, width=5)
            spin.pack(side="left")
            self.controls.append((spin, "normal"))
        self.button(action, "Сравнить", self.run)
        self.cancel_button = ttk.Button(
            action, text="Отмена", command=self.cancelled.set, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=4)
        ttk.Combobox(
            action,
            textvariable=self.method,
            values=list(METHOD_LABELS.values()),
            state="readonly",
            width=22,
        ).pack(side="right")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=5)
        texts = ttk.Frame(self.tabs)
        self.tabs.add(texts, text="Текст и реферат")
        pane = ttk.Panedwindow(texts, orient="horizontal")
        pane.pack(fill="both", expand=True)
        self.original = ScrolledText(pane, wrap="word", font=("Segoe UI", 11), width=50)
        self.summary = ScrolledText(pane, wrap="word", font=("Segoe UI", 11), width=50)
        pane.add(self.original, weight=1)
        pane.add(self.summary, weight=1)
        self.original.tag_configure("selected", background="#d6eee4")
        scores = ttk.Frame(self.tabs)
        self.tabs.add(scores, text="Веса предложений")
        self.score_tree = ttk.Treeview(
            scores, columns=("index", "score", "selected", "text"), show="headings"
        )
        for key, title, width in [
            ("index", "№", 50),
            ("score", "Вес", 100),
            ("selected", "Выбрано", 70),
            ("text", "Предложение", 800),
        ]:
            self.score_tree.heading(key, text=title)
            self.score_tree.column(key, width=width)
        scroll = ttk.Scrollbar(scores, orient="vertical", command=self.score_tree.yview)
        self.score_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.score_tree.pack(fill="both", expand=True)
        self.comparison = ScrolledText(self.tabs, wrap="word", font=("Consolas", 11))
        self.tabs.add(self.comparison, text="Сравнение")
        bottom = ttk.Frame(self.root, padding=6)
        bottom.pack(fill="x")
        self.export_button = self.button(bottom, "Сохранить отчёт", self.save_report)
        self.print_button = self.button(bottom, "Печать", self.print_report)
        self.source_button = self.button(bottom, "Открыть оригинал", self.open_source)
        ttk.Label(self.root, textvariable=self.status, padding=8, wraplength=1150).pack(fill="x")
        self.invalidate()

    @staticmethod
    def set_text(widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure({"state": "disabled"})

    def invalidate(self, *_: object) -> None:
        self.result = None
        self.report = None
        self.set_text(self.original, "")
        self.set_text(self.summary, "")
        self.set_text(self.comparison, "")
        self.score_tree.delete(*self.score_tree.get_children())
        self.export_button.configure(state="disabled")
        self.print_button.configure(state="disabled")

    def refresh_sources(self) -> None:
        self.invalidate()
        self.tree.delete(*self.tree.get_children())
        for i, source in enumerate(self.sources):
            self.tree.insert(
                "", "end", iid=str(i), values=(source.language, source.domain, source.title)
            )
        if self.sources:
            self.tree.selection_set("0")
        self.status.set(f"Документов: {len(self.sources)}. Нажмите «Сравнить».")

    def demo(self) -> None:
        self.open_manifest(DEMO)

    def open_manifest(self, path: Path | None = None) -> None:
        if self.busy:
            return
        if path is None:
            chosen = filedialog.askopenfilename(filetypes=[("Корпус JSON", "*.json")])
            if not chosen:
                return
            path = Path(chosen)
        try:
            self.sources = read_manifest(path)
            self.refresh_sources()
        except (OSError, ValueError) as error:
            self.error(error)

    def save_corpus(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Корпус JSON", "*.json")]
        )
        if path:
            try:
                save_manifest(Path(path), self.sources)
            except OSError as error:
                self.error(error)

    def add(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=[("Документы", "*.txt *.pdf")])
        try:
            url = source_url(self.url.get().strip())
            self.sources.extend(
                Source(Path(p), self.language.get(), self.domain.get(), Path(p).stem, url)
                for p in paths
            )
            self.refresh_sources()
        except ValueError as error:
            self.error(error)

    def remove(self) -> None:
        for index in sorted((int(i) for i in self.tree.selection()), reverse=True):
            del self.sources[index]
        self.refresh_sources()

    def start_job(
        self, job: Callable[[], object], done: Callable[[object], None], *, cancellable: bool = True
    ) -> None:
        if self.busy:
            return
        self.busy = True
        self.cancelled.clear()
        for widget, _ in self.controls:
            widget.configure({"state": "disabled"})
        self.cancel_button.configure(state="normal" if cancellable else "disabled")

        def worker() -> None:
            try:
                self.events.put(("done", job()))
            except Exception as error:
                logging.getLogger("lab3").exception("Background task failed")
                self.events.put(("error", error))

        def poll() -> None:
            self.poll_id = None
            if self.closed:
                return
            try:
                while True:
                    kind, value = self.events.get_nowait()
                    if kind == "progress":
                        self.status.set(str(value))
                        continue
                    self.busy = False
                    for widget, state in self.controls:
                        widget.configure({"state": state})
                    self.cancel_button.configure(state="disabled")
                    if self.result is None:
                        self.export_button.configure(state="disabled")
                        self.print_button.configure(state="disabled")
                    if kind == "done":
                        done(value)
                    else:
                        assert isinstance(value, Exception)
                        self.error(value)
                    return
            except Empty:
                pass
            self.poll_id = self.root.after(80, poll)

        Thread(target=worker, daemon=True).start()
        self.poll_id = self.root.after(80, poll)

    def run(self) -> None:
        try:
            count, words = int(self.sentences.get()), int(self.keyword_count.get())
            if not 1 <= count <= 100 or not 1 <= words <= 100:
                raise ValueError("Размер реферата и число ключевых слов: от 1 до 100.")
        except ValueError as error:
            self.error(error)
            return
        sources = list(self.sources)
        self.invalidate()
        self.start_job(
            lambda: self.service.run(
                load_corpus(sources),
                count,
                words,
                lambda message: self.events.put(("progress", message)),
                self.cancelled.is_set,
            ),
            self.receive,
        )

    def receive(self, value: object) -> None:
        assert isinstance(value, Experiment)
        self.result = value
        self.export_button.configure(state="normal")
        self.print_button.configure(state="normal")
        self.status.set("Готово. Выберите документ и метод; можно сохранить или распечатать отчёт.")
        self.show_result()

    def show_result(self) -> None:
        if self.result is None or not self.tree.selection():
            return
        result = self.result.documents[int(self.tree.selection()[0])]
        method = next(key for key, label in METHOD_LABELS.items() if label == self.method.get())
        summary = next(s for s in result.summaries if s.method == method)
        self.set_text(self.original, result.analyzed.document.text)
        self.original.tag_remove("selected", "1.0", "end")
        for index in summary.selected:
            sentence = result.analyzed.sentences[index]
            self.original.tag_add("selected", f"1.0+{sentence.start}c", f"1.0+{sentence.end}c")
        text = "КЛАССИЧЕСКИЙ РЕФЕРАТ\n\n" + "\n\n".join(
            result.analyzed.sentences[i].text for i in summary.selected
        )
        text += "\n\nКЛЮЧЕВЫЕ СЛОВА\n\n" + "; ".join(w for w, _ in summary.keywords)
        text += "\n\n" + "\n".join(self.result.warnings + summary.warnings)
        self.set_text(self.summary, text)
        self.score_tree.delete(*self.score_tree.get_children())
        for sentence, score in zip(result.analyzed.sentences, summary.scores, strict=True):
            self.score_tree.insert(
                "",
                "end",
                values=(
                    sentence.index + 1,
                    f"{score:.6f}",
                    "✓" if sentence.index in summary.selected else "",
                    sentence.text,
                ),
            )
        lines = ["Jaccard — согласие методов; качество требует экспертной оценки.\n"]
        for item in self.result.documents:
            lines.append(
                f"{item.analyzed.document.source.title}\n"
                f"  NLP: {item.analyzed.preprocessing_seconds * 1000:.2f} мс; "
                f"Jaccard: {item.agreement:.3f}"
            )
            for outcome in item.summaries:
                lines.append(
                    f"  {METHOD_LABELS[outcome.method]}: "
                    f"{outcome.ranking_seconds * 1000:.2f} мс; "
                    f"сохранено слов {outcome.word_ratio:.1%}"
                )
            lines.append("")
        self.set_text(self.comparison, "\n".join(lines))

    def save_report(self, output: Path | None = None, open_after: bool = False) -> None:
        if self.result is None or self.busy:
            return
        if output is None:
            chosen = filedialog.askdirectory(title="Папка для отчёта")
            if not chosen:
                return
            output = Path(chosen)
        result = self.result

        def done(value: object) -> None:
            assert isinstance(value, Path)
            self.report = value
            self.status.set(f"Отчёт сохранён: {value}")
            if open_after:
                webbrowser.open(value.resolve().as_uri())

        self.status.set("Сохранение отчёта…")
        self.start_job(lambda: export_report(result, output), done, cancellable=False)

    def print_report(self) -> None:
        if self.report is not None:
            webbrowser.open(self.report.resolve().as_uri())
        else:
            self.save_report(ROOT / "reports" / "last", open_after=True)

    def open_source(self) -> None:
        if self.tree.selection():
            source = self.sources[int(self.tree.selection()[0])]
            webbrowser.open(source.path.resolve().as_uri())

    def error(self, error: Exception) -> None:
        self.status.set(str(error))
        if not isinstance(error, CancelledError):
            messagebox.showerror("Лабораторная 3", str(error), parent=self.root)

    def help(self) -> None:
        messagebox.showinfo("Справка", HELP, parent=self.root)

    def close(self) -> None:
        self.closed = True
        self.cancelled.set()
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
        self.root.destroy()


def launch() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()
