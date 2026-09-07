"""Métadonnées légères de modification (calcul du delta)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TouchedInfo:
    """Information légère pour le calcul du delta (mode incrémental).

    C'est ce qui permet de ne re-télécharger que les pages modifiées sans
    avoir à récupérer leur contenu.
    """

    pageid: int | None
    title: str
    namespace: int = 0
    touched: str | None = None
    missing: bool = False