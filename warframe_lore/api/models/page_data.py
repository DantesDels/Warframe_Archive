"""Contenu brut d'une page de source (pré-nettoyage)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageData:
    """Contenu brut d'une page (avant tout nettoyage).

    ``content`` reste en format natif de la source (ex: Wikitext pour le
    wiki).  Le nettoyeur sait quel format traiter selon la source.
    """

    pageid: int
    title: str
    namespace: int
    touched: str | None = None
    last_revision_timestamp: str | None = None
    url: str = ""
    content: str = ""