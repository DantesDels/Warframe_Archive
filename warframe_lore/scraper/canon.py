"""Signaux canon d'une page : resolved spéculation + statut final.

Mixin de ``Scraper``.  Le statut canon au niveau page est calculé par
recoupement de ``Category:Speculation`` et des signaux détectés dans le
corps par le cleaner (``CleanOutput``).
"""

from __future__ import annotations

import logging
from typing import Callable

from ..output import CanonStatus

log = logging.getLogger("warframe_lore.scraper")


class CanonSignalsMixin:
    """Résolution de la catégorie spéculative + fusion des statuts."""

    async def _resolve_speculation_titles(self) -> None:
        """Développe la ``Category:Speculation`` pour connaître les pages
        considérées comme conjecturales par le wiki."""
        resolve_members: Callable[..., dict[str, set[str]]] = \
            self.source.resolve_categories
        mapping = resolve_members(["Speculation"])
        self._speculation_titles = mapping.get("Speculation", set())
        if self._speculation_titles:
            log.info("Category:Speculation résolue : %d page(s) conjecturales",
                     len(self._speculation_titles))

    def _page_canon_status(
        self,
        page_title: str,
        non_canon_detected_in_body: bool,
        canon_detected_in_body: bool,
    ) -> CanonStatus:
        """Calcule le statut canon d'une page (niveau page + signaux inline).

        Priorités : une page listée dans ``Category:Speculation`` OU qui
        contient un template ``{{Speculation}}`` en ligne -> speculation ;
        sinon canon.
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
        # merge_canon_status retient le statut le plus faible (priorité la
        # plus haute) : un seul signal spéculatif suffit à classer en spec.
        from ..output import merge_canon_status

        return merge_canon_status(page_status, body_status)