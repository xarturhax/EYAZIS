"""Desktop translation with the existing reusable lab2 background task runner."""

import logging
import sqlite3
import tkinter as tk
import webbrowser
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from lab2.presentation.tasks import TaskRunner

from lab4.application.translation import CancelledError
from lab4.bootstrap import ROOT, build_service
from lab4.domain.models import Entry, Result, children, with_entries
from lab4.infrastructure.export import dictionary_rows, export_report
from lab4.infrastructure.grammar import explain

HELP = """Лабораторная №4 · Вариант 12 · EN→FR

1. Вставьте английский текст или откройте UTF-8 TXT.
2. Выберите medicine (медицина) или art (художественная критика).
   Кнопки демо загружают короткие учебные примеры.
3. «Перевести» выполняет локальный перевод и пополняет SQLite-словарь.
4. Вкладка 1: словарь отсортирован по убыванию частоты в текущем тексте.
   Ключ — лемма + часть речи. Теги расшифрованы, все формы учтены.
   Двойной щелчок / «Исправить» сохраняет ручной французский эквивалент.
   «Автопополнение» обновляет автоматические записи, сохраняя ручные.
   «Сбросить правку» удаляет выбранный эквивалент; затем заполните автоматически.
5. Вкладка 2: выберите предложение, чтобы увидеть настоящее дерево
   зависимостей spaCy. ROOT — корень, head — управляющее слово.
6. «Сохранить» создаёт Unicode TXT (UTF-8 с BOM), JSON, CSV, SVG и HTML.
   «Печать» открывает HTML с кнопкой печати / сохранения PDF.

Слово при подсчёте исходника — токен spaCy с хотя бы одной буквой.
Переведённые слова — исходные словоупотребления с непустым словарным
эквивалентом. Автопереводы, совпавшие с английской леммой, до ручного
подтверждения исключаются из покрытия (review). Это не оценка точности.
Число французских слов показано отдельно.

Автословарь переводит отдельные леммы: неоднозначные эквиваленты проверяйте.
Ручная правка словаря не заменяет слова в нейронном переводе всего текста.
Область разделяет словари; модель отдельно по областям не дообучалась.
Отмена проверяется между предложениями/группами слов.
Если модель отсутствует: python -m lab4.tools.download_model.
"""


class Application:
    def __init__(self, root: tk.Tk, database: Path | None = None) -> None:
        self.root = root
        root.title("ЕЯЗиС · Лабораторная 4 · EN→FR")
        root.geometry("1320x850")
        root.minsize(1000, 680)
        self.service, self.lexicon = build_service(database)
        self.runner = TaskRunner(root)
        self.result: Result | None = None
        self.report: Path | None = None
        self.domain = tk.StringVar(value="medicine")
        self.status = tk.StringVar(value="Введите английский текст или загрузите демо.")
        self.selected_sentence = tk.StringVar()
        self.controls: list[tuple[ttk.Widget, str]] = []
        self._build()
        self.domain.trace_add("write", lambda *_: self.invalidate())
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F1>", lambda _: self.help())

    def button(self, frame: ttk.Frame, text: str, command: Callable[[], None]) -> ttk.Button:
        widget = ttk.Button(frame, text=text, command=command)
        widget.pack(side="left", padx=3, pady=3)
        self.controls.append((widget, "normal"))
        return widget

    def _build(self) -> None:
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(fill="x")
        self.button(toolbar, "Открыть TXT", self.open_text)
        self.button(toolbar, "Демо: медицина", lambda: self.demo("medicine"))
        self.button(toolbar, "Демо: искусство", lambda: self.demo("art"))
        self.button(toolbar, "Справка · F1", self.help)
        ttk.Label(toolbar, text="Область").pack(side="left", padx=8)
        combo = ttk.Combobox(
            toolbar,
            textvariable=self.domain,
            values=("medicine", "art"),
            state="readonly",
            width=12,
        )
        combo.pack(side="left")
        self.controls.append((combo, "readonly"))
        self.button(toolbar, "Перевести", self.run)
        self.cancel_button = ttk.Button(
            toolbar, text="Отмена", command=self.runner.cancelled.set, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=5)
        pane = ttk.Panedwindow(self.root, orient="horizontal")
        pane.pack(fill="both", padx=8)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=1)
        pane.add(right, weight=1)
        ttk.Label(left, text="English · входной текст").pack(anchor="w")
        ttk.Label(right, text="Français · перевод").pack(anchor="w")
        self.input = ScrolledText(left, height=10, wrap="word", font=("Segoe UI", 11))
        self.output = ScrolledText(right, height=10, wrap="word", font=("Segoe UI", 11))
        self.input.pack(fill="both", expand=True)
        self.output.pack(fill="both", expand=True)
        self.input.bind("<<Modified>>", self.modified)
        self.output.configure(state="disabled")
        self.metrics = ttk.Label(self.root, text="", padding=7)
        self.metrics.pack(fill="x")
        tabs = ttk.Notebook(self.root)
        tabs.pack(fill="both", expand=True, padx=8, pady=4)
        dictionary_tab = ttk.Frame(tabs)
        tabs.add(dictionary_tab, text="1 · Частотный словарь и грамматика")
        columns = ("lemma", "translation", "frequency", "pos", "tags", "forms", "morph", "origin")
        self.dictionary = ttk.Treeview(dictionary_tab, columns=columns, show="headings")
        for key, title, width in zip(
            columns,
            (
                "Лемма",
                "Французский",
                "Частота",
                "POS · расшифровка",
                "Теги · расшифровка",
                "Словоформы",
                "Морфология",
                "Источник",
            ),
            (110, 150, 65, 170, 230, 150, 230, 70),
            strict=True,
        ):
            self.dictionary.heading(key, text=title)
            self.dictionary.column(key, width=width, minwidth=50)
        yscroll = ttk.Scrollbar(dictionary_tab, command=self.dictionary.yview)
        xscroll = ttk.Scrollbar(dictionary_tab, orient="horizontal", command=self.dictionary.xview)
        self.dictionary.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")
        self.dictionary.pack(fill="both", expand=True)
        self.dictionary.bind("<Double-1>", lambda _: self.correct())
        tree_tab = ttk.Frame(tabs)
        tabs.add(tree_tab, text="2 · Дерево синтаксического разбора")
        self.sentence_combo = ttk.Combobox(
            tree_tab, textvariable=self.selected_sentence, state="readonly"
        )
        self.sentence_combo.pack(fill="x", padx=4, pady=4)
        self.controls.append((self.sentence_combo, "readonly"))
        self.sentence_combo.bind("<<ComboboxSelected>>", lambda _: self.show_tree())
        self.syntax = ttk.Treeview(
            tree_tab, columns=("lemma", "morph", "relation"), show="tree headings"
        )
        self.syntax.heading("#0", text="Слово [POS / тег] · зависимость")
        self.syntax.column("#0", width=650)
        for key, label in [
            ("lemma", "Лемма"),
            ("morph", "Морфология"),
            ("relation", "Расшифровка связи"),
        ]:
            self.syntax.heading(key, text=label)
        scroll = ttk.Scrollbar(tree_tab, command=self.syntax.yview)
        self.syntax.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.syntax.pack(fill="both", expand=True)
        bottom = ttk.Frame(self.root, padding=5)
        bottom.pack(fill="x")
        self.result_buttons = [
            self.button(bottom, "Исправить эквивалент", self.correct),
            self.button(bottom, "Сбросить правку", self.reset),
            self.button(bottom, "Автопополнение", self.populate),
            self.button(bottom, "Сохранить", self.save),
            self.button(bottom, "Печать", self.print_result),
        ]
        ttk.Label(self.root, textvariable=self.status, padding=7, wraplength=1250).pack(fill="x")
        self.invalidate()

    def modified(self, _: object = None) -> None:
        if self.input.edit_modified():
            self.invalidate()
            self.input.edit_modified(False)

    def invalidate(self) -> None:
        self.result, self.report = None, None
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self.metrics.configure(text="")
        self.dictionary.delete(*self.dictionary.get_children())
        self.syntax.delete(*self.syntax.get_children())
        self.sentence_combo.configure(values=[])
        self.selected_sentence.set("")
        for button in self.result_buttons:
            button.configure(state="disabled")

    def demo(self, domain: str) -> None:
        self.domain.set(domain)
        self.input.delete("1.0", "end")
        self.input.insert("1.0", (ROOT / "data/demo" / f"{domain}.txt").read_text(encoding="utf-8"))
        self.input.edit_modified(False)
        self.invalidate()

    def open_text(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Unicode TXT", "*.txt")])
        if path:
            try:
                p = Path(path)
                if p.stat().st_size > 1024 * 1024:
                    raise ValueError("Файл больше 1 МиБ.")
                text = p.read_text(encoding="utf-8-sig")
                self.input.delete("1.0", "end")
                self.input.insert("1.0", text)
                self.input.edit_modified(False)
                self.invalidate()
            except (OSError, ValueError, sqlite3.Error) as error:
                self.error(error)

    def busy(self, value: bool) -> None:
        for widget, state in self.controls:
            widget.configure({"state": "disabled" if value else state})
        self.input.configure(state="disabled" if value else "normal")
        self.cancel_button.configure(state="normal" if value else "disabled")
        if not value and self.result is None:
            for button in self.result_buttons:
                button.configure(state="disabled")

    def start(
        self,
        job: Callable[[Callable[[str], None], Callable[[], bool]], object],
        done: Callable[[object], None],
        *,
        cancellable: bool = True,
    ) -> None:
        if self.runner.busy:
            return
        self.busy(True)
        if not cancellable:
            self.cancel_button.configure(state="disabled")

        def success(value: object) -> None:
            self.busy(False)
            done(value)

        def failure(error: Exception) -> None:
            self.busy(False)
            self.error(error)

        self.runner.start(job, success, failure, self.status.set)

    def run(self) -> None:
        text, domain = self.input.get("1.0", "end-1c"), self.domain.get()
        self.invalidate()
        self.start(
            lambda progress, cancelled: self.service.run(text, domain, progress, cancelled),
            self.receive,
        )

    def receive(self, value: object) -> None:
        assert isinstance(value, Result)
        self.result = value
        self.report = None
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", value.translation)
        self.output.configure(state="disabled")
        self.metrics.configure(
            text=f"Исходных слов: {value.source_words} · "
            f"Переведённых (покрытие словарём): {value.translated_source_words} · "
            f"Французских слов: {value.target_words} · "
            "Автоматические эквиваленты требуют проверки"
        )
        self.dictionary.delete(*self.dictionary.get_children())
        for index, row in enumerate(dictionary_rows(value)):
            self.dictionary.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    row[0],
                    row[1],
                    row[2],
                    f"{row[3]} · {row[4]}",
                    row[6],
                    row[7],
                    row[8],
                    f"{row[9]} · {row[10]}",
                ),
            )
        self.sentence_combo.configure(
            values=[f"{s.index + 1}. {s.text[:130]}" for s in value.analysis.sentences]
        )
        self.sentence_combo.current(0)
        self.show_tree()
        for button in self.result_buttons:
            button.configure(state="normal")
        self.status.set(
            "Готово. Проверьте словарные эквиваленты; можно сохранить Unicode TXT и печатать."
        )

    def show_tree(self) -> None:
        self.report = None
        self.syntax.delete(*self.syntax.get_children())
        if self.result is None or self.sentence_combo.current() < 0:
            return
        sentence = self.result.analysis.sentences[self.sentence_combo.current()]
        root, mapping = children(sentence)
        pending = [(root, "")]
        while pending:
            index, parent = pending.pop()
            token = sentence.tokens[index]
            self.syntax.insert(
                parent,
                "end",
                iid=str(index),
                open=True,
                text=f"{index + 1}. {token.text} [{token.pos}/{token.tag}] · {token.dependency}",
                values=(token.lemma, token.morphology, explain(token.dependency)),
            )
            pending.extend((child, str(index)) for child in reversed(mapping[index]))

    def current_entry(self) -> Entry | None:
        if self.result is None or not self.dictionary.selection() or self.runner.busy:
            return None
        return self.result.entries[int(self.dictionary.selection()[0])]

    def model_key(self) -> str:
        assert self.result is not None
        return self.result.versions["model"] + "@" + self.result.versions["revision"]

    def correct_value(self, entry: Entry, value: str) -> None:
        assert self.result is not None
        self.lexicon.correct(entry.lemma, entry.pos, self.domain.get(), self.model_key(), value)
        entries = tuple(
            replace(e, translation=value.strip(), origin="manual")
            if (e.lemma, e.pos) == (entry.lemma, entry.pos)
            else e
            for e in self.result.entries
        )
        self.receive(with_entries(self.result, entries))

    def correct(self) -> None:
        entry = self.current_entry()
        if entry is not None:
            value = simpledialog.askstring(
                "Корректировка словаря",
                f"{entry.lemma} [{entry.pos}] → français",
                initialvalue=entry.translation,
                parent=self.root,
            )
            if value is not None:
                try:
                    self.correct_value(entry, value)
                except (OSError, ValueError, sqlite3.Error) as error:
                    self.error(error)

    def reset(self) -> None:
        entry = self.current_entry()
        if entry is not None and self.result is not None:
            try:
                self.lexicon.reset(entry.lemma, entry.pos, self.domain.get(), self.model_key())
            except sqlite3.Error as error:
                self.error(error)
                return
            entries = tuple(
                replace(e, translation="", origin="missing")
                if (e.lemma, e.pos) == (entry.lemma, entry.pos)
                else e
                for e in self.result.entries
            )
            self.receive(with_entries(self.result, entries))

    def populate(self) -> None:
        if self.result is None:
            return
        result, domain, model = self.result, self.domain.get(), self.model_key()
        self.start(
            lambda progress, cancelled: with_entries(
                result,
                self.service.populate(result.analysis, domain, model, True, progress, cancelled),
            ),
            self.receive,
        )

    def save(self, output: Path | None = None, open_after: bool = False) -> None:
        if self.result is None:
            return
        if output is None:
            value = filedialog.askdirectory(title="Сохранить результаты")
            if not value:
                return
            output = Path(value)
        result, selected = self.result, self.sentence_combo.current()

        def done(value: object) -> None:
            assert isinstance(value, Path)
            self.report = value
            self.status.set(f"Сохранено: {value}")
            if open_after:
                webbrowser.open(value.resolve().as_uri())

        self.start(lambda _p, _c: export_report(result, output, selected), done, cancellable=False)

    def print_result(self) -> None:
        if self.report:
            webbrowser.open(self.report.resolve().as_uri())
        else:
            self.save(ROOT / "reports/last", open_after=True)

    def error(self, error: Exception) -> None:
        logging.getLogger("lab4").error("%s", error, exc_info=error)
        self.status.set(str(error))
        if not isinstance(error, CancelledError):
            messagebox.showerror("Лабораторная 4", str(error), parent=self.root)

    def help(self) -> None:
        messagebox.showinfo("Справка", HELP, parent=self.root)

    def close(self) -> None:
        self.runner.close()
        self.root.destroy()


def launch() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()
