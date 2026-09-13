"""Concepteur (creator) pseudonym detection.

A non-Creator member citing the Concepteur's pseudo — any casing or CamelCase
fragment ("dantes", "Dels", "DANTEs" from "DantesDels") — feeds the persona
jealousy directive instead of the lore archives.  Pure string work: the raw
snowflake is never involved here.
"""

from __future__ import annotations

import re

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-zà-ÿ])(?=[A-ZÀ-Ý])")


def creator_pseudo_variants(display: str) -> list[str]:
    """Canonical spellings derived from the Concepteur's display name.

    "DantesDels" -> ["dantesdels", "dantes", "dels"]: the head is the fragment
    before the first CamelCase boundary, the tail the fragment after it.
    """
    if not display:
        return []
    parts = _CAMEL_BOUNDARY.split(display)
    variants = [display.lower()]
    if parts:
        head = parts[0].lower()
        tail = parts[-1].lower()
        if head and head not in variants:
            variants.append(head)
        if len(parts) > 1 and tail and tail != head:
            variants.append(tail)
    return variants


def creator_mentioned(text: str, display: str) -> str | None:
    """Return the pseudo spelling an organic just cited, else ``None``.

    Case-insensitive whole-word match on each derived variant.  The canonical
    display name is preferred for the full spelling; derived forms are
    title-cased so the injected directive reads naturally.
    """
    if not display:
        return None
    for variant in creator_pseudo_variants(display):
        if re.search(rf"\b{re.escape(variant)}\b", (text or ""),
                     re.IGNORECASE):
            if variant == display.lower():
                return display
            return variant[:1].upper() + variant[1:]
    return None


__all__ = ["creator_mentioned", "creator_pseudo_variants"]
