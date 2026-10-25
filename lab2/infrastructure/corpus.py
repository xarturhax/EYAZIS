"""Манифест сохраняет метки, разделение по источникам и относительные пути."""

import json
from pathlib import Path
from typing import cast

from lab2.domain.models import CorpusEntry, LabError, Language, Split


def load_manifest(path: Path) -> list[CorpusEntry]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        if raw.get("schema") != 1 or not isinstance(raw.get("documents"), list):
            raise LabError("Неизвестный формат манифеста; требуется schema=1 и documents")
        entries = []
        for item in raw["documents"]:
            local_path = Path(item["path"])
            entries.append(
                CorpusEntry(
                    (path.parent / local_path).resolve(),
                    cast(Split, item["split"]),
                    cast(Language | None, item.get("language")),
                    str(item.get("source_id", "")),
                    str(item.get("source_url", "")),
                    str(item.get("title", local_path.stem)),
                )
            )
        return entries
    except LabError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise LabError(f"Неверный манифест {path}: {exc}") from exc


def save_manifest(entries: list[CorpusEntry], path: Path) -> None:
    import os

    data = {
        "schema": 1,
        "documents": [
            {
                "path": os.path.relpath(entry.path, path.parent),
                "split": entry.split,
                "language": entry.language,
                "source_id": entry.source_id,
                "source_url": entry.source_url,
                "title": entry.title,
            }
            for entry in entries
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
