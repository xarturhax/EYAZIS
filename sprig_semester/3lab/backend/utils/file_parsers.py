"""File parsing utilities: HTML, TXT, RTF, PDF, DOCX, DOC."""
import os


def _parse_html(path: str) -> str:
    from bs4 import BeautifulSoup
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    soup = BeautifulSoup(content, "lxml")
    # Remove script and style elements
    for tag in soup(["script", "style", "head", "meta", "link"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _parse_txt(path: str) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(f"Cannot decode file: {path}")


def _parse_rtf(path: str) -> str:
    from striprtf.striprtf import rtf_to_text
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        rtf_content = f.read()
    return rtf_to_text(rtf_content)


def _parse_pdf(path: str) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except ImportError:
        pass
    import pypdf
    reader = pypdf.PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def _parse_doc(path: str) -> str:
    import docx2txt
    return docx2txt.process(path)


_DISPATCH = {
    ".html": _parse_html,
    ".htm": _parse_html,
    ".txt": _parse_txt,
    ".rtf": _parse_rtf,
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".doc": _parse_doc,
}

SUPPORTED_FORMATS = list(_DISPATCH.keys())


def parse_file(path: str) -> str:
    """Extract raw text from a file."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in _DISPATCH:
        raise ValueError(
            f"Unsupported format: {ext}. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )
    return _DISPATCH[ext](path)


def parse_bytes(data: bytes, filename: str) -> tuple[str, str]:
    """Extract raw text from in-memory bytes. Returns (text, format_ext)."""
    import tempfile

    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = ".txt"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        text = parse_file(tmp_path)
        return text, ext.lstrip(".")
    finally:
        os.unlink(tmp_path)
