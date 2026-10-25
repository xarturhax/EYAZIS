"""Documents router: upload, list, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, SessionLocal
from backend.models.document import Document
from backend.models.sentence import Sentence
from backend.services.ingest import ingest_stream
from backend.utils.file_parsers import SUPPORTED_FORMATS

router = APIRouter(prefix="/api/documents", tags=["documents"])

_ACCEPT = {f".{f}" if not f.startswith(".") else f for f in SUPPORTED_FORMATS}


@router.post("")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document. Returns an SSE stream with progress events."""
    import os

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ACCEPT:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported format '{ext}'. Accepted: {', '.join(sorted(_ACCEPT))}",
        )

    data = await file.read()
    filename = file.filename or "upload"

    async def generator():
        # Create a fresh session inside the generator so it stays alive
        # for the entire duration of the SSE stream (Depends lifecycle
        # would close the session before streaming finishes).
        async with SessionLocal() as db:
            async for chunk in ingest_stream(db, filename, data):
                yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.get("")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """Return all documents with sentence count."""
    stmt = (
        select(
            Document.id,
            Document.filename,
            Document.source_format,
            Document.created_at,
            func.count(Sentence.id).label("sentence_count"),
        )
        .outerjoin(Sentence, Sentence.doc_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "source_format": r.source_format,
            "created_at": r.created_at.isoformat(),
            "sentence_count": r.sentence_count,
        }
        for r in rows
    ]


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()
