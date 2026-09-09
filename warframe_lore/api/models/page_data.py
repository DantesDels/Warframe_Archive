"""Raw content of a source page (pre-cleaning)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageData:
    """Raw content of a page (before any cleaning).

    ``content`` stays in the source's native format (e.g. Wikitext for the
    wiki).  The cleaner knows which format to process based on the source.
    """

    pageid: int
    title: str
    namespace: int
    touched: str | None = None
    last_revision_timestamp: str | None = None
    url: str = ""
    content: str = ""