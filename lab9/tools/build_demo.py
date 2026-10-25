"""Labelled synthetic French test set; does not record a microphone or execute actions."""

import csv
import json
import sys
from dataclasses import asdict
from html import escape
from typing import Any

import numpy as np
import soundfile as sf
from lab8.bootstrap import build_service as build_tts
from lab8.domain.models import Settings

from lab9.application.recognition import RecognitionService
from lab9.bootstrap import DEFAULT_COMMANDS, ROOT
from lab9.domain.commands import Router, word_error_rate
from lab9.infrastructure.audio import load_pcm
from lab9.infrastructure.config import load_policy
from lab9.infrastructure.recognizer import VoskEngine


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    folder = ROOT / "reports/demo"
    audio_folder = folder / "audio"
    audio_folder.mkdir(parents=True, exist_ok=True)
    policy = load_policy(DEFAULT_COMMANDS)
    metrics_path = folder / "metrics.json"
    previous = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    cached = {r["id"]: r for r in previous.get("cases", [])}
    tts = build_tts()
    recognition = RecognitionService(VoskEngine())
    commands = [c for c in policy.commands if c.language == "fr" and c.enabled]
    cases: list[dict[str, Any]] = []
    for voice in ("siwis", "tom"):
        for command in commands:
            cases.append(
                dict(
                    id=f"{voice}_{command.action.value}",
                    text=command.phrase,
                    voice=voice,
                    expected=command.action.value,
                    category="command",
                )
            )
        for i, text in enumerate(
            (
                "Le roman invite le lecteur à réfléchir à la justice.",
                "Lecteur commence le récit de ce personnage.",
                "Ce livre décrit la vie quotidienne.",
            ),
            1,
        ):
            cases.append(
                dict(
                    id=f"{voice}_negative{i}",
                    text=text,
                    voice=voice,
                    expected=None,
                    category="negative",
                )
            )
    cases.append(
        dict(
            id="dictation_hugo",
            text=(ROOT.parent / "lab8/data/essai_hugo.txt").read_text(encoding="utf-8").strip(),
            voice="siwis",
            expected=None,
            category="dictation",
        )
    )
    results: list[dict[str, Any]] = []
    for case in cases:
        path = audio_folder / (case["id"] + ".wav")
        existed = path.exists()
        if existed and (
            case["id"] not in cached
            or any(cached[case["id"]][k] != case[k] for k in ("text", "voice"))
        ):
            raise FileExistsError(
                "Cached WAV does not match the request. Preserve reports/demo under another name before rebuilding."
            )
        if not existed:
            tts.render(case["text"], Settings(case["voice"], 1, 0.8), path)
        pcm, metadata = load_pcm(path)
        if existed and metadata["sha256"] != cached[case["id"]]["input"]["sha256"]:
            raise ValueError("Cached WAV hash mismatch.")
        recognized = recognition.run(pcm, 16000, "fr")
        router = Router(policy)
        decisions = [
            router.resolve(u, "fr", u.words[-1].end if u.words else 0)
            for u in recognized.utterances
        ]
        actions = [d.action.value for d in decisions if d.action is not None]
        expected = [case["expected"]] if case["expected"] is not None else []
        hypothesis = " ".join(u.text for u in recognized.utterances)
        row = case | dict(
            source_kind="SYNTHETIC_PIPER",
            input=metadata,
            hypothesis=hypothesis,
            decisions=[asdict(d) for d in decisions],
            actions=actions,
            correct_action=actions == expected,
            word_errors=word_error_rate(case["text"], hypothesis),
            initialization_seconds=recognized.initialization_seconds,
            recognition_seconds=recognized.recognition_seconds,
        )
        results.append(row)
        print(case["id"], actions, "expected", expected, flush=True)
    for name, samples in (
        ("silence", np.zeros(16000 * 2)),
        ("noise", np.random.default_rng(98).normal(0, 0.025, 16000 * 2)),
    ):
        path = audio_folder / f"{name}.wav"
        if not path.exists():
            sf.write(path, samples, 16000, subtype="PCM_16")
        pcm, metadata = load_pcm(path)
        recognized = recognition.run(pcm, 16000, "fr")
        router = Router(policy)
        decisions = [
            router.resolve(u, "fr", u.words[-1].end if u.words else 0)
            for u in recognized.utterances
        ]
        actions = [d.action.value for d in decisions if d.action is not None]
        results.append(
            dict(
                id=name,
                text="",
                voice="none",
                category="technical_negative",
                source_kind="SYNTHETIC_SIGNAL",
                input=metadata,
                hypothesis=" ".join(u.text for u in recognized.utterances),
                decisions=[asdict(d) for d in decisions],
                actions=actions,
                expected=None,
                correct_action=not actions,
                word_errors=word_error_rate("", ""),
                recognition_seconds=recognized.recognition_seconds,
                initialization_seconds=recognized.initialization_seconds,
            )
        )
    command_cases = [r for r in results if r["category"] == "command"]
    negative_cases = [r for r in results if r["category"] != "command"]
    errors = sum(r["word_errors"]["errors"] for r in results if r["text"])
    words = sum(r["word_errors"]["reference_words"] for r in results if r["text"])
    summary = dict(
        command_cases=len(command_cases),
        correct_commands=sum(r["correct_action"] for r in command_cases),
        command_accuracy=sum(r["correct_action"] for r in command_cases) / len(command_cases),
        negative_cases=len(negative_cases),
        false_activations=sum(bool(r["actions"]) for r in negative_cases),
        normalized_wer=errors / words,
        word_errors=errors,
        reference_words=words,
        source_kind="SYNTHETIC_ONLY",
        human_microphone_evaluation="PENDING",
        policy=asdict(policy),
    )
    payload = {"summary": summary, "cases": results}
    (folder / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (folder / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "id",
                "expected",
                "recognized",
                "actions",
                "correct",
                "recognition_seconds",
                "duration",
            ]
        )
        for row in results:
            writer.writerow(
                [
                    row["id"],
                    row["expected"],
                    row["hypothesis"],
                    " ".join(row["actions"]),
                    row["correct_action"],
                    row["recognition_seconds"],
                    row["input"]["duration"],
                ]
            )
    html_rows = "".join(
        f"<tr><td>{r['id']}</td><td>{escape(r['text'])}</td><td>{escape(r['hypothesis'])}</td>"
        f"<td>{escape(str(r['expected']))}</td><td>{escape(str(r['actions']))}</td>"
        f"<td>{r['correct_action']}</td><td><audio controls preload='none' src='audio/{r['id']}.wav'></audio></td></tr>"
        for r in results
    )
    (folder / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Лабораторная 9</title>'
        "<style>body{font:15px system-ui;margin:25px}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ccd;padding:6px}audio{width:190px}pre{white-space:pre-wrap}"
        '@media print{audio,button{display:none}}</style><button onclick="window.print()">Печать</button>'
        "<h1>Французское распознавание и команды · вариант 8</h1>"
        "<p>Только синтетический тест Piper и технические сигналы. Действия/динамики/микрофон "
        "не включались. Человеческая речь и реальный акустический тракт ещё не оценивались.</p>"
        f"<pre>{escape(json.dumps(summary, ensure_ascii=False, indent=2))}</pre>"
        "<table><tr><th>ID</th><th>Эталон</th><th>Распознано</th><th>Ожидалось</th><th>Принято</th>"
        "<th>Совпало</th><th>Аудио</th></tr>" + html_rows + "</table></html>",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
