"""KIM reference machinery: text cleanup & jump-reference resolution.

Single responsibility: recognise and purge wiki navigation instructions
(branch conditions, position markers, inline pointers), normalise lines for
reference matching, and resolve the jump/extension annotations of the
original KIM scripts (``[Continues as above, from: "X"]`` etc.).
"""

from __future__ import annotations

import re

# Inline navigation pointer embedded in the middle of a message (closed): ``{...}``
# containing a navigation keyword -> removed from message text.  Requires
# closing brace to never truncate the line, and excludes terminal markers
# ``{... ends ...}`` (e.g.: ``{Convo. Ends. Followed by
# jumpscare image.}``) that might contain ``jump`` or ``same``.
_KIM_INLINE_NAV = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)

# Branch conditions (``{If ...}``) and position markers (``{P1}``…):
# purged from message text (speaker/speech).
_KIM_CONDITION_MARK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)
_KIM_POSITION_MARK = re.compile(r"\{P\d+\}", re.I)

# Residual quotes to strip from the start/end of a dialogue line.
_DIALOGUE_STRIP_CHARS = ' "”«»'

# Terminal marker for a KIM conversation (``{Convo ends.}`` and variants).
_CONVO_ENDS = re.compile(r"\{[Cc]onvo[^}\n]{0,16}ends\.?\}", re.I)
_JUMP_ABOVE = re.compile(
    r"\[(?:Continues|Same) as above[,:]?\s*from:?\s*\"(?P<ref>[^\"]*)\",?\s*\]", re.I)
_JUMP_BELOW = re.compile(r"\[Goes the same as below choice\]", re.I)
_ANNOT_PAREN = re.compile(r"^\(\s*(?P<body>.*)\s*\)$", re.S)
_JUMP_QUOTED = re.compile(
    r"conversation\s+continues\s+as\s+below[,:]?\s+starting\s+at\s+"
    r"\"(?P<below>[^\"]*)\""
    r"|\bsame\s+as\s+above[,:]?\s+from:?\s+\"(?P<above>[^\"]*)\"",
    re.I)
_JUMP_VAGUE = re.compile(
    r"\[goes\s+(?:the\s+)?same\s+as\s+(?:above|below(?:\s+choice)?|choice)\]",
    re.I)


def clean_kim_text(text: str) -> str:
    """Remove KIM navigation instructions from text.

    Purges branch conditions (``{If ...}``), position markers
    (``{P1}`` … ``{P5}``) and closed inline navigation pointers
    (``{Continues ...}``, ``{Same ...}``, ``{Jump ...}``, ``{Goes ...}``)
    embedded in the message.  Stage directions (``{Smile!}``, …) and
    ``{Convo. ends.}`` (terminal) are kept.
    """
    cleaned = _KIM_INLINE_NAV.sub("", text or "")
    cleaned = _KIM_CONDITION_MARK.sub("", cleaned)
    cleaned = _KIM_POSITION_MARK.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def is_player_speaker(speaker: str) -> bool:
    """True if the speaker is the player character (Tenno)."""
    return bool(re.search(
        r"operator|player|\btenno\b|drifter|walley|indifference", speaker, re.I))


def normalise_dialogue_ref(text: str) -> str:
    """Canonical form of a line to resolve jump references."""
    t = text.casefold()
    t = re.sub(r"\{p\s*\d+\}", " ", t)          # {P1}/{P2}: page pauses
    t = re.sub(r"\{[^{}]*\}", " ", t)           # {…} (conditions, {Convo ends.})
    t = re.sub(r"^>+\s*", "", t)                # "> Ah" -> "Ah"
    t = re.sub(r"[.!?]+$", "", t)               # trailing punctuation
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalise_ref(text: str) -> str:
    """Normalise a string for reference resolution (jumps)."""
    out = _CONVO_ENDS.sub("", text)
    out = re.sub(r"\s+", " ", out).strip().strip("*").strip()
    return out.lower()[:120]


def slug_for_id(text: str) -> str:
    """Simple ASCII identifier slug (alphabetic) from text."""
    return re.sub(r"[^A-Za-z0-9]+", "", text)
