"""ENGRAM ingestion scripts (ETL)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ingest import main

__all__ = ["main"]


def __getattr__(name: str):
    """Lazy import of ``main``: keeps ``python -m ...scripts.ingest``
    executable (an eager ``from .ingest import main`` here makes runpy
    reuse the already-imported module without running it)."""
    if name == "main":
        from .ingest import main

        return main
    raise AttributeError(name)
