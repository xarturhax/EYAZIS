"""Pinned model versions from the official Vosk catalogue."""

import argparse
import hashlib
import io
import json
import shutil
import ssl
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MODELS = {"fr": "vosk-model-small-fr-0.22", "en": "vosk-model-small-en-us-0.15"}


def main() -> None:
    import truststore

    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=["fr", "en", "all"], default="all")
    selected = parser.parse_args().language
    for language, name in MODELS.items():
        if selected not in ("all", language):
            continue
        target = ROOT / "models" / name
        if (target / "provenance.json").is_file():
            print(language, "ready", flush=True)
            continue
        url = f"https://alphacephei.com/vosk/models/{name}.zip"
        print("Downloading", name, flush=True)
        with urlopen(
            url, timeout=60, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ) as response:
            data = response.read(150 * 1024 * 1024)
        stage = ROOT / "models" / f".{name}.partial"
        stage.mkdir(parents=True, exist_ok=True)
        with ZipFile(io.BytesIO(data)) as archive:
            for entry in archive.infolist():
                parts = Path(entry.filename).parts
                if not parts or parts[0] != name or ".." in parts:
                    raise ValueError("Unexpected archive member.")
                destination = (stage / Path(*parts[1:])).resolve()
                if not destination.is_relative_to(stage.resolve()):
                    raise ValueError("Archive path escapes model directory.")
                if entry.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, destination.open("wb") as output:
                        shutil.copyfileobj(source, output)
        hashes = {}
        for path in stage.rglob("*"):
            if path.is_file():
                with path.open("rb") as stream:
                    hashes[str(path.relative_to(stage)).replace("\\", "/")] = hashlib.file_digest(
                        stream, "sha256"
                    ).hexdigest()
        (stage / "provenance.json").write_text(
            json.dumps(
                {
                    "language": language,
                    "model": name,
                    "url": url,
                    "license": "Apache-2.0",
                    "archive_sha256": hashlib.sha256(data).hexdigest(),
                    "files": hashes,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if target.exists():
            raise FileExistsError("Incomplete target exists; preserve it under another name.")
        stage.rename(target)
        print(language, "installed", flush=True)


if __name__ == "__main__":
    main()
