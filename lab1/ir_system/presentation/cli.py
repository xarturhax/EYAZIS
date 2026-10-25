"""Парсинг CLI, управление runtime и обработка ошибок на внешней границе."""

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import replace
from typing import TextIO

from lab1.ir_system.bootstrap import application_runtime
from lab1.ir_system.config import AppConfig
from lab1.ir_system.domain.errors import ApplicationError

from .commands import HANDLERS

logger = logging.getLogger(__name__)


def create_parser(config: AppConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ИПС — вариант 36: Интернет, английский язык, BM25"
    )
    parser.add_argument("--db", default=config.database, help="Путь к базе SQLite")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="Графический интерфейс (по умолчанию)")
    commands.add_parser("demo", help="Добавить учебную коллекцию и разметку")
    search = commands.add_parser("search", help="Поиск в текущей коллекции")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    fetch = commands.add_parser("fetch", help="Загрузить одну интернет-страницу")
    fetch.add_argument("url")
    evaluation = commands.add_parser("evaluate", help="Рассчитать метрики и экспортировать отчёт")
    evaluation.add_argument(
        "--demo", action="store_true", help="Изолированная учебная коллекция в памяти"
    )
    evaluation.add_argument("--query", help="Оценить один запрос вместо всех размеченных")
    evaluation.add_argument("--output", default=config.reports)
    return parser


def run(
    argv: Sequence[str] | None = None, output: TextIO | None = None, errors: TextIO | None = None
) -> int:
    output = output if output is not None else sys.stdout
    errors = errors if errors is not None else sys.stderr
    for stream in (output, errors):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    config = AppConfig()
    args = create_parser(config).parse_args(argv)
    command = args.command or "gui"
    database = ":memory:" if command == "evaluate" and args.demo else args.db
    try:
        with application_runtime(replace(config, database=database)) as services:
            HANDLERS[command](args, services, output)
        return 0
    except ApplicationError as exc:
        print(f"Ошибка: {exc}", file=errors)
        return 1
    except Exception:
        logger.exception("Неожиданная ошибка выполнения команды %s", command)
        print("Неожиданная ошибка приложения; подробности в диагностике выше", file=errors)
        return 1
