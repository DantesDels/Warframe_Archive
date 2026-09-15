"""Truncation of page footer noise (navboxes, categories, update history)."""

from __future__ import annotations

import re

# Exact metadata lines rendered as raw text by Wiki navboxes,
# typically at page bottom: ``Quotes`` then ``quotesnav``, or ``Sentient``
# for pages related to Sentients.
_FOOTER_METADATA_LINE = re.compile(r"^(?:quotesnav|quotes|sentient)$", re.I)
# Update history: ``Update 27.2``... (noise, non-canon) -- the structured
# format ``[{version, notes}]`` is already extracted elsewhere (patch notes).
_HISTORY_LINE = re.compile(r"^update\s+\d+", re.I)


def cut_footer_noise(markdown_text: str) -> str:
    """Truncates everything after the first footer line.

    Once a line exactly matches a navbox/category keyword
    (``quotesnav``, ``Quotes``, ``Sentient``) or an ``Update N`` history,
    all remaining text is scrape noise (navboxes, categories):
    we ignore and truncate.  Matches on exact line (single occurrence).
    """
    lines = markdown_text.split("\n")
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        if _FOOTER_METADATA_LINE.match(stripped) or _HISTORY_LINE.match(stripped):
            # Index 0 = header artifact (e.g. ``Sentient`` above a
            # ``Damage/Sentient`` page): truncating the whole page would be worse.
            if i == 0:
                return markdown_text
            return "\n".join(lines[:i]).rstrip() + "\n"
    return markdown_text


__all__ = ["cut_footer_noise"]
