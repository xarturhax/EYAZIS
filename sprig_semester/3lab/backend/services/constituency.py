"""Constituency (phrase-structure) tree extraction via standalone benepar.Parser."""
from __future__ import annotations

from typing import Any


def extract_const_tree(sent) -> tuple[str, dict[str, Any]]:
    """Return (bracket_string, json_tree) for a spaCy Span.

    Uses standalone benepar.Parser (avoids spaCy retokenization bugs).
    Falls back to a chunked phrase tree when benepar is unavailable or fails.
    """
    from backend.utils.nlp import get_benepar_parser

    bracket = ""
    parser = get_benepar_parser()

    if parser is not None:
        try:
            # Pass the raw sentence text — benepar handles its own tokenization
            tree = parser.parse(sent.text)
            bracket = str(tree)
        except Exception:
            pass

    if not bracket:
        bracket = _make_chunk_bracket(sent)

    return bracket, _parse_bracket(bracket)


def _make_chunk_bracket(sent) -> str:
    """Build phrase-grouped bracket tree using spaCy noun_chunks + VP heuristic.

    Group labels are the actual words they contain ("The cat", "is jumping").
    Each word node has its POS tag as a child leaf.
    """
    tokens = list(sent)
    n = len(tokens)

    # Noun phrase spans via spaCy noun_chunks
    in_chunk: dict[int, tuple[int, int]] = {}
    for chunk in sent.noun_chunks:
        start = chunk.start - sent.start
        end = chunk.end - sent.start
        for i in range(start, end):
            in_chunk[i] = (start, end)

    groups = []
    i = 0
    seen: set[int] = set()

    while i < n:
        if i in seen:
            i += 1
            continue
        if i in in_chunk:
            start, end = in_chunk[i]
            label = " ".join(t.text for t in tokens[start:end])
            parts = " ".join(f"({t.text} {t.pos_})" for t in tokens[start:end])
            groups.append(f"({label} {parts})")
            seen.update(range(start, end))
            i = end
        elif tokens[i].pos_ == "AUX" and i + 1 < n and tokens[i + 1].pos_ == "VERB":
            t1, t2 = tokens[i], tokens[i + 1]
            label = f"{t1.text} {t2.text}"
            groups.append(f"({label} ({t1.text} {t1.pos_}) ({t2.text} {t2.pos_}))")
            seen.add(i)
            seen.add(i + 1)
            i += 2
        else:
            t = tokens[i]
            groups.append(f"({t.text} {t.pos_})")
            seen.add(i)
            i += 1

    return f"(S {' '.join(groups)})"


def _parse_bracket(s: str) -> dict[str, Any]:
    """Parse PTB bracket notation into nested dict.

    Supports multi-word labels like (The cat (The DET) (cat NOUN)):
    label is everything before the first '(' inside the node.
    """
    s = s.strip()
    if not s:
        return {"label": "", "children": []}

    if not s.startswith("("):
        return {"label": s, "children": []}

    inner = s[1:-1].strip()
    paren_idx = inner.find("(")

    if paren_idx == -1:
        # No nested brackets: (label leaf) or (label)
        space_idx = inner.find(" ")
        if space_idx == -1:
            return {"label": inner, "children": []}
        label = inner[:space_idx]
        leaf = inner[space_idx + 1:].strip()
        if leaf:
            return {"label": label, "children": [{"label": leaf, "children": []}]}
        return {"label": label, "children": []}

    # Label = everything before first '('
    label = inner[:paren_idx].strip()
    rest = inner[paren_idx:].strip()

    children: list[dict[str, Any]] = []
    i = 0
    while i < len(rest):
        ch = rest[i]
        if ch == "(":
            depth = 0
            j = i
            while j < len(rest):
                if rest[j] == "(":
                    depth += 1
                elif rest[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            children.append(_parse_bracket(rest[i: j + 1]))
            i = j + 1
        elif ch == " ":
            i += 1
        else:
            j = i
            while j < len(rest) and rest[j] not in (" ", ")"):
                j += 1
            word = rest[i:j]
            if word:
                children.append({"label": word, "children": []})
            i = j

    return {"label": label, "children": children}
