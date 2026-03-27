"""
Unit tests for the Telegram → UnifiedIncomingMessage adapter.

These are pure function tests — no DB, no HTTP, no fixtures.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modules.inbound_messages.adapters.telegram import (
    TelegramAdapterError,
    normalize_telegram_update,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_update(
    *,
    update_id: int = 100,
    message_id: int = 1,
    user_id: int = 99887766,
    first_name: str = "Anna",
    last_name: str | None = "Petrova",
    username: str | None = "annapetrova",
    language_code: str | None = "ru",
    chat_type: str = "private",
    text: str = "Хочу записаться на чистку",
    date: int = 1711130981,
) -> dict:
    from_user: dict = {
        "id": user_id,
        "is_bot": False,
        "first_name": first_name,
        "language_code": language_code,
    }
    chat: dict = {"id": user_id, "type": chat_type}

    if last_name is not None:
        from_user["last_name"] = last_name
        chat["last_name"] = last_name
    if username is not None:
        from_user["username"] = username
        chat["username"] = username

    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "from": from_user,
            "chat": chat,
            "date": date,
            "text": text,
        },
    }


def _caption_update(*, caption: str = "Check this out") -> dict:
    """A photo message with a caption (no text field)."""
    raw = _text_update()
    msg = raw["message"]
    del msg["text"]
    msg["caption"] = caption
    msg["photo"] = [{"file_id": "abc", "width": 100, "height": 100, "file_size": 1024}]
    return raw


def _sticker_update() -> dict:
    """A sticker message — no text, no caption."""
    raw = _text_update()
    msg = raw["message"]
    del msg["text"]
    msg["sticker"] = {"file_id": "sticker_abc", "emoji": "👍"}
    return raw


# ---------------------------------------------------------------------------
# Schema & channel fields
# ---------------------------------------------------------------------------

def test_schema_version() -> None:
    result = normalize_telegram_update(_text_update())
    assert result.schema_version == "incoming_message_unified.v1"


def test_channel_code() -> None:
    result = normalize_telegram_update(_text_update())
    assert result.channel.code == "telegram"
    assert result.channel.source_channel_code == "telegram"


# ---------------------------------------------------------------------------
# Contact fields
# ---------------------------------------------------------------------------

def test_contact_external_id_is_string() -> None:
    result = normalize_telegram_update(_text_update(user_id=99887766))
    assert result.contact.external_id == "99887766"


def test_contact_full_name_fields() -> None:
    result = normalize_telegram_update(_text_update())
    assert result.contact.first_name == "Anna"
    assert result.contact.last_name == "Petrova"
    assert result.contact.username == "annapetrova"


def test_contact_display_name_first_and_last() -> None:
    result = normalize_telegram_update(_text_update(first_name="Anna", last_name="Petrova"))
    assert result.contact.display_name == "Anna Petrova"


def test_contact_display_name_first_only() -> None:
    result = normalize_telegram_update(_text_update(first_name="Anna", last_name=None))
    assert result.contact.display_name == "Anna"


def test_contact_display_name_falls_back_to_username() -> None:
    result = normalize_telegram_update(_text_update(first_name="", last_name=None))
    # first_name is empty string → treated as falsy after name_parts filter
    assert result.contact.display_name in ("annapetrova", "99887766")


def test_contact_no_phone_or_email() -> None:
    result = normalize_telegram_update(_text_update())
    assert result.contact.phone is None
    assert result.contact.email is None


# ---------------------------------------------------------------------------
# Conversation fields
# ---------------------------------------------------------------------------

def test_conversation_external_chat_id() -> None:
    result = normalize_telegram_update(_text_update(user_id=99887766))
    assert result.conversation.external_chat_id == "99887766"


def test_conversation_not_a_group_for_private_chat() -> None:
    result = normalize_telegram_update(_text_update(chat_type="private"))
    assert result.conversation.is_group is False


def test_conversation_is_group_for_group_chat() -> None:
    result = normalize_telegram_update(_text_update(chat_type="group"))
    assert result.conversation.is_group is True


# ---------------------------------------------------------------------------
# Message fields
# ---------------------------------------------------------------------------

def test_message_direction_and_sender_type() -> None:
    result = normalize_telegram_update(_text_update())
    assert result.message.direction == "inbound"
    assert result.message.sender_type == "contact"


def test_message_type_for_text() -> None:
    result = normalize_telegram_update(_text_update(text="Hello"))
    assert result.message.message_type == "text"


def test_message_text_and_normalized_text() -> None:
    result = normalize_telegram_update(_text_update(text="Здравствуйте"))
    assert result.message.text == "Здравствуйте"
    assert result.message.normalized_text == "Здравствуйте"


def test_message_external_id_is_string() -> None:
    result = normalize_telegram_update(_text_update(message_id=42))
    assert result.message.external_message_id == "42"


def test_message_sent_at_from_unix_timestamp() -> None:
    date_unix = 1711130981
    result = normalize_telegram_update(_text_update(date=date_unix))
    assert result.message.sent_at == datetime.fromtimestamp(date_unix, tz=UTC)


def test_message_language_hint() -> None:
    result = normalize_telegram_update(_text_update(language_code="ru"))
    assert result.message.language_hint == "ru"


# ---------------------------------------------------------------------------
# Caption / photo messages
# ---------------------------------------------------------------------------

def test_caption_message_type_is_image() -> None:
    result = normalize_telegram_update(_caption_update(caption="Look at this"))
    assert result.message.message_type == "image"


def test_caption_normalized_text_uses_caption() -> None:
    result = normalize_telegram_update(_caption_update(caption="Look at this"))
    assert result.message.normalized_text == "Look at this"
    assert result.message.caption == "Look at this"


# ---------------------------------------------------------------------------
# Unsupported message types (sticker, voice, etc.)
# ---------------------------------------------------------------------------

def test_sticker_message_type_is_unsupported() -> None:
    result = normalize_telegram_update(_sticker_update())
    assert result.message.message_type == "unsupported"
    assert result.message.normalized_text is None


# ---------------------------------------------------------------------------
# contact_match_keys
# ---------------------------------------------------------------------------

def test_contact_match_keys_username_populated() -> None:
    result = normalize_telegram_update(_text_update(username="annapetrova"))
    assert result.contact_match_keys.telegram_username == "annapetrova"


def test_contact_match_keys_username_none_when_missing() -> None:
    result = normalize_telegram_update(_text_update(username=None))
    assert result.contact_match_keys.telegram_username is None


def test_contact_match_keys_no_phone_or_email() -> None:
    result = normalize_telegram_update(_text_update())
    assert result.contact_match_keys.phone is None
    assert result.contact_match_keys.email is None


# ---------------------------------------------------------------------------
# Event / deduplication
# ---------------------------------------------------------------------------

def test_event_type() -> None:
    result = normalize_telegram_update(_text_update())
    assert result.event.event_type == "message.received"
    assert result.event.source_system == "telegram"


def test_deduplication_key_includes_message_id() -> None:
    result = normalize_telegram_update(_text_update(message_id=42))
    assert result.event.deduplication_key == "telegram:42"
    assert result.event.event_id == "telegram:42"


# ---------------------------------------------------------------------------
# raw_payload
# ---------------------------------------------------------------------------

def test_raw_payload_preserved() -> None:
    raw = _text_update()
    result = normalize_telegram_update(raw)
    assert result.raw_payload == raw


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_unsupported_update_type_raises() -> None:
    raw = {"update_id": 100, "channel_post": {"text": "hi"}}
    with pytest.raises(TelegramAdapterError, match="Unsupported update type"):
        normalize_telegram_update(raw)


def test_edited_message_raises() -> None:
    raw = {"update_id": 100, "edited_message": {"message_id": 1, "text": "edited"}}
    with pytest.raises(TelegramAdapterError, match="Unsupported update type"):
        normalize_telegram_update(raw)


def test_missing_from_id_raises() -> None:
    raw = {
        "update_id": 100,
        "message": {
            "message_id": 1,
            "chat": {"id": 99887766, "type": "private"},
            "date": 1711130981,
            "text": "Hello",
        },
    }
    with pytest.raises(TelegramAdapterError, match="Missing 'from.id'"):
        normalize_telegram_update(raw)


def test_missing_message_id_raises() -> None:
    raw = {
        "update_id": 100,
        "message": {
            "from": {"id": 99887766},
            "chat": {"id": 99887766, "type": "private"},
            "date": 1711130981,
            "text": "Hello",
        },
    }
    with pytest.raises(TelegramAdapterError, match="Missing 'message_id'"):
        normalize_telegram_update(raw)
