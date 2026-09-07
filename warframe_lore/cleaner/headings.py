"""Titres Wiki -> Markdown : reflow ``== X ==`` et abaissement des profonds."""

from __future__ import annotations

import re

_HEADING_WIKI = re.compile(r"^(={2,})(.*?)(?:={2,}|$)", re.MULTILINE)


def reflow_headings_to_markdown(wikitext: str) -> str:
    """Convertit ``== Titre ==`` en ``## Titre`` (niveau limité à 6)."""

    def _heading_replacement(match: re.Match) -> str:
        heading_equals_count = match.group(1).count("=")
        heading_title = match.group(2).strip()
        markdown_level = min(heading_equals_count, 6)
        return f"\n\n{'#' * markdown_level} {heading_title}\n"

    return _HEADING_WIKI.sub(_heading_replacement, wikitext)


def normalise_deep_headings(markdown_text: str) -> str:
    """Abaisse les titres résiduels profonds (``#### X``) en titres ``## X``.

    Le Wiki utilise des titres profonds (``==== Leaving without purchasing ====``)
    pour découper les transcriptions ; ce sont de véritables titres de section,
    pas du bruit.  On reflète le niveau à un titre lisible ``##``.
    """
    return re.sub(r"^#{3,}\s*", "## ", markdown_text, flags=re.MULTILINE)


__all__ = ["reflow_headings_to_markdown", "normalise_deep_headings"]