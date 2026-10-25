import argparse
import logging
import sys
from pathlib import Path

from lab3.bootstrap import DEMO, ROOT, build_summarizer, configure_logging
from lab3.infrastructure.documents import load_corpus, read_manifest
from lab3.infrastructure.export import export_report


def main() -> int:
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Лабораторная 3, вариант 27: реферирование EN/ES")
    sub = parser.add_subparsers(dest="command")
    evaluate = sub.add_parser("evaluate", help="Сравнить оба метода и сохранить отчёт")
    evaluate.add_argument("--manifest", type=Path, default=DEMO)
    evaluate.add_argument("--output", type=Path, default=ROOT / "reports" / "demo")
    evaluate.add_argument("--sentences", type=int, default=10)
    evaluate.add_argument("--keywords", type=int, default=10)
    args = parser.parse_args()
    try:
        configure_logging()
        if args.command == "evaluate":
            experiment = build_summarizer().run(
                load_corpus(read_manifest(args.manifest)),
                args.sentences,
                args.keywords,
                progress=print,
            )
            print(export_report(experiment, args.output))
        else:
            from lab3.presentation.gui import launch

            launch()
    except (OSError, ValueError) as error:
        logging.getLogger("lab3").exception("Application error")
        parser.exit(1, f"Ошибка: {error}\n")
    return 0
