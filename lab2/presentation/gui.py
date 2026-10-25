"""Настольный интерфейс; обучение и экспорт выполняются в фоне."""

import json
import logging
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from lab2.bootstrap import DEMO_MANIFEST, ROOT, build_experiment
from lab2.domain.models import (
    LANGUAGE_NAMES,
    METHOD_NAMES,
    CorpusEntry,
    ExperimentReport,
    LabError,
    Language,
    Settings,
    Split,
)
from lab2.infrastructure.corpus import load_manifest, save_manifest
from lab2.infrastructure.export import charts, export_report

from .tasks import TaskRunner

HELP = """ЛАБОРАТОРНАЯ №2 · ВАРИАНТ 36

Быстрый запуск
1. Нажмите «Демо-коллекция».
2. Нажмите «Обучить и сравнить».
3. На вкладке результатов выберите документ: ниже появятся оценки и объяснения.
4. «Экспорт отчёта» сохраняет HTML, JSON, CSV, SVG и PNG.
5. «Печать» открывает HTML: нажмите в нём «Распечатать» или Ctrl+P.

Свои PDF
Выберите роль train/test и язык EN/ES перед добавлением.
Для тестового PDF язык можно оставить неизвестным: он будет распознан, но не войдёт
в оценку точности. Нужны обучающие документы обоих языков.
Одинаковые исходные книги не должны попадать одновременно в train и test.
Для своих отрывков укажите одинаковый source_id исходной книги в JSON-манифесте
(«Сохранить список»). Дубликаты текста проверяются автоматически.
При изменении списка или параметров предыдущий результат сбрасывается.

Методы
Короткие слова: длина до 5, не менее 4 появлений в языковом обучающем корпусе;
сглаживание и отрицательная средняя log-вероятность. Стоп-слова сохраняются.
Алфавитный: L1-расстояние между частотами отдельных букв.
Это статистический вариант метода для языков с общей латиницей.
Нейросетевой: символьные TF-IDF 2–4 -> MLP, один скрытый слой.
Числа разных методов имеют разные шкалы; сравнивать их между собой нельзя.

Метрики и время
Accuracy — доля правильных ответов среди размеченных тестовых PDF.
Отказ считается ошибкой, неразмеченные PDF исключаются.
Измеряется медиана повторов после прогрева; чтение PDF и обучение учитываются отдельно.
Размер обучения — нормализованный UTF-8 текст: 20–120 KiB на язык.
Тестовые документы должны быть примерно одного размера.
Демо — литература; точность на ней не гарантирует качество на других жанрах.

Ограничения
PDF должен иметь текстовый слой. OCR и парольные файлы не поддерживаются.
Выбор осуществляется только между EN и ES. Короткий, смешанный или третий язык
может дать ошибочный ответ. Оценки MLP не калиброваны.
Отмена проверяется между этапами; текущий fit нейросети завершается перед отменой.
"""


class Application:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.entries: list[CorpusEntry] = []
        self.report: ExperimentReport | None = None
        self.last_export: Path | None = None
        self.canvas: FigureCanvasTkAgg | None = None
        self.tasks = TaskRunner(root)
        root.title("ЕЯЗиС · Лабораторная 2 · Вариант 36")
        root.geometry("1180x800")
        root.minsize(950, 650)
        self.status = tk.StringVar(value="Загрузите демо-коллекцию или добавьте PDF.")
        self.role = tk.StringVar(value="test")
        self.language = tk.StringVar(value="en")
        self.seed = tk.StringVar(value="36")
        self.repetitions = tk.StringVar(value="5")
        self.controls: list[ttk.Button | ttk.Entry | ttk.Combobox] = []
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F1>", lambda _: self.help())
        self.seed.trace_add("write", lambda *_: self.invalidate())
        self.repetitions.trace_add("write", lambda *_: self.invalidate())

    def button(self, parent: tk.Misc, text: str, command: Callable[[], None]) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side="left", padx=3, pady=4)
        self.controls.append(button)
        return button

    @staticmethod
    def tree(parent: tk.Misc, columns: tuple[str, ...], headers: tuple[str, ...]) -> ttk.Treeview:
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)
        tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="extended")
        scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        for column, label in zip(columns, headers, strict=True):
            tree.heading(column, text=label)
            tree.column(column, width=130, minwidth=65)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _build(self) -> None:
        banner = ttk.Frame(self.root, padding=12)
        banner.pack(fill="x")
        ttk.Label(banner, text="Распознавание языка PDF", font=("Segoe UI", 18, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            banner, text="EN / ES   •   Короткие слова   •   Алфавитный профиль   •   Нейросеть"
        ).pack(anchor="w")
        toolbar = ttk.Frame(self.root, padding=(8, 0))
        toolbar.pack(fill="x")
        self.button(toolbar, "Демо-коллекция", self.load_demo)
        self.button(toolbar, "Открыть список", self.open_manifest)
        self.button(toolbar, "Сохранить список", self.save_list)
        self.button(toolbar, "Обучить и сравнить", self.analyze)
        self.button(toolbar, "Экспорт отчёта", self.export)
        self.button(toolbar, "Печать", self.print_report)
        self.button(toolbar, "Справка · F1", self.help)
        self.cancel_button = ttk.Button(
            toolbar, text="Отмена", command=self.tasks.cancelled.set, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=3)
        settings = ttk.Frame(self.root, padding=(12, 4))
        settings.pack(fill="x")
        for label, variable in (("Seed", self.seed), ("Повторов времени", self.repetitions)):
            ttk.Label(settings, text=label).pack(side="left", padx=4)
            field = ttk.Entry(settings, textvariable=variable, width=7)
            field.pack(side="left", padx=4)
            self.controls.append(field)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)
        collection, results, graphs = (ttk.Frame(self.notebook, padding=8) for _ in range(3))
        for frame, name in (
            (collection, "Коллекция"),
            (results, "Результаты"),
            (graphs, "Графики"),
        ):
            self.notebook.add(frame, text=name)
        add = ttk.Frame(collection)
        add.pack(fill="x")
        for label, variable, values in (
            ("Роль", self.role, ("train", "test")),
            ("Язык", self.language, ("en", "es", "?")),
        ):
            ttk.Label(add, text=label).pack(side="left", padx=4)
            combo = ttk.Combobox(
                add, textvariable=variable, values=values, state="readonly", width=8
            )
            combo.pack(side="left", padx=4)
            self.controls.append(combo)
        self.button(add, "Добавить PDF", self.add_pdfs)
        self.button(add, "Удалить выбранные", self.remove)
        self.button(add, "Открыть PDF", self.open_pdf)
        self.collection_tree = self.tree(
            collection,
            ("role", "lang", "file", "source"),
            ("Роль", "Эталонный язык", "PDF", "Источник"),
        )
        self.collection_tree.column("file", width=430)
        self.collection_tree.bind("<Double-1>", lambda _: self.open_pdf())
        self.summary = ttk.Label(
            results, text="Результат появится после сравнения.", wraplength=1040
        )
        self.summary.pack(fill="x", pady=(0, 8))
        self.result_tree = self.tree(
            results, ("file", "truth", *METHOD_NAMES), ("PDF", "Эталон", *METHOD_NAMES.values())
        )
        self.result_tree.column("file", width=300)
        self.result_tree.bind("<<TreeviewSelect>>", lambda _: self.details())
        self.result_tree.bind("<Double-1>", lambda _: self.open_result_pdf())
        self.details_text = ScrolledText(results, height=9, wrap="word", state="disabled")
        self.details_text.pack(fill="x", pady=(8, 0))
        self.graph_frame = graphs
        ttk.Label(self.root, textvariable=self.status, padding=10, wraplength=1120).pack(fill="x")

    def error(self, error: Exception) -> None:
        self.busy(False)
        if not isinstance(error, (LabError, OSError, ValueError)):
            logging.getLogger(__name__).error(
                "Ошибка GUI", exc_info=(type(error), error, error.__traceback__)
            )
        self.status.set(str(error))
        messagebox.showerror("Ошибка", str(error), parent=self.root)

    def busy(self, value: bool) -> None:
        for widget in self.controls:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="disabled" if value else "readonly")
            else:
                widget.configure(state="disabled" if value else "normal")
        self.cancel_button.configure(state="normal" if value else "disabled")

    def invalidate(self) -> None:
        self.report = None
        self.last_export = None
        self.result_tree.delete(*self.result_tree.get_children())
        self.summary.configure(text="Список или параметры изменены. Запустите сравнение.")
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.configure(state="disabled")
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None

    def refresh(self) -> None:
        self.collection_tree.delete(*self.collection_tree.get_children())
        for index, entry in enumerate(self.entries):
            self.collection_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    entry.split,
                    entry.language or "?",
                    entry.path.name,
                    entry.source_id or "не указан",
                ),
            )
        self.invalidate()
        self.status.set(f"В коллекции {len(self.entries)} PDF.")

    def load_demo(self) -> None:
        self.load(DEMO_MANIFEST)

    def load(self, path: Path) -> None:
        try:
            self.entries = load_manifest(path)
            self.refresh()
        except LabError as exc:
            self.error(exc)

    def open_manifest(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Манифест JSON", "*.json")])
        if path:
            self.load(Path(path))

    def save_list(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")]
        )
        if path:
            try:
                save_manifest(self.entries, Path(path))
            except OSError as exc:
                self.error(exc)

    def add_pdfs(self) -> None:
        if self.role.get() == "train" and self.language.get() == "?":
            self.error(LabError("Укажите язык обучающих PDF."))
            return
        paths = filedialog.askopenfilenames(filetypes=[("Документы PDF", "*.pdf")])
        existing = {e.path.resolve() for e in self.entries}
        for path in paths:
            resolved = Path(path).resolve()
            if resolved not in existing:
                self.entries.append(
                    CorpusEntry(
                        resolved,
                        cast(Split, self.role.get()),
                        cast(Language, self.language.get()) if self.language.get() != "?" else None,
                    )
                )
                existing.add(resolved)
        if paths:
            self.refresh()

    def remove(self) -> None:
        ids = {int(i) for i in self.collection_tree.selection()}
        self.entries = [e for i, e in enumerate(self.entries) if i not in ids]
        self.refresh()

    def open_pdf(self) -> None:
        if ids := self.collection_tree.selection():
            webbrowser.open(self.entries[int(ids[0])].path.resolve().as_uri())

    def open_result_pdf(self) -> None:
        if self.report and (ids := self.result_tree.selection()):
            webbrowser.open(Path(self.report.rows[int(ids[0])].path).as_uri())

    def analyze(self) -> None:
        try:
            settings = Settings(seed=int(self.seed.get()), repetitions=int(self.repetitions.get()))
            entries = tuple(self.entries)
            if not entries:
                raise LabError("Добавьте PDF или загрузите демо-коллекцию.")
            self.invalidate()
            self.busy(True)
            self.tasks.start(
                lambda progress, cancel: build_experiment(settings).run(entries, progress, cancel),
                self.show_report,
                self.error,
                self.status.set,
            )
        except (ValueError, LabError) as exc:
            self.error(exc)

    def show_report(self, value: object) -> None:
        assert isinstance(value, ExperimentReport)
        self.busy(False)
        self.report = value
        summaries = []
        for method, label in METHOD_NAMES.items():
            metric = value.metrics[method]
            accuracy = "нет разметки" if metric["accuracy"] is None else f"{metric['accuracy']:.1%}"
            summaries.append(f"{label}: {accuracy}; {metric['mean_ms']:.3f} мс")
        self.summary.configure(text="\n".join(summaries))
        for index, row in enumerate(value.rows):
            self.result_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    Path(row.path).name,
                    row.expected or "?",
                    *[LANGUAGE_NAMES[row.predictions[m].language or "?"] for m in METHOD_NAMES],
                ),
            )
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.canvas = FigureCanvasTkAgg(charts(value), master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.notebook.select(1)
        self.status.set(f"Готово: {len(value.rows)} документов. " + " ".join(value.warnings))
        if value.rows:
            self.result_tree.selection_set("0")
            self.details()

    def details(self) -> None:
        if self.report is None or not (ids := self.result_tree.selection()):
            return
        row = self.report.rows[int(ids[0])]
        lines = [row.path, f"Страниц: {row.pages}; символов: {row.characters}"]
        for method, prediction in row.predictions.items():
            lines.extend(
                [
                    f"\n{METHOD_NAMES[method]}: {prediction.score_kind}",
                    json.dumps(prediction.scores, ensure_ascii=False),
                    prediction.explanation,
                ]
            )
        lines.extend(row.warnings)
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", "\n".join(lines))
        self.details_text.configure(state="disabled")

    def export(self) -> None:
        if self.report is None:
            self.error(LabError("Сначала выполните сравнение."))
            return
        directory = filedialog.askdirectory(title="Папка отчёта")
        if directory:
            report = self.report
            self.busy(True)
            self.tasks.start(
                lambda progress, cancel: export_report(report, Path(directory)),
                self.exported,
                self.error,
                self.status.set,
            )

    def exported(self, value: object) -> None:
        assert isinstance(value, Path)
        self.busy(False)
        self.last_export = value
        self.status.set(f"Сохранено: {value}")
        webbrowser.open(value.resolve().as_uri())

    def print_report(self) -> None:
        if self.last_export and self.last_export.exists():
            webbrowser.open(self.last_export.resolve().as_uri())
            messagebox.showinfo(
                "Печать", "В открытом отчёте нажмите «Распечатать» или Ctrl+P.", parent=self.root
            )
        elif self.report:
            report = self.report
            self.busy(True)
            self.tasks.start(
                lambda progress, cancel: export_report(report, ROOT / "reports" / "print"),
                self.exported,
                self.error,
                self.status.set,
            )
        else:
            self.error(LabError("Сначала выполните сравнение."))

    def help(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Справка")
        window.geometry("850x650")
        text = ScrolledText(window, wrap="word", font=("Segoe UI", 11))
        text.pack(fill="both", expand=True, padx=12, pady=12)
        text.insert("1.0", HELP)
        text.configure(state="disabled")

    def close(self) -> None:
        self.tasks.close()
        self.root.destroy()


def launch() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()
