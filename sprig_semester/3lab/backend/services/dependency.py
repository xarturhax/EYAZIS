"""Dependency tree extraction from spaCy sentence spans."""
from __future__ import annotations

from typing import Any


def extract_dep_tree(sent) -> dict[str, Any]:
    """Convert a spaCy Span (sentence) into a dependency tree dict.

    Returns:
        {
          "tokens": [{"i", "text", "lemma", "pos", "tag", "dep", "head"}, ...],
          "tree": recursive node {"i", "text", "lemma", "pos", "dep", "children": [...]}
        }
    """
    offset = sent.start
    tokens = [
        {
            "i": token.i - offset,
            "text": token.text,
            "lemma": token.lemma_,
            "pos": token.pos_,
            "tag": token.tag_,
            "dep": token.dep_,
            "head": token.head.i - offset,
        }
        for token in sent
    ]

    # Locate root
    root_idx = next(
        (t["i"] for t in tokens if t["dep"] == "ROOT"),
        0,
    )

    def build_node(idx: int, visited: set[int] | None = None) -> dict[str, Any]:
        if visited is None:
            visited = set()
        visited.add(idx)
        t = tokens[idx]
        children = [
            build_node(c["i"], visited)
            for c in tokens
            if c["head"] == idx and c["i"] != idx and c["i"] not in visited
        ]
        return {
            "i": t["i"],
            "text": t["text"],
            "lemma": t["lemma"],
            "pos": t["pos"],
            "dep": t["dep"],
            "children": children,
        }

    return {
        "tokens": tokens,
        "tree": build_node(root_idx),
    }
