from pathlib import Path

from lab3.domain.models import Analyzed, Document, Sentence, Source


def analyzed(paragraphs: list[tuple[str, tuple[str, ...]]], language: str = "en") -> Analyzed:
    text = "\n\n".join(p[0] for p in paragraphs)
    document = Document(Source(Path("example.txt"), language, "medicine", "Example"), text)
    sentences = []
    offset = 0
    for index, (value, terms) in enumerate(paragraphs):
        sentences.append(
            Sentence(
                index,
                value,
                offset,
                offset + len(value),
                offset,
                offset + len(value),
                terms,
                len(value.split()),
            )
        )
        offset += len(value) + 2
    return Analyzed(document, tuple(sentences), 0.0)


def fixture() -> list[Analyzed]:
    return [
        analyzed(
            [
                ("Alpha alpha beta.", ("alpha", "alpha", "beta")),
                ("Beta common.", ("beta", "common")),
            ]
        ),
        analyzed([("Beta common.", ("beta", "common"))]),
        analyzed([("Common.", ("common",))]),
    ]
