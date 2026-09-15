"""Everything that shapes the LLM payload of a Roleplay turn.

Facade: the sliding window (BLOC 2 history), the directive texts (civility,
jealousy, answer language) and the block assembly.  Callers import the public
names from here, whatever the internal split is.
"""

from __future__ import annotations

from .blocks import ARCHIVES_HEADER, archive_bloc, turn_directives
from .directives import (
    CIVILITY_DIRECTIVE,
    DEFAULT_LANGUAGE,
    JEALOUSY_DIRECTIVE,
    LANGUAGE_DIRECTIVE,
    LANGUAGE_NAMES,
    NO_HISTORY_LINE,
    SPEAKER_HEADER,
    STORY_DIRECTIVE,
    STORY_LENS_STARTS,
    TARGETED_STORY_DIRECTIVE,
    language_directive,
    speaker_bloc,
    story_directive,
    targeted_story_directive,
)
from .window import SlidingWindow

__all__ = [
    "ARCHIVES_HEADER", "CIVILITY_DIRECTIVE", "DEFAULT_LANGUAGE",
    "JEALOUSY_DIRECTIVE", "LANGUAGE_DIRECTIVE", "LANGUAGE_NAMES",
    "NO_HISTORY_LINE", "SPEAKER_HEADER", "STORY_DIRECTIVE",
    "STORY_LENS_STARTS", "TARGETED_STORY_DIRECTIVE", "SlidingWindow",
    "archive_bloc", "language_directive", "speaker_bloc", "story_directive",
    "targeted_story_directive", "turn_directives",
]
