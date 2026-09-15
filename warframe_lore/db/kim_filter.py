"""Business filter for the KIM dialogue extraction (junk exclusion).

The ``kim_dialogues`` table stores narrative dialogue only.  This module
drops non-narrative rows before insertion: UI labels and patch-note / loot
mechanics markers ("Known Issue", "Reward", "NEW", "Blueprint"...) and bare
numeric values ("40%", "1").

The filter is data-calibrated: junk rows systematically expose the marker
either as the SPEAKER of the line, as the leading LABEL of the message
("Reward: 1 Warframe Slot") or as a bare value.  A marker used inside a
narrative sentence is legitimate and is kept ("That's new.", "I shall
reward you.", "trying to fix it.").
"""

from __future__ import annotations

import re

# Junk markers (lowercased): UI labels, patch-note phrases, loot/drop and
# game-mechanics vocabulary that never belongs to narrative dialogue.
_KIM_JUNK_MARKERS = (
    "known issue",
    "reward",
    "new",
    "complete quest",
    "banishing",
    "drop chance",
    "update",
    "fix",
    "blueprint",
)

# Whole-word search of any marker, with common inflections
# ("update"/"updated", "fix"/"fixed", "reward"/"rewards"...).
_JUNK_WORD_PATTERN = re.compile(
    r"\b(?:" + "|".join(
        re.escape(marker) + r"(?:s|d|ed|es|ing|en)?"
        for marker in _KIM_JUNK_MARKERS) + r")\b",
    re.IGNORECASE,
)
# Marker used as the leading token of a message (UI label position).
_JUNK_LABEL_PATTERN = re.compile(
    r"^\s*(?:" + "|".join(re.escape(marker)
                          for marker in _KIM_JUNK_MARKERS) + r")\b",
    re.IGNORECASE,
)
# Bare values only: "40%", "1", "0.5%".
_NUMERIC_ONLY_PATTERN = re.compile(r"^[\d\s.,%\-/()]+$")


def _is_leading_junk_label(message_text: str) -> bool:
    """True if a marker is used as a label at the start of the message.

    A label is a marker followed by nothing, a colon or a dash
    ("NEW", "Reward: ...").  A marker followed by narrative prose
    ("new me, i felt alive") is not a label.
    """
    match = _JUNK_LABEL_PATTERN.match(message_text)
    if match is None:
        return False
    remainder = message_text[match.end():].lstrip()
    return not remainder or remainder.startswith((":", "-"))


def is_dialogue_junk(speaker: str, message_text: str) -> bool:
    """True when the row cannot be narrative dialogue (drop silently)."""
    if _NUMERIC_ONLY_PATTERN.match(message_text.strip()):
        return True
    if _JUNK_WORD_PATTERN.search(speaker):
        return True
    return _is_leading_junk_label(message_text)


__all__ = ["is_dialogue_junk"]
