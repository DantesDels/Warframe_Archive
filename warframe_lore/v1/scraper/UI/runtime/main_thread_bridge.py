"""Marshal worker-thread signals into the Qt main thread."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Slot


class MainThreadBridge(QObject):
    """QObject living on the UI thread that forwards worker signal payloads."""

    def __init__(self, callback: Callable[..., None]) -> None:
        super().__init__()
        self._callback = callback

    @Slot(object)
    def on_value(self, value: Any) -> None:
        self._callback(value)

    @Slot(str, object)
    def on_event(self, event_type: str, payload: Any) -> None:
        self._callback(event_type, payload)
