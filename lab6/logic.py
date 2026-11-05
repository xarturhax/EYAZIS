from datetime import datetime
from pathlib import Path

from lab5.analysis import export_analysis
from lab5.audio import crop, gain, load, save
from lab6.prosody import coupled_contour, coupled_shift, manipulate

"""Изменение F0, длительности и амплитуды выбранной фразы."""


ROOT = Path(__file__).resolve().parent


def word_permutations(prefix="word"):
    from lab7.logic import extract_bank, permutations

    folder = ROOT / "reports/local" / datetime.now().strftime("permutations_%Y%m%d_%H%M%S_%f")
    folder.mkdir(parents=True)
    bank = folder / "bank"
    extract_bank(bank)
    permutations(bank, folder / "words", prefix)
    playlist = sorted((folder / "words").glob("*.wav"))
    metrics = export_analysis(playlist[0], folder / "analysis")
    return {
        "audio": playlist[0],
        "original": bank / "ref_1.wav",
        "folder": folder,
        "metrics": metrics,
        "playlist": playlist,
    }


def process(
    source, start, end, method, pitch_points, duration_points, rate_points, semitones, gain_values
):
    folder = ROOT / "reports/local" / datetime.now().strftime("desktop_%Y%m%d_%H%M%S_%f")
    folder.mkdir(parents=True)
    audio, metadata = load(Path(source))
    audio = crop(audio, start, end)
    original = folder / "original.wav"
    save(audio, original)
    if method == "PSOLA":
        result = manipulate(audio, pitch_points, duration_points)
    elif method == "Сдвиг с изменением темпа":
        result = coupled_shift(audio, semitones)
    elif method == "Контур скорости":
        result = coupled_contour(audio, rate_points)
    else:
        raise ValueError("Неизвестный метод.")
    if gain_values is not None:
        result = gain(result, *gain_values)
    target = folder / "processed.wav"
    save(result, target)
    import json

    controls = {
        "source": metadata,
        "interval": [start, end],
        "method": method,
        "pitch_points": pitch_points,
        "duration_points": duration_points,
        "rate_points": rate_points,
        "semitones": semitones,
        "gain": gain_values,
        "listening": "NOT_ASSESSED",
    }
    (folder / "controls.json").write_text(
        json.dumps(controls, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    export_analysis(original, folder / "source_analysis")
    metrics = export_analysis(target, folder / "analysis")
    return {
        "audio": target,
        "original": original,
        "folder": folder,
        "metrics": metrics,
        "playlist": [],
    }
