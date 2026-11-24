"""Outbound adapter: thread-safe append-only JSONL event log."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonlEventLogAdapter:
    """Outbound adapter implementing EventLogPort with thread-safe writes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event_type: str, **payload: Any) -> dict[str, Any]:
        event: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "type": event_type,
            **payload,
        }
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        return event
