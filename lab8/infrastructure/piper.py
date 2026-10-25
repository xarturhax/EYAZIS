import hashlib
import json
from collections.abc import Callable
from importlib.metadata import version
from typing import Any

import numpy as np

from lab8.domain.models import Audio, CancelledError, Settings
from lab8.tools.download_voices import MODELS, REVISION, VOICES


class PiperSynthesizer:
    """Only one worker uses the models; no synthesis concurrently with another request."""

    def __init__(self) -> None:
        self.models: dict[str, Any] = {}

    def prepare(self, voice: str) -> dict[str, str]:
        from piper import PiperVoice

        if voice not in VOICES:
            raise ValueError("Unknown French voice.")
        if voice not in self.models:
            folder = MODELS / voice
            manifest = folder / "manifest.json"
            if not manifest.is_file():
                raise ValueError(
                    "Французский голос не установлен. Выполните python -m lab8.tools.download_voices."
                )
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            if metadata["revision"] != REVISION:
                raise ValueError("Ревизия голоса не соответствует приложению.")
            for name, digest in metadata["sha256"].items():
                path = folder / name
                if path.resolve().parent != folder.resolve():
                    raise ValueError("Некорректный путь в манифесте голоса.")
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                        raise ValueError(
                            "Контрольная сумма голоса не совпадает; повторите установку."
                        )
            model = folder / f"fr_FR-{voice}-medium.onnx"
            self.models[voice] = PiperVoice.load(model, use_cuda=False)
            if self.models[voice].config.espeak_voice not in {"fr", "fr-fr", "fr_FR"}:
                del self.models[voice]
                raise ValueError("Загруженный голос не французский.")
        return {
            "piper-tts": version("piper-tts"),
            "onnxruntime": version("onnxruntime"),
            "numpy": version("numpy"),
            "model_revision": REVISION,
            "device": "CPU",
            "voice": voice,
            "normalization": "Piper per sentence; output peak factor 0.98",
            "noise_scale": "0",
            "noise_w_scale": "0",
        }

    def synthesize(self, text: str, settings: Settings, cancelled: Callable[[], bool]) -> Audio:
        from piper import SynthesisConfig

        if cancelled():
            raise CancelledError("Синтез отменён.")
        voice = self.models[settings.voice]
        configuration = SynthesisConfig(
            length_scale=1 / settings.speed,
            noise_scale=0,
            noise_w_scale=0,
            volume=1,
            normalize_audio=True,
        )
        blocks = []
        rate = voice.config.sample_rate
        for chunk in voice.synthesize(text, syn_config=configuration):
            if cancelled():
                raise CancelledError("Синтез отменён.")
            if chunk.sample_rate != rate or chunk.sample_channels != 1:
                raise ValueError("Движок вернул неожиданный аудиоформат.")
            blocks.append(chunk.audio_float_array)
        if not blocks:
            raise ValueError("Движок не создал звук для данного фрагмента.")
        samples = np.concatenate(blocks).astype(np.float32)
        if not np.isfinite(samples).all():
            raise ValueError("Движок вернул некорректные аудиоотсчёты.")
        samples *= settings.volume * 0.98
        return Audio(samples, rate)
