"""Создание графического представления; сервисы передаются извне."""

import tkinter as tk

from lab1.ir_system.application.services import Services
from lab1.ir_system.domain.errors import ApplicationError
from lab1.ir_system.domain.models import DocumentDraft

from .controller import GuiController
from .tasks import TaskRunner
from .window import MainWindow


def run(services: Services) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise ApplicationError(
            f"Не удалось запустить Tkinter; проверьте установку Tcl/Tk: {exc}"
        ) from exc
    tasks = TaskRunner[DocumentDraft](root)
    try:
        controller = GuiController(MainWindow(root), services, tasks)
        controller.bind()
        controller.refresh()
        root.mainloop()
    finally:
        tasks.close()
        try:
            root.destroy()
        except tk.TclError:
            pass  # Окно уже уничтожено обработчиком WM_DELETE_WINDOW.
