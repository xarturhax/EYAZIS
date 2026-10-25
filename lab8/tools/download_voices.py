"""Pinned French voices, downloaded only by explicit setup command."""

import hashlib
import json
import ssl
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
REPOSITORY = "rhasspy/piper-voices"
REVISION = "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd"
VOICES = {"siwis": "Siwis · français (France)", "tom": "Tom · français (France)"}


def main() -> None:
    import truststore

    for name in VOICES:
        folder = MODELS / name
        folder.mkdir(parents=True, exist_ok=True)
        files = {}
        prefix = f"fr_FR-{name}-medium.onnx"
        for filename in (prefix, prefix + ".json", "MODEL_CARD"):
            target = folder / filename
            url = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/fr/fr_FR/{name}/medium/{filename}"
            if not target.is_file():
                print("Downloading", name, filename, flush=True)
                partial = target.with_suffix(target.suffix + ".part")
                with urlopen(
                    url, timeout=60, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ) as response:
                    with partial.open("wb") as output:
                        while block := response.read(1024 * 1024):
                            output.write(block)
                partial.replace(target)
            with target.open("rb") as stream:
                files[filename] = hashlib.file_digest(stream, "sha256").hexdigest()
        (folder / "manifest.json").write_text(
            json.dumps(
                {"repository": REPOSITORY, "revision": REVISION, "voice": name, "sha256": files},
                indent=2,
            ),
            encoding="utf-8",
        )
    print("French voices ready.")


if __name__ == "__main__":
    main()
