"""
Unit tests for the routing logic in inbound_messages/service.py.

All external dependencies (DB, Gemini, Telegram) are mocked.
Tests verify that process_incoming_message correctly:
  - routes by classification result
  - updates conversation status
  - creates handoff_tasks for escalation intents
  - generates and sends replies
  - stores outbound messages
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.modules.inbound_messages.constants import (
    ConversationStatusCode,
    HandoffTaskType,
    IntentCode,
    Priority,
    RouteType,
)
from app.modules.inbound_messages.schemas import (
    ChannelPayload,
    ContactMatchKeysPayload,
    ContactPayload,
    ConversationPayload,
    EventPayload,
    MessagePayload,
    SourceMetadataPayload,
    UnifiedIncomingMessage,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _make_unified(
    text: str = "Hello",
    channel_code: str = "telegram",
    external_id: str = "12345",
    chat_id: str = "12345",
) -> UnifiedIncomingMessage:
    """Build a minimal UnifiedIncomingMessage for testing."""
    now = datetime.now(UTC)
    return UnifiedIncomingMessage(
        event=EventPayload(
            event_id="telegram:1",
            received_at=now,
            deduplication_key="telegram:1",
            source_system="telegram",
        ),
        channel=ChannelPayload(code=channel_code),
        contact=ContactPayload(
            external_id=external_id,
            display_name="Test User",
        ),
        conversation=ConversationPayload(external_chat_id=chat_id),
        message=MessagePayload(
            external_message_id="1",
            sent_at=now,
            message_type="text",
            normalized_text=text,
        ),
        contact_match_keys=ContactMatchKeysPayload(),
        source_metadata=SourceMetadataPayload(provider="telegram"),
    )


def _mock_contact_response(contact_id: int = 1, channel_id: int = 1):
    """Build a fake ResolveContactResponse."""
    return SimpleNamespace(
        found=True,
        contact=SimpleNamespace(id=contact_id),
        identity=SimpleNamespace(channel_id=channel_id),
        matched_by="external_id",
    )


def _mock_conversation(conv_id: int = 10):
    """Build a fake Conversation object."""
    return SimpleNamespace(id=conv_id, status_id=1, priority="normal", updated_at=None)


def _mock_message(msg_id: int = 100):
    """Build a fake Message with an id assigned after flush."""
    msg = MagicMock()
    msg.id = msg_id
    return msg


def _classification(
    intent: str = IntentCode.GREETING,
    route: str = RouteType.AUTO_REPLY,
    confidence: float = 0.95,
    entities: dict | None = None,
):
    from app.modules.inbound_messages.gemini import ClassificationResult
    return ClassificationResult(
        intent_code=intent,
        route_type=route,
        confidence=confidence,
        extracted_entities=entities or {},
    )


# All the patches we need for every test
_PATCHES = {
    "resolve_contact": "app.modules.inbound_messages.service.resolve_contact",
    "create_contact": "app.modules.inbound_messages.service.create_contact_from_identity",
    "get_or_create_conv": "app.modules.inbound_messages.service.get_or_create_conversation",
    "classify": "app.modules.inbound_messages.service.classify_message",
    "gen_reply": "app.modules.inbound_messages.service.generate_reply",
    "send_tg": "app.modules.inbound_messages.service.send_telegram_message",
    "build_history": "app.modules.inbound_messages.service._build_conversation_history",
    "build_contact_ctx": "app.modules.inbound_messages.service._build_contact_context",
    "upsert_appt_req": "app.modules.inbound_messages.service.upsert_appointment_request",
}


@pytest.fixture
def mocks():
    """Patch all external dependencies and return a dict of mocks."""
    with (
        patch(_PATCHES["resolve_contact"]) as m_resolve,
        patch(_PATCHES["create_contact"]) as m_create,
        patch(_PATCHES["get_or_create_conv"]) as m_conv,
        patch(_PATCHES["classify"]) as m_classify,
        patch(_PATCHES["gen_reply"]) as m_reply,
        patch(_PATCHES["send_tg"]) as m_send,
        patch(_PATCHES["build_history"]) as m_history,
        patch(_PATCHES["build_contact_ctx"]) as m_ctx,
        patch(_PATCHES["upsert_appt_req"]) as m_upsert,
    ):
        m_resolve.return_value = _mock_contact_response()
        m_conv.return_value = _mock_conversation()
        m_classify.return_value = _classification()
        m_reply.return_value = "Hello! How can I help?"
        m_history.return_value = []
        m_ctx.return_value = SimpleNamespace()
        # upsert_appointment_request returns (req, missing_fields)
        m_upsert.return_value = (SimpleNamespace(id=1), [])

        # Mock session
        session = MagicMock()
        session.flush.side_effect = lambda: None
        session.scalar.return_value = SimpleNamespace(id=1, code="classified")

        yield {
            "session": session,
            "resolve_contact": m_resolve,
            "create_contact": m_create,
            "get_or_create_conv": m_conv,
            "classify": m_classify,
            "gen_reply": m_reply,
            "send_tg": m_send,
            "build_history": m_history,
            "build_contact_ctx": m_ctx,
            "upsert_appt_req": m_upsert,
        }


# ---------------------------------------------------------------------------
# Auto-reply flow
# ---------------------------------------------------------------------------

class TestAutoReplyFlow:

    def test_greeting_sends_reply(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.GREETING, RouteType.AUTO_REPLY
        )
        mocks["gen_reply"].return_value = "Hello! How can I help?"

        process_incoming_message(mocks["session"], _make_unified("Hi"))

        mocks["gen_reply"].assert_called_once()
        mocks["send_tg"].assert_called_once_with(chat_id="12345", text="Hello! How can I help?")

    def test_reply_stored_as_outbound_message(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.GREETING, RouteType.AUTO_REPLY
        )
        mocks["gen_reply"].return_value = "Hi there!"

        process_incoming_message(mocks["session"], _make_unified("Hello"))

        # session.add should be called at least twice (inbound + outbound)
        add_calls = mocks["session"].add.call_args_list
        assert len(add_calls) >= 3  # Message, ConversationIntent, outbound Message

    def test_session_committed(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        process_incoming_message(mocks["session"], _make_unified("Hello"))

        mocks["session"].commit.assert_called_once()


# ---------------------------------------------------------------------------
# Handoff flows
# ---------------------------------------------------------------------------

class TestHandoffFlow:

    def test_emergency_creates_urgent_handoff_task(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.EMERGENCY, RouteType.HANDOFF_URGENT
        )

        process_incoming_message(mocks["session"], _make_unified("My tooth is killing me"))

        # Should add: inbound Message, ConversationIntent, HandoffTask, outbound Message
        add_calls = mocks["session"].add.call_args_list
        # HandoffTask should be among the added objects
        added_types = [type(c[0][0]).__name__ for c in add_calls]
        assert "HandoffTask" in added_types

    def test_complaint_creates_handoff_task(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.COMPLAINT_OR_NEGATIVE_FEEDBACK, RouteType.HANDOFF_ADMIN
        )

        process_incoming_message(mocks["session"], _make_unified("I'm very unhappy"))

        added_types = [type(c[0][0]).__name__ for c in mocks["session"].add.call_args_list]
        assert "HandoffTask" in added_types

    def test_handoff_still_generates_acknowledgement_reply(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.EMERGENCY, RouteType.HANDOFF_URGENT
        )
        mocks["gen_reply"].return_value = "We've flagged this as urgent."

        process_incoming_message(mocks["session"], _make_unified("Severe pain!"))

        mocks["gen_reply"].assert_called_once()
        mocks["send_tg"].assert_called_once()


# ---------------------------------------------------------------------------
# Auto-reply-and-collect flow
# ---------------------------------------------------------------------------

class TestAutoReplyAndCollect:

    def test_appointment_request_generates_reply(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.APPOINTMENT_REQUEST, RouteType.AUTO_REPLY_AND_COLLECT,
            entities={"service": "cleaning"},
        )
        mocks["gen_reply"].return_value = "Great, what date works for you?"

        process_incoming_message(mocks["session"], _make_unified("I want a cleaning"))

        mocks["gen_reply"].assert_called_once()
        mocks["send_tg"].assert_called_once()

    def test_no_handoff_task_for_auto_reply(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.APPOINTMENT_REQUEST, RouteType.AUTO_REPLY_AND_COLLECT,
        )

        process_incoming_message(mocks["session"], _make_unified("Book me"))

        added_types = [type(c[0][0]).__name__ for c in mocks["session"].add.call_args_list]
        assert "HandoffTask" not in added_types


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_telegram_send_failure_does_not_crash(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message
        from app.modules.inbound_messages.telegram_client import TelegramClientError

        mocks["classify"].return_value = _classification(
            IntentCode.GREETING, RouteType.AUTO_REPLY
        )
        mocks["send_tg"].side_effect = TelegramClientError("timeout")

        # Should not raise
        process_incoming_message(mocks["session"], _make_unified("Hello"))

        mocks["session"].commit.assert_called_once()

    def test_none_reply_sends_fallback_and_escalates(self, mocks):
        """When generate_reply() returns None on an AUTO_REPLY route, the bot must
        send the static fallback message and create an admin handoff task instead
        of silently dropping the conversation."""
        from app.modules.inbound_messages.service import (
            _FALLBACK_REPLY,
            process_incoming_message,
        )

        mocks["classify"].return_value = _classification(
            IntentCode.GREETING, RouteType.AUTO_REPLY
        )
        mocks["gen_reply"].return_value = None

        process_incoming_message(mocks["session"], _make_unified("Hello"))

        # Fallback message must be sent
        mocks["send_tg"].assert_called_once_with(chat_id="12345", text=_FALLBACK_REPLY)

        # A HandoffTask must have been added to the session
        added_objects = [
            call_args[0][0]
            for call_args in mocks["session"].add.call_args_list
        ]
        from app.db.models import HandoffTask
        handoff_tasks = [o for o in added_objects if isinstance(o, HandoffTask)]
        assert handoff_tasks, "Expected a HandoffTask to be created when reply is None"
        task = handoff_tasks[-1]
        assert task.task_type == HandoffTaskType.ADMIN_FOLLOWUP

    def test_new_contact_is_created_when_not_found(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        not_found = SimpleNamespace(
            found=False,
            contact=SimpleNamespace(id=None),
            identity=SimpleNamespace(channel_id=None),
            matched_by=None,
        )
        created = _mock_contact_response(contact_id=42, channel_id=2)

        mocks["resolve_contact"].return_value = not_found
        mocks["create_contact"].return_value = created

        process_incoming_message(mocks["session"], _make_unified("Hello"))

        mocks["create_contact"].assert_called_once()

    def test_silent_ignore_skips_reply(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.NON_RELEVANT_MESSAGE, RouteType.SILENT_IGNORE
        )

        process_incoming_message(mocks["session"], _make_unified("Buy cheap pills"))

        mocks["gen_reply"].assert_not_called()
        mocks["send_tg"].assert_not_called()


# ---------------------------------------------------------------------------
# Booking flow integration
# ---------------------------------------------------------------------------

class TestBookingFlow:

    def test_appointment_request_calls_upsert(self, mocks):
        """For appointment_request intent, upsert_appointment_request must be called."""
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.APPOINTMENT_REQUEST,
            RouteType.AUTO_REPLY_AND_COLLECT,
            entities={"service": "cleaning"},
        )

        process_incoming_message(mocks["session"], _make_unified("I want a cleaning"))

        mocks["upsert_appt_req"].assert_called_once()

    def test_provide_booking_data_calls_upsert(self, mocks):
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.PROVIDE_BOOKING_DATA,
            RouteType.AUTO_REPLY_AND_COLLECT,
            entities={"name": "Anna", "phone": "+44123"},
        )

        process_incoming_message(mocks["session"], _make_unified("My name is Anna, phone +44123"))

        mocks["upsert_appt_req"].assert_called_once()

    def test_non_booking_intent_does_not_call_upsert(self, mocks):
        """Greeting should NOT trigger the booking flow."""
        from app.modules.inbound_messages.service import process_incoming_message

        mocks["classify"].return_value = _classification(
            IntentCode.GREETING, RouteType.AUTO_REPLY
        )

        process_incoming_message(mocks["session"], _make_unified("Hello"))

        mocks["upsert_appt_req"].assert_not_called()

    def test_missing_fields_passed_to_generate_reply(self, mocks):
        """missing_fields returned by upsert should reach generate_reply."""
        from app.modules.inbound_messages.service import process_incoming_message
        from types import SimpleNamespace

        mocks["classify"].return_value = _classification(
            IntentCode.APPOINTMENT_REQUEST,
            RouteType.AUTO_REPLY_AND_COLLECT,
            entities={"service": "cleaning"},
        )
        mocks["upsert_appt_req"].return_value = (
            SimpleNamespace(id=1),
            ["date_preference", "phone"],
        )

        process_incoming_message(mocks["session"], _make_unified("I want a cleaning"))

        _, gen_kwargs = mocks["gen_reply"].call_args
        assert gen_kwargs.get("missing_fields") == ["date_preference", "phone"]

    def test_empty_missing_fields_passes_none_to_generate_reply(self, mocks):
        """When all booking fields are collected, generate_reply gets missing_fields=None."""
        from app.modules.inbound_messages.service import process_incoming_message
        from types import SimpleNamespace

        mocks["classify"].return_value = _classification(
            IntentCode.APPOINTMENT_REQUEST,
            RouteType.AUTO_REPLY_AND_COLLECT,
        )
        mocks["upsert_appt_req"].return_value = (SimpleNamespace(id=1), [])

        process_incoming_message(mocks["session"], _make_unified("Book me"))

        _, gen_kwargs = mocks["gen_reply"].call_args
        assert gen_kwargs.get("missing_fields") is None
