import math
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

LANGUAGES = {"fr": "Français · основной", "en": "English · дополнительный"}
WAKE_WORDS = {"fr": "lecteur", "en": "reader"}


class Action(StrEnum):
    READ = "read"
    STOP = "stop"
    NEXT = "next"
    PREVIOUS = "previous"
    REPEAT = "repeat"
    FASTER = "faster"
    SLOWER = "slower"


LABELS = {
    Action.READ: "Читать",
    Action.STOP: "Остановить",
    Action.NEXT: "Следующий абзац",
    Action.PREVIOUS: "Предыдущий абзац",
    Action.REPEAT: "Повторить",
    Action.FASTER: "Быстрее",
    Action.SLOWER: "Медленнее",
}


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
