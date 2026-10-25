"""Download portable Praat from its official GitHub release; never launch it here."""

import hashlib
import io
import json
import ssl
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

VERSION = "7.0.02"
URL = "https://github.com/praat/praat/releases/download/v7.0.02/praat7002_win-x64v1.zip"


def main() -> None:
    import truststore

    folder = Path(__file__).resolve().parents[1] / "vendor/praat"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "Praat.exe"
    if target.exists():
        print("Praat already exists:", target)
        return
    with urlopen(
        URL, timeout=60, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ) as response:
        payload = response.read(100 * 1024 * 1024)
    with ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if Path(name).name.casefold() == "praat.exe"]
        if len(names) != 1:
            raise ValueError("Unexpected official archive structure.")
        data = archive.read(names[0])
    if not data.startswith(b"MZ"):
        raise ValueError("Not a Windows executable.")
    target.write_bytes(data)
    (folder / "provenance.json").write_text(
        json.dumps(
            {"version": VERSION, "source": URL, "sha256": hashlib.sha256(data).hexdigest()},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Portable Praat ready:", target)


if __name__ == "__main__":
    main()
