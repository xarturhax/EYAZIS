"""Один worker; очередь сообщений; никаких вызовов Tk из рабочего потока."""

import tkinter as tk
from collections.abc import Callable
from queue import Empty, Queue
from threading import Event, Thread


class TaskRunner:
    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self.events: Queue[tuple[str, object]] = Queue()
        self.cancelled = Event()
        self.busy = False
        self.closed = False
        self.poll_id: str | None = None

    def start(
        self,
        job: Callable[[Callable[[str], None], Callable[[], bool]], object],
        on_success: Callable[[object], None],
        on_error: Callable[[Exception], None],
        on_progress: Callable[[str], None],
    ) -> bool:
        if self.busy or self.closed:
            return False
        self.busy = True
        self.cancelled.clear()

        def worker() -> None:
            try:
                value = job(
                    lambda message: self.events.put(("progress", message)), self.cancelled.is_set
                )
                self.events.put(("success", value))
            except Exception as error:
                self.events.put(("error", error))

        def poll() -> None:
            self.poll_id = None
            if self.closed:
                return
            try:
                while True:
                    kind, value = self.events.get_nowait()
                    if kind == "progress":
                        on_progress(str(value))
                    elif kind == "success":
                        self.busy = False
                        on_success(value)
                        return
                    else:
                        self.busy = False
                        assert isinstance(value, Exception)
                        on_error(value)
                        return
            except Empty:
                pass
            self.poll_id = self.root.after(80, poll)

        self.poll_id = self.root.after(80, poll)
        Thread(target=worker, daemon=True).start()
        return True

    def close(self) -> None:
        self.closed = True
        self.cancelled.set()
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
