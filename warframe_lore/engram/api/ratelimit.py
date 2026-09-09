"""Limiteur de débit en mémoire (fenêtre glissante, par IP).

Défense anti-DDoS / anti-abuse de l'API ENGRAM : un débit excessif (boucle
d'attaque, demandes automatisées) est coupé en amont du LLM — HTTP 429 pour la
route `POST /v1/rag`, fermeture WS 1008 pour le terminal Roleplay.  Les seuils
viennent de la configuration ``ENGRAM_RATE_LIMIT_*`` ; la mémoire est
volatile (perte au redémarrage), le stockage reste limité au nombre de clés
actives.
"""

from __future__ import annotations

import time
from collections import deque


class SlidingWindowLimiter:
    """Autorise au plus ``max_events`` appels par ``window_seconds`` et par clé.

    Fenêtre glissante (pas de pics d'horloge) : les horodatages par clé sont
    conservés en deque et purgés des entrées expirées à chaque appel.
    """

    def __init__(self, max_events: int, window_seconds: float,
                 _clock=time.monotonic) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = _clock
        self._events: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        """Compte un appel si le quota le permet, sinon refuse (``False``)."""
        now = self._clock()
        dq = self._events.setdefault(key, deque())
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()
        if len(dq) >= self.max_events:
            return False
        dq.append(now)
        return True


__all__ = ["SlidingWindowLimiter"]