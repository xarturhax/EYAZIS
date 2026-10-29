"""Plot the full human-confirmed 42-unit teaching inventory from immutable WAVs."""

import argparse
import hashlib
import json
from html import escape
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from scipy.signal import welch

from lab5_7.application.project import ROOT, segment_path
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.wav import load
from lab5_7.tools.prepare_review import label


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bank", type=Path, default=ROOT / "reports/local/lab7_reference3_mama_v1/bank"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "reports/local/phoneme_atlas_v1")
    args = parser.parse_args()
    folder = args.output
    if folder.exists():
        raise FileExistsError("Choose a new atlas directory.")
    paths = sorted(args.bank.glob("ph_*.json"))
    if len(paths) != 42:
        raise ValueError("A complete 42-phone teaching bank is required.")
    entries = []
    for path in paths:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        row = metadata["segment"]
        if row["reviewed"] != "yes":
            raise ValueError("Unconfirmed unit: " + row["id"])
        if (
            hashlib.sha256(segment_path(row["file"]).read_bytes()).hexdigest()
            != metadata["source"]["sha256"]
        ):
            raise ValueError("Source recording changed.")
        audio, wav_meta = load(path.with_suffix(".wav"))
        entries.append((row, audio, wav_meta))
    folder.mkdir(parents=True)
    records, cards = [], []
    for row, audio, wav_meta in entries:
        ident = row["id"]
        target = folder / (ident + ".wav")
        target.write_bytes(Path(str(wav_meta["path"])).read_bytes())
        figure = Figure(figsize=(10, 3), constrained_layout=True)
        FigureCanvasAgg(figure)
        wave, spectrum = figure.subplots(1, 2)
        stride = max(1, len(audio.samples) // 5000)
        wave.plot(
            np.arange(0, len(audio.samples), stride) / audio.rate, audio.samples[::stride], lw=0.6
        )
        wave.set(title=label(ident), xlabel="Time, s", ylabel="Amplitude")
        frequencies, power = welch(audio.samples, audio.rate, nperseg=min(1024, len(audio.samples)))
        spectrum.plot(frequencies, 10 * np.log10(np.maximum(power, 1e-16)), lw=0.8)
        spectrum.set(xlabel="Frequency, Hz", ylabel="PSD, dB/Hz", xlim=(0, 8000))
        figure.savefig(folder / (ident + ".png"), dpi=110)
        measured = analyze(audio)
        record = {
            "id": ident,
            "label": label(ident),
            "segment": row,
            "wav": target.name,
            "sha256": wav_meta["sha256"],
            "duration": audio.duration,
            "f0_median_hz": measured["f0_median_hz"],
            "warnings": measured["warnings"],
        }
        records.append(record)
        f0 = (
            f"{measured['f0_median_hz']:.2f} Гц"
            if measured["f0_median_hz"] is not None
            else "не определена"
        )
        cards.append(
            f'<article><h2>{escape(label(ident))}</h2><audio controls preload="none" src="{target.name}"></audio>'
            f"<p>{escape(row['file'])}: {float(row['start']):.4f}–{float(row['end']):.4f} с; "
            f"длина {audio.duration * 1000:.2f} мс; медиана F0: {f0}.</p>"
            f'<img src="{ident}.png" alt="Осциллограмма и спектр {escape(label(ident), quote=True)}"></article>'
        )
    (folder / "atlas.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "inventory": "42-unit simplified teaching alphabet",
                "all_boundaries_human_confirmed": True,
                "results": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (folder / "index.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Атлас 42 звуков</title>'
        "<style>body{font:17px system-ui;max-width:1050px;margin:30px auto;padding:0 18px}article{border:1px solid #ccd;border-radius:8px;padding:15px;margin:18px 0;break-inside:avoid}img{width:100%}audio{max-width:100%}p{line-height:1.5}@media print{button,audio{display:none}}</style>"
        '<button onclick="window.print()">Печать</button><h1>42 подтверждённых звука учебного банка</h1>'
        "<p>Это точные копии фрагментов с проверенными пользователем границами. Новая разметка и новые оценки не требуются. "
        "Медиана F0 рассчитана на голосовых кадрах; у кратких и неголосовых звуков она может не определяться. "
        "Спектр Welch показан как PSD, а цифровая амплитуда не является калиброванной акустической громкостью.</p>"
        + "".join(cards)
        + "</html>",
        encoding="utf-8",
    )
    print("Built 42 waveforms/spectra from confirmed units; no new human observations generated.")
    print(folder / "index.html")


if __name__ == "__main__":
    main()
