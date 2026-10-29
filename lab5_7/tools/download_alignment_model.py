"""Optional offline Russian word timing model from the official Vosk catalogue."""

import hashlib
import io
import json
import ssl
from urllib.request import urlopen
from zipfile import ZipFile

import truststore

from lab5_7.application.project import ROOT

NAME = "vosk-model-small-ru-0.22"
URL = "https://alphacephei.com/vosk/models/" + NAME + ".zip"


def main() -> None:
    target = ROOT / "vendor" / NAME
    if (target / "provenance.json").is_file():
        print("Alignment model already installed")
        return
    with urlopen(
        URL, timeout=60, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ) as response:
        payload = response.read(100 * 1024 * 1024 + 1)
    if len(payload) > 100 * 1024 * 1024:
        raise ValueError("Unexpected archive size.")
    base = (ROOT / "vendor").resolve()
    base.mkdir(exist_ok=True)
    with ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.infolist():
            destination = (base / entry.filename).resolve()
            if not destination.is_relative_to(target.resolve()) or ".." in entry.filename.split(
                "/"
            ):
                raise ValueError("Unexpected model archive path.")
        archive.extractall(base)
    files = {}
    for path in target.rglob("*"):
        if path.is_file():
            files[path.relative_to(target).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    (target / "provenance.json").write_text(
        json.dumps(
            {
                "model": NAME,
                "url": URL,
                "license": "Apache-2.0",
                "archive_sha256": hashlib.sha256(payload).hexdigest(),
                "files": files,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Installed", NAME)


if __name__ == "__main__":
    main()
