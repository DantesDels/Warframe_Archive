"""Anchoring of an open narrative: what an explicit continuation replays.

Second half of the storyteller domain (``story.py`` detects a REQUEST): a
:class:`StoryMode` is the anchoring one turn streams with — starting lens,
targeted era, dossier subject, Leverian frame — and :func:`detect_story_mode`
derives it from the request.  A follow-up that names no subject of its own
("continue", "la suite") must NOT fall back to free chat: the bot replays the
anchoring of the narrative it just told, which keeps the turn inside the
archives (and therefore inside the deterministic entity gate — playtest: an
unanchored "continue" let the sheet persona invent a whole Codex page).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .story import (
    detect_leverian_warframe,
    detect_story_lens,
    detect_targeted_era,
    is_story_request,
    targeted_subject_mention,
)

# Explicit cues asking to CONTINUE the narrative just told (FR/EN).  A
# continuation is SHORT by nature: the word budget below separates "poursuis"
# from a new request that merely happens to contain "encore" or "la suite".
STORY_CONTINUATION_TRIGGERS = (
    "continue", "poursuis", "poursuit", "la suite", "raconte la suite",
    "encore", "et ensuite", "et après", "go on", "keep going",
    "continue the story", "more",
)
STORY_CONTINUATION_MAX_WORDS = 5


@dataclass(frozen=True)
class StoryMode:
    """Anchoring of one narrative: its request and the frame fields it sets."""

    request: str = ""
    story_lens: str | None = None
    targeted_era: str | None = None
    targeted_subject: str | None = None
    leverian_warframe: str | None = None

    @property
    def streamable(self) -> bool:
        """True when the anchoring can open a narrative (a lens or an era)."""
        return self.story_lens is not None or self.targeted_era is not None


def is_story_continuation(text: str) -> bool:
    """True when a SHORT message only asks to continue the open narrative.

    Length-bounded on purpose: a long message that contains a cue word is a new
    request, never a follow-up of the running story.
    """
    words = re.sub(r"[^\w\s]", " ", (text or "").lower()).split()
    if not words or len(words) > STORY_CONTINUATION_MAX_WORDS:
        return False
    joined = " ".join(words)
    return any(trigger in joined for trigger in STORY_CONTINUATION_TRIGGERS)


def detect_story_mode(text: str) -> StoryMode:
    """Anchoring a NEW request implies (empty :class:`StoryMode` = free chat).

    An explicit temporal lens wins over the default era of a named subject, and
    the dossier subject only exists when a targeted era was recognized — the
    exact rules the storyteller router applies to a story request.
    """
    if not is_story_request(text):
        return StoryMode()
    lens = detect_story_lens(text)
    era = None if lens is not None else detect_targeted_era(text)
    return StoryMode(
        request=text,
        story_lens=lens,
        targeted_era=era,
        targeted_subject=(targeted_subject_mention(text)
                          if era is not None else None),
        leverian_warframe=detect_leverian_warframe(text))


__all__ = [
    "STORY_CONTINUATION_MAX_WORDS",
    "STORY_CONTINUATION_TRIGGERS",
    "StoryMode",
    "detect_story_mode",
    "is_story_continuation",
]
