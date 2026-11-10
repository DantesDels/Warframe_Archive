"""Neutral local-infrastructure bootstrap (Docker engine + PostgreSQL).

Facade: exposes :func:`ensure_database` to every entry point that needs the
compose stack (``cephalon run``, ``cephalon update``, the Discord bot).
"""

from __future__ import annotations

from .db_bootstrap import ensure_database

__all__ = ["ensure_database"]
