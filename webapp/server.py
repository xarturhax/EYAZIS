"""Loopback-only API and built React application."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from webapp.experiments import Experiments
from webapp.jobs import Jobs
from webapp.live import Live
from webapp.workspace import ROOT, Workspace, write_json

MATERIALS = {
    1: [
        ("Демонстрационный отчёт", "lab1/reports/demo/report.html"),
        ("Инструкция", "lab1/README.md"),
    ],
    2: [
        ("Сравнение трёх методов", "lab2/reports/demo/report.html"),
        ("Инструкция", "lab2/README.md"),
    ],
    3: [
        ("Сравнение рефератов", "lab3/reports/demo/report.html"),
        ("Инструкция", "lab3/README.md"),
    ],
    4: [
        ("Перевод и грамматический анализ", "lab4/reports/demo/index.html"),
        ("Инструкция", "lab4/README.md"),
    ],
    5: [
        ("Атлас 42 звуков", "lab5_7/reports/local/phoneme_atlas_v1/index.html"),
        (
            "Периоды и шумовые циклы",
            "lab5_7/reports/local/lab5_phonetics_v1/index.html",
        ),
        (
            "Контекстные сравнения",
            "lab5_7/reports/local/lab5_comparisons_v1/index.html",
        ),
        ("Отчёт №5", "lab5_7/docs/LAB5_REPORT.md"),
    ],
    6: [
        (
            "Шесть итоговых примеров",
            "lab5_7/reports/local/lab6_selected_examples/index.html",
        ),
        ("Все исходные опыты", "lab5_7/reports/local/lab6_experiments_v1/index.html"),
        ("Отчёт №6", "lab5_7/docs/LAB6_REPORT.md"),
    ],
    7: [
        (
            "Третья фраза с «Мама»",
            "lab5_7/reports/local/lab7_reference3_mama_v1/index.html",
        ),
        (
            "Обработка первой фразы",
            "lab5_7/reports/local/lab7_repair_v1/selected/index.html",
        ),
        (
            "Ранняя матрица сравнений",
            "lab5_7/reports/local/lab7_synthesis_v2/index.html",
        ),
        ("Отчёт №7", "lab5_7/docs/LAB7_REPORT.md"),
    ],
    8: [
        ("Два голоса и примеры синтеза", "lab8/reports/demo/index.html"),
        ("Инструкция", "lab8/README.md"),
    ],
    9: [
        ("Распознавание и команды", "lab9/reports/demo/index.html"),
        ("Инструкция", "lab9/README.md"),
    ],
}


def create_app(folder: Path | None = None) -> FastAPI:
    workspace = Workspace(
        folder or Path(os.environ.get("EYAZIS_WEB_WORK", ROOT / "webapp/work"))
    )
    jobs = Jobs(workspace.folder / "jobs")
    experiments = Experiments(workspace)
    live = Live(workspace)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        live.close()
        jobs.close()

    app = FastAPI(title="ЕЯЗиС", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.workspace, app.state.jobs, app.state.experiments, app.state.live = (
        workspace,
        jobs,
        experiments,
        live,
    )

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        from urllib.parse import urlsplit

        host = request.url.hostname
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse(
                {"detail": "Доступ разрешён только с этого компьютера."},
                status_code=403,
            )
        origin = request.headers.get("origin")
        if origin and (
            urlsplit(origin).netloc != request.headers.get("host")
            or urlsplit(origin).scheme != request.url.scheme
        ):
            return JSONResponse(
                {"detail": "Посторонний источник запроса."}, status_code=403
            )
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("x-eyazis") != "local"
        ):
            return JSONResponse(
                {"detail": "Запустите операцию из интерфейса приложения."},
                status_code=403,
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request: Request, error: FileNotFoundError):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.get("/api/health")
    def health():
        return {"app": "eyazis-web", "status": "ok"}

    @app.get("/api/catalog")
    def catalog():
        from lab5_7.application.project import segments
        from webapp.workspace import plain

        recipes = json.loads(
            (ROOT / "lab5_7/data/recipes.json").read_text(encoding="utf-8")
        )
        materials = {
            lab: [
                {
                    "title": title,
                    "url": "/files/" + path,
                    "available": (ROOT / path).is_file(),
                }
                for title, path in rows
            ]
            for lab, rows in MATERIALS.items()
        }
        sources = [
            {"id": p.stem, "name": p.name}
            for p in sorted((ROOT / "lab5_7/data/raw").glob("*.wav"))
        ]
        return {
            "materials": materials,
            "recipes": recipes,
            "sources": sources,
            "segments": plain(segments()),
        }

    @app.get("/api/lab1/data")
    def collection(query: str = ""):
        return experiments.lab1_data(query)

    @app.post("/api/labs/{lab}/run")
    def run(lab: int, body: dict[str, Any]):
        if lab not in range(1, 10):
            raise HTTPException(404, "Нет такой лабораторной.")
        return jobs.submit(
            lab,
            str(body.get("action", "run")),
            lambda job: experiments.execute(lab, body, job),
        )

    @app.get("/api/jobs")
    def history():
        return [
            {k: v for k, v in item.items() if k != "result"} for item in jobs.history()
        ]

    @app.get("/api/jobs/{ident}")
    def job_state(ident: str):
        return jobs.get(ident)

    @app.post("/api/jobs/{ident}/cancel")
    def cancel(ident: str):
        data = jobs.get(ident)
        if ident in jobs.items and data["status"] in {
            "queued",
            "running",
            "cancelling",
        }:
            jobs.items[ident].cancel.set()
            jobs.items[ident].update(
                status="cancelling", message="Отмена после текущего этапа…"
            )
        return jobs.get(ident)

    @app.get("/api/jobs/{ident}/archive")
    def archive(ident: str):
        state = jobs.get(ident)
        if state["status"] != "completed":
            raise HTTPException(409, "Дождитесь завершения опыта.")
        base = workspace.folder / "jobs" / ident
        target = workspace.folder / "archives" / (ident + ".zip")
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            temporary = target.with_suffix(".tmp")
            with ZipFile(temporary, "w", ZIP_DEFLATED) as stream:
                for source in base.rglob("*"):
                    if source.is_file() and source.suffix != ".tmp":
                        stream.write(source, source.relative_to(base).as_posix())
            temporary.replace(target)
        return FileResponse(target, filename=f"lab{state['lab']}-{ident[:8]}.zip")

    @app.post("/api/uploads")
    async def upload(file: UploadFile):
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".pdf", ".txt", ".wav", ".json"}:
            raise ValueError("Выберите PDF, TXT, WAV или JSON.")
        ident = uuid4().hex
        folder = workspace.folder / "uploads" / ident
        folder.mkdir(parents=True)
        target = folder / ("input" + suffix)
        count = 0
        try:
            with target.open("xb") as stream:
                while block := await file.read(1024 * 1024):
                    count += len(block)
                    if count > 50 * 1024 * 1024:
                        raise ValueError("Максимальный размер файла — 50 МиБ.")
                    stream.write(block)
            if not count:
                raise ValueError("Файл пуст.")
            write_json(
                folder / "metadata.json",
                {
                    "name": Path(file.filename or "file").name,
                    "stored_name": target.name,
                },
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return {
            "id": ident,
            "name": Path(file.filename or "file").name,
            "bytes": count,
            "url": workspace.url(target),
        }

    @app.get("/api/devices")
    def devices():
        import sounddevice as sd

        return [
            {"id": index, "name": item["name"], "rate": item["default_samplerate"]}
            for index, item in enumerate(sd.query_devices())
            if item["max_input_channels"] > 0
        ]

    @app.get("/api/commands")
    def commands():
        return json.loads(
            (workspace.folder / "commands.json").read_text(encoding="utf-8")
        )

    @app.post("/api/commands")
    def save_commands(body: dict[str, Any]):
        from lab9.infrastructure.config import load_policy, save_policy

        temporary = workspace.folder / "commands-validation.json"
        write_json(temporary, body)
        try:
            policy = load_policy(temporary)
            save_policy(workspace.folder / "commands.json", policy)
        finally:
            temporary.unlink(missing_ok=True)
        return {"saved": True}

    @app.get("/api/live")
    def live_state(after: int = 0):
        return live.state(after)

    @app.post("/api/live/start")
    def start_live(body: dict[str, Any]):
        live.start(str(body.get("language", "fr")), body.get("device"))
        return live.state()

    @app.post("/api/live/heartbeat")
    def heartbeat(body: dict[str, Any]):
        live.touch(bool(body.get("paused", False)))
        return {"ok": True}

    @app.post("/api/live/stop")
    def stop_live():
        live.close()
        return live.state()

    @app.get("/files/{area}/{relative:path}")
    def files(area: str, relative: str):
        path = workspace.resolve(area, relative)
        return FileResponse(
            path,
            media_type="text/plain; charset=utf-8" if path.suffix == ".md" else None,
        )

    frontend = ROOT / "webapp/frontend/dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    else:

        @app.get("/")
        def unbuilt():
            return JSONResponse(
                {
                    "detail": "Соберите интерфейс: cd webapp/frontend; npm ci; npm run build"
                },
                status_code=503,
            )

    return app
