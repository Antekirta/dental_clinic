from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import ConversationIntent, Message
from app.modules.contacts.schemas import (
    CreateContactFromChannelRequest,
    ResolveChannelPayload,
    ResolveContactMatchKeysPayload,
    ResolveContactPayload,
    ResolveContactRequest,
)
from app.modules.contacts.service import create_contact_from_identity, resolve_contact
from app.modules.conversations.service import get_or_create_conversation
from app.modules.inbound_messages.schemas import UnifiedIncomingMessage
from app.modules.inbound_messages.telegram_client import (
    TelegramClientError,
    send_telegram_message,
)

logger = logging.getLogger(__name__)

_SUPPORTED_MESSAGE_TYPES = {"text", "image", "file", "audio"}


@dataclass
class _ClassificationResult:
    intent_code: str
    route_type: str
    confidence: float
    extracted_entities: dict = field(default_factory=dict)
    suggested_reply: str | None = None


def _classify_message(unified: UnifiedIncomingMessage) -> _ClassificationResult:
    """
    Stub classifier — always returns a greeting intent.

    Replace this with a real Gemini call in the next iteration.
    The real implementation will pass conversation history + normalized_text
    to Gemini and parse a structured JSON response back.
    """
    return _ClassificationResult(
        intent_code="greeting",
        route_type="auto_reply",
        confidence=1.0,
        extracted_entities={},
        suggested_reply=(
            "Здравствуйте! Вы написали в BrightSmile Dental Clinic. "
            "Чем можем помочь?"
        ),
    )


def process_incoming_message(
    session: Session,
    unified: UnifiedIncomingMessage,
) -> None:
    """
    Main orchestration entry point for every inbound message.

    Steps:
      1. Resolve or create contact
      2. Get or create conversation
      3. Store the message
      4. Classify intent (stub: always returns greeting)
      5. Store conversation_intent record
      6. Route by route_type (auto_reply → send reply; others → log stub)
      7. Commit the transaction

    This function owns the single transaction boundary for the whole request.
    All upstream helpers call flush(), not commit().
    """

    # --- 1. Resolve or create contact ---
    resolve_request = ResolveContactRequest(
        channel=ResolveChannelPayload(code=unified.channel.code),
        contact=ResolveContactPayload(
            external_id=unified.contact.external_id,
            username=unified.contact.username,
            display_name=unified.contact.display_name,
            phone=unified.contact.phone,
            email=unified.contact.email,
        ),
        contact_match_keys=ResolveContactMatchKeysPayload(
            phone=unified.contact_match_keys.phone,
            email=unified.contact_match_keys.email,
        ),
    )

    contact_response = resolve_contact(session, resolve_request)

    if not contact_response.found:
        contact_response = create_contact_from_identity(
            session,
            CreateContactFromChannelRequest(
                channel_code=unified.channel.code,
                external_id=unified.contact.external_id,
                username=unified.contact.username,
                display_name=unified.contact.display_name,
                phone=unified.contact.phone,
                email=unified.contact.email,
            ),
        )

    contact_id = contact_response.contact.id
    channel_id = contact_response.identity.channel_id

    logger.info(
        "Contact resolved: id=%s matched_by=%s",
        contact_id,
        contact_response.matched_by,
    )

    # --- 2. Get or create conversation ---
    conversation = get_or_create_conversation(
        session,
        contact_id=contact_id,
        channel_id=channel_id,
        external_chat_id=unified.conversation.external_chat_id,
    )

    # --- 3. Store message ---
    message_type = unified.message.message_type
    if message_type not in _SUPPORTED_MESSAGE_TYPES:
        message_type = "text"

    now = datetime.now(UTC)
    message = Message(
        conversation_id=conversation.id,
        direction="inbound",
        sender_type="contact",
        message_text=unified.message.normalized_text,
        message_type=message_type,
        external_message_id=unified.message.external_message_id,
        sent_at=unified.message.sent_at,
        created_at=now,
    )
    session.add(message)
    session.flush()

    logger.info(
        "Stored message id=%s in conversation id=%s",
        message.id,
        conversation.id,
    )

    # --- 4. Classify intent ---
    classification = _classify_message(unified)

    # --- 5. Store conversation_intent ---
    intent = ConversationIntent(
        conversation_id=conversation.id,
        message_id=message.id,
        intent_code=classification.intent_code,
        route_type=classification.route_type,
        confidence=classification.confidence,
        is_primary=True,
        extracted_entities=classification.extracted_entities or None,
        created_at=now,
    )
    session.add(intent)
    session.flush()

    logger.info(
        "Classified intent=%s route=%s for message id=%s",
        classification.intent_code,
        classification.route_type,
        message.id,
    )

    # --- 6. Route ---
    if classification.route_type == "auto_reply" and classification.suggested_reply:
        try:
            send_telegram_message(
                chat_id=unified.conversation.external_chat_id,
                text=classification.suggested_reply,
            )
        except TelegramClientError as exc:
            # Log but don't re-raise — the message is already stored.
            # A failed reply is recoverable; a failed commit is not.
            logger.error("Failed to send Telegram reply: %s", exc)
    else:
        logger.info(
            "Route '%s' — no auto-reply sent (not yet implemented)",
            classification.route_type,
        )

    # --- 7. Commit ---
    session.commit()
