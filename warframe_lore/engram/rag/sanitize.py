"""Output trailing-padding sanitization (model artifacts).

Gemma-2 sometimes finishes a generation on a formatting artifact (a lone
asterisk, a stray hyphen or residual whitespace) that then pollutes the
final message on Discord or the HTTP answer.  ``strip_trailing_padding``
is applied just before the final emission — the WebSocket ``end`` frame
(``routers/roleplay.py``) and the non-streaming HTTP answer
(``RAGService.answer_with_sources``) — never mid-stream.

Since the persona is allowed MARKDOWN layout/emotion, only ORPHAN padding is
purged: a trailing run of ``*``/``-``/whitespace is removed unless it is a
markdown closer ATTACHED to the last word (``**mot**`` / ``*mot*`` / ``mot-``
are preserved).
"""

from __future__ import annotations

import re

# Trailing asterisks, hyphens and whitespace, all the way to the end of the
# generation.  A ``**mot**``-style closer survives; a stray " *", " -" or a
# whitespace-only tail is dropped.
_TRAILING_JUNK = re.compile(r"[\*\-\s]+$")
_MARKDOWN_CLOSER = re.compile(r"[*\-_]{1,2}\Z")


def strip_trailing_padding(text: str) -> str:
    """Strips an ORPHAN trailing run of ``*``, ``-`` and whitespace chars.

    Markdown closers attached to the last word (``**mot**``, ``*mot*``,
    ``mot-``) are kept; a stray `` *``, `` -``, empty padding or a
    whitespace-only tail is removed.
    """
    if not text:
        return text
    match = _TRAILING_JUNK.search(text)
    if not match:
        return text
    tail = match.group(0)
    before = text[match.start() - 1] if match.start() else ""
    if before.isalnum() and _MARKDOWN_CLOSER.fullmatch(tail):
        return text
    return text[:match.start()]


__all__ = ["strip_trailing_padding"]
