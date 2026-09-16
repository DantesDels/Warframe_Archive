"""Output entry construction (factories).

The dataclasses themselves (``OutputEntry``, ``MegafileMetadata``) live
in ``output/models/``; this module exposes schema-compliant construction
(``canon_status`` field to segment canon vs player theories).
"""

from __future__ import annotations

from .models import CanonStatus, OutputEntry


def build_output_entry(
    page_title: str,
    category: str,
    touched: str | None,
    content_markdown: str,
    canon_status: CanonStatus,
    pageid: int | None,
    source_wiki_url: str,
    page_url: str | None = None,
) -> OutputEntry:
    """Builds an :class:`OutputEntry` conforming to the documented schema.

    ``source_wiki_url`` is the wiki base URL (e.g.
    ``https://wiki.warframe.com/wiki/``).  ``page_url`` overrides the
    base + title reconstruction with the canonical page URL (needed by the
    French wiki, whose stored title carries a ``(fr)`` suffix).
    """
    date_last_updated = (touched or "")[:10]  # YYYY-MM-DD
    source_page_url = page_url or (source_wiki_url + page_title.replace(" ", "_"))
    return OutputEntry(
        page_title=page_title,
        category=category,
        last_updated=date_last_updated,
        content_markdown=content_markdown,
        canon_status=canon_status,
        source=source_page_url,
        pageid=pageid,
    )
