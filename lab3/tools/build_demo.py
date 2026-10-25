"""Rebuild the local demonstration corpus from attributed source snapshots."""

import hashlib
import json
import re
import ssl
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

from lab3.bootstrap import ROOT
from lab3.infrastructure.documents import normalize

BASE = ROOT / "data" / "demo"
SOURCES = [
    dict(
        id="medical_en",
        file="medical_en.xml",
        language="en",
        domain="medicine",
        title="Reduced insulin use and diabetes complications — excerpt",
        url="https://doi.org/10.1371/journal.pmed.1004559",
        download="https://journals.plos.org/plosmedicine/article/file?id=10.1371/journal.pmed.1004559&type=manuscript",
        attribution="Global Health & Population Project on Access to Care for Cardiometabolic Diseases (HPACC), PLOS Medicine 22(4), 2025",
        license="CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/",
    ),
    dict(
        id="medical_es",
        file="medical_es.pdf",
        language="es",
        domain="medicine",
        title="Calidad de vida en adultos mayores con diabetes mellitus — fragmento",
        url="https://doi.org/10.56294/sctconf2023501",
        download="https://dialnet.unirioja.es/descarga/articulo/9871989.pdf",
        attribution="Leyllan Izquierdo Martínez, Gicela Díaz Pita, Iván Bustinzuriaga Marto, Aileen Leal Flores; Salud, Ciencia y Tecnología — Serie de Conferencias, 2:501, 2023",
        license="CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/",
    ),
    dict(
        id="art_en",
        file="art_en.txt",
        language="en",
        domain="art",
        title="The Meaning of Pictures: Truth in Painting — excerpt",
        url="https://www.gutenberg.org/ebooks/72598",
        download="https://www.gutenberg.org/cache/epub/72598/pg72598.txt",
        attribution="John C. Van Dyke, The Meaning of Pictures, Charles Scribner's Sons, 1911 edition; Project Gutenberg #72598",
        license="Public domain in USA; Gutenberg source snapshot contains its redistribution terms",
    ),
    dict(
        id="art_es",
        file="art_es.html",
        language="es",
        domain="art",
        title="Las meninas: técnica e interpretación — fragmento",
        url="https://es.wikipedia.org/wiki/Las_meninas",
        download="https://es.wikipedia.org/wiki/Las_meninas",
        attribution="Contributors to Spanish Wikipedia, Las meninas; history: https://es.wikipedia.org/w/index.php?title=Las_meninas&action=history",
        license="CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/; extracted text and summaries retain this license",
    ),
]


def download() -> None:
    import truststore

    folder = BASE / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        target = folder / source["file"]
        if not target.exists():
            request = Request(
                source["download"], headers={"User-Agent": "EYAZIS-Educational-Corpus/1.0"}
            )
            with urlopen(
                request, timeout=40, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ) as response:
                target.write_bytes(response.read(10_000_000))


def paragraphs(identifier: str) -> list[str]:
    from bs4 import BeautifulSoup

    folder = BASE / "sources"
    if identifier == "medical_en":
        article = ET.fromstring((folder / "medical_en.xml").read_bytes())
        # Drop bibliography markers before segmentation: "[1]." can become a
        # standalone sentence in general-domain models.
        for parent in article.iter():
            for child in list(parent):
                if child.tag == "xref" and child.get("ref-type") == "bibr":
                    tail = child.tail or ""
                    previous = list(parent).index(child)
                    if previous:
                        sibling = list(parent)[previous - 1]
                        sibling.tail = (sibling.tail or "") + tail
                    else:
                        parent.text = (parent.text or "") + tail
                    parent.remove(child)
        # Only Introduction, Methods, Results, Discussion; no metadata or author summary.
        nodes = article.findall("./body/sec")[:4]
        return [
            re.sub(r"\[\s*[,\s]*\]", "", "".join(p.itertext()))
            for node in nodes
            for p in node.findall(".//p")
        ]
    if identifier == "medical_es":
        import pymupdf

        blocks: list[str] = []
        with pymupdf.open(folder / "medical_es.pdf") as pdf:
            for page in pdf:
                blocks.extend(
                    b[4]
                    for b in page.get_text("blocks", sort=True)
                    if b[6] == 0 and 60 < b[1] < 720 and b[3] < 735
                )
        text = "\n\n".join(blocks)
        text = text.split("INTRODUCCIÓN", 1)[1].split("REFERENCIAS", 1)[0]
        return [p for p in text.split("\n\n") if len(p.strip()) > 120]
    if identifier == "art_en":
        text = (folder / "art_en.txt").read_text(encoding="utf-8-sig")
        text = text[text.index("THOSE people") :]
        return [
            p
            for p in re.split(r"\n\s*\n", text)
            if len(p.strip()) > 120 and not p.lstrip().startswith("[Illustration")
        ]
    soup = BeautifulSoup((folder / "art_es.html").read_bytes(), "html.parser")
    for node in soup.select("sup, .mw-editsection"):
        node.decompose()
    active = False
    result = []
    for node in soup.find_all(["h2", "h3", "p"]):
        label = node.get_text(" ", strip=True)
        if node.name in {"h2", "h3"}:
            if label == "Técnica":
                active = True
            if label.startswith("Influencia"):
                break
        elif active and len(label) > 120:
            result.append(label)
    return result


def excerpt(parts: list[str]) -> str:
    selected = []
    size = 0
    for part in parts:
        cleaned = normalize(part)
        if not cleaned:
            continue
        selected.append(cleaned)
        size += len(cleaned) + 2
        if size >= 12_000:
            break
    text = "\n\n".join(selected)
    if not 12_000 <= len(text) <= 15_000:
        raise ValueError(f"Unexpected excerpt size: {len(text)}")
    return text


def main() -> None:
    download()
    folder = BASE / "texts"
    folder.mkdir(exist_ok=True)
    records = []
    provenance = []
    for source in SOURCES:
        text = excerpt(paragraphs(source["id"]))
        target = folder / (source["id"] + ".txt")
        target.write_text(text, encoding="utf-8")
        records.append(
            {
                "path": str(target.relative_to(BASE)).replace("\\", "/"),
                **{
                    k: source[k]
                    for k in ("language", "domain", "title", "url", "attribution", "license")
                },
            }
        )
        provenance.append(
            {
                **source,
                "retrieved": "2026-10-24",
                "characters": len(text),
                "paragraphs": len(text.split("\n\n")),
                "source_sha256": hashlib.sha256(
                    (BASE / "sources" / source["file"]).read_bytes()
                ).hexdigest(),
                "text_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "transformation": "First complete paragraphs reaching 12000 characters in the selected section; NFC, whitespace normalization; bibliography markers removed from EN medical XML and ES art HTML. Original files retained.",
            }
        )
        print(source["id"], len(text), "characters")
    (BASE / "manifest.json").write_text(
        json.dumps({"schema": 1, "documents": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (BASE / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
