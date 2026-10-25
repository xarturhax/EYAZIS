"""Запуск из PyCharm или командой python lab2/main.py."""

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab2.presentation.cli import run

if __name__ == "__main__":
    raise SystemExit(run())
