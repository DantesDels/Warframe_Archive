"""Outbound port for HTTP fetching/caching."""

from __future__ import annotations

from typing import Any, Protocol


class HttpPort(Protocol):
    """Outbound: perform policy-aware HTTP requests."""

    def get(self, url: str, **kwargs: Any) -> Any: ...
