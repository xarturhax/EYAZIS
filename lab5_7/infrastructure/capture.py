"""Read-only device listing; actual recording only through an explicit capture call."""

import json
from pathlib import Path

import soundfile as sf


def devices() -> str:
    import sounddevice as sd

    try:
        return str(sd.query_devices())
    except sd.PortAudioError as error:
        raise ValueError(f"Не удалось получить устройства: {error}") from error


def record(path: Path, seconds: float, rate: int, bits: int, device: int | None) -> None:
    import sounddevice as sd

    if path.exists():
        raise FileExistsError("Сначала сохраните прежнюю попытку под другим именем.")
    if (
        not 1 <= seconds <= 300
        or rate not in (4000, 8000, 16000, 32000, 44100, 48000)
        or bits not in (8, 16)
    ):
        raise ValueError("Проверьте длительность, частоту и PCM-разрядность.")
    try:
        sd.check_input_settings(device=device, channels=1, samplerate=rate)
        samples = sd.rec(
            round(seconds * rate), samplerate=rate, channels=1, dtype="float64", device=device
        )
        try:
            flags = sd.wait()
        finally:
            sd.stop()
    except sd.PortAudioError as error:
        raise ValueError(f"Микрофон или частота недоступны: {error}") from error
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        sf.write(stream, samples, rate, format="WAV", subtype="PCM_U8" if bits == 8 else "PCM_16")
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "source_kind": "recording",
                "requested_rate": rate,
                "stored_bits": bits,
                "device": device,
                "portaudio_status": str(flags),
                "note": "Driver may internally resample; requested rate is not proof of physical ADC rate.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
