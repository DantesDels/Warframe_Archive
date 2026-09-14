"""Discord guild domain: member naming, question routing, role hierarchy.

Facade: the public names of this package are re-exported here so callers keep
importing from ``warframe_lore.discord.guild`` whatever the internal split is
(``naming`` / ``creator`` / ``questions`` / ``lore`` / ``roles``).
"""

from __future__ import annotations

from .creator import creator_mentioned, creator_pseudo_variants
from .lore import LORE_TRIGGERS, wants_lore
from .naming import (
    leetspeak,
    match_member_token,
    normalize_mentions,
    normalize_message,
)
from .questions import is_member_question, roles_question, self_info_request
from .roles import Accreditation, RoleHierarchy

__all__ = [
    "LORE_TRIGGERS",
    "Accreditation",
    "RoleHierarchy",
    "creator_mentioned",
    "creator_pseudo_variants",
    "is_member_question",
    "leetspeak",
    "match_member_token",
    "normalize_mentions",
    "normalize_message",
    "roles_question",
    "self_info_request",
    "wants_lore",
]
