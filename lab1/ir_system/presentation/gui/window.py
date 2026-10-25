"""Оболочка Tkinter и диалоги. Не содержит сценариев приложения."""

import tkinter as tk
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from lab1.ir_system.domain.models import Document, Keyword

from .tabs import CollectionTab, QualityTab, SearchTab
from .widgets import TextPanel


class MainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("ИПС — лабораторная работа, вариант 36")
        root.geometry("1150x780")
        root.minsize(850, 600)
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.collection = CollectionTab(self.tabs)
        self.search = SearchTab(self.tabs)
        self.quality = QualityTab(self.tabs)
        for tab, name in (
            (self.collection, "Коллекция"),
            (self.search, "Поиск"),
            (self.quality, "Оценка качества"),
        ):
            self.tabs.add(tab, text=name)
        self.status = tk.StringVar(value="Загрузите демо или добавьте интернет-страницу")
        ttk.Label(root, textvariable=self.status, anchor="w").pack(fill="x", padx=12, pady=(0, 8))

    def bind_menu(self, on_evaluate: Callable[[], None], on_help: Callable[[], None]) -> None:
        menu = tk.Menu(self.root)
        quality = tk.Menu(menu, tearoff=False)
        quality.add_command(label="Открыть оценку качества", command=self.select_quality)
        quality.add_command(label="Оценить все размеченные запросы", command=on_evaluate)
        menu.add_cascade(label="Оценка качества", menu=quality)
        menu.add_command(label="Справка", command=on_help)
        self.root.configure(menu=menu)

    def select_quality(self) -> None:
        self.tabs.select(self.quality)

    def show_error(self, message: str) -> None:
        messagebox.showerror("Ошибка", message, parent=self.root)

    def confirm_delete(self, count: int) -> bool:
        return messagebox.askyesno(
            "Удаление", f"Удалить {count} документов и связанные оценки?", parent=self.root
        )

    def choose_report_directory(self) -> str:
        return filedialog.askdirectory(title="Папка для отчёта", parent=self.root)

    def open_url(self, url: str) -> None:
        webbrowser.open(url)

    def show_document(self, document: Document, keywords: Sequence[Keyword]) -> None:
        window = tk.Toplevel(self.root)
        window.title(document.title)
        window.geometry("800x550")
        link = tk.Label(window, text=document.url, fg="blue", cursor="hand2", wraplength=760)
        link.pack(pady=8)
        link.bind("<Button-1>", lambda event: self.open_url(document.url))
        text = TextPanel(window)
        text.pack(fill="both", expand=True, padx=10, pady=10)
        words = ", ".join(f"{item.term}: {item.weight:.3f}" for item in keywords)
        text.show(
            f"Добавлен (UTC): {document.added_at}\nКлючевые слова TF-IDF:\n{words}\n\n{document.text}"
        )

    def show_help(self) -> None:
        content = Path(__file__).with_name("help.txt").read_text(encoding="utf-8")
        window = tk.Toplevel(self.root)
        window.title("Справка")
        window.geometry("830x650")
        text = TextPanel(window)
        text.pack(fill="both", expand=True)
        text.show(content)
