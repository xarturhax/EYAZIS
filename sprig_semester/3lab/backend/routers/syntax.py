"""Syntax router: sentences list, per-sentence analysis, export."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.document import Document
from backend.models.sentence import Sentence
from backend.models.syntax import SyntaxResult
from backend.services.quiz import get_syntax_quiz

router = APIRouter(prefix="/api/syntax", tags=["syntax"])


@router.get("/quiz")
async def syntax_quiz(
    doc_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await get_syntax_quiz(db, doc_id)


@router.get("/{doc_id}/sentences")
async def list_sentences(doc_id: int, db: AsyncSession = Depends(get_db)):
    """Return all sentences for a document (id, idx, text)."""
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stmt = (
        select(Sentence)
        .where(Sentence.doc_id == doc_id)
        .order_by(Sentence.idx)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": s.id, "idx": s.idx, "text": s.text} for s in rows]


@router.get("/sentence/{sent_id}")
async def get_sentence_syntax(sent_id: int, db: AsyncSession = Depends(get_db)):
    """Return full syntactic analysis for a single sentence."""
    sentence = await db.get(Sentence, sent_id)
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")

    stmt = select(SyntaxResult).where(SyntaxResult.sent_id == sent_id)
    syntax = (await db.execute(stmt)).scalar_one_or_none()
    if not syntax:
        raise HTTPException(status_code=404, detail="Syntax result not found")

    return {
        "sentence_id": sent_id,
        "text": sentence.text,
        "dependency": syntax.dep_tree,
        "constituency_bracket": syntax.const_tree,
        "constituency_tree": syntax.const_tree_json,
        "roles": syntax.roles,
    }


@router.get("/{doc_id}/roles")
async def list_roles(doc_id: int, db: AsyncSession = Depends(get_db)):
    """Return syntactic roles for every sentence in a document."""
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stmt = (
        select(Sentence, SyntaxResult)
        .join(SyntaxResult, SyntaxResult.sent_id == Sentence.id)
        .where(Sentence.doc_id == doc_id)
        .order_by(Sentence.idx)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "sentence_id": s.id,
            "idx": s.idx,
            "text": s.text,
            "roles": r.roles,
        }
        for s, r in rows
    ]


@router.get("/{doc_id}/export")
async def export_analysis(doc_id: int, fmt: str = "json", db: AsyncSession = Depends(get_db)):
    """Export full syntactic analysis of a document.

    fmt=json returns JSON file, fmt=txt returns bracket strings.
    """
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stmt = (
        select(Sentence, SyntaxResult)
        .join(SyntaxResult, SyntaxResult.sent_id == Sentence.id)
        .where(Sentence.doc_id == doc_id)
        .order_by(Sentence.idx)
    )
    rows = (await db.execute(stmt)).all()

    if fmt == "txt":
        lines = [f"[{s.idx}] {s.text}\n{r.const_tree}\n" for s, r in rows]
        content = "\n".join(lines)
        return Response(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="syntax_{doc_id}.txt"'},
        )

    # default JSON
    data = {
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "source_format": doc.source_format,
        },
        "sentences": [
            {
                "id": s.id,
                "idx": s.idx,
                "text": s.text,
                "dependency": r.dep_tree,
                "constituency_bracket": r.const_tree,
                "constituency_tree": r.const_tree_json,
                "roles": r.roles,
            }
            for s, r in rows
        ],
    }
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="syntax_{doc_id}.json"'},
    )
