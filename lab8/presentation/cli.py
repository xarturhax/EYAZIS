import argparse
import logging
import sys
from pathlib import Path

from lab8.bootstrap import build_service, configure_logging
from lab8.domain.models import Settings
from lab8.infrastructure.export import report
from lab8.tools.download_voices import MODELS, VOICES


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Лабораторная №8, вариант 8: французский TTS")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("voices")
    speak = sub.add_parser("synthesize")
    group = speak.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path)
    group.add_argument("--text")
    speak.add_argument("--voice", choices=list(VOICES), default="siwis")
    speak.add_argument("--speed", type=float, default=1)
    speak.add_argument("--volume", type=float, default=0.8)
    speak.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command is None:
        from webapp.__main__ import main as launch_web

        launch_web(["--lab", "8"])
        return 0
    try:
        configure_logging()
        if args.command == "voices":
            for voice, label in VOICES.items():
                print(
                    voice,
                    label,
                    "READY" if (MODELS / voice / "manifest.json").exists() else "NOT_INSTALLED",
                )
        elif args.command == "synthesize":
            if args.input and args.input.stat().st_size > 1024 * 1024:
                raise ValueError("TXT больше 1 МиБ.")
            text = args.input.read_text(encoding="utf-8-sig") if args.input else args.text
            result = build_service().render(
                text, Settings(args.voice, args.speed, args.volume), args.output, progress=print
            )
            report(result)
            print(result.wav_path)
    except (OSError, ValueError, RuntimeError) as error:
        logging.getLogger("lab8").exception("Application error")
        parser.exit(1, f"Ошибка: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Синтез остановлен.\n")
    return 0
