"""Local input adapters. TXT paragraphs are authoritative; PDF layout is approximate."""

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from lab3.domain.models import Document, Source

MAX_BYTES = 20 * 1024 * 1024
MAX_CHARACTERS = 200_000


def source_url(value: str) -> str:
    if not value:
        return ""
    if urlparse(value).scheme not in {"http", "https"} or not urlparse(value).netloc:
        raise ValueError("Ссылка на источник должна начинаться с http:// или https://.")
    return value


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace("\u00ad", "")
    # Preserve paragraph boundaries while undoing visual line wrapping.
    paragraphs = re.split(r"\n[ \t]*\n+", text)
    return "\n\n".join(" ".join(p.split()) for p in paragraphs if p.strip())


def read_document(source: Source) -> Document:
    path = source.path
    if not path.is_file():
        raise ValueError(f"Файл не найден: {path}")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Файл больше 20 МиБ.")
    source_url(source.url)
    warnings: list[str] = []
    if path.suffix.lower() == ".txt":
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as error:
            raise ValueError("TXT должен быть сохранён в UTF-8.") from error
    elif path.suffix.lower() == ".pdf":
        import pymupdf

        try:
            with pymupdf.open(path) as pdf:
                if pdf.needs_pass:
                    raise ValueError("PDF защищён паролем.")
                if len(pdf) > 100:
                    raise ValueError("В PDF больше 100 страниц.")
                parts: list[str] = []
                for page in pdf:
                    blocks = page.get_text("blocks", sort=True)
                    parts.extend(b[4].strip() for b in blocks if b[6] == 0 and b[4].strip())
                text = "\n\n".join(parts)
        except (pymupdf.FileDataError, RuntimeError) as error:
            raise ValueError(f"Не удалось прочитать PDF: {error}") from error
        warnings.append(
            "PDF: блоки извлечения приняты за абзацы; проверьте порядок колонок, "
            "колонтитулы и переносы. Для точных позиций используйте подготовленный TXT."
        )
    else:
        raise ValueError("Поддерживаются TXT (UTF-8) и PDF с текстовым слоем.")
    text = normalize(text)
    if not any(c.isalpha() for c in text):
        raise ValueError("Нет буквенного текста. Сканированный PDF требует OCR.")
    if len(text) > MAX_CHARACTERS:
        raise ValueError("Текст больше 200 000 символов.")
    return Document(source, text, tuple(warnings))


def read_manifest(path: Path) -> list[Source]:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Манифест больше 2 МиБ.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data["schema"] != 1 or not isinstance(data["documents"], list):
            raise ValueError("Ожидается schema=1 и список documents.")
        sources = []
        for row in data["documents"]:
            if not isinstance(row, dict) or any(not isinstance(v, str) for v in row.values()):
                raise ValueError("Поля документа должны быть строками.")
            sources.append(
                Source(
                    (path.parent / row["path"]).resolve(),
                    row["language"],
                    row["domain"],
                    row["title"],
                    source_url(row.get("url", "")),
                    row.get("attribution", ""),
                    row.get("license", ""),
                )
            )
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"Некорректный манифест: {error}") from error
    if not 1 <= len(sources) <= 100:
        raise ValueError("В корпусе должно быть от 1 до 100 документов.")
    return sources


def save_manifest(path: Path, sources: list[Source]) -> None:
    rows = []
    for source in sources:
        row = asdict(source)
        row["path"] = str(source.path.resolve())
        rows.append(row)
    path.write_text(
        json.dumps(
            {"schema": 1, "documents": rows},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_corpus(sources: list[Source]) -> list[Document]:
    if not 1 <= len(sources) <= 100:
        raise ValueError("В корпусе должно быть от 1 до 100 документов.")
    documents = []
    seen = set()
    for source in sources:
        document = read_document(source)
        digest = hashlib.sha256(document.text.encode("utf-8")).hexdigest()
        if digest in seen:
            raise ValueError(f"Повтор текста в корпусе: {source.title}")
        seen.add(digest)
        documents.append(document)
    return documents
