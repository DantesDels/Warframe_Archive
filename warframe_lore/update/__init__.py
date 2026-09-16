"""Cephalon update chain: scraper → structured ETL → export → static lists."""

from __future__ import annotations

from .run import run_update

__all__ = ["run_update"]
