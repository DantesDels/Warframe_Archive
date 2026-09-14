"""Hostile session per attacker (anti-aggression persona until an apology).

Facade: re-exports the apology detection (:mod:`apology`) and the dedicated WS
session (:mod:`link`) so callers keep importing
``warframe_lore.discord.moderation.hostile_link``.
"""

from __future__ import annotations

from .apology import (
    APOLOGY_MARKERS,
    SARCASTIC_MARKERS,
    is_apology,
    is_sincere_apology,
)
from .link import HostileLink

__all__ = ["APOLOGY_MARKERS", "HostileLink", "SARCASTIC_MARKERS", "is_apology",
           "is_sincere_apology"]
