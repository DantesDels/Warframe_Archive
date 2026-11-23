"""Thread-safe atomic JSON persistence helpers shared by v1 registries."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_WRITE_LOCK = threading.Lock()


def read_json(path: Path, default: Any) -> Any:
    """Read JSON, returning ``default`` for missing or unreadable files."""
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        logger.warning("Unable to read %s: %s", path, exc)
        return default


def write_json(path: Path, payload: Any) -> None:
    """Atomically write JSON with a lock and retry on transient Windows locks."""
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with _WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f"{path.suffix}.{threading.get_ident()}.tmp")
        tmp.write_text(serialized, encoding="utf-8")
        for attempt in range(4):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 3:
                    tmp.unlink(missing_ok=True)
                    raise
                time.sleep(0.05 * (attempt + 1))
