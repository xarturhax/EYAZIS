"""Конфигурация приложения; пути задаются один раз при запуске."""

from dataclasses import dataclass
from pathlib import Path

from lab1.ir_system.domain.models import BM25Parameters

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppConfig:
    database: str | Path = PROJECT_ROOT / "data" / "search.sqlite3"
    fixture: Path = PROJECT_ROOT / "fixtures" / "collection.json"
    reports: Path = PROJECT_ROOT / "reports" / "local"
    bm25: BM25Parameters = BM25Parameters()
    http_timeout: float = 15
    max_page_bytes: int = 2 * 1024 * 1024
