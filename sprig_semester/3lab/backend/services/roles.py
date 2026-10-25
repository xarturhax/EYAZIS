"""Syntactic role extraction (subject / predicate / object / modifier)."""
from __future__ import annotations

from typing import Any

_SUBJECT_DEPS = {"nsubj", "nsubjpass", "csubj", "csubjpass", "expl"}
_OBJECT_DEPS = {"dobj", "iobj", "pobj", "obj", "obl", "oprd"}
_MODIFIER_DEPS = {"amod", "advmod", "prep", "attr", "xcomp", "acomp", "npadvmod", "neg"}


def extract_roles(sent) -> dict[str, Any]:
    """Return {subjects, predicates, objects, modifiers} for a spaCy Span."""
    offset = sent.start
    subjects: list[dict] = []
    predicates: list[dict] = []
    objects: list[dict] = []
    modifiers: list[dict] = []

    for token in sent:
        item = {"text": token.text, "idx": token.i - offset, "dep": token.dep_, "pos": token.pos_}
        if token.dep_ in _SUBJECT_DEPS:
            subjects.append(item)
        elif token.dep_ == "ROOT":
            predicates.append(item)
        elif token.dep_ == "conj" and token.pos_ in ("VERB", "AUX"):
            predicates.append(item)
        elif token.dep_ in _OBJECT_DEPS:
            objects.append(item)
        elif token.dep_ in _MODIFIER_DEPS:
            modifiers.append(item)

    return {
        "subjects": subjects,
        "predicates": predicates,
        "objects": objects,
        "modifiers": modifiers,
    }
