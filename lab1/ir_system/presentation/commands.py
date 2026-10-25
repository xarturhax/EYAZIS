"""Каждая CLI-команда отображает результат одного прикладного сценария."""

import json
from argparse import Namespace
from collections.abc import Callable
from typing import TextIO

from lab1.ir_system.application.services import Services
from lab1.ir_system.reporting import metric_values, search_result_values

CommandHandler = Callable[[Namespace, Services, TextIO], None]


def gui_command(args: Namespace, services: Services, output: TextIO) -> None:
    from .gui import run

    run(services)


def demo_command(args: Namespace, services: Services, output: TextIO) -> None:
    result = services.collection.import_demo()
    print(
        f"Документов: {len(services.collection.documents())}; демо-запросов: {len(result.queries)}",
        file=output,
    )


def fetch_command(args: Namespace, services: Services, output: TextIO) -> None:
    draft = services.collection.fetch(args.url)
    document_id = services.collection.add(draft)
    print(f"Документ #{document_id}: {draft.title}", file=output)


def search_command(args: Namespace, services: Services, output: TextIO) -> None:
    results = services.search.search(args.query, args.limit)
    print(
        json.dumps(
            [search_result_values(result) for result in results], ensure_ascii=False, indent=2
        ),
        file=output,
    )


def evaluate_command(args: Namespace, services: Services, output: TextIO) -> None:
    if args.demo:
        services.collection.import_demo()
    queries = [args.query] if args.query is not None else services.judgments.queries()
    report = services.evaluation.evaluate(queries)
    path = services.reports.export(report, args.output)
    print(
        json.dumps(metric_values(report.averages, aggregate=True), ensure_ascii=False, indent=2),
        file=output,
    )
    print(f"Отчёт: {path.resolve()}", file=output)
    for excluded in report.excluded_queries:
        print(f"Исключён запрос «{excluded.query}»: {excluded.reason}", file=output)


HANDLERS: dict[str, CommandHandler] = {
    "gui": gui_command,
    "demo": demo_command,
    "fetch": fetch_command,
    "search": search_command,
    "evaluate": evaluate_command,
}
