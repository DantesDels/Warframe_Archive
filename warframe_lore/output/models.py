"""Modèles de la couche Output (schéma JSON documenté).

Définit le contrat de sortie exposé aux consommateurs (agents IA,
notebooks RAG, humains).  Chaque entrée porte un champ ``canon_status``
qui permet de segmenter structurellement le lore officiel des théories
des joueurs (exigence canon/non-canon).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CanonStatus(str, Enum):
    """Statut canonique d'une page.

    Values:
        canon: lore officiel établi (descriptions de jeu, quêtes, dialogues.
        speculation: conjecture signalée par le wiki (template/catégorie
            ``{{Speculation}}``) — à ne PAS prendre comme source primaire.
        community_theory: théorie des joueurs (ex: flair Reddit) — jamais
            au même niveau que le canon.
    """

    CANON = "canon"
    SPECULATION = "speculation"
    COMMUNITY_THEORY = "community_theory"


# Ordre de priorité : si plusieurs signaux coexistent, le plus faible l'emporte
# (une page peut contenir du canon ET une spec ; le RAG doit savoir qu'il y a
# du non-canon présent).
_CANON_PRIORITY: dict[CanonStatus, int] = {
    CanonStatus.CANON: 0,
    CanonStatus.SPECULATION: 1,
    CanonStatus.COMMUNITY_THEORY: 2,
}


def merge_canon_status(*statuses: CanonStatus | None) -> CanonStatus:
    """Combine des statuts canon en retenant le plus faible (le plus prudent).

    Exemple : une page canon qui contient un template {{Speculation}} en
    ligne -> statut final "speculation" (le lecteur doit être alerté).
    """
    present = [s for s in statuses if s is not None]
    if not present:
        return CanonStatus.CANON
    return min(present, key=lambda s: _CANON_PRIORITY[s])


@dataclass
class OutputEntry:
    """Une entrée du megafile de sortie (schéma JSON documenté)."""

    page_title: str
    category: str
    last_updated: str  # YYYY-MM-DD
    content_markdown: str
    canon_status: CanonStatus
    source: str = ""
    pageid: int | None = None
    extra: dict = field(default_factory=dict)

    def to_json_dict(self) -> dict:
        """Sérialise vers le dict conforme au schéma de sortie."""
        payload = {
            "page_title": self.page_title,
            "category": self.category,
            "last_updated": self.last_updated,
            "canon_status": self.canon_status.value,
            "content_markdown": self.content_markdown,
            "_source": self.source,
        }
        if self.pageid is not None:
            payload["_pageid"] = self.pageid
        payload.update(self.extra)
        return payload


@dataclass
class MegafileMetadata:
    """Métadonnées de tête d'un megafile JSON."""

    bucket_title: str
    generated_at: str
    total_pages: int
    source_api: str
    note: str = ""


def build_output_entry(
    page_title: str,
    category: str,
    touched: str | None,
    content_markdown: str,
    canon_status: CanonStatus,
    pageid: int | None,
    source_wiki_url: str,
) -> OutputEntry:
    """Construit une :class:`OutputEntry` selon le schéma documenté.

    ``source_wiki_url`` est l'URL de base du wiki (ex:
    ``https://wiki.warframe.com/wiki/``).
    """
    date_last_updated = (touched or "")[:10]  # YYYY-MM-DD
    source_page_url = source_wiki_url + page_title.replace(" ", "_")
    return OutputEntry(
        page_title=page_title,
        category=category,
        last_updated=date_last_updated,
        content_markdown=content_markdown,
        canon_status=canon_status,
        source=source_page_url,
        pageid=pageid,
    )