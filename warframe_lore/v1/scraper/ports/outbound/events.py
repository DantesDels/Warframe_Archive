"""Outbound port for audit/event logging."""

from __future__ import annotations

from typing import Any, Protocol


class EventLogPort(Protocol):
    """Outbound: append immutable audit events."""

    def emit(self, event_type: str, **payload: Any) -> dict[str, Any]: ...
