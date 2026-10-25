"""Извлечение текста: сканы без OCR и запароленные PDF диагностируются явно."""

import hashlib

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from lab2.domain.models import CorpusEntry, Document, LabError
from lab2.domain.text import normalize


class PdfDocumentReader:
    def read(self, entry: CorpusEntry) -> Document:
        path = entry.path
        if path.suffix.lower() != ".pdf":
            raise LabError(f"{path.name}: нужен файл PDF")
        try:
            if path.stat().st_size > 20 * 1024 * 1024:
                raise LabError(f"{path.name}: размер превышает 20 MiB")
            reader = PdfReader(path)
            if reader.is_encrypted and not reader.decrypt(""):
                raise LabError(f"{path.name}: PDF защищён паролем; предоставьте открытый PDF")
            if len(reader.pages) > 100:
                raise LabError(f"{path.name}: более 100 страниц; разделите документ")
            pages = [page.extract_text() or "" for page in reader.pages]
            text = normalize("\n".join(pages))
            if len(text) > 1_000_000:
                raise LabError(f"{path.name}: слишком много текста (более 1 млн символов)")
            if not any(c.isalpha() for c in text):
                raise LabError(f"{path.name}: текстовый слой отсутствует. Нужен OCR вне программы.")
            notes = []
            empty = sum(not p.strip() for p in pages)
            if empty:
                notes.append(f"{empty} страниц без извлечённого текста; возможны сканы.")
            if len(text) < 200:
                notes.append("Короткий текст: результат может быть ненадёжным.")
            return Document(
                entry,
                text,
                len(pages),
                hashlib.sha256(text.casefold().encode("utf-8")).hexdigest(),
                tuple(notes),
            )
        except LabError:
            raise
        except (OSError, PyPdfError, ValueError, TypeError, KeyError) as exc:
            raise LabError(f"Не удалось прочитать {path.name}: {exc}") from exc
