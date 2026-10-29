"""Explicit microphone session with heartbeat, bounded events and echo pause."""

from dataclasses import asdict
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any

from webapp.workspace import Workspace


class Live:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.lock = Lock()
        self.stop = Event()
        self.paused = Event()
        self.thread: Thread | None = None
        self.events: list[dict[str, Any]] = []
        self.sequence = 0
        self.message = "Микрофон выключен"
        self.heartbeat = 0.0

    def start(self, language: str, device: int | None) -> None:
        from lab9.domain.commands import Router
        from lab9.infrastructure.config import load_policy

        if language not in {"fr", "en"}:
            raise ValueError("Выберите fr или en.")
        if self.thread and self.thread.is_alive():
            raise ValueError("Микрофон уже включён. Сначала остановите текущий сеанс.")
        router = Router(load_policy(self.workspace.folder / "commands.json"))
        self.stop.clear()
        self.paused.clear()
        self.heartbeat = monotonic()
        self.message = "Подготовка микрофона…"

        def run() -> None:
            from lab9.infrastructure.recognizer import VoskEngine

            def emit(utterance: Any) -> None:
                decision = router.resolve(utterance, language, monotonic())
                with self.lock:
                    self.sequence += 1
                    self.events.append(
                        {
                            "id": self.sequence,
                            "time": monotonic(),
                            "source": "microphone",
                            "language": language,
                            **asdict(decision),
                            "message": decision.reason,
                            "final": utterance.final,
                        }
                    )
                    self.events = self.events[-300:]

            def progress(message: str) -> None:
                with self.lock:
                    self.message = message

            try:
                VoskEngine().listen(
                    language,
                    device,
                    emit,
                    progress,
                    lambda: self.stop.is_set() or monotonic() - self.heartbeat > 20,
                    self.paused,
                )
            except Exception as error:
                import logging

                logging.getLogger(__name__).exception("Microphone session failed")
                progress(str(error))
            finally:
                self.stop.set()
                with self.lock:
                    if "…" in self.message or "включён" in self.message:
                        self.message = "Микрофон выключен"

        self.thread = Thread(target=run, daemon=True, name="eyazis-microphone")
        self.thread.start()

    def state(self, after: int = 0) -> dict[str, Any]:
        with self.lock:
            return {
                "active": bool(self.thread and self.thread.is_alive()),
                "paused": self.paused.is_set(),
                "message": self.message,
                "events": [e for e in self.events if e["id"] > after],
                "sequence": self.sequence,
            }

    def touch(self, paused: bool) -> None:
        self.heartbeat = monotonic()
        if paused:
            self.paused.set()
        else:
            self.paused.clear()

    def close(self) -> None:
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
