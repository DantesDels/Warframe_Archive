"""Compatibility HTTP facade over outbound HTTP adapter."""

from __future__ import annotations

from ..adapters.outbound.http.client import FetchResponse, HttpClientAdapter
from ..adapters.outbound.http.headers import (
    BOT_UA,
    BROWSER_UA,
    bot_headers,
    browser_headers,
)

HttpClient = HttpClientAdapter

__all__ = [
    "BOT_UA", "BROWSER_UA", "FetchResponse",
    "HttpClient", "bot_headers", "browser_headers",
]
