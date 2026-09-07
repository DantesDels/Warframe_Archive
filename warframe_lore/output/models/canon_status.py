"""Statut canonique d'une page de lore (canon vs conjecture)."""

from __future__ import annotations

from enum import Enum


class CanonStatus(str, Enum):
    """Statut canonique d'une page.

    Values:
        canon: lore officiel établi (descriptions de jeu, quêtes, dialogues).
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
    return max(present, key=lambda s: _CANON_PRIORITY[s])