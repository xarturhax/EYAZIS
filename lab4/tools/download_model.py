"""Download the pinned official model with TLS validation and a hash manifest."""

import hashlib
import json
import ssl
from pathlib import Path
from urllib.request import urlopen

MODEL_ID = "Helsinki-NLP/opus-mt-en-fr"
REVISION = "dd7f6540a7a48a7f4db59e5c0b9c42c8eea67f18"
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "opus-mt-en-fr"
FILES = (
    "config.json",
    "generation_config.json",
    "tokenizer_config.json",
    "source.spm",
    "target.spm",
    "vocab.json",
    "pytorch_model.bin",
    "README.md",
)


def main() -> None:
    import truststore

    MODEL_PATH.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in FILES:
        target = MODEL_PATH / name
        if not target.is_file():
            print("Downloading", name, flush=True)
            partial = target.with_name(name + ".part")
            url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}"
            with urlopen(
                url, timeout=90, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ) as response:
                with partial.open("wb") as stream:
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
            partial.replace(target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (MODEL_PATH / "revision.json").write_text(
        json.dumps({"model": MODEL_ID, "revision": REVISION, "sha256": hashes}, indent=2),
        encoding="utf-8",
    )
    print("Local model ready:", MODEL_PATH)


if __name__ == "__main__":
    main()
