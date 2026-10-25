import json
from dataclasses import asdict
from pathlib import Path

from lab9.domain.commands import Action, Command, Policy


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
