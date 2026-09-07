"""Pointeurs de navigation KIM à purger avant découpage en chunks.

Pointeurs en tête de ligne de dialogue (``> **{Continues/Same/Jump ...}``,
préfixés ``{If ...}``, ``> **>``, ``> >``) et pointeurs embarqués (fermés) :
artefacts du datamine à ne pas chunker.  ``{Convo. ends.}`` est volontairement
conservé (marqueur terminal du sim).
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
    """Purge les instructions de continuité/condition KIM du texte à découper."""
    text = _KIM_POINTER_LINE_CHUNK.sub("", markdown or "")
    text = _KIM_INLINE_NAV_CHUNK.sub("", text)
    text = _KIM_CONDITION_CHUNK.sub("", text)
    text = _KIM_POSITION_CHUNK.sub("", text)
    return re.sub(r"[ \t]+(?=\n)", "", text)