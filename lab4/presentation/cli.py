import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

from lab4.bootstrap import ROOT, build_service, configure_logging
from lab4.infrastructure.export import export_report


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Лабораторная №4, вариант 12: перевод EN→FR")
    sub = parser.add_subparsers(dest="command")
    command = sub.add_parser("translate")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--domain", choices=["medicine", "art"], required=True)
    command.add_argument("--output", type=Path, default=ROOT / "reports" / "last")
    command.add_argument("--database", type=Path)
    command.add_argument(
        "--sentence", type=int, default=1, help="Номер предложения для дерева (от 1)"
    )
    args = parser.parse_args()
    try:
        configure_logging()
        if args.command is None:
            from lab4.presentation.gui import launch

            launch()
        else:
            if args.input.stat().st_size > 1024 * 1024:
                raise ValueError("Входной TXT больше 1 МиБ.")
            service, _ = build_service(args.database)
            result = service.run(
                args.input.read_text(encoding="utf-8-sig"), args.domain, progress=print
            )
            provenance = args.input.parent / "provenance.json"
            if provenance.is_file():
                records = json.loads(provenance.read_text(encoding="utf-8"))
                if isinstance(records, list):
                    source = next((r for r in records if r.get("path") == args.input.name), None)
                    if source:
                        metadata = {
                            f"source_{k}": str(source.get(k, ""))
                            for k in ("title", "url", "attribution", "license")
                        }
                        result = replace(result, versions=result.versions | metadata)
            print(export_report(result, args.output, args.sentence - 1))
    except (OSError, ValueError, sqlite3.Error) as error:
        logging.getLogger("lab4").exception("Application error")
        parser.exit(1, f"Ошибка: {error}\n")
    return 0
