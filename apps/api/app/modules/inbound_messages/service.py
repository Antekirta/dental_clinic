"""
Inbound message orchestration — the main pipeline.

process_incoming_message() is the single entry point for every incoming message.
It owns the DB transaction boundary (commit); all helpers use flush().

Two-call Gemini flow:
  1. classify_message() → intent + entities
  2. Python routing logic (update conversation status, create handoff_task if needed)
  3. generate_reply() → reply text (only for auto_reply / auto_reply_and_collect)
  4. Send reply via Telegram
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ConversationIntent,
    ConversationStatus,
    HandoffTask,
    Message,
)
from app.modules.contacts.schemas import (
    CreateContactFromChannelRequest,
    ResolveChannelPayload,
    ResolveContactMatchKeysPayload,
    ResolveContactPayload,
    ResolveContactRequest,
)
from app.modules.contacts.service import create_contact_from_identity, resolve_contact
from app.modules.conversations.service import get_or_create_conversation
from app.modules.appointment_requests.service import upsert_appointment_request
from app.modules.inbound_messages.constants import (
    BOOKING_INTENTS,
    ConversationStatusCode,
    HandoffTaskType,
    IntentCode,
    Priority,
    RouteType,
)
from app.modules.inbound_messages.gemini import (
    ClassificationResult,
    ContactContext,
    ConversationTurn,
    classify_message,
    generate_reply,
)
from app.modules.inbound_messages.schemas import UnifiedIncomingMessage
from app.modules.inbound_messages.telegram_client import (
    TelegramClientError,
    send_telegram_message,
)

logger = logging.getLogger(__name__)

_SUPPORTED_MESSAGE_TYPES = {"text", "image", "file", "audio"}

# Maps intent → handoff_task type for intents that require escalation.
_INTENT_HANDOFF_TYPE: dict[str, str] = {
    IntentCode.EMERGENCY: HandoffTaskType.URGENT_CASE,
    IntentCode.INSURANCE_OR_DOCUMENTS: HandoffTaskType.DOCUMENT_REQUEST,
    IntentCode.RESCHEDULE_APPOINTMENT: HandoffTaskType.MANUAL_RESCHEDULE,
    IntentCode.CANCEL_APPOINTMENT: HandoffTaskType.MANUAL_CANCEL,
    IntentCode.CONTACT_REQUEST: HandoffTaskType.CALLBACK_REQUEST,
    IntentCode.COMPLAINT_OR_NEGATIVE_FEEDBACK: HandoffTaskType.COMPLAINT,
    IntentCode.POST_VISIT_FOLLOWUP: HandoffTaskType.POST_VISIT,
    IntentCode.TREATMENT_PLAN_QUESTION: HandoffTaskType.ADMIN_FOLLOWUP,
    IntentCode.RESULTS_OR_RECORDS_REQUEST: HandoffTaskType.DOCUMENT_REQUEST,
    IntentCode.APPOINTMENT_DETAILS: HandoffTaskType.ADMIN_FOLLOWUP,
}

# Maps intent → priority override.
_INTENT_PRIORITY: dict[str, str] = {
    IntentCode.EMERGENCY: Priority.URGENT,
    IntentCode.COMPLAINT_OR_NEGATIVE_FEEDBACK: Priority.HIGH,
    IntentCode.POST_VISIT_FOLLOWUP: Priority.HIGH,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_conversation_history(
    session: Session,
    conversation_id: int,
    limit: int = 20,
) -> list[ConversationTurn]:
    """Load recent messages for Gemini context."""
    messages = session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).all()

    turns: list[ConversationTurn] = []
    for msg in reversed(messages):  # oldest first
        turns.append(ConversationTurn(role=msg.sender_type, text=msg.message_text or ""))
    return turns


def _build_contact_context(
    session: Session,
    contact_id: int,
) -> ContactContext:
    """Build ContactContext from the DB contact record."""
    from app.db.models import Contact

    contact = session.get(Contact, contact_id)
    if contact is None:
        return ContactContext()

    return ContactContext(
        name=contact.full_name,
        phone=contact.phone,
        email=contact.email,
        is_existing_patient=contact.lifecycle_stage in ("patient", "booked"),
    )


def _update_conversation_status(
    session: Session,
    conversation: Any,
    status_code: str,
) -> None:
    """Set conversation status by code. Silently skips if code not found."""
    status = session.scalar(
        select(ConversationStatus).where(ConversationStatus.code == status_code)
    )
    if status is not None:
        conversation.status_id = status.id
        conversation.updated_at = datetime.now(UTC)
        session.flush()


def _create_handoff_task(
    session: Session,
    conversation_id: int,
    task_type: str,
    priority: str,
    summary: str,
) -> None:
    """Create a handoff_task for admin/urgent escalation."""
    now = datetime.now(UTC)
    task = HandoffTask(
        conversation_id=conversation_id,
        task_type=task_type,
        priority=priority,
        status="new",
        payload={"summary": summary},
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.flush()
    logger.info(
        "Created handoff_task type=%s priority=%s for conversation=%s",
        task_type,
        priority,
        conversation_id,
    )


def _load_reference_data(
    session: Session,
    intent_code: str,
) -> dict[str, Any] | None:
    """
    Load reference data relevant to the intent for reply generation.

    Only loads data that Gemini needs to compose a helpful answer.
    Returns None if no special data is needed.
    """
    if intent_code == IntentCode.CLINIC_HOURS:
        return _load_branch_hours(session)
    if intent_code == IntentCode.LOCATION_QUESTION:
        return _load_branch_location(session)
    if intent_code == IntentCode.PRICE_QUESTION:
        return _load_service_prices(session)
    return None


def _load_branch_hours(session: Session) -> dict[str, Any]:
    """Load working hours for the first active branch."""
    from app.db.models import Branch, BranchHour

    branch = session.scalar(select(Branch).where(Branch.is_active.is_(True)).limit(1))
    if branch is None:
        return {"clinic_hours": "Working hours information is temporarily unavailable."}

    hours = session.scalars(
        select(BranchHour)
        .where(BranchHour.branch_id == branch.id)
        .order_by(BranchHour.weekday)
    ).all()

    day_names = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    lines = []
    for h in hours:
        day = day_names.get(h.weekday, str(h.weekday))
        if not h.is_active:
            lines.append(f"{day}: closed")
        else:
            lines.append(f"{day}: {h.open_time:%H:%M}–{h.close_time:%H:%M}")

    return {"clinic_name": branch.name, "clinic_hours": "\n".join(lines) if lines else "Not specified"}


def _load_branch_location(session: Session) -> dict[str, Any]:
    """Load address and directions for the first active branch."""
    from app.db.models import Branch

    branch = session.scalar(select(Branch).where(Branch.is_active.is_(True)).limit(1))
    if branch is None:
        return {"location": "Location information is temporarily unavailable."}

    data: dict[str, Any] = {"clinic_name": branch.name}
    if branch.address:
        data["address"] = branch.address
    if branch.parking_info:
        data["parking"] = branch.parking_info
    if branch.directions:
        data["directions"] = branch.directions
    if branch.map_url:
        data["map_link"] = branch.map_url
    return data


def _load_service_prices(session: Session) -> dict[str, Any]:
    """Load a summary of service prices."""
    from app.db.models import Service

    services = session.scalars(
        select(Service).where(Service.is_active.is_(True)).limit(30)
    ).all()

    if not services:
        return {"prices": "Price list is temporarily unavailable. Please contact the administrator."}

    lines = []
    for s in services:
        price_str = f"£{s.base_price}" if s.base_price else "on request"
        lines.append(f"- {s.name}: {price_str}")
    return {"service_prices": "\n".join(lines)}


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def process_incoming_message(
    session: Session,
    unified: UnifiedIncomingMessage,
) -> None:
    """
    Main orchestration entry point for every inbound message.

    Steps:
      1. Resolve or create contact
      2. Get or create conversation
      3. Store the inbound message
      4. Build context and classify via Gemini (Call 1)
      5. Store conversation_intent record
      6. Python routing logic (update status, create handoff_task)
      7. Generate reply via Gemini (Call 2) — only for auto_reply routes
      8. Send reply via Telegram and store outbound message
      9. Commit the transaction

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

    # --- 3. Store inbound message ---
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

    # --- 4. Classify via Gemini (Call 1) ---
    history = _build_conversation_history(session, conversation.id)
    contact_ctx = _build_contact_context(session, contact_id)

    classification: ClassificationResult = classify_message(
        text=unified.message.normalized_text or "",
        conversation_history=history,
        contact_context=contact_ctx,
    )

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
        "Classified intent=%s route=%s confidence=%.2f for message id=%s",
        classification.intent_code,
        classification.route_type,
        classification.confidence,
        message.id,
    )

    # --- 5.5. Appointment booking flow ---
    # For booking-related intents, create/update the appointment_request and
    # compute which fields are still missing so Gemini can ask for them.
    missing_fields: list[str] = []

    if (
        classification.intent_code in BOOKING_INTENTS
        and route == RouteType.AUTO_REPLY_AND_COLLECT
    ):
        _, missing_fields = upsert_appointment_request(
            session,
            contact_id=contact_id,
            conversation_id=conversation.id,
            channel_id=channel_id,
            source_message_id=message.id,
            extracted_entities=classification.extracted_entities,
        )
        logger.info(
            "Booking flow: conversation=%s missing_fields=%s",
            conversation.id,
            missing_fields,
        )

    # --- 6. Python routing logic ---
    route = classification.route_type

    # Update conversation status based on route
    if route == RouteType.HANDOFF_URGENT:
        _update_conversation_status(session, conversation, ConversationStatusCode.URGENT_HANDOFF)
        conversation.priority = Priority.URGENT
        session.flush()
    elif route == RouteType.HANDOFF_ADMIN:
        _update_conversation_status(session, conversation, ConversationStatusCode.WAITING_FOR_ADMIN)
        priority_override = _INTENT_PRIORITY.get(classification.intent_code)
        if priority_override:
            conversation.priority = priority_override
            session.flush()
    elif route in (RouteType.AUTO_REPLY, RouteType.AUTO_REPLY_AND_COLLECT):
        if missing_fields:
            # Still collecting data for a booking.
            _update_conversation_status(
                session, conversation, ConversationStatusCode.WAITING_FOR_PATIENT_DATA
            )
        elif classification.intent_code in BOOKING_INTENTS:
            # All booking data collected — ready for admin to confirm.
            _update_conversation_status(
                session, conversation, ConversationStatusCode.BOOKING_REQUEST_CREATED
            )
        else:
            _update_conversation_status(
                session, conversation, ConversationStatusCode.CLASSIFIED
            )

    # Create handoff_task if needed
    handoff_type = _INTENT_HANDOFF_TYPE.get(classification.intent_code)
    if handoff_type and route in (RouteType.HANDOFF_ADMIN, RouteType.HANDOFF_URGENT):
        task_priority = _INTENT_PRIORITY.get(classification.intent_code, Priority.NORMAL)
        summary = (
            f"Intent: {classification.intent_code}. "
            f"Message: {(unified.message.normalized_text or '')[:200]}"
        )
        _create_handoff_task(
            session,
            conversation_id=conversation.id,
            task_type=handoff_type,
            priority=task_priority,
            summary=summary,
        )

    # --- 7. Generate reply via Gemini (Call 2) ---
    reply_text: str | None = None

    if route in (RouteType.AUTO_REPLY, RouteType.AUTO_REPLY_AND_COLLECT):
        reference_data = _load_reference_data(session, classification.intent_code)

        # For handoff routes that also need a reply (e.g., emergency acknowledgement),
        # we still generate but with a different tone set by the intent context.
        reply_text = generate_reply(
            intent_code=classification.intent_code,
            extracted_entities=classification.extracted_entities,
            conversation_history=history,
            reference_data=reference_data,
            missing_fields=missing_fields or None,
        )
    elif route in (RouteType.HANDOFF_ADMIN, RouteType.HANDOFF_URGENT):
        # For handoff routes, generate an acknowledgement reply
        reply_text = generate_reply(
            intent_code=classification.intent_code,
            extracted_entities=classification.extracted_entities,
            conversation_history=history,
            reference_data=None,
        )

    # --- 8. Send reply and store outbound message ---
    if reply_text:
        try:
            send_telegram_message(
                chat_id=unified.conversation.external_chat_id,
                text=reply_text,
            )
        except TelegramClientError as exc:
            logger.error("Failed to send Telegram reply: %s", exc)
            reply_text = None  # Don't store a message we couldn't send

        if reply_text:
            outbound = Message(
                conversation_id=conversation.id,
                direction="outbound",
                sender_type="bot",
                message_text=reply_text,
                message_type="text",
                sent_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            )
            session.add(outbound)
            session.flush()

            logger.info(
                "Sent and stored bot reply for conversation=%s intent=%s",
                conversation.id,
                classification.intent_code,
            )
    else:
        logger.info(
            "No reply generated for route=%s intent=%s",
            route,
            classification.intent_code,
        )

    # --- 9. Commit ---
    session.commit()
