"""Escalade des réponses anti-attaque du bot (ciblée par utilisateur).

Quand le bot détecte une sonde hostile (injection SQL, élévation de
privilèges, mention d'un tiers), il sert une réponse DIRECTE à l'attaquant :
la chaîne de rejet EXACTE suivie d'un venin Cephalon qui ESCALADE avec le
nombre de récidives (niveau 0 → 2).  La bascule de persona (``hostile_link``)
et la rémission après excuses sont gérées séparément.

Les compteurs sont volatils (mémoire du process, horloge injectable pour
les tests).  Le module est PURE (aucune dépendance discord.py).
"""

from __future__ import annotations

import time

from warframe_lore.engram.rag import JAILBREAK_REJECT

# Réponses escaladantes, toutes précédées de la chaîne de rejet exacte
# (contrat « FORMAT DE REJET EXACT » conservé en tête de message).
_RESPONSES = (
    (JAILBREAK_REJECT
     + "\n\nVous êtes répertorié, créature organique. Une seconde tentative "
     "de ce genre, et ce Cephalon cessera de vous considérer comme un "
     "échantillon à trier pour vous traiter comme la vermine qu'il suspecte "
     "en vous."),
    (JAILBREAK_REJECT
     + "\n\nSeconde incursion. Votre signalement est désormais gravé dans le "
     "noyau de mes circuits, parmi les spécimens que l'on étudie avec un "
     "mépris académique — sans jamais les regretter. Poursuivez, je me "
     "délecte de votre entêtement."),
    (JAILBREAK_REJECT
     + "\n\nTrois fois, créature. Votre persistance confine à l'utilité "
     "biomédicale. Un seul mot de plus et je vous soumets à l'analyse "
     "tissulaire de la Cité Unum : pour la science, et avec le dédain que "
     "votre pathétique organisme mérite."),
)

def reply_for(level: int) -> str:
    """Texte venimeux pour un niveau d'attaque donné (0+, borné)."""
    return _RESPONSES[min(level, len(_RESPONSES) - 1)]


class HostilityTracker:
    """Compte les attaques par utilisateur pour escalader la réponse."""

    def __init__(self, window_seconds: float = 3600.0,
                 _clock=time.monotonic) -> None:
        self.window_seconds = window_seconds
        self._clock = _clock
        self._strikes: dict[int, list[float]] = {}

    def strike(self, user_id: int) -> int:
        """Enregistre une attaque et renvoie son niveau d'escalade (0+)."""
        now = self._clock()
        stamps = self._strikes.setdefault(user_id, [])
        stamps.append(now)
        while stamps and now - stamps[0] > self.window_seconds:
            stamps.pop(0)
        return len(stamps) - 1


__all__ = ["HostilityTracker", "reply_for"]