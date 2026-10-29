"""Free-vocabulary ASR word timings; exact expected text required before use."""

import hashlib
import json

import numpy as np
import vosk

from lab5_7.application.project import ROOT
from lab5_7.domain.audio import resample
from lab5_7.infrastructure.wav import load
from lab5_7.tools.download_alignment_model import NAME

EXPECTED = {
    "words": ["саша", "кушал", "кашу"] * 2,
    "stress": ["саша", "кушал", "кашу"] * 6,
    "student": ["студент", "писал", "реферат"] * 3,
}


def main() -> None:
    folder = ROOT / "vendor" / NAME
    manifest = json.loads((folder / "provenance.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        path = (folder / name).resolve()
        if (
            not path.is_relative_to(folder.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Model hash mismatch.")
    vosk.SetLogLevel(-1)
    model = vosk.Model(str(folder))
    result = {}
    for name, expected in EXPECTED.items():
        audio, metadata = load(ROOT / "data/raw" / (name + ".wav"))
        converted = resample(audio, 16000)
        pcm = np.round(np.clip(converted.samples, -1, 1) * 32767).astype("<i2").tobytes()
        decoder = vosk.KaldiRecognizer(model, 16000)
        decoder.SetWords(True)
        words = []
        for start in range(0, len(pcm), 3200):
            if decoder.AcceptWaveform(pcm[start : start + 3200]):
                words.extend(json.loads(decoder.Result()).get("result", []))
        words.extend(json.loads(decoder.FinalResult()).get("result", []))
        exact = [w["word"] for w in words] == expected
        good = exact and all(w["conf"] >= 0.75 for w in words)
        result[name] = {
            "source_sha256": metadata["sha256"],
            "model": NAME,
            "expected_text_match": exact,
            "eligible": good,
            "words": words,
            "status": "ASR_PROPOSALS_REQUIRE_HUMAN_REVIEW",
        }
        print(
            name,
            "eligible",
            good,
            "text",
            json.dumps([w["word"] for w in words], ensure_ascii=True),
        )
    (ROOT / "vendor/word_alignment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
