"""Build short attributed excerpts from the real English corpus already in lab3."""

import hashlib
import json

from lab4.bootstrap import ROOT
from lab4.infrastructure.nlp import EnglishAnalyzer


def main() -> None:
    corpus = ROOT.parent / "lab3/data/demo"
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    analyzer = EnglishAnalyzer()
    analyzer.prepare()
    provenance = []
    for domain, limit in (("medicine", 3), ("art", 6)):
        source = next(
            row
            for row in manifest["documents"]
            if row["language"] == "en" and row["domain"] == domain
        )
        original = corpus / source["path"]
        analysis = analyzer.analyze(original.read_text(encoding="utf-8"))
        text = " ".join(s.text for s in analysis.sentences[:limit]) + "\n"
        target = ROOT / f"data/demo/source_{domain}.txt"
        target.write_text(text, encoding="utf-8")
        provenance.append(
            {
                **source,
                "path": target.name,
                "selection": f"First {limit} complete sentences",
                "original_path": str(original),
                "original_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
        print(domain, len(text), "characters")
    (ROOT / "data/demo/provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
