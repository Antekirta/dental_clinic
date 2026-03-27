from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_db_session
from app.modules.inbound_messages.adapters.telegram import (
    TelegramAdapterError,
    normalize_telegram_update,
)
from app.modules.inbound_messages.service import process_incoming_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/telegram", status_code=200)
async def telegram_webhook(
    request: Request,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
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

    try:
        process_incoming_message(session, unified)
    except Exception as exc:
        logger.error(
            "Error processing Telegram message from contact=%s: %s",
            unified.contact.external_id,
            exc,
            exc_info=True,
        )

    return {"ok": True}
