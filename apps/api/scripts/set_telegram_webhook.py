#!/usr/bin/env python
"""
Register the FastAPI /webhooks/telegram endpoint with the Telegram Bot API.

Usage (from the api/ directory):
    python scripts/set_telegram_webhook.py https://<your-cloudflared-tunnel>.trycloudflare.com

Run this once after starting cloudflared and before testing end-to-end.
The script reads TELEGRAM_HTTP_API_TOKEN from the project .env file automatically.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path


def _load_token() -> str:
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        print(f"ERROR: .env not found at {env_path}", file=sys.stderr)
        sys.exit(1)

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("TELEGRAM_HTTP_API_TOKEN="):
            token = line.split("=", 1)[1].strip()
            if token:
                return token

    print("ERROR: TELEGRAM_HTTP_API_TOKEN not found or empty in .env", file=sys.stderr)
    sys.exit(1)


def _call(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <base_url>")
        print(f"Example: python {sys.argv[0]} https://abc123.trycloudflare.com")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    webhook_url = f"{base_url}/webhooks/telegram"
    token = _load_token()

    result = _call(
        f"https://api.telegram.org/bot{token}/setWebhook",
        {"url": webhook_url, "drop_pending_updates": True},
    )

    if result.get("ok"):
        print(f"✅  Webhook registered: {webhook_url}")
    else:
        print(f"❌  Telegram API error: {result}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
