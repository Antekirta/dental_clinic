"""
Unit tests for the Gemini AI integration (gemini.py).

All Gemini API calls are mocked — no real network requests.
Tests cover: successful classification, fallback on error, entity extraction,
unknown intent validation, reply generation, and edge cases.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.modules.inbound_messages.constants import IntentCode, RouteType, INTENT_ROUTE_MAP


# ---------------------------------------------------------------------------
# We must patch the module-level SDK init before importing gemini.py,
# because it creates a genai.Client() on first use.
# ---------------------------------------------------------------------------

_mock_client = MagicMock()


@pytest.fixture(autouse=True)
def _patch_genai(monkeypatch):
    """Prevent real Gemini SDK initialisation on every test."""
    import app.modules.inbound_messages.gemini as mod

    monkeypatch.setattr(mod, "_get_client", lambda: _mock_client)
    _mock_client.reset_mock()
    _mock_client.models.generate_content.side_effect = None


def _get_mock_client() -> MagicMock:
    return _mock_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(text: str) -> SimpleNamespace:
    """Simulate a Gemini API response object with a .text attribute."""
    return SimpleNamespace(text=text)


def _classification_json(
    intent_code: str = "greeting",
    confidence: float = 0.95,
    extracted_entities: dict | None = None,
) -> str:
    payload = {"intent_code": intent_code, "confidence": confidence}
    if extracted_entities:
        payload["extracted_entities"] = extracted_entities
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# classify_message — happy path
# ---------------------------------------------------------------------------

class TestClassifyMessage:

    def test_greeting_classification(self):
        from app.modules.inbound_messages.gemini import classify_message

        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("greeting", 0.98)
        )

        result = classify_message("Hello!", conversation_history=[])

        assert result.intent_code == "greeting"
        assert result.route_type == RouteType.AUTO_REPLY
        assert result.confidence == pytest.approx(0.98)
        assert result.extracted_entities == {}

    def test_appointment_request_with_entities(self):
        from app.modules.inbound_messages.gemini import classify_message

        entities = {"service": "cleaning", "date_preference": "tomorrow"}
        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("appointment_request", 0.92, entities)
        )

        result = classify_message("I want to book a cleaning tomorrow", conversation_history=[])

        assert result.intent_code == "appointment_request"
        assert result.route_type == RouteType.AUTO_REPLY_AND_COLLECT
        assert result.extracted_entities == {"service": "cleaning", "date_preference": "tomorrow"}

    def test_emergency_routes_to_handoff_urgent(self):
        from app.modules.inbound_messages.gemini import classify_message

        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("emergency", 0.99)
        )

        result = classify_message("My tooth is killing me!", conversation_history=[])

        assert result.intent_code == "emergency"
        assert result.route_type == RouteType.HANDOFF_URGENT

    def test_route_type_comes_from_map_not_gemini(self):
        """Route type is always looked up from INTENT_ROUTE_MAP, never from Gemini."""
        from app.modules.inbound_messages.gemini import classify_message

        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("clinic_hours", 0.85)
        )

        result = classify_message("What are your hours?", conversation_history=[])

        assert result.route_type == INTENT_ROUTE_MAP["clinic_hours"]
        assert result.route_type == RouteType.AUTO_REPLY

    def test_empty_string_entities_are_cleaned(self):
        """Gemini sometimes returns empty strings for unfound entities."""
        from app.modules.inbound_messages.gemini import classify_message

        raw = json.dumps({
            "intent_code": "greeting",
            "confidence": 0.9,
            "extracted_entities": {"name": "", "phone": "", "service": "cleaning"},
        })
        _get_mock_client().models.generate_content.return_value = _make_response(raw)

        result = classify_message("Hi, I need a cleaning", conversation_history=[])

        assert result.extracted_entities == {"service": "cleaning"}
        assert "name" not in result.extracted_entities
        assert "phone" not in result.extracted_entities


# ---------------------------------------------------------------------------
# classify_message — error / fallback
# ---------------------------------------------------------------------------

class TestClassifyMessageFallback:

    def test_api_exception_returns_unknown(self):
        from app.modules.inbound_messages.gemini import classify_message

        _get_mock_client().models.generate_content.side_effect = RuntimeError("API quota exceeded")

        result = classify_message("Hello", conversation_history=[])

        assert result.intent_code == IntentCode.UNKNOWN
        assert result.route_type == RouteType.AUTO_REPLY_AND_COLLECT
        assert result.confidence == 0.0

    def test_invalid_json_returns_unknown(self):
        from app.modules.inbound_messages.gemini import classify_message

        _get_mock_client().models.generate_content.return_value = _make_response("not json at all")

        result = classify_message("Hello", conversation_history=[])

        assert result.intent_code == IntentCode.UNKNOWN
        assert result.confidence == 0.0

    def test_hallucinated_intent_falls_back_to_unknown(self):
        """If Gemini returns an intent_code not in our taxonomy, fall back."""
        from app.modules.inbound_messages.gemini import classify_message

        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("book_haircut", 0.88)
        )

        result = classify_message("I want a haircut", conversation_history=[])

        assert result.intent_code == IntentCode.UNKNOWN
        assert result.route_type == RouteType.AUTO_REPLY_AND_COLLECT


# ---------------------------------------------------------------------------
# classify_message — context building
# ---------------------------------------------------------------------------

class TestClassifyMessageContext:

    def test_contact_context_included_in_prompt(self):
        from app.modules.inbound_messages.gemini import (
            classify_message,
            ContactContext,
        )

        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("greeting", 0.9)
        )

        classify_message(
            "Hi",
            conversation_history=[],
            contact_context=ContactContext(
                name="John",
                phone="+441234567890",
                is_existing_patient=True,
                has_active_appointment=True,
            ),
        )

        call_args = _get_mock_client().models.generate_content.call_args
        prompt_text = call_args.kwargs["contents"]
        assert "John" in prompt_text
        assert "existing patient" in prompt_text
        assert "Has active appointment: yes" in prompt_text

    def test_conversation_history_included_in_prompt(self):
        from app.modules.inbound_messages.gemini import (
            classify_message,
            ConversationTurn,
        )

        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("appointment_request", 0.9)
        )

        history = [
            ConversationTurn(role="contact", text="Hello"),
            ConversationTurn(role="bot", text="Hi! How can I help?"),
        ]
        classify_message("I want to book an appointment", conversation_history=history)

        call_args = _get_mock_client().models.generate_content.call_args
        prompt_text = call_args.kwargs["contents"]
        assert "Patient: Hello" in prompt_text
        assert "Bot: Hi! How can I help?" in prompt_text

    def test_history_limited_to_10_turns(self):
        from app.modules.inbound_messages.gemini import (
            classify_message,
            ConversationTurn,
        )

        _get_mock_client().models.generate_content.return_value = _make_response(
            _classification_json("greeting", 0.9)
        )

        history = [ConversationTurn(role="contact", text=f"msg {i}") for i in range(20)]
        classify_message("Latest message", conversation_history=history)

        call_args = _get_mock_client().models.generate_content.call_args
        prompt_text = call_args.kwargs["contents"]
        # Only last 10 should appear
        assert "msg 10" in prompt_text
        assert "msg 19" in prompt_text
        assert "msg 0" not in prompt_text


# ---------------------------------------------------------------------------
# generate_reply — happy path
# ---------------------------------------------------------------------------

class TestGenerateReply:

    def test_returns_reply_text(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.return_value = _make_response(
            "Hello! How can I help you today?"
        )

        result = generate_reply(
            intent_code="greeting",
            extracted_entities={},
            conversation_history=[],
        )

        assert result == "Hello! How can I help you today?"

    def test_strips_whitespace(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.return_value = _make_response(
            "  Here are our hours.  \n"
        )

        result = generate_reply(
            intent_code="clinic_hours",
            extracted_entities={},
            conversation_history=[],
        )

        assert result == "Here are our hours."

    def test_reference_data_included_in_prompt(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.return_value = _make_response("We're open Mon-Fri 9-17.")

        generate_reply(
            intent_code="clinic_hours",
            extracted_entities={},
            conversation_history=[],
            reference_data={"clinic_hours": "Mon-Fri: 09:00-17:00"},
        )

        call_args = _get_mock_client().models.generate_content.call_args
        prompt_text = call_args.kwargs["contents"]
        assert "Mon-Fri: 09:00-17:00" in prompt_text
        assert "Clinic reference data:" in prompt_text

    def test_missing_fields_included_in_prompt(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.return_value = _make_response("What date works for you?")

        generate_reply(
            intent_code="appointment_request",
            extracted_entities={"service": "cleaning"},
            conversation_history=[],
            missing_fields=["date_preference", "phone"],
        )

        call_args = _get_mock_client().models.generate_content.call_args
        prompt_text = call_args.kwargs["contents"]
        assert "Missing data for booking: date_preference, phone" in prompt_text

    def test_extracted_entities_in_prompt(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.return_value = _make_response("Got it!")

        generate_reply(
            intent_code="appointment_request",
            extracted_entities={"service": "whitening", "name": "Alice"},
            conversation_history=[],
        )

        call_args = _get_mock_client().models.generate_content.call_args
        prompt_text = call_args.kwargs["contents"]
        assert "service: whitening" in prompt_text
        assert "name: Alice" in prompt_text


# ---------------------------------------------------------------------------
# generate_reply — error cases
# ---------------------------------------------------------------------------

class TestGenerateReplyErrors:

    def test_api_exception_returns_none(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.side_effect = RuntimeError("network error")

        result = generate_reply(
            intent_code="greeting",
            extracted_entities={},
            conversation_history=[],
        )

        assert result is None

    def test_empty_response_returns_none(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.return_value = _make_response("")

        result = generate_reply(
            intent_code="greeting",
            extracted_entities={},
            conversation_history=[],
        )

        assert result is None

    def test_whitespace_only_response_returns_none(self):
        from app.modules.inbound_messages.gemini import generate_reply

        _get_mock_client().models.generate_content.return_value = _make_response("   \n  ")

        result = generate_reply(
            intent_code="greeting",
            extracted_entities={},
            conversation_history=[],
        )

        assert result is None
