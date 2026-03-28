from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.modules.conversations.service import (
    ConversationNotFoundError,
    delete_conversation,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.delete(
    "/{conversation_id}",
    status_code=204,
    summary="Delete a conversation",
)
def delete_conversation_endpoint(
    conversation_id: int,
    session: Session = Depends(get_db_session),
) -> None:
    """Delete a conversation and all its messages, intents, and handoff tasks."""
    try:
        delete_conversation(session, conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
