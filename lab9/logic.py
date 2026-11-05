from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import StrEnum
from importlib.metadata import version
from math import gcd
from pathlib import Path
from queue import Empty, Full, Queue
from statistics import fmean
from threading import Event
from time import perf_counter
from typing import Any

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from lab9.tools.download_models import MODELS, ROOT

LANGUAGES = ("fr", "en")
WAKE_WORDS = {"fr": "lecteur", "en": "reader"}


class Action(StrEnum):
    READ = "read"
    STOP = "stop"
    NEXT = "next"
    PREVIOUS = "previous"
    REPEAT = "repeat"
    FASTER = "faster"
    SLOWER = "slower"


def normalize(text: str) -> str:
    folded = "".join(
        c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c)
    )
    return " ".join(re.findall(r"[^\W\d_]+", folded))


@dataclass(frozen=True)
class Command:
    language: str
    phrase: str
    action: Action
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.phrase, str) or not isinstance(self.language, str):
            raise ValueError("Command language and phrase must be strings.")
        words = normalize(self.phrase).split()
        if self.language not in LANGUAGES or not 2 <= len(words) <= 12:
            raise ValueError("Язык fr/en; команда должна содержать 2–12 слов.")
        if words[0] != WAKE_WORDS[self.language]:
            raise ValueError("Команда начинается с lecteur (fr) или reader (en).")
        if not isinstance(self.action, Action) or not isinstance(self.enabled, bool):
            raise ValueError("Некорректная операция или признак включения.")


@dataclass(frozen=True)
class Policy:
    commands: tuple[Command, ...]
    threshold: float = 0.75
    cooldown_seconds: float = 1.2

    def __post_init__(self) -> None:
        keys = [(c.language, normalize(c.phrase)) for c in self.commands]
        if len(keys) != len(set(keys)):
            raise ValueError("Фразы команд дублируются после нормализации.")
        if not 1 <= len(keys) <= 100:
            raise ValueError("В списке должно быть 1–100 команд.")
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("Порог уверенности должен быть от 0 до 1.")
        if not math.isfinite(self.cooldown_seconds) or not 0 <= self.cooldown_seconds <= 10:
            raise ValueError("Интервал повторов должен быть от 0 до 10 с.")


@dataclass(frozen=True)
class Word:
    text: str
    confidence: float
    start: float
    end: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) for x in (self.confidence, self.start, self.end)):
            raise ValueError("Некорректные числовые поля слова.")
        if not 0 <= self.confidence <= 1 or not 0 <= self.start <= self.end:
            raise ValueError("Некорректная уверенность или времена слова.")


@dataclass(frozen=True)
class Utterance:
    text: str
    words: tuple[Word, ...] = ()
    final: bool = True

    @property
    def confidence(self) -> float | None:
        return fmean(w.confidence for w in self.words) if self.words else None


@dataclass(frozen=True)
class Decision:
    status: str
    action: Action | None
    text: str
    confidence: float | None
    reason: str


class Router:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.last: dict[tuple[str, Action], float] = {}

    def resolve(self, utterance: Utterance, language: str, now: float) -> Decision:
        def result(status: str, action: Action | None, reason: str) -> Decision:
            return Decision(status, action, utterance.text, utterance.confidence, reason)

        if not utterance.final:
            return result("PARTIAL", None, "Промежуточный результат не выполняется.")
        if language not in LANGUAGES:
            raise ValueError("Выберите поддерживаемый язык.")
        phrase = normalize(utterance.text)
        match = next(
            (
                c
                for c in self.policy.commands
                if c.language == language and normalize(c.phrase) == phrase
            ),
            None,
        )
        if match is None:
            return result("UNKNOWN", None, "Фраза не совпадает с заданной командой целиком.")
        if not match.enabled:
            return result("DISABLED", None, "Операция для этой фразы отключена.")
        if normalize(" ".join(w.text for w in utterance.words)) != phrase:
            return result("LOW_CONFIDENCE", None, "Word scores do not cover the full transcript.")
        if utterance.confidence is None or utterance.confidence < self.policy.threshold:
            return result("LOW_CONFIDENCE", None, "Недостаточная средняя уверенность.")
        if min(w.confidence for w in utterance.words) < max(0, self.policy.threshold - 0.2):
            return result("LOW_CONFIDENCE", None, "В команде есть неуверенно распознанное слово.")
        key = (language, match.action)
        if (
            match.action != Action.STOP
            and now - self.last.get(key, float("-inf")) < self.policy.cooldown_seconds
        ):
            return result("COOLDOWN", None, "Повтор операции в защитном интервале.")
        self.last[key] = now
        return result("ACCEPTED", match.action, "Команда принята.")


def word_error_rate(reference: str, hypothesis: str) -> dict[str, float | int]:
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    previous = list(range(len(hyp) + 1))
    for i, left in enumerate(ref, 1):
        current = [i]
        for j, right in enumerate(hyp, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    errors = previous[-1]
    return {
        "errors": errors,
        "reference_words": len(ref),
        "wer": errors / len(ref) if ref else float(bool(hyp)),
    }


def load_pcm(path: Path) -> tuple[bytes, dict[str, object]]:
    if not path.is_file() or path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Нет WAV или размер больше 50 МиБ.")
    info = sf.info(path)
    if info.format != "WAV" or not 0 < info.duration <= 180:
        raise ValueError("Нужен WAV длительностью до 3 минут.")
    samples, rate = sf.read(path, dtype="float64", always_2d=True)
    values = samples[:, 0]
    if not np.isfinite(values).all():
        raise ValueError("Некорректные аудиоотсчёты.")
    if rate != 16000:
        divisor = gcd(rate, 16000)
        values = resample_poly(values, 16000 // divisor, rate // divisor)
    pcm = np.round(np.clip(values, -1, 1) * 32767).astype("<i2").tobytes()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return pcm, {
        "source": str(path.resolve()),
        "sha256": digest,
        "original_rate": rate,
        "original_channels": info.channels,
        "selected_channel": 1,
        "decoder_rate": 16000,
        "duration": len(pcm) / 32000,
    }


class CancelledError(Exception):
    pass


def parse_result(payload: str, final: bool = True) -> Utterance:
    data = json.loads(payload)
    words = tuple(
        Word(str(w["word"]), float(w["conf"]), float(w["start"]), float(w["end"]))
        for w in data.get("result", [])
    )
    return Utterance(str(data.get("text" if final else "partial", "")), words, final)


class VoskEngine:
    def __init__(self) -> None:
        self.models: dict[str, Any] = {}

    def prepare(self, language: str) -> dict[str, str]:
        import vosk

        if language not in MODELS:
            raise ValueError("Поддерживаются языки fr и en.")
        if language not in self.models:
            folder = ROOT / "models" / MODELS[language]
            if not (folder / "provenance.json").is_file():
                raise ValueError(
                    "Модель отсутствует. Выполните python -m lab9.tools.download_models."
                )
            vosk.SetLogLevel(-1)
            self.models[language] = vosk.Model(str(folder))
        return {"vosk": version("vosk"), "model": MODELS[language], "language": language}

    def decoder(self, language: str, rate: int) -> Any:
        import vosk

        decoder = vosk.KaldiRecognizer(self.models[language], rate)
        decoder.SetWords(True)
        return decoder

    def decode(
        self, pcm: bytes, rate: int, language: str, cancelled: Callable[[], bool] = lambda: False
    ) -> list[Utterance]:
        self.prepare(language)
        decoder = self.decoder(language, rate)
        results = []
        for start in range(0, len(pcm), max(2, round(rate * 0.1) * 2)):
            if cancelled():
                raise CancelledError("Распознавание отменено.")
            if decoder.AcceptWaveform(pcm[start : start + round(rate * 0.1) * 2]):
                value = parse_result(decoder.Result())
                if value.text:
                    results.append(value)
        if cancelled():
            raise CancelledError("Распознавание отменено.")
        final = parse_result(decoder.FinalResult())
        if final.text:
            results.append(final)
        return results

    def listen(
        self,
        language: str,
        device: int | None,
        emit: Callable[[Utterance], None],
        progress: Callable[[str], None],
        cancelled: Callable[[], bool],
        paused: Event,
    ) -> None:
        import sounddevice as sd

        progress("Загрузка модели распознавания…")
        self.prepare(language)
        if cancelled():
            return
        packets: Queue[bytes] = Queue(maxsize=30)
        problem: list[str] = []
        try:
            info = sd.query_devices(device, "input")
            rate = round(info["default_samplerate"])
            decoder = self.decoder(language, rate)

            def callback(data: Any, frames: int, timing: Any, status: Any) -> None:
                if status:
                    problem.append(str(status))
                    return
                if paused.is_set():
                    return
                try:
                    packets.put_nowait(bytes(data))
                except Full:
                    problem.append("Переполнение очереди аудио; прослушивание остановлено.")

            with sd.RawInputStream(
                device=device,
                samplerate=rate,
                blocksize=round(rate * 0.1),
                channels=1,
                dtype="int16",
                callback=callback,
            ):
                progress(f"Микрофон включён · {language} · {rate} Гц")
                last_partial = ""
                reset_pending = False
                while not cancelled():
                    if problem:
                        raise ValueError(problem[0])
                    if paused.is_set():
                        reset_pending = True
                        while not packets.empty():
                            try:
                                packets.get_nowait()
                            except Empty:
                                break
                        try:
                            packets.get(timeout=0.05)
                        except Empty:
                            pass
                        continue
                    if reset_pending:
                        decoder.Reset()
                        reset_pending = False
                        last_partial = ""
                    try:
                        packet = packets.get(timeout=0.15)
                    except Empty:
                        continue
                    if cancelled() or paused.is_set():
                        continue
                    if decoder.AcceptWaveform(packet):
                        value = parse_result(decoder.Result())
                        if value.text:
                            emit(value)
                    else:
                        value = parse_result(decoder.PartialResult(), False)
                        if value.text != last_partial:
                            last_partial = value.text
                            emit(value)
        except sd.PortAudioError as error:
            raise ValueError(f"Не удалось открыть микрофон: {error}") from error
        # Do not flush a trailing partial after the user stops listening.


def load_policy(path: Path) -> Policy:
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Конфигурация больше 1 МиБ.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a JSON object.")
        if data["schema"] != 1:
            raise ValueError("Ожидается schema=1.")
        commands = tuple(
            Command(r["language"], r["phrase"], Action(r["action"]), r["enabled"])
            for r in data["commands"]
        )
        return Policy(commands, float(data["threshold"]), float(data["cooldown_seconds"]))
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Некорректная конфигурация команд.") from error


def save_policy(path: Path, policy: Policy) -> None:
    payload = {
        "schema": 1,
        "threshold": policy.threshold,
        "cooldown_seconds": policy.cooldown_seconds,
        "commands": [asdict(command) for command in policy.commands],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


@dataclass(frozen=True)
class RecognitionResult:
    utterances: tuple[Utterance, ...]
    initialization_seconds: float
    recognition_seconds: float
    versions: dict[str, str]


class RecognitionService:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def run(
        self, pcm: bytes, rate: int, language: str, cancelled: Callable[[], bool] = lambda: False
    ) -> RecognitionResult:
        if not pcm or len(pcm) % 2 or not 8000 <= rate <= 96000:
            raise ValueError("Нужен непустой mono PCM16 и частота 8–96 кГц.")
        start = perf_counter()
        versions = self.engine.prepare(language)
        initialization = perf_counter() - start
        start = perf_counter()
        utterances = self.engine.decode(pcm, rate, language, cancelled)
        return RecognitionResult(
            tuple(utterances), initialization, perf_counter() - start, versions
        )


DEFAULT_COMMANDS = ROOT / "data/commands.json"
