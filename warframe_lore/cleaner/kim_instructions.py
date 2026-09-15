"""KIM dialogue instructions (wiki): pointers and navigation markers.

``{Convo. ends.}`` is intentionally kept (terminal marker consumed by
the server flow-chart); continuation/conditions/position pointers are
removed from served Markdown and RAG model chunks.
"""

from __future__ import annotations

import re

# KIM navigation instruction at the head of a dialogue line (wiki pointers):
#   ``> **{Continues as above from "X:** ..."`` | ``> **{Same as below:}**``
#   | ``> **{Jump above to "X:** ..."`` | ``> **{Continue with convo below:}**``
#   | ``> **{Goes the same as above, from:}**``
# and variants prefixed by one or more conditions
# ``> **{If ...} {If ...} {Continues ...}`` or ``> **> {...`` / ``> > {...``.
# The navigation keyword ALWAYS lives inside a brace; closing brace
# is not required.  ``{If ...}`` and ``{Convo. ends.}`` do not
# contain these keywords -> not affected.
_KIM_POINTER_LINE = re.compile(
    r"(?im)^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")
# Inline (closed) navigation pointer inside a message: removed from text,
# unless the content refers to a terminal ``{... ends ...}``
# (e.g. ``{Convo. Ends. Followed by jumpscare image.}``).
_KIM_INLINE_NAV = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)
_KIM_POSITION_MARK = re.compile(r"\{P\d+\}", re.I)
_KIM_CONDITION_MARK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)
_KIM_ARTIFACT_LINE = re.compile(r"^\s*>?\s*\*{1,2}\s*$")


def strip_kim_dialog_instructions(markdown: str) -> str:
    """Permanently removes KIM continuation instructions (``{...}``).

    Purged: continuation pointer lines, branch conditions
    (``{If ...}``) and position markers (``{P1}`` ...).  They must not
    appear in the UI or in RAG model chunks.
    """
    if not markdown:
        return markdown
    text = _KIM_POINTER_LINE.sub("", markdown)
    text = _KIM_INLINE_NAV.sub("", text)
    text = _KIM_CONDITION_MARK.sub("", text)
    text = _KIM_POSITION_MARK.sub("", text)
    text = _KIM_ARTIFACT_LINE.sub("", text)
    # Residue from removing an ``{If ...}`` between ``> **`` and the name:
    # ``> ** Arthur:**`` -> ``> **Arthur:**`` (opening only, never the
    # closing pair ``** text``).
    text = re.sub(r"(?m)(^\s*[*>\-]+\s*)\*\*[ \t]+(?=\w)", r"\1**", text)
    text = re.sub(r"[ \t]+(?=\n)", "", text)
    return text


__all__ = ["strip_kim_dialog_instructions"]
