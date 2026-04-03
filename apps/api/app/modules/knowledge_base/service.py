"""
Knowledge base ingestion and retrieval service.

Ingestion pipeline:
  1. Chunk markdown content by headings
  2. Embed each chunk via Gemini text-embedding-004
  3. Store KbDocument + KbChunk rows (with FTS tsvector and pgvector embedding)

Search pipeline:
  1. Embed the query
  2. FTS leg: top-20 by ts_rank
  3. Semantic leg: top-20 by cosine distance
  4. Merge with Reciprocal Rank Fusion, return top-N
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.gemini_client import get_gemini_client
from app.db.models import KbDocument
from app.modules.knowledge_base.schemas import IngestResponse, SearchResult

logger = logging.getLogger(__name__)

# Rough character limit per chunk before splitting on paragraphs.
# ~2000 chars ≈ 500 tokens at average English word length.
_MAX_CHUNK_CHARS = 2000

# RRF constant — standard value, controls how much early ranks dominate.
_RRF_K = 60


# ---------------------------------------------------------------------------
# Public: ingest
# ---------------------------------------------------------------------------
def ingest_document(session: Session, filename: str, content: str) -> IngestResponse:
    """
    Ingest a markdown document into the knowledge base.

    Idempotent: if a document with the same SHA-256 content hash already
    exists, returns the existing document's metadata without re-processing.
    """
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    existing = (
        session.query(KbDocument)
        .filter(KbDocument.content_hash == content_hash)
        .first()
    )
    if existing is not None:
        logger.info(
            "Document '%s' already ingested (id=%d, hash=%s), skipping.",
            filename,
            existing.id,
            content_hash,
        )
        return IngestResponse(
            document_id=existing.id,
            chunk_count=existing.chunk_count,
            status=existing.status,
        )

    # Create the document record (status=processing)
    doc = KbDocument(
        filename=filename,
        content_hash=content_hash,
        file_size_bytes=len(content.encode()),
        chunk_count=0,
        status="processing",
    )
    session.add(doc)
    session.flush()  # get doc.id

    try:
        chunks = _chunk_markdown(content)

        chunk_texts = [text_content for _, _, text_content in chunks]
        embeddings = _embed_texts(chunk_texts)

        for (chunk_index, heading_path, chunk_text), embedding in zip(chunks, embeddings):
            token_count = len(chunk_text.split())
            session.execute(
                text(
                    """
                    INSERT INTO kb_chunks
                        (document_id, chunk_index, heading_path, content,
                         token_count, content_tsv, embedding, metadata)
                    VALUES
                        (:doc_id, :chunk_index, :heading_path, :content,
                         :token_count, to_tsvector('english', :content),
                         CAST(:embedding AS vector), '{}'::jsonb)
                    """
                ),
                {
                    "doc_id": doc.id,
                    "chunk_index": chunk_index,
                    "heading_path": heading_path,
                    "content": chunk_text,
                    "token_count": token_count,
                    "embedding": str(embedding),
                },
            )

        doc.chunk_count = len(chunks)
        doc.status = "ready"
        session.flush()

        logger.info(
            "Ingested document '%s' (id=%d) with %d chunks.",
            filename,
            doc.id,
            len(chunks),
        )
        return IngestResponse(
            document_id=doc.id,
            chunk_count=len(chunks),
            status="ready",
        )

    except Exception:
        logger.exception("Failed to ingest document '%s'", filename)
        doc.status = "error"
        doc.error_message = "Ingestion failed — see server logs."
        session.flush()
        return IngestResponse(
            document_id=doc.id or 0,
            chunk_count=0,
            status="error",
        )


# ---------------------------------------------------------------------------
# Public: search
# ---------------------------------------------------------------------------
def search_knowledge_base(
    session: Session,
    query_text: str,
    limit: int = 5,
) -> list[SearchResult]:
    """
    Hybrid search over the knowledge base using FTS + semantic similarity.

    Results from both legs are merged with Reciprocal Rank Fusion and the
    top-N deduplicated results are returned.
    """
    query_embedding = _embed_texts([query_text])[0]

    fts_rows = _fts_search(session, query_text)
    semantic_rows = _semantic_search(session, query_embedding)

    merged = _rrf_merge(fts_rows, semantic_rows, limit=limit)
    return merged


# ---------------------------------------------------------------------------
# Internal: chunking
# ---------------------------------------------------------------------------
def _chunk_markdown(content: str) -> list[tuple[int, str | None, str]]:
    """
    Split markdown content into chunks by headings (## and ###).

    Returns a list of (chunk_index, heading_path, text) tuples.

    Each heading section becomes one chunk. Sections longer than
    _MAX_CHUNK_CHARS are split further at double-newline paragraph
    boundaries.
    """
    # Pattern matches lines starting with ## or ### (not deeper)
    heading_pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

    sections: list[tuple[str | None, str]] = []

    matches = list(heading_pattern.finditer(content))

    if not matches:
        # No headings — treat entire document as one chunk
        sections.append((None, content.strip()))
    else:
        # Text before first heading
        preamble = content[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))

        h2_heading: str | None = None

        for i, match in enumerate(matches):
            level = len(match.group(1))  # 2 or 3
            heading_text = match.group(2).strip()

            # Determine section body: text until next heading
            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[body_start:body_end].strip()

            # Build heading path
            if level == 2:
                h2_heading = heading_text
                heading_path = heading_text
            else:
                heading_path = f"{h2_heading} > {heading_text}" if h2_heading else heading_text

            full_text = f"{heading_text}\n\n{body}" if body else heading_text
            sections.append((heading_path, full_text))

    # Split oversized sections at paragraph boundaries
    result: list[tuple[int, str | None, str]] = []
    chunk_index = 0

    for heading_path, section_text in sections:
        if len(section_text) <= _MAX_CHUNK_CHARS:
            result.append((chunk_index, heading_path, section_text))
            chunk_index += 1
        else:
            paragraphs = re.split(r"\n\n+", section_text)
            current_parts: list[str] = []
            current_len = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if current_len + len(para) > _MAX_CHUNK_CHARS and current_parts:
                    result.append((chunk_index, heading_path, "\n\n".join(current_parts)))
                    chunk_index += 1
                    current_parts = [para]
                    current_len = len(para)
                else:
                    current_parts.append(para)
                    current_len += len(para)

            if current_parts:
                result.append((chunk_index, heading_path, "\n\n".join(current_parts)))
                chunk_index += 1

    return result


# ---------------------------------------------------------------------------
# Internal: embeddings
# ---------------------------------------------------------------------------
def _embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using Gemini text-embedding-004.
    Returns a parallel list of 768-dimensional float vectors.
    """
    response = get_gemini_client().models.embed_content(
        model=settings.gemini_embedding_model,
        contents=texts,
    )
    return [emb.values for emb in response.embeddings]


# ---------------------------------------------------------------------------
# Internal: search legs
# ---------------------------------------------------------------------------
def _fts_search(session: Session, query: str) -> list[dict[str, Any]]:
    """Full-text search leg. Returns up to 20 rows ranked by ts_rank."""
    rows = session.execute(
        text(
            """
            SELECT
                c.id          AS chunk_id,
                d.filename    AS document_filename,
                c.heading_path,
                c.content,
                ts_rank(c.content_tsv, plainto_tsquery('english', :query)) AS rank
            FROM kb_chunks c
            JOIN kb_documents d ON d.id = c.document_id
            WHERE c.content_tsv @@ plainto_tsquery('english', :query)
              AND d.status = 'ready'
            ORDER BY rank DESC
            LIMIT 20
            """
        ),
        {"query": query},
    ).mappings().all()

    return [dict(r) for r in rows]


def _semantic_search(session: Session, embedding: list[float]) -> list[dict[str, Any]]:
    """Semantic search leg. Returns up to 20 rows ranked by cosine distance."""
    rows = session.execute(
        text(
            """
            SELECT
                c.id          AS chunk_id,
                d.filename    AS document_filename,
                c.heading_path,
                c.content,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM kb_chunks c
            JOIN kb_documents d ON d.id = c.document_id
            WHERE d.status = 'ready'
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT 20
            """
        ),
        {"embedding": str(embedding)},
    ).mappings().all()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Internal: RRF merge
# ---------------------------------------------------------------------------
def _rrf_merge(
    fts_rows: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
    limit: int,
) -> list[SearchResult]:
    """
    Merge FTS and semantic results with Reciprocal Rank Fusion.

    score(chunk) = 1 / (k + rank_fts) + 1 / (k + rank_semantic)

    Chunks appearing in only one leg still get a score from that leg alone.
    """
    scores: dict[int, float] = {}
    chunk_data: dict[int, dict[str, Any]] = {}

    for rank, row in enumerate(fts_rows):
        cid = row["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank)
        chunk_data[cid] = row

    for rank, row in enumerate(semantic_rows):
        cid = row["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank)
        if cid not in chunk_data:
            chunk_data[cid] = row

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    return [
        SearchResult(
            chunk_id=cid,
            document_filename=chunk_data[cid]["document_filename"],
            heading_path=chunk_data[cid]["heading_path"],
            content=chunk_data[cid]["content"],
            score=round(score, 6),
        )
        for cid, score in ranked
    ]
