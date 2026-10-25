import csv
import json
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import spectrogram

from lab5_7.domain.audio import Audio
from lab5_7.infrastructure.wav import load


def analyze(audio: Audio, floor: float = 60, ceiling: float = 500) -> dict[str, Any]:
    import parselmouth

    if not 40 <= floor < ceiling <= min(1200, audio.rate / 2):
        raise ValueError("Неверный диапазон F0.")
    x = audio.samples
    window = max(1, round(0.025 * audio.rate))
    hop = max(1, round(0.01 * audio.rate))
    times, rms = [], []
    for start in range(0, max(1, len(x) - window + 1), hop):
        frame = x[start : min(start + window, len(x))]
        times.append((start + len(frame) / 2) / audio.rate)
        rms.append(float(np.sqrt(np.mean(frame**2))))
    pitch_times, frequencies = [], []
    warnings = []
    if audio.duration >= 3 / floor:
        pitch = parselmouth.Sound(x, sampling_frequency=audio.rate).to_pitch_ac(
            time_step=0.01, pitch_floor=floor, pitch_ceiling=ceiling
        )
        pitch_times = pitch.xs().tolist()
        frequencies = [float(f) if f > 0 else None for f in pitch.selected_array["frequency"]]
    else:
        warnings.append("Фрагмент слишком короткий для выбранного окна F0.")
    voiced = [v for v in frequencies if v is not None]
    if not voiced:
        warnings.append("F0 не определена: это не означает частоту 0 Гц.")
    peak = float(np.max(np.abs(x)))
    return {
        "duration": audio.duration,
        "samples": len(x),
        "rate": audio.rate,
        "peak": peak,
        "rms": float(np.sqrt(np.mean(x * x))),
        "dc_offset": float(np.mean(x)),
        "near_full_scale_fraction": float(np.mean(np.abs(x) >= 32767 / 32768)),
        "f0_median_hz": float(np.median(voiced)) if voiced else None,
        "voiced_fraction": len(voiced) / len(frequencies) if frequencies else 0,
        "f0_range": [floor, ceiling],
        "f0_time": pitch_times,
        "f0_hz": frequencies,
        "rms_time": times,
        "rms_dbfs": [20 * np.log10(v) if v > 0 else None for v in rms],
        "warnings": warnings,
        "versions": {"parselmouth": parselmouth.VERSION, "praat_engine": parselmouth.PRAAT_VERSION},
    }


def export_analysis(
    path: Path, output: Path, kind: str = "recording", floor: float = 60, ceiling: float = 500
) -> dict[str, Any]:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    if kind not in ("recording", "synthetic"):
        raise ValueError("Источник: recording или synthetic.")
    audio, metadata = load(path)
    result = analyze(audio, floor, ceiling)
    result.update(
        input=metadata,
        source_kind=kind,
        status="TECHNICAL_TEST_ONLY" if kind == "synthetic" else "MEASURED_NOT_REVIEWED",
    )
    output.mkdir(parents=True, exist_ok=True)
    figure = Figure(figsize=(11, 9), constrained_layout=True)
    FigureCanvasAgg(figure)
    axes = figure.subplots(4, 1)
    x = audio.samples
    stride = max(1, len(x) // 100000)
    axes[0].plot(np.arange(0, len(x), stride) / audio.rate, x[::stride], lw=0.5)
    axes[0].set(ylabel="Амплитуда", title=f"{path.name} · {kind}")
    size = min(len(x), max(16, round(0.025 * audio.rate)))
    frequencies, times, power = spectrogram(
        x, audio.rate, nperseg=size, noverlap=min(size - 1, round(0.015 * audio.rate))
    )
    axes[1].pcolormesh(times, frequencies, 10 * np.log10(np.maximum(power, 1e-15)), shading="auto")
    axes[1].set(ylabel="Частота, Гц", ylim=(0, min(8000, audio.rate / 2)))
    pitch_values = [v if v is not None else np.nan for v in result["f0_hz"]]
    axes[2].plot(result["f0_time"], pitch_values, ".-", ms=2)
    axes[2].set(ylabel="F0, Гц", ylim=(floor, ceiling))
    axes[3].plot(result["rms_time"], [v if v is not None else np.nan for v in result["rms_dbfs"]])
    axes[3].set(ylabel="RMS, dBFS", xlabel="Время, с")
    figure.savefig(output / "contours.png", dpi=140)
    (output / "metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    for name, time_key, value_key in (
        ("f0.csv", "f0_time", "f0_hz"),
        ("rms.csv", "rms_time", "rms_dbfs"),
    ):
        with (output / name).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["time_seconds", value_key])
            writer.writerows(zip(result[time_key], result[value_key], strict=True))
    note = (
        "ТЕХНИЧЕСКИЙ СИНТЕТИЧЕСКИЙ СИГНАЛ. Не результат опыта с голосом."
        if kind == "synthetic"
        else "Измерения записи. Границы фонем и выводы о звучании ещё требуют проверки."
    )
    (output / "report.html").write_text(
        '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Анализ WAV</title>'
        "<style>body{font:16px system-ui;max-width:1000px;margin:25px auto}img{max-width:100%}"
        '@media print{button{display:none}}</style><button onclick="window.print()">Печать</button>'
        f'<h1>{escape(path.name)}</h1><p>{note}</p><audio controls src="{escape(path.resolve().as_uri(), quote=True)}"></audio>'
        '<img src="contours.png" alt="Осциллограмма, спектрограмма, F0 и RMS">'
        f"<pre>{escape(json.dumps({k: result[k] for k in ('duration', 'peak', 'rms', 'f0_median_hz', 'warnings')}, ensure_ascii=False, indent=2))}</pre>"
        "<p>RMS dBFS не является калиброванной громкостью в dB SPL. Неголосовые участки F0 "
        "оставлены пустыми. Ошибки октавы и выделения тона проверяются в Praat.</p></html>",
        encoding="utf-8",
    )
    return result
