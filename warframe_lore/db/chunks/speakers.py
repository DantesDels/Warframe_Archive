"""KIM dialogue speakers: line detection and chunk metadata.

Single responsibility: recognise a real KIM speaker on a ``> **Name:** text``
line and build the ``metadata["speakers"]`` list of a dialogue chunk.  Pure
functions, shared by the dialogue splitter — no chunking logic here.
"""

from __future__ import annotations

import re
from typing import Any

# KIM dialogue line: '> **Amir:** text' (the ':' is INSIDE the bold:
# '**' + 'Amir:' + '**').  We capture the speaker name.
_BLOCKQUOTE_SPEAKER_PATTERN = re.compile(
    r"^>\s*\*\*(?P<speaker>[^*:]+?):\*\*\s*")

# Tags, navigation and branch markers: never part of a character name.
_NON_NAME_MARKERS = ("*", "_", "]", "}", "(", "[", ">")
_SENTENCE_PUNCTUATION = (".", ",", "?", "!")
MAX_SPEAKER_LENGTH = 24


def speakers_metadata(speakers: list[str]) -> dict[str, Any]:
    """Builds the ``metadata`` dict of a dialogue chunk.

    Returns ``{}`` if there is no real speaker (preamble / non-dialogue
    notes); otherwise ``{"speakers": [unique names, order of appearance]}``.
    """
    unique_speakers = list(dict.fromkeys(speakers))
    if not unique_speakers:
        return {}
    return {"speakers": unique_speakers}


def line_speaker(line: str) -> str | None:
    """Extracts the speaker name from a ``> **Name:**`` dialogue line.

    Strict filter: a real KIM speaker is a short proper name without special
    punctuation or navigation tag (``(Jump …``, ``[Jump``, ``> …``).  Dialogue
    options and KIM page annotations are not speakers.
    """
    match = _BLOCKQUOTE_SPEAKER_PATTERN.match(line.strip())
    if match is None:
        return None
    candidate = match.group("speaker").strip()
    if not candidate:
        return None
    if any(marker in candidate for marker in _NON_NAME_MARKERS):
        return None
    # A real character name starts with an uppercase letter, is short and
    # contains no sentence punctuation.
    if not (candidate[0].isalpha() and candidate[0].isupper()):
        return None
    if len(candidate) > MAX_SPEAKER_LENGTH:
        return None
    if any(character in candidate for character in _SENTENCE_PUNCTUATION):
        return None
    return candidate


__all__ = ["line_speaker", "speakers_metadata"]
