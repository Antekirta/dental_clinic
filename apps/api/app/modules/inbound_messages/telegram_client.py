from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramClientError(Exception):
    """Raised when the Telegram Bot API returns an error or is unreachable."""


def send_telegram_message(chat_id: str, text: str) -> None:
    """
    Send a text message to a Telegram chat via the Bot API.

    Uses urllib.request only — no extra dependencies needed.
    Reads TELEGRAM_HTTP_API_TOKEN from app settings.

    Raises TelegramClientError on API errors or network failures.
    """
    token = settings.telegram_http_api_token
    url = f"{_TELEGRAM_API_BASE}/bot{token}/sendMessage"

    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read())
        raise TelegramClientError(
            f"Telegram API error {exc.code}: {body.get('description', exc.reason)}"
        ) from exc
    except Exception as exc:
        raise TelegramClientError(f"Failed to reach Telegram API: {exc}") from exc

    if not body.get("ok"):
        raise TelegramClientError(
            f"Telegram API responded not ok: {body.get('description', body)}"
        )

    logger.info("Sent Telegram message to chat_id=%s", chat_id)
