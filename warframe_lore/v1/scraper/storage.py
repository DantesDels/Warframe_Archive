"""Minimal JSON persistence helpers shared by v1 registries."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
    """Write a JSON file and create its parent directory when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
