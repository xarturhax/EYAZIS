"""Only labelled technical signals; never populate data/raw with them."""

import numpy as np

from lab5_7.application.experiments import quality
from lab5_7.application.project import ROOT
from lab5_7.domain.audio import Audio, concatenate, crop, gain, loop
from lab5_7.infrastructure.analysis import export_analysis
from lab5_7.infrastructure.prosody import coupled_contour, coupled_shift, manipulate
from lab5_7.infrastructure.wav import save


def main() -> None:
    folder = ROOT / "work/technical"
    folder.mkdir(parents=True, exist_ok=True)
    rate = 48000
    t = np.arange(rate * 2) / rate
    harmonic = Audio(0.3 * np.sin(2 * np.pi * 200 * t) + 0.1 * np.sin(2 * np.pi * 400 * t), rate)
    noise = Audio(np.random.default_rng(567).normal(0, 0.06, len(t)), rate)
    silence = Audio(np.zeros(rate), rate)
    signals = {
        "harmonic_200Hz": harmonic,
        "noise": noise,
        "silence": silence,
        "psola_300Hz": manipulate(harmonic, [(0, 300), (2, 300)]),
        "stretched": manipulate(harmonic, [], [(0, 1.2), (2, 1.2)]),
        "coupled_12st": coupled_shift(harmonic, 12),
        "coupled_contour": coupled_contour(harmonic, [(0, 0.8), (1, 1.2), (2, 0.8)]),
        "gain_3dB": gain(harmonic, 0.5, 1.0, 3),
        "period_loop": loop(crop(harmonic, 0.5, 0.505), 200),
        "crossfade": concatenate([crop(harmonic, 0, 0.2), crop(noise, 0, 0.2)], 3),
    }
    for name, audio in signals.items():
        path = folder / f"{name}.wav"
        if not path.exists():
            save(audio, path)
        export_analysis(path, ROOT / "reports/technical" / name, "synthetic")
        print(name, "OK", flush=True)
    qfolder = ROOT / "reports/technical/quality"
    if not (qfolder / "experiment.json").exists():
        quality(folder / "harmonic_200Hz.wav", qfolder, "synthetic")
    (ROOT / "reports/technical/README.md").write_text(
        "# TECHNICAL TESTS ONLY\n\nSynthetic tones/noise/silence, not the user's voice. "
        "No speech intelligibility, emotional, or speaker-comparison conclusions are supplied.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
