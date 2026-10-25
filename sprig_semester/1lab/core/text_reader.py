import os


def read_txt(path: str) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(f"Cannot decode file: {path}")


def read_rtf(path: str) -> str:
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError:
        raise ImportError("striprtf is not installed. Run: pip install striprtf")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        rtf_content = f.read()
    return rtf_to_text(rtf_content)


def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return read_txt(path)
    elif ext == ".rtf":
        return read_rtf(path)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: TXT, RTF")
