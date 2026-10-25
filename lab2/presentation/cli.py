import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lab2.bootstrap import DEMO_MANIFEST, ROOT, build_experiment
from lab2.domain.models import CorpusEntry, LabError, Settings
from lab2.infrastructure.corpus import load_manifest
from lab2.infrastructure.export import export_report


def run(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Лаба 2, вариант 36: EN/ES, PDF, три метода")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="Открыть окно (по умолчанию)")
    check = sub.add_parser("evaluate", help="Обучить и сравнить методы")
    check.add_argument("--manifest", type=Path, default=DEMO_MANIFEST)
    check.add_argument("--output", type=Path, default=ROOT / "reports" / "local")
    check.add_argument("--seed", type=int, default=36)
    check.add_argument("--repetitions", type=int, default=5)
    check.add_argument(
        "--pdf", type=Path, nargs="*", help="Неразмеченные PDF вместо test манифеста"
    )
    args = parser.parse_args(argv)
    try:
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[
                RotatingFileHandler(
                    logs / "lab2.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
                )
            ],
        )
        if args.command in (None, "gui"):
            from .gui import launch

            launch()
            return 0
        entries = load_manifest(args.manifest)
        if args.pdf is not None:
            entries = [e for e in entries if e.split == "train"] + [
                CorpusEntry(p.resolve(), "test", None) for p in args.pdf
            ]
        report = build_experiment(Settings(seed=args.seed, repetitions=args.repetitions)).run(
            entries, lambda message: print(message, file=sys.stderr)
        )
        target = export_report(report, args.output)
        for method, values in report.metrics.items():
            print(f"{method}: accuracy={values['accuracy']}, mean_ms={values['mean_ms']:.4f}")
        print(f"Отчёт: {target.resolve()}")
        return 0
    except (LabError, OSError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except Exception:
        logging.getLogger(__name__).exception("Неожиданная ошибка")
        print("Неожиданная ошибка. Подробности: lab2/logs/lab2.log", file=sys.stderr)
        return 1
