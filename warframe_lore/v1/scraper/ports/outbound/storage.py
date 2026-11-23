"""Outbound ports for persistence."""

from __future__ import annotations

from typing import Any, Protocol


class DocumentStorePort(Protocol):
    """Outbound: persist workspace documents, versions, runs."""

    def save_run(self, payload: dict[str, Any]) -> None: ...
