import argparse
import json
import sys
import time
from pathlib import Path

from lab5_7.application.project import ROOT, export_status, recording_path, status, tasks
from lab5_7.domain.audio import crop, gain, loop
from lab5_7.infrastructure.wav import load, save


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Лабораторные 5–7: подготовка и анализ записи голоса"
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status")
    sub.add_parser("devices")
    record = sub.add_parser("record", help="Запуск микрофона только по явной команде пользователя")
    record.add_argument("task")
    record.add_argument("--seconds", type=float, required=True)
    record.add_argument("--device", type=int)
    record.add_argument("--rate", type=int, default=48000)
    record.add_argument("--bits", type=int, choices=[8, 16], default=16)
    record.add_argument("--output", type=Path)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("--output", type=Path, required=True)
    analyze.add_argument("--kind", choices=["recording", "synthetic"], default="recording")
    analyze.add_argument("--floor", type=float, default=60)
    analyze.add_argument("--ceiling", type=float, default=500)
    quality_parser = sub.add_parser("quality")
    quality_parser.add_argument("input", type=Path)
    quality_parser.add_argument("--output", type=Path, required=True)
    quality_parser.add_argument("--kind", choices=["recording", "synthetic"], default="recording")
    extract = sub.add_parser("extract")
    extract.add_argument("input", type=Path)
    extract.add_argument("--start", type=float, required=True)
    extract.add_argument("--end", type=float, required=True)
    extract.add_argument("--repeat", type=int, default=1)
    extract.add_argument("--output", type=Path, required=True)
    bank = sub.add_parser("bank")
    bank.add_argument("--output", type=Path, required=True)
    assembly = sub.add_parser("assemble")
    assembly.add_argument("recipe")
    assembly.add_argument("--bank", type=Path, required=True)
    assembly.add_argument("--output", type=Path, required=True)
    assembly.add_argument("--crossfade-ms", type=float, default=0)
    permutation = sub.add_parser("permutations")
    permutation.add_argument("--bank", type=Path, required=True)
    permutation.add_argument("--output", type=Path, required=True)
    permutation.add_argument(
        "--prefix", choices=["word", "stress1", "stress2", "stress3"], default="word"
    )
    prosody = sub.add_parser("prosody")
    prosody.add_argument("input", type=Path)
    prosody.add_argument("--controls", type=Path, required=True)
    prosody.add_argument("--output", type=Path, required=True)
    grid = sub.add_parser("textgrid")
    grid.add_argument("input", type=Path)
    grid.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command in (None, "status"):
            for row in status():
                print(f"{row['id']:24} {row['state']}")
            export_status(ROOT / "reports/status")
            print("Инструкция записи: lab5_7/docs/RECORDING_GUIDE.md")
        elif args.command == "devices":
            from lab5_7.infrastructure.capture import devices

            print(devices())
        elif args.command == "record":
            from lab5_7.infrastructure.capture import record as capture

            target = args.output or recording_path(args.task)
            if target.exists():
                raise FileExistsError(
                    "Recording already exists; preserve it under another name first."
                )
            task = next((t for t in tasks() if t["id"] == args.task), None)
            if task is None:
                raise ValueError("Unknown recording task.")
            print(task["prompt"])
            print("Recording starts in 3 seconds. Ctrl+C cancels.", flush=True)
            time.sleep(3)
            print("RECORDING", flush=True)
            capture(target, args.seconds, args.rate, args.bits, args.device)
            print(target)
        elif args.command == "analyze":
            from lab5_7.infrastructure.analysis import export_analysis

            export_analysis(args.input, args.output, args.kind, args.floor, args.ceiling)
            print(args.output / "report.html")
        elif args.command == "quality":
            from lab5_7.application.experiments import quality

            quality(args.input, args.output, args.kind)
        elif args.command == "extract":
            audio, _ = load(args.input)
            save(loop(crop(audio, args.start, args.end), args.repeat), args.output)
        elif args.command == "bank":
            from lab5_7.application.experiments import extract_bank

            print("Извлечено единиц:", extract_bank(args.output))
        elif args.command == "assemble":
            from lab5_7.application.experiments import assemble

            assemble(args.recipe, args.bank, args.output, args.crossfade_ms)
        elif args.command == "permutations":
            from lab5_7.application.experiments import permutations

            permutations(args.bank, args.output, args.prefix)
        elif args.command == "textgrid":
            from lab5_7.infrastructure.textgrid import textgrid

            textgrid(args.input, args.output)
        elif args.command == "prosody":
            from lab5_7.infrastructure.prosody import coupled_contour, coupled_shift, manipulate

            audio, _ = load(args.input)
            controls = json.loads(args.controls.read_text(encoding="utf-8"))
            if controls.get("status") != "READY":
                raise ValueError("Задайте настоящие точки и status=READY в файле управления.")
            method = controls.get("method", "psola")
            if method == "psola":
                result = manipulate(
                    audio,
                    controls.get("pitch_points", []),
                    controls.get("duration_points"),
                    controls.get("floor", 60),
                    controls.get("ceiling", 500),
                )
            elif method == "coupled_contour":
                result = coupled_contour(audio, controls["rate_points"])
            elif method == "coupled":
                result = coupled_shift(audio, float(controls["semitones"]))
            else:
                raise ValueError("Метод должен быть psola, coupled_contour или coupled.")
            for interval in controls.get("gain", []):
                result = gain(result, *interval)
            save(result, args.output)
            args.output.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "input": str(args.input.resolve()),
                        "controls": controls,
                        "original_duration": audio.duration,
                        "result_duration": result.duration,
                        "note": "Gain intervals refer to the output timeline after duration changes.",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Ошибка: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Операция отменена.\n")
    return 0
