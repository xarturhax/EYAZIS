"""Запуск лабораторной из PyCharm или корня проекта."""

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab1.ir_system.presentation.cli import run

if __name__ == "__main__":
    raise SystemExit(run())
