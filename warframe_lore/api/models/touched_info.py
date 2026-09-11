"""Light modification metadata (delta computation)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TouchedInfo:
    """Light information for delta computation (incremental mode).

    This is what allows re-downloading only the modified pages without
    having to fetch their content.
    """

    pageid: int | None
    title: str
    namespace: int = 0
    touched: str | None = None
    missing: bool = False