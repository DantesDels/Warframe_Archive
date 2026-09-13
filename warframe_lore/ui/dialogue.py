"""Wiki dialogue parsing — aggregation facade.

The logic has been split by responsibility:

* :mod:`warframe_lore.ui.refs`     -> text cleanup / jump-reference machinery;
* :mod:`warframe_lore.ui.sections` -> recognition, extraction, conversations.

WARFRAME wiki pages (KIM and quests): this module keeps the historical
import surface for the store, the graph and the script builders.
"""

from __future__ import annotations

from .refs import (
    _ANNOT_PAREN,
    _CONVO_ENDS,
    _DIALOGUE_STRIP_CHARS,
    _JUMP_ABOVE,
    _JUMP_BELOW,
    _JUMP_QUOTED,
    _JUMP_VAGUE,
    _KIM_CONDITION_MARK,
    _KIM_INLINE_NAV,
    _KIM_POSITION_MARK,
    clean_kim_text,
    is_player_speaker,
    normalise_dialogue_ref,
    normalise_ref,
    slug_for_id,
)
from .sections import (
    _BLOCKQUOTE_SPEAKER,
    _BOILERPLATE_LINE,
    _DIALOGUE_EXCLUDE_EXACT,
    _DIALOGUE_EXCLUDE_RE,
    _KIM_CONVO_NUMBER,
    _KIM_POINTER_LINE,
    _KIM_RANK_TITLE,
    _KIM_SECTION_TITLE,
    _SPOILER_WARNING,
    KIM_BUCKET_ID,
    looks_like_dialogue,
    make_snippet,
    parse_dialogue,
    speakers,
    split_kim_conversations,
    spoiler_warning,
)

__all__ = [
    "KIM_BUCKET_ID",
    "_ANNOT_PAREN",
    "_BLOCKQUOTE_SPEAKER",
    "_BOILERPLATE_LINE",
    "_CONVO_ENDS",
    "_DIALOGUE_EXCLUDE_EXACT",
    "_DIALOGUE_EXCLUDE_RE",
    "_DIALOGUE_STRIP_CHARS",
    "_JUMP_ABOVE",
    "_JUMP_BELOW",
    "_JUMP_QUOTED",
    "_JUMP_VAGUE",
    "_KIM_CONDITION_MARK",
    "_KIM_CONVO_NUMBER",
    "_KIM_INLINE_NAV",
    "_KIM_POINTER_LINE",
    "_KIM_POSITION_MARK",
    "_KIM_RANK_TITLE",
    "_KIM_SECTION_TITLE",
    "_SPOILER_WARNING",
    "clean_kim_text",
    "is_player_speaker",
    "looks_like_dialogue",
    "make_snippet",
    "normalise_dialogue_ref",
    "normalise_ref",
    "parse_dialogue",
    "slug_for_id",
    "speakers",
    "split_kim_conversations",
    "spoiler_warning",
]
