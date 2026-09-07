"""Helpers d'actifs : noms de fichier sûrs, validation, textes localisés."""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


def sanitize_asset_filename(asset: str) -> str:
    """Nom de fichier sûr pour le cache local (``!00_`` etc. ne sont pas
    valides sur tous les systèmes de fichiers)."""
    return asset.replace("!", "_").replace("/", "_").replace("\\", "_")


def is_valid_asset_payload(payload: bytes, category: str) -> bool:
    """Vrai si ``payload`` est un actif JSON exploitable.

    Miroir de ce que ``extract_entities`` accepte : soit un objet dont la
    clé ``category`` mène à une liste, soit une liste à la racine.  Une
    réponse tronquée, vide ou d'une structure inattendue est considérée
    invalide (à ne pas mettre en cache).
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("JSON illisible (%s)", error)
        return False
    entries = data.get(category) if isinstance(data, dict) else data
    return isinstance(entries, list)


def as_text(value, *, default: str | None = None) -> str | None:
    """Normalise un champ localisé (``str``, ``list[str]``, ``dict``, ``None``).

    Certains exports (mods de combos) portent ``description`` sous forme de
    liste de fragments — on la joint en une chaîne lisible.
    """
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        return text or default
    if isinstance(value, list):
        parts = [as_text(part) for part in value]
        joined = " ".join(part for part in parts if part)
        return joined or default
    if isinstance(value, dict):
        # ``{"name": ...}`` localisé : on reprend le premier champ texte.
        for key in ("name", "value", "0"):
            if key in value:
                return as_text(value[key], default=default)
        return default
    return str(value)