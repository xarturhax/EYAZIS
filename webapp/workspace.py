"""Private web workspace, safe file URLs and JSON conversion."""

import dataclasses
import json
import math
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = {
    ".wav",
    ".html",
    ".css",
    ".js",
    ".json",
    ".csv",
    ".svg",
    ".png",
    ".txt",
    ".md",
    ".pdf",
}


def plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return plain(value.item())
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)


class Workspace:
    def __init__(self, folder: Path) -> None:
        self.folder = folder.resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        for target, source in [
            ("search.sqlite3", ROOT / "lab1/data/search.sqlite3"),
            ("lexicon.sqlite3", ROOT / "lab4/data/lexicon.sqlite3"),
        ]:
            if source.exists() and not (self.folder / target).exists():
                # SQLite backup includes committed data even when the old GUI uses WAL.
                import sqlite3

                with (
                    sqlite3.connect(
                        f"file:{source.as_posix()}?mode=ro", uri=True
                    ) as original,
                    sqlite3.connect(self.folder / target) as destination,
                ):
                    original.backup(destination)
        policy = self.folder / "commands.json"
        if not policy.exists():
            shutil.copyfile(ROOT / "lab9/data/commands.json", policy)

    def resolve(self, area: str, relative: str) -> Path:
        base = self.folder if area == "work" else ROOT / area
        if area not in {
            "work",
            "lab1",
            "lab2",
            "lab3",
            "lab4",
            "lab5_7",
            "lab8",
            "lab9",
        }:
            raise ValueError("Неизвестный каталог.")
        path = (base / relative).resolve()
        if (
            not path.is_relative_to(base.resolve())
            or path.suffix.lower() not in EXTENSIONS
        ):
            raise ValueError("Файл недоступен.")
        if area != "work" and (
            not Path(relative).parts
            or Path(relative).parts[0] not in {"reports", "docs", "data", "README.md"}
        ):
            raise ValueError("Разрешены только материалы лабораторных.")
        if not path.is_file():
            raise FileNotFoundError("Материал не найден на этом компьютере.")
        return path

    def url(self, path: Path) -> str:
        from urllib.parse import quote

        path = path.resolve()
        if path.is_relative_to(self.folder):
            return "/files/work/" + quote(path.relative_to(self.folder).as_posix())
        relative = path.relative_to(ROOT)
        return "/files/" + quote(relative.as_posix())

    def upload(self, ident: str) -> Path:
        if (
            not ident
            or any(c not in "0123456789abcdef" for c in ident)
            or len(ident) != 32
        ):
            raise ValueError("Некорректный идентификатор файла.")
        folder = self.folder / "uploads" / ident
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        return folder / meta["stored_name"]
