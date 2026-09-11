"""Page canon signals: resolved speculation + final status.

Mixin of ``Scraper``.  The page-level canon status is computed by
cross-referencing ``Category:Speculation`` with signals detected in the
body by the cleaner (``CleanOutput``).
"""

from __future__ import annotations

import logging
from typing import Callable

from ..output import CanonStatus

log = logging.getLogger("warframe_lore.scraper")


class CanonSignalsMixin:
    """Speculation category resolution + status merging."""

    async def _resolve_speculation_titles(self) -> None:
        """Expands ``Category:Speculation`` to know which pages are
        considered speculative by the wiki."""
        resolve_members: Callable[..., dict[str, set[str]]] = \
            self.source.resolve_categories
        mapping = resolve_members(["Speculation"])
        self._speculation_titles = mapping.get("Speculation", set())
        if self._speculation_titles:
            log.info("Category:Speculation resolved: %d speculative page(s)",
                     len(self._speculation_titles))

    def _page_canon_status(
        self,
        page_title: str,
        non_canon_detected_in_body: bool,
        canon_detected_in_body: bool,
    ) -> CanonStatus:
        """Computes a page's canon status (page level + inline signals).

        Priorities: a page listed in ``Category:Speculation`` OR containing
        an inline ``{{Speculation}}`` template -> speculation; otherwise canon.
        """
        page_level_speculative = page_title in self._speculation_titles
        inline_non_canon = non_canon_detected_in_body

        page_status = (
            CanonStatus.SPECULATION if page_level_speculative
            else CanonStatus.CANON
        )
        body_status = (
            CanonStatus.SPECULATION if inline_non_canon
            else CanonStatus.CANON
        )
        # merge_canon_status keeps the weakest status (highest priority):
        # a single speculative signal is enough to classify as spec.
        from ..output import merge_canon_status

        return merge_canon_status(page_status, body_status)
