from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Token:
    index: int
    text: str
    lemma: str
    pos: str
    tag: str
    morphology: str
    dependency: str
    head: int
    start: int
    end: int

    @property
    def is_word(self) -> bool:
        return any(c.isalpha() for c in self.text)


@dataclass(frozen=True)
class Sentence:
    index: int
    paragraph: int
    text: str
    tokens: tuple[Token, ...]


@dataclass(frozen=True)
class Analysis:
    text: str
    sentences: tuple[Sentence, ...]


@dataclass(frozen=True)
class Entry:
    lemma: str
    pos: str
    frequency: int
    forms: tuple[tuple[str, int], ...]
    tags: tuple[str, ...]
    morphology: tuple[str, ...]
    translation: str = ""
    origin: str = "missing"

    @property
    def covered(self) -> bool:
        # Shared EN/FR forms can be valid, but require explicit confirmation.
        return bool(self.translation.strip()) and (
            self.origin == "manual" or self.translation.casefold() != self.lemma.casefold()
        )


@dataclass(frozen=True)
class Result:
    analysis: Analysis
    translated_sentences: tuple[str, ...]
    translation: str
    entries: tuple[Entry, ...]
    source_words: int
    translated_source_words: int
    target_words: int
    timings: dict[str, float]
    versions: dict[str, str]
    warnings: tuple[str, ...]


def with_entries(result: Result, entries: tuple[Entry, ...]) -> Result:
    return replace(
        result,
        entries=entries,
        translated_source_words=sum(e.frequency for e in entries if e.covered),
    )


def dictionary(analysis: Analysis) -> tuple[Entry, ...]:
    from collections import Counter, defaultdict

    groups: dict[tuple[str, str], list[Token]] = defaultdict(list)
    for sentence in analysis.sentences:
        for token in sentence.tokens:
            if token.is_word:
                groups[(token.lemma, token.pos)].append(token)
    return tuple(
        sorted(
            (
                Entry(
                    lemma,
                    pos,
                    len(tokens),
                    tuple(sorted(Counter(t.text for t in tokens).items())),
                    tuple(sorted({t.tag for t in tokens})),
                    tuple(sorted({t.morphology for t in tokens if t.morphology})),
                )
                for (lemma, pos), tokens in groups.items()
            ),
            key=lambda entry: (-entry.frequency, entry.lemma, entry.pos),
        )
    )


def children(sentence: Sentence) -> tuple[int, dict[int, list[int]]]:
    """Adapted from spring 3lab/services/dependency.py, with strict tree validation."""
    roots = [t.index for t in sentence.tokens if t.index == t.head]
    if len(roots) != 1 or [t.index for t in sentence.tokens] != list(range(len(sentence.tokens))):
        raise ValueError("Некорректный корень или индексы дерева.")
    mapping: dict[int, list[int]] = {t.index: [] for t in sentence.tokens}
    for token in sentence.tokens:
        if token.head not in mapping:
            raise ValueError("Связь дерева выходит за границы предложения.")
        if token.head != token.index:
            mapping[token.head].append(token.index)
    visited = set()
    pending = [roots[0]]
    while pending:
        node = pending.pop()
        if node in visited:
            raise ValueError("Цикл в дереве зависимостей.")
        visited.add(node)
        pending.extend(mapping[node])
    if len(visited) != len(sentence.tokens):
        raise ValueError("Несвязное дерево зависимостей.")
    return roots[0], mapping
