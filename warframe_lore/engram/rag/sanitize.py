"""Output trailing-padding sanitization (model artifacts).

Gemma-2 sometimes finishes a generation on a formatting artifact (a lone
asterisk, a stray hyphen or residual whitespace) that then pollutes the
final message on Discord or the HTTP answer.  ``strip_trailing_padding``
is applied just before the final emission — the WebSocket ``end`` frame
(``routers/roleplay.py``) and the non-streaming HTTP answer
(``RAGService.answer_with_sources``) — never mid-stream.
"""

from __future__ import annotations

import re

# Trailing asterisks, hyphens and whitespace, all the way to the end of the
# generation.  Content beyond the tail (``a * b *``) is preserved: only an
# EMPTY tail (nothing but ``*`` / ``-`` / whitespace) is stripped.
_TRAILING_PADDING = re.compile(r"[\*\-\s]+$")


def strip_trailing_padding(text: str) -> str:
    """Strips a trailing run of ``*``, ``-`` and whitespace characters."""
    if not text:
        return text
    return _TRAILING_PADDING.sub("", text)


__all__ = ["strip_trailing_padding"]