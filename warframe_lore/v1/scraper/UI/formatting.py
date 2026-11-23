"""Display helpers for French UI labels and common formatting."""

from __future__ import annotations

from typing import Any

KIND_LABELS = {
    "website": "Site web",
    "api": "API",
    "wiki": "Wiki",
    "document": "Document",
    "local_directory": "Dossier local",
}
SOURCE_STATUS_LABELS = {
    "approved": "Actif",
    "candidate": "Candidat",
    "rejected": "Rejeté",
    "disabled": "Désactivé",
    "active": "Actif",
    "suspended": "Suspendu",
    "blacklisted": "Blacklisté",
    "proposed": "Proposé",
}
UNIVERSE_STATUS_LABELS = {
    "actif": "Actif",
    "en curation": "En curation",
}
RUN_STATUS_LABELS = {
    "done": "Terminé",
    "running": "En cours",
    "failed": "Échoué",
    "pending": "En attente",
}


def label(mapping: dict[str, str], value: str) -> str:
    """Return a French label or the raw value as a fallback."""
    return mapping.get(value, value)


def display_kind(value: str) -> str:
    return label(KIND_LABELS, value)


def display_source_status(value: str) -> str:
    return label(SOURCE_STATUS_LABELS, value)


def display_universe_status(value: str) -> str:
    return label(UNIVERSE_STATUS_LABELS, value)


def display_run_status(value: str) -> str:
    return label(RUN_STATUS_LABELS, value)


def coerce_score(value: Any) -> float:
    """Return a bounded 0..1 score, tolerating legacy malformed values."""
    try:
        return max(0.0, min(1.0, float(value or 0)))
    except (TypeError, ValueError, OverflowError):
        return 0.0


def display_percent(score: float | int) -> str:
    """Format a 0..1 score or 0..100 value as a percentage string."""
    value = float(score)
    if 0 <= value <= 1:
        value *= 100
    return f"{value:.0f} %"
