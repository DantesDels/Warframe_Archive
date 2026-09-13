"""KIM navigation pointers to purge before chunking.

Pointers at the start of a dialogue line (``> **{Continues/Same/Jump ...}``,
prefixed with ``{If ...}``, ``> **>``, ``> >``) and embedded (closed)
pointers: datamine artifacts that must not be chunked.  ``{Convo. ends.}``
is intentionally kept (terminal marker of the sim).
"""

from __future__ import annotations

import re

_KIM_POINTER_LINE_CHUNK = re.compile(
    r"(?im)^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")
_KIM_INLINE_NAV_CHUNK = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)
_KIM_POSITION_CHUNK = re.compile(r"\{P\d+\}", re.I)
_KIM_CONDITION_CHUNK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)


def strip_kim_chunk_meta(markdown: str) -> str:
    """Purges the KIM continuity/condition instructions from the text to split."""
    text = _KIM_POINTER_LINE_CHUNK.sub("", markdown or "")
    text = _KIM_INLINE_NAV_CHUNK.sub("", text)
    text = _KIM_CONDITION_CHUNK.sub("", text)
    text = _KIM_POSITION_CHUNK.sub("", text)
    return re.sub(r"[ \t]+(?=\n)", "", text)
