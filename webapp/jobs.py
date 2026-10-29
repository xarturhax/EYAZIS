"""One model worker, cooperative cancellation and durable experiment results."""

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from typing import Any
from uuid import uuid4

from webapp.workspace import write_json


class Job:
    def __init__(self, folder: Path, lab: int, action: str) -> None:
        self.id = folder.name
        self.folder = folder
        self.cancel = Event()
        self.lock = Lock()
        self.data: dict[str, Any] = {
            "id": self.id,
            "lab": lab,
            "action": action,
            "status": "queued",
            "message": "Ожидание запуска…",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
        }
        folder.mkdir(parents=True, exist_ok=True)
        self.save()

    def save(self) -> None:
        write_json(self.folder / "state.json", self.data)

    def update(self, **values: Any) -> None:
        with self.lock:
            self.data.update(values)
            self.save()

    def progress(self, message: str) -> None:
        self.update(message=message)

    def checkpoint(self) -> None:
        if self.cancel.is_set():
            raise InterruptedError("Выполнение отменено.")

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.data)


class Jobs:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="eyazis-model"
        )
        self.items: dict[str, Job] = {}
        self.lock = Lock()
        for path in folder.glob("*/state.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["status"] in {"queued", "running", "cancelling"}:
                data.update(
                    status="interrupted",
                    message="Сервер был остановлен. Запустите опыт повторно.",
                )
                write_json(path, data)

    def submit(
        self, lab: int, action: str, function: Callable[[Job], Any]
    ) -> dict[str, Any]:
        with self.lock:
            if (
                sum(
                    j.data["status"] in {"queued", "running", "cancelling"}
                    for j in self.items.values()
                )
                >= 20
            ):
                raise ValueError(
                    "Очередь заполнена. Дождитесь завершения текущих задач."
                )
            job = Job(self.folder / uuid4().hex, lab, action)
            self.items[job.id] = job
        self.executor.submit(self.run, job, function)
        return job.snapshot()

    @staticmethod
    def run(job: Job, function: Callable[[Job], Any]) -> None:
        try:
            job.checkpoint()
            job.update(status="running", message="Подготовка…")
            result = function(job)
            job.checkpoint()
            job.update(status="completed", message="Готово", result=result)
        except Exception as error:
            if job.cancel.is_set():
                job.update(
                    status="cancelled",
                    message="Выполнение отменено. Созданные файлы сохранены в каталоге опыта.",
                )
            else:
                import logging

                logging.getLogger(__name__).exception("Experiment failed: %s", job.id)
                job.update(
                    status="failed",
                    message="Не удалось выполнить операцию",
                    error=str(error),
                )

    def get(self, ident: str) -> dict[str, Any]:
        if len(ident) != 32 or any(c not in "0123456789abcdef" for c in ident):
            raise ValueError("Некорректный номер опыта.")
        if ident in self.items:
            return self.items[ident].snapshot()
        return json.loads(
            (self.folder / ident / "state.json").read_text(encoding="utf-8")
        )

    def history(self) -> list[dict[str, Any]]:
        paths = sorted(
            self.folder.glob("*/state.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:100]
        return [self.get(p.parent.name) for p in paths]

    def close(self) -> None:
        for job in self.items.values():
            job.cancel.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
