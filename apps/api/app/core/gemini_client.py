"""Shared Gemini client singleton.

Deferred initialisation so tests can mock before the first real call.
"""
from __future__ import annotations

from google import genai

from app.config import settings

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Return the shared Gemini client, creating it on first call."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client
