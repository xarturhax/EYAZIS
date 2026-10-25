"""Жизненный цикл одного фонового задания; Tk и SQL остаются в главном потоке."""

from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class Scheduler(Protocol):
    def after(self, milliseconds: int, callback: Callable[[], None]) -> str: ...
    def after_cancel(self, identifier: str) -> None: ...


@dataclass(frozen=True)
class Success(Generic[T]):
    value: T


@dataclass(frozen=True)
class Failure:
    error: Exception


def launch_thread(job: Callable[[], None]) -> None:
    Thread(target=job, daemon=True).start()


class TaskRunner(Generic[T]):
    def __init__(
        self, scheduler: Scheduler, executor: Callable[[Callable[[], None]], None] = launch_thread
    ) -> None:
        self._scheduler, self._executor = scheduler, executor
        self._results: Queue[Success[T] | Failure] = Queue()
        self._poll_id: str | None = None
        self._closed = False
        self.running = False

    def start(
        self,
        job: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[Exception], None],
    ) -> bool:
        if self._closed or self.running:
            return False
        self.running = True

        def worker() -> None:
            try:
                self._results.put(Success(job()))
            except Exception as exc:
                self._results.put(Failure(exc))

        def poll() -> None:
            self._poll_id = None
            if self._closed:
                return
            try:
                result = self._results.get_nowait()
            except Empty:
                self._poll_id = self._scheduler.after(100, poll)
                return
            self.running = False
            if isinstance(result, Failure):
                on_error(result.error)
            else:
                on_success(result.value)

        try:
            self._poll_id = self._scheduler.after(100, poll)
            self._executor(worker)
        except Exception:
            if self._poll_id is not None:
                self._scheduler.after_cancel(self._poll_id)
                self._poll_id = None
            self.running = False
            raise
        return True

    def close(self) -> None:
        self._closed = True
        self.running = False
        if self._poll_id is not None:
            self._scheduler.after_cancel(self._poll_id)
            self._poll_id = None
