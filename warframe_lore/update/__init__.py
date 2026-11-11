"""Backward-compatibility facade — real code lives in warframe_lore.scraper.update.

This module re-exports everything so existing imports continue to work:
    from warframe_lore.update import run_update  # still valid
"""

from __future__ import annotations

from warframe_lore.scraper.update import run_update  # noqa: F401

__all__ = ["run_update"]

