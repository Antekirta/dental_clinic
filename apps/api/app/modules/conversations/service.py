from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, ConversationStatus

logger = logging.getLogger(__name__)


class ConversationStatusNotFoundError(Exception):
    """Raised when a required conversation_status code is missing from the DB."""


def get_or_create_conversation(
    session: Session,
    contact_id: int,
    channel_id: int,
    external_chat_id: str,
) -> Conversation:
    """
    Return an existing Conversation or create a new one.

    Looks up by (contact_id, channel_id, external_chat_id).
    New conversations start with status 'new_incoming'.

    Does NOT commit — the caller owns the transaction boundary.
    """
    existing = session.scalar(
        select(Conversation)
        .where(
            Conversation.contact_id == contact_id,
            Conversation.channel_id == channel_id,
            Conversation.external_chat_id == external_chat_id,
        )
        .limit(1)
    )
    if existing is not None:
        return existing

    status = session.scalar(
        select(ConversationStatus).where(ConversationStatus.code == "new_incoming")
    )
    if status is None:
        raise ConversationStatusNotFoundError(
            "ConversationStatus 'new_incoming' not found in DB. Run seed_db.py first."
        )

    now = datetime.now(UTC)
    conversation = Conversation(
        contact_id=contact_id,
        channel_id=channel_id,
        external_chat_id=external_chat_id,
        status_id=status.id,
        handoff_status="none",
        priority="normal",
        is_spam=False,
        created_at=now,
        updated_at=now,
    )
    session.add(conversation)
    session.flush()

    logger.info(
        "Created conversation id=%s for contact_id=%s channel_id=%s",
        conversation.id,
        contact_id,
        channel_id,
    )
    return conversation
