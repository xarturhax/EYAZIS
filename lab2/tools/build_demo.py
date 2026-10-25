"""Воспроизводимая подготовка PDF из открытых литературных источников."""

import hashlib
import html
import json
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

import truststore
from matplotlib import get_data_path
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

from lab2.bootstrap import ROOT
from lab2.domain.text import normalize

# Каждое произведение принадлежит только одному split; тестовые авторы также не обучающие.
BOOKS = (
    (11, "en", "train", "Alice's Adventures in Wonderland", "Lewis Carroll"),
    (1342, "en", "train", "Pride and Prejudice", "Jane Austen"),
    (2000, "es", "train", "Don Quijote", "Miguel de Cervantes"),
    (17340, "es", "train", "Marianela", "Benito Perez Galdos"),
    (1661, "en", "test", "The Adventures of Sherlock Holmes", "Arthur Conan Doyle"),
    (29506, "es", "test", "El sombrero de tres picos", "Pedro Antonio de Alarcon"),
)


def body_text(raw: str, number: int) -> str:
    start = re.search(r"\*\*\* START OF .*?\*\*\*", raw)
    end = re.search(r"\*\*\* END OF .*?\*\*\*", raw)
    if not start or not end:
        raise ValueError("Gutenberg markers not found")
    body = raw[start.end() : end.start()]
    if number == 29506:
        # Это учебное издание с английским введением и словарём: их исключаем явно.
        begin = body.index("DE CUÁNDO SUCEDIÓ LA COSA")
        end_notes = re.search(r"\nNOTES\s*\n", body[begin:])
        if end_notes is None:
            raise ValueError("End of Spanish main text not found")
        body = body[begin : begin + end_notes.start()]
    body = re.sub(r"\[[^\]]*\]", " ", body)  # номера страниц/примечаний/illustration
    return normalize(body.replace("_", ""))


def write_pdf(path: Path, text: str) -> None:
    font = Path(get_data_path()) / "fonts" / "ttf" / "DejaVuSerif.ttf"
    if "Lab2Serif" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Lab2Serif", str(font)))
    style = ParagraphStyle("body", fontName="Lab2Serif", fontSize=11, leading=16)
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=48,
        bottomMargin=48,
        title="Language identification sample",
        author="",
    )
    document.build([Paragraph(html.escape(text), style)])
    if len(PdfReader(path).pages) != 1:
        raise ValueError(f"Expected one A4 page: {path}")


def main() -> None:
    destination = ROOT / "data" / "demo"
    sources = destination / "sources"
    pdfs = destination / "pdf"
    sources.mkdir(parents=True, exist_ok=True)
    pdfs.mkdir(exist_ok=True)
    manifest: dict[str, object] = {
        "schema": 1,
        "description": "Public-domain literary excerpts; 32 train / 16 test; one A4 page each.",
        "selection": "8 excerpts/book, about 2400 characters, main-text positions 10%..80%.",
        "documents": [],
    }
    documents = []
    provenance = []
    sequence = 0
    for number, language, split, title, author in BOOKS:
        source_path = sources / f"pg{number}.txt"
        url = f"https://www.gutenberg.org/cache/epub/{number}/pg{number}.txt"
        if not source_path.exists():
            request = Request(url, headers={"User-Agent": "EYAZIS-Lab2/1.0 educational"})
            with urlopen(
                request, timeout=45, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ) as response:
                data = response.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError("Source is too large")
            source_path.write_bytes(data)
        raw = source_path.read_text(encoding="utf-8-sig")
        if not re.search(r"Language:\s*" + ("English" if language == "en" else "Spanish"), raw):
            raise ValueError(f"Unexpected language metadata: {number}")
        body = body_text(raw, number)
        if len(body) < 40_000:
            raise ValueError(f"Source too short: {number}")
        provenance.append(
            {
                "ebook": number,
                "title": title,
                "author": author,
                "language": language,
                "split": split,
                "url": url,
                "page": f"https://www.gutenberg.org/ebooks/{number}",
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            }
        )
        for index in range(8):
            sequence += 1
            start = body.find(" ", int(len(body) * (0.1 + index * 0.1))) + 1
            end = body.rfind(" ", start, start + 2400)
            excerpt = body[start:end]
            if len(excerpt) < 2300:
                raise ValueError("Unexpected excerpt length")
            path = pdfs / f"doc{sequence:03}.pdf"
            write_pdf(path, excerpt)
            documents.append(
                {
                    "path": path.relative_to(destination).as_posix(),
                    "language": language,
                    "split": split,
                    "source_id": f"gutenberg:{number}",
                    "source_url": f"https://www.gutenberg.org/ebooks/{number}",
                    "title": f"{title} [{index + 1}]",
                    "offset": start,
                    "characters": len(excerpt),
                }
            )
        print(number, language, split, "8 PDFs", flush=True)
    manifest["documents"] = documents
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (destination / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Generated:", len(documents), "PDFs")


if __name__ == "__main__":
    main()
