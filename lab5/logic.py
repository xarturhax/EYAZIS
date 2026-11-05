from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from lab5.audio import load, resample, save

ROOT = Path(__file__).resolve().parent


def output_folder():
    from datetime import datetime

    folder = ROOT / "reports/local" / datetime.now().strftime("desktop_%Y%m%d_%H%M%S_%f")
    folder.mkdir(parents=True)
    return folder


def experiment(source, action="analyze", start=0.0, end=None, repeats=50, folder=None):
    from lab5.analysis import export_analysis
    from lab5.audio import crop, loop

    folder = folder or output_folder()
    audio, metadata = load(Path(source))
    target = Path(source)
    playlist = []
    if action == "quality":
        quality(Path(source), folder / "quality", "recording")
        playlist = sorted((folder / "quality").glob("*.wav"))
    elif action in {"crop", "loop"}:
        audio = crop(audio, start, audio.duration if end is None else end)
        if action == "loop":
            audio = loop(audio, repeats)
        target = folder / "fragment.wav"
        save(audio, target)
    elif action != "analyze":
        raise ValueError("Неизвестная операция.")
    metrics = export_analysis(target, folder / "analysis")
    return {
        "audio": target,
        "folder": folder,
        "metrics": metrics,
        "playlist": playlist,
        "source": metadata,
    }


def tasks() -> list[dict[str, object]]:
    return json.loads((ROOT / "data/tasks.json").read_text(encoding="utf-8"))


def recording_path(identifier: str) -> Path:
    if identifier not in {t["id"] for t in tasks()}:
        raise ValueError("Неизвестный идентификатор записи.")
    return ROOT / "data/raw" / f"{identifier}.wav"


def status() -> list[dict[str, object]]:
    result = []
    for task in tasks():
        path = recording_path(str(task["id"]))
        state, note = "MISSING", ""
        if path.exists():
            try:
                _, metadata = load(path)
                state = "PRESENT_NOT_REVIEWED"
                note = f"{metadata['rate']} Hz, {metadata['subtype']}"
            except (ValueError, RuntimeError) as error:
                state, note = "INVALID", str(error)
        result.append(task | {"path": str(path), "state": state, "note": note})
    return result


def segments() -> list[dict[str, str]]:
    with (ROOT / "data/segments.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Идентификаторы сегментов должны быть уникальны.")
    return rows


def segment_path(filename: str) -> Path:
    base = (ROOT / "data/raw").resolve()
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Сегменты должны ссылаться на data/raw.")
    return target


def quality(path: Path, output: Path, kind: str) -> None:
    audio, metadata = load(path)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for rate in (4000, 8000, 16000, 32000):
        reference = resample(audio, rate)
        for bits in (8, 16):
            target = output / f"{rate}Hz_{bits}bit.wav"
            save(reference, target, bits)
            restored, _ = load(target)
            error = float(np.mean((restored.samples - reference.samples) ** 2))
            power = float(np.mean(reference.samples**2))
            results.append(
                {
                    "file": target.name,
                    "rate": rate,
                    "bits": bits,
                    "actual_subtype": sf.info(target).subtype,
                    "bytes": target.stat().st_size,
                    "quantization_mse": error,
                    "quantization_snr_db": float(10 * np.log10(power / error))
                    if power > 0 and error > 0
                    else None,
                }
            )
    (output / "experiment.json").write_text(
        json.dumps(
            {
                "source": metadata,
                "source_kind": kind,
                "method": "Digital resampling with anti-aliasing, then WAV PCM quantization; NOT native ADC recordings.",
                "results": results,
                "listening_assessment": "PENDING",
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    with (output / "listening.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "intelligibility_1_5", "quality_1_5", "noise_comment"])
        writer.writerows([r["file"], "", "", ""] for r in results)
