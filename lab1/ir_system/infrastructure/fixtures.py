"""Преобразование внешнего JSON в предметные данные без изменения базы."""

import json
from pathlib import Path

from lab1.ir_system.domain.errors import ValidationError
from lab1.ir_system.domain.models import DemoCollection, DemoDocument, DemoQuery, DocumentDraft


class JsonCollectionSource:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> DemoCollection:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            documents = tuple(
                DemoDocument(item["key"], DocumentDraft(item["url"], item["title"], item["text"]))
                for item in data["documents"]
            )
            queries = tuple(DemoQuery(item["text"], item["grades"]) for item in data["queries"])
            if any(not isinstance(item.key, str) or not item.key for item in documents):
                raise ValidationError("Каждый документ демо должен иметь строковый ключ")
            return DemoCollection(documents, queries)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValidationError(f"Не удалось прочитать демо-коллекцию: {exc}") from exc
