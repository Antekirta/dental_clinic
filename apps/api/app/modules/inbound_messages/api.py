from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from app.modules.inbound_messages.adapters.telegram import (
    TelegramAdapterError,
    normalize_telegram_update,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/telegram", status_code=200)
async def telegram_webhook(request: Request) -> dict[str, Any]:
    """
    Receive a Telegram Bot webhook update.

    Always returns 200 so Telegram does not retry the delivery — even for
    update types we don't yet support (stickers, channel posts, etc.).
    """
    raw: dict[str, Any] = await request.json()

    try:
        unified = normalize_telegram_update(raw)
    except TelegramAdapterError as exc:
        logger.warning("Skipping unsupported Telegram update: %s", exc)
        return {"ok": True}

    logger.info(
        "Telegram | contact=%s chat=%s type=%s text=%r",
        unified.contact.external_id,
        unified.conversation.external_chat_id,
        unified.message.message_type,
        unified.message.normalized_text,
    )

    # TODO: call process_incoming_message(unified, session)
    # This is the next step — for now we just log and acknowledge.

    return {"ok": True}
