"""French execution labels shared by the desktop status panel."""

from __future__ import annotations

STATE_LABELS = {
    "idle": "Aucune exécution en cours.",
    "starting": "Préparation de l'exécution...",
    "running": "Exécution en cours",
    "busy": "Une exécution est déjà en cours.",
    "paused": "Exécution en pause.",
    "done": "Exécution terminée.",
    "cancelled": "Exécution annulée.",
    "error": "Erreur d'exécution.",
}

STATUS_LABELS = {
    "idle": "Prêt",
    "starting": "Exécution en cours",
    "running": "Exécution en cours",
    "busy": "Exécution déjà en cours",
    "paused": "Pause",
    "done": "Prêt",
    "cancelled": "Annulé",
    "error": "Erreur",
}

ACTIVE_STATES = frozenset({"starting", "running", "busy", "paused"})
