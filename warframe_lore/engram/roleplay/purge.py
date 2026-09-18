"""Canonical end-of-part text: one closing line, clean trailing artifacts.

A narrating model sometimes appends the mandatory closing sentence twice
(playtest: the page-turning invitation echoed verbatim), pads the tail with
markdown rollovers, or answers with ONLY the closing line — a degenerate
part carrying no narration at all (playtest: a standalone invitation posted
as its own part).  This module turns the end of a part into its canonical
form BEFORE the answer leaves the server: trailing padding stripped, trailing
repeats merged into ONE occurrence, a closing-only answer replaced by the
archivist closing, the "nothing more to say" stop — and the sentence that
matches the cursor state FORCED to close the part, because
``story_more`` (the server's pagination truth) decides which one is served.
"""

from __future__ import annotations

from ..rag import strip_trailing_padding
from .prompt import STORY_COMPLETE_SENTENCE, STORY_PAGINATION_SENTENCE

__all__ = ["canonical_story_closing", "collapse_repeated_closing",
           "purge_story_closing"]


def collapse_repeated_closing(text: str, sentence: str) -> str:
    """Collapse repeated TRAILING occurrences of the mandatory closing line.

    Only the trailing repeats (whitespace-separated) are merged into ONE
    occurrence: the EARLIEST one keeps its place, so the spacing before it
    is preserved and nothing that precedes it is touched.  An occurrence
    followed by more narration is the model's own structure and stays.
    Trailing whitespace of the original text is preserved.
    """
    stripped = text.rstrip()
    pos = len(stripped)
    count = 0
    first_start = 0
    while pos > 0:
        start = stripped.rfind(sentence, 0, pos)
        if start < 0 or stripped[start + len(sentence):pos].strip():
            break
        first_start = start
        count += 1
        pos = start
        while pos > 0 and stripped[pos - 1].isspace():
            pos -= 1
    if count <= 1:
        return text
    return stripped[:first_start] + sentence + text[len(stripped):]


def purge_story_closing(text: str) -> str:
    """End-of-part canonical text: no trailing padding, ONE closing line.

    A response reduced to ONLY the closing sentence means the model had no
    narration left to add (degenerate part): the archivist closing replaces
    it, the "nothing more to say" end.  Applied BEFORE the answer leaves
    the server, so the token the client renders holds the same single
    closing line as the ``end`` frame.
    """
    text = strip_trailing_padding(text)
    for closing in (STORY_PAGINATION_SENTENCE, STORY_COMPLETE_SENTENCE):
        text = collapse_repeated_closing(text, closing)
    if text.strip() in (STORY_PAGINATION_SENTENCE, STORY_COMPLETE_SENTENCE):
        return STORY_COMPLETE_SENTENCE
    return text


def canonical_story_closing(text: str, more: bool) -> str:
    """Force the end-of-part closing that matches the cursor state.

    ``story_more`` is authoritative on the server (the dossier pagination):
    while unseen fragments remain, the served part must close with the
    *invitation*; once the dossier is drained, it must close with the
    *archivist stop*.  A model tail that is missing, wrong or stacked is
    replaced by that ONE canonical sentence — a live part can never end
    without the truthful closing, not even a short "nothing left" answer
    served mid-dossier (playtest: 11-word parts closing with neither
    sentence while ``story_more`` was still True).
    """
    if text.strip() == STORY_COMPLETE_SENTENCE:
        return text                    # degenerate stop, already canonical
    expected = (STORY_PAGINATION_SENTENCE if more
                else STORY_COMPLETE_SENTENCE)
    text = strip_trailing_padding(text).rstrip()
    while True:
        for closing in (STORY_PAGINATION_SENTENCE, STORY_COMPLETE_SENTENCE):
            if text.endswith(closing):
                text = text[: -len(closing)].rstrip()
                break
        else:
            break
    return text + " " + expected if text else expected
