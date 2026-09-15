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
from .story import (
    LENS_1999,
    LENS_COSMOGONIC,
    LENS_INITIATE,
    LENS_KEYWORDS,
    LENS_LABELS,
    LENS_QUESTION,
    MENU_INDEX_ERROR,
    STORY_SUBJECT_CHOICES,
    STORY_TRIGGERS,
    StoryAsk,
    detect_story_lens,
    is_out_of_range_index,
    is_story_request,
    parse_lens_answer,
    parse_subject_answer,
    story_subject,
    story_subject_choices,
    story_subject_question,
    substitute_story_subject,
)

__all__ = [
    "LENS_1999",
    "LENS_COSMOGONIC",
    "LENS_INITIATE",
    "LENS_KEYWORDS",
    "LENS_LABELS",
    "LENS_QUESTION",
    "LORE_TRIGGERS",
    "MENU_INDEX_ERROR",
    "STORY_SUBJECT_CHOICES",
    "STORY_TRIGGERS",
    "Accreditation",
    "RoleHierarchy",
    "StoryAsk",
    "creator_mentioned",
    "creator_pseudo_variants",
    "detect_story_lens",
    "is_member_question",
    "is_out_of_range_index",
    "is_story_request",
    "leetspeak",
    "match_member_token",
    "normalize_mentions",
    "normalize_message",
    "parse_lens_answer",
    "parse_subject_answer",
    "roles_question",
    "self_info_request",
    "story_subject",
    "story_subject_choices",
    "story_subject_question",
    "substitute_story_subject",
    "wants_lore",
]
