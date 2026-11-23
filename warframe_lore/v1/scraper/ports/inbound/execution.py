"""Inbound port for execution/discovery/sync use cases."""

from __future__ import annotations

from typing import Any, Protocol


class ExecutionPort(Protocol):
    """Inbound: start collection runs for selected universes."""

    def run(self, plan: Any) -> dict[str, Any]: ...
