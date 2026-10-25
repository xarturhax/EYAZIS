import json
from collections.abc import Callable
from importlib.metadata import version
from queue import Empty, Full, Queue
from threading import Event
from typing import Any

from lab9.domain.commands import Utterance, Word
from lab9.tools.download_models import MODELS, ROOT


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
