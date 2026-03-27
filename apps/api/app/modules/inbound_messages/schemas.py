from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    event_type: str = "message.received"
    event_id: str
    received_at: datetime
    deduplication_key: str
    source_system: str
    source_account_id: str | None = None


class ChannelPayload(BaseModel):
    code: str  # "telegram" | "whatsapp" | "gmail" | "website_chat"
    display_name: str | None = None
    source_channel_code: str | None = None


class ContactPayload(BaseModel):
    external_id: str
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    phone: str | None = None
    email: str | None = None


class ConversationPayload(BaseModel):
    external_chat_id: str
    external_thread_id: str | None = None
    subject: str | None = None
    is_group: bool = False


class AttachmentPayload(BaseModel):
    attachment_id: str | None = None
    type: str  # "image" | "file" | "audio"
    mime_type: str | None = None
    file_name: str | None = None
    file_size_bytes: int | None = None
    url: str | None = None
    storage_key: str | None = None
    sha256: str | None = None
    duration_seconds: int | None = None


class MessagePayload(BaseModel):
    direction: str = "inbound"
    sender_type: str = "contact"
    external_message_id: str
    reply_to_external_message_id: str | None = None
    sent_at: datetime
    message_type: str  # "text" | "image" | "file" | "audio" | "unsupported"
    subject: str | None = None
    text: str | None = None
    normalized_text: str | None = None
    html: str | None = None
    caption: str | None = None
    language_hint: str | None = None
    attachments: list[AttachmentPayload] = Field(default_factory=list)


class ContactMatchKeysPayload(BaseModel):
    phone: str | None = None
    email: str | None = None
    telegram_username: str | None = None
    whatsapp_phone: str | None = None
    website_visitor_id: str | None = None


class ContextPayload(BaseModel):
    is_first_message_in_conversation: bool | None = None
    is_existing_contact: bool | None = None
    has_active_appointment: bool | None = None


class SourceMetadataPayload(BaseModel):
    provider: str
    provider_message_type: str | None = None
    provider_chat_type: str | None = None
    provider_thread_id: str | None = None
    provider_labels: list[str] = Field(default_factory=list)
    provider_flags: dict[str, Any] = Field(default_factory=dict)


class UnifiedIncomingMessage(BaseModel):
    schema_version: str = "incoming_message_unified.v1"
    event: EventPayload
    channel: ChannelPayload
    contact: ContactPayload
    conversation: ConversationPayload
    message: MessagePayload
    contact_match_keys: ContactMatchKeysPayload
    context: ContextPayload = Field(default_factory=ContextPayload)
    source_metadata: SourceMetadataPayload
    raw_payload: dict[str, Any] = Field(default_factory=dict)
