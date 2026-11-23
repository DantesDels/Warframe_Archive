"""Ports used by application use cases."""

from __future__ import annotations

from typing import Any, Protocol


class ExecutionObserver(Protocol):
    def progress(self, percent: int, step: str) -> None: ...
    def log(self, message: str) -> None: ...
    def event(self, event_type: str, **payload: Any) -> None: ...


class UniverseRunContext(Protocol):
    client: Any
    export_root: Any
    snapshot: Any
    state: dict[str, Any]
    observer: ExecutionObserver
