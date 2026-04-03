from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.modules.knowledge_base.schemas import (
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
)
from app.modules.knowledge_base.service import ingest_document, search_knowledge_base

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.post("/ingest", response_model=IngestResponse, summary="Ingest a markdown document")
def ingest_endpoint(
    payload: IngestRequest,
    session: Session = Depends(get_db_session),
) -> IngestResponse:
    return ingest_document(session, payload.filename, payload.content)


@router.post("/search", response_model=SearchResponse, summary="Search the knowledge base")
def search_endpoint(
    payload: SearchRequest,
    session: Session = Depends(get_db_session),
) -> SearchResponse:
    results = search_knowledge_base(session, payload.query, limit=payload.limit)
    return SearchResponse(results=results)
