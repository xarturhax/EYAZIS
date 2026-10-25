import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from lab9.application.recognition import RecognitionService
from lab9.bootstrap import DEFAULT_COMMANDS, configure_logging
from lab9.domain.commands import Router
from lab9.infrastructure.audio import load_pcm
from lab9.infrastructure.config import load_policy
from lab9.infrastructure.export import export_journal
from lab9.infrastructure.recognizer import VoskEngine


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Лабораторная 9, вариант 8: французский ASR и команды"
    )
    sub = parser.add_subparsers(dest="command")
    command = sub.add_parser("recognize")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--language", choices=["fr", "en"], default="fr")
    command.add_argument("--commands", type=Path, default=DEFAULT_COMMANDS)
    command.add_argument("--output", type=Path, required=True)
    sub.add_parser("devices")
    args = parser.parse_args()
    try:
        configure_logging()
        if args.command == "recognize":
            pcm, metadata = load_pcm(args.input)
            result = RecognitionService(VoskEngine()).run(pcm, 16000, args.language)
            router = Router(load_policy(args.commands))
            events = []
            for utterance in result.utterances:
                when = utterance.words[-1].end if utterance.words else 0
                decision = router.resolve(utterance, args.language, when)
                events.append(
                    dict(
                        time=when,
                        source="WAV_TEST",
                        language=args.language,
                        text=utterance.text,
                        confidence=utterance.confidence,
                        status=decision.status,
                        action=decision.action or "",
                        message=decision.reason,
                    )
                )
                print(utterance.text, "→", decision.action or decision.status)
            export_journal(events, args.output)
            (args.output / "recognition.json").write_text(
                json.dumps(
                    {
                        "input": metadata,
                        "recognition": asdict(result),
                        "mode": "WAV_TEST_NO_ACTION_EXECUTION",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        elif args.command == "devices":
            import sounddevice as sd

            print(sd.query_devices())
        else:
            from lab9.presentation.gui import launch

            launch()
    except (OSError, ValueError, RuntimeError) as error:
        logging.getLogger("lab9").exception("Application error")
        parser.exit(1, f"Ошибка: {error}\n")
    return 0
