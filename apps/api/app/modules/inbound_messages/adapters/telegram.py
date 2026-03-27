from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.modules.inbound_messages.schemas import (
    ChannelPayload,
    ContactMatchKeysPayload,
    ContactPayload,
    ConversationPayload,
    ContextPayload,
    EventPayload,
    MessagePayload,
    SourceMetadataPayload,
    UnifiedIncomingMessage,
)


class TelegramAdapterError(Exception):
    """Raised when a Telegram update cannot be adapted to UnifiedIncomingMessage."""


def normalize_telegram_update(raw: dict[str, Any]) -> UnifiedIncomingMessage:
    """
    Convert a raw Telegram Update dict into a UnifiedIncomingMessage.

    Currently handles:
    - Text messages (message.text)
    - Photo/file messages with a caption (message.caption)

    Raises TelegramAdapterError for unsupported update types (e.g. edited_message,
    channel_post, callback_query) or for malformed payloads missing required fields.
    The webhook endpoint catches this and returns 200 so Telegram does not retry.
    """
    message = raw.get("message")
    if not message:
        supported = ["message"]
        received = [k for k in raw if k != "update_id"]
        raise TelegramAdapterError(
            f"Unsupported update type. Supported: {supported}. Got keys: {received}"
        )

    from_user: dict[str, Any] = message.get("from") or {}
    chat: dict[str, Any] = message.get("chat") or {}

    user_id = from_user.get("id")
    if user_id is None:
        raise TelegramAdapterError("Missing 'from.id' in Telegram message.")

    message_id = message.get("message_id")
    if message_id is None:
        raise TelegramAdapterError("Missing 'message_id' in Telegram message.")

    # --- text resolution --------------------------------------------------
    text: str | None = message.get("text")
    caption: str | None = message.get("caption")

    if text:
        message_type = "text"
        normalized_text: str | None = text
    elif caption:
        # photo / document / video with a caption
        message_type = "image"
        normalized_text = caption
    else:
        # sticker, voice, unsupported binary — keep for audit, skip AI
        message_type = "unsupported"
        normalized_text = None

    # --- identity ---------------------------------------------------------
    external_id = str(user_id)
    chat_id = str(chat.get("id") or user_id)
    username: str | None = from_user.get("username")
    first_name: str | None = from_user.get("first_name")
    last_name: str | None = from_user.get("last_name")
    language_code: str | None = from_user.get("language_code")
    chat_type: str = chat.get("type") or "private"

    name_parts = [p for p in [first_name, last_name] if p]
    display_name = " ".join(name_parts) if name_parts else (username or external_id)

    # --- timestamps -------------------------------------------------------
    date_unix: int | None = message.get("date")
    sent_at = datetime.fromtimestamp(date_unix, tz=UTC) if date_unix else datetime.now(UTC)
    received_at = datetime.now(UTC)

    event_id = f"telegram:{message_id}"

    return UnifiedIncomingMessage(
        event=EventPayload(
            event_type="message.received",
            event_id=event_id,
            received_at=received_at,
            deduplication_key=event_id,
            source_system="telegram",
            source_account_id=None,
        ),
        channel=ChannelPayload(
            code="telegram",
            display_name="Telegram",
            source_channel_code="telegram",
        ),
        contact=ContactPayload(
            external_id=external_id,
            display_name=display_name,
            first_name=first_name,
            last_name=last_name,
            username=username,
            phone=None,
            email=None,
        ),
        conversation=ConversationPayload(
            external_chat_id=chat_id,
            is_group=(chat_type != "private"),
        ),
        message=MessagePayload(
            direction="inbound",
            sender_type="contact",
            external_message_id=str(message_id),
            sent_at=sent_at,
            message_type=message_type,
            text=text or caption,
            normalized_text=normalized_text,
            caption=caption,
            language_hint=language_code,
        ),
        contact_match_keys=ContactMatchKeysPayload(
            telegram_username=username,
        ),
        context=ContextPayload(),
        source_metadata=SourceMetadataPayload(
            provider="telegram",
            provider_message_type="text" if text else ("caption" if caption else "other"),
            provider_chat_type=chat_type,
        ),
        raw_payload=raw,
    )
