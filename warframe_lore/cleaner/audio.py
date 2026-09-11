"""Removal of Wiki audio file names (.ogg/.mp3/.wav).

File names left by audio players in quest transcriptions:
    * unique token          -> ``LeekterSlippery.ogg``, ``DCodexA00010Silvana_en.ogg``
    * code created in two   -> ``DWraithQM1CrpArrive0060RJCephalon en.ogg``
      parts (locale en)       ``DThroneRoom0050Erra en.mp3`` ``BbPainAmbulas00020 en.ogg``
Note: ``[a-z0-9_]`` with re.IGNORECASE also accepts uppercase.
"""

from __future__ import annotations

import re

_AUDIO_LOCALE_TOKEN = re.compile(
    r"\b[a-z0-9_]+[ \t]{1,3}en\.(?:ogg|mp3)\b", re.IGNORECASE)
_AUDIO_FILE_TOKEN = re.compile(r"\b[\w-]+\.(?:ogg|mp3|wav)\b", re.IGNORECASE)


def strip_audio_filenames(markdown: str) -> str:
    """Removes Wiki audio metadata (file names .ogg/.mp3/.wav).

    Pass 1: the code created followed by locale is removed in one go
    (``DThroneRoom0050Erra en.mp3``), otherwise the orphan locale ``en.ogg``
    would remain stuck to the text.
    Pass 2: any remaining standalone ``Word.ogg/.mp3/.wav`` token.
    Pass 3: lines that became empty or reduced to a single speaker
    (e.g. ``> **Angel's song:**`` after file removal) are removed,
    regardless of origin.
    """
    if not markdown:
        return markdown
    text = _AUDIO_LOCALE_TOKEN.sub("", markdown)
    text = _AUDIO_FILE_TOKEN.sub("", text)
    lines_out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        body = stripped[1:].strip() if stripped.startswith(">") else stripped
        # Residual speaker alone on its line: ``> **Angel's song:**``
        body = re.sub(r"^\*\*[^*]*\*\*\s*:?\s*$", "", body)
        # Residual label alone: ``Angel's song:``
        body = re.sub(
            r"^[A-Za-z][\w''']*(?:[ -][A-Za-z][\w''']*)*\s*:\s*$", "", body)
        # Markdown cruft (``*`` ``_`` ``>`` ``:`` ``"`` ``-`` ...) without text.
        body = re.sub(r"[>*_:.\"''\-\u2013\u2014]", "", body).strip()
        if body:
            lines_out.append(line)
    return "\n".join(lines_out)


__all__ = ["strip_audio_filenames"]
