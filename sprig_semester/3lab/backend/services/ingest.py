"""Document ingestion pipeline with SSE progress streaming."""
from __future__ import annotations

import asyncio
import json
import traceback
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.document import Document
from backend.models.sentence import Sentence
from backend.models.syntax import SyntaxResult
from backend.services.dependency import extract_dep_tree
from backend.services.constituency import extract_const_tree
from backend.services.roles import extract_roles
from backend.utils.file_parsers import parse_bytes
from backend.utils.nlp import get_nlp

# Limit text length to avoid OOM on very large documents
_MAX_CHARS = 100_000


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _run_nlp(text: str):
    """Run spaCy pipeline in a thread to avoid blocking the event loop.
    benepar is called separately per-sentence in constituency.py."""
    nlp = get_nlp()
    return nlp(text)


async def ingest_stream(
    db: AsyncSession, filename: str, file_bytes: bytes
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE strings.

    Events:
      status   – {"message": str}
      progress – {"current": int, "total": int}
      done     – {"doc_id": int}
      error    – {"message": str}
    """
    try:
        # --- 1. Parse file -----------------------------------------------
        yield _sse("status", {"message": "Parsing file…"})
        text, fmt = parse_bytes(file_bytes, filename)
        text = text[:_MAX_CHARS]

        # --- 2. Create document record ------------------------------------
        yield _sse("status", {"message": "Saving document…"})
        doc = Document(filename=filename, source_format=fmt, raw_text=text)
        db.add(doc)
        await db.flush()

        # --- 3. NLP pipeline (run in thread — spaCy/benepar block) --------
        yield _sse("status", {"message": "Running NLP pipeline…"})
        doc_nlp = await asyncio.to_thread(_run_nlp, text)
        sentences = [s for s in doc_nlp.sents if len(s.text.strip()) > 2]
        total = len(sentences)

        if total == 0:
            await db.rollback()
            yield _sse("error", {"message": "No sentences found in document."})
            return

        # --- 4. Process each sentence -------------------------------------
        for i, sent in enumerate(sentences):
            sentence = Sentence(doc_id=doc.id, idx=i, text=sent.text.strip())
            db.add(sentence)
            await db.flush()

            dep_tree = extract_dep_tree(sent)
            const_str, const_json = extract_const_tree(sent)
            roles = extract_roles(sent)

            syntax = SyntaxResult(
                sent_id=sentence.id,
                dep_tree=dep_tree,
                const_tree=const_str,
                const_tree_json=const_json,
                roles=roles,
            )
            db.add(syntax)

            yield _sse("progress", {"current": i + 1, "total": total})

        await db.commit()
        yield _sse("done", {"doc_id": doc.id})

    except Exception as exc:
        traceback.print_exc()  # full traceback in server console
        try:
            await db.rollback()
        except Exception:
            pass
        msg = repr(exc) if not str(exc) else str(exc)
        yield _sse("error", {"message": msg})
