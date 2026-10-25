"""UPOS descriptions plus spaCy's authoritative Penn Treebank/dependency explanations."""

from functools import lru_cache

POS = {
    "ADJ": "прилагательное",
    "ADP": "предлог/послелог",
    "ADV": "наречие",
    "AUX": "вспомогательный глагол",
    "CCONJ": "сочинительный союз",
    "DET": "определитель",
    "INTJ": "междометие",
    "NOUN": "существительное",
    "NUM": "числительное",
    "PART": "частица",
    "PRON": "местоимение",
    "PROPN": "имя собственное",
    "PUNCT": "пунктуация",
    "SCONJ": "подчинительный союз",
    "SYM": "символ",
    "VERB": "глагол",
    "X": "прочее",
    "SPACE": "пробел",
}


@lru_cache(maxsize=256)
def explain(tag: str) -> str:
    import spacy

    return POS.get(tag) or spacy.explain(tag) or "нет описания"


def tag_descriptions(tags: tuple[str, ...]) -> str:
    return "; ".join(f"{tag}: {explain(tag)}" for tag in tags)
