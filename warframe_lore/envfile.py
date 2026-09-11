"""Lightweight ``.env`` loader from the project root (no dependency).

Parses ``KEY=value`` lines (``#`` comments, single/double quotes, end-of-line
comments). Never overrides a variable already set in the shell environment:
the shell always wins; the ``.env`` file is a fallback.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _parse(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        body = line.split(" #", 1)[0].strip()
        key, sep, value = body.partition("=")
        if not sep or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_dotenv(path: Path | str = PROJECT_ROOT / ".env") -> None:
    """Load ``path`` into ``os.environ`` without overwriting existing values."""
    if not Path(path).is_file():
        return
    for key, value in _parse(
            Path(path).read_text(encoding="utf-8-sig").splitlines()).items():
        if key not in os.environ:
            os.environ[key] = value


__all__ = ["load_dotenv"]