"""Extraction d'entités localisées depuis un actif JSON."""

from __future__ import annotations

import json
import logging

from .assets import as_text
from .models import GameEntity

log = logging.getLogger(__name__)


def extract_entities(
    categories: dict[str, str],
    lang: str,
    category: str,
    payload: bytes,
) -> list[GameEntity]:
    """Extrait :class:`GameEntity` d'un manifest.

    Le fichier JSON est ``{"Export<Category>": [ ... ]}`` ; chaque entrée
    porte ``uniqueName``, ``name`` (localisé) et ``description`` (localisé).
    Les entrées sans ``uniqueName`` sont ignorées.
    """
    entity_type = categories[category]
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("JSON illisible pour %s/%s : %s", category, lang, error)
        return []
    entries = data.get(category) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        log.warning("Structure inattendue pour %s/%s (type %s).",
                    category, lang, type(entries).__name__)
        return []
    entities = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        entity_id = item.get("uniqueName")
        if not entity_id:
            continue
        entities.append(GameEntity(
            entity_id=str(entity_id),
            entity_type=entity_type,
            lang=lang,
            name=as_text(item.get("name"), default="") or "",
            description=as_text(item.get("description")),
        ))
    return entities