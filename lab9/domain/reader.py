import re
from dataclasses import dataclass

from lab9.domain.commands import Action


@dataclass(frozen=True)
class Effect:
    message: str
    speak: bool = False


class Reader:
    def __init__(self) -> None:
        self.paragraphs: tuple[str, ...] = ()
        self.position = 0
        self.speed = 1.0

    def set_text(self, text: str) -> None:
        if len(text) > 5000:
            raise ValueError("Текст чтения: максимум 5000 символов.")
        self.paragraphs = tuple(p.strip() for p in re.split(r"\n\s*\n", text) if p.strip())
        self.position = 0

    @property
    def current(self) -> str:
        return self.paragraphs[self.position] if self.paragraphs else ""

    def apply(self, action: Action) -> Effect:
        if action == Action.STOP:
            return Effect("Чтение остановлено.")
        if action in (Action.FASTER, Action.SLOWER):
            self.speed = round(
                min(2, max(0.5, self.speed + (0.1 if action == Action.FASTER else -0.1))), 2
            )
            return Effect(f"Темп: {self.speed:.2f}×. Изменение применяется при следующем чтении.")
        if not self.paragraphs:
            return Effect("Нет текста для чтения.")
        if action == Action.NEXT:
            self.position = min(self.position + 1, len(self.paragraphs) - 1)
        elif action == Action.PREVIOUS:
            self.position = max(0, self.position - 1)
        return Effect(
            f"Абзац {self.position + 1}/{len(self.paragraphs)}",
            action in (Action.READ, Action.REPEAT),
        )
