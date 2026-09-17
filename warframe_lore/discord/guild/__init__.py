"""Discord guild domain: member naming, question routing, role hierarchy.

Facade: the public names of this package are re-exported here so callers keep
importing from ``warframe_lore.discord.guild`` whatever the internal split is
(``naming`` / ``creator`` / ``questions`` / ``lore`` / ``story`` /
``story_mode`` / ``story_eras`` / ``roles``).
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
    LEVERIAN_WARFRAMES,
    MENU_INDEX_ERROR,
    STORY_SUBJECT_CHOICES,
    STORY_TRIGGERS,
    TARGETED_SUBJECT_ERAS,
    StoryAsk,
    detect_leverian_warframe,
    detect_story_lens,
    detect_targeted_era,
    is_out_of_range_index,
    is_story_request,
    parse_lens_answer,
    parse_subject_answer,
    story_subject,
    story_subject_choices,
    story_subject_question,
    substitute_story_subject,
    targeted_subject_mention,
)
from .story_mode import (
    STORY_CONTINUATION_MAX_WORDS,
    STORY_CONTINUATION_TRIGGERS,
    StoryMode,
    detect_story_mode,
    is_story_continuation,
)

__all__ = [
    "LENS_1999",
    "LENS_COSMOGONIC",
    "LENS_INITIATE",
    "LENS_KEYWORDS",
    "LENS_LABELS",
    "LENS_QUESTION",
    "LEVERIAN_WARFRAMES",
    "LORE_TRIGGERS",
    "MENU_INDEX_ERROR",
    "STORY_SUBJECT_CHOICES",
    "STORY_CONTINUATION_MAX_WORDS",
    "STORY_CONTINUATION_TRIGGERS",
    "STORY_TRIGGERS",
    "TARGETED_SUBJECT_ERAS",
    "Accreditation",
    "RoleHierarchy",
    "StoryAsk",
    "StoryMode",
    "creator_mentioned",
    "creator_pseudo_variants",
    "detect_leverian_warframe",
    "detect_story_lens",
    "detect_story_mode",
    "detect_targeted_era",
    "is_member_question",
    "is_out_of_range_index",
    "is_story_continuation",
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
    "targeted_subject_mention",
    "wants_lore",
]
