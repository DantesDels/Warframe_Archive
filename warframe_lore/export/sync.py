"""Synchronisation des entités localisées vers la base (boucle async)."""

from __future__ import annotations

import logging

from .extract import extract_entities
from .fetch import fetch_asset, fetch_index

log = logging.getLogger(__name__)


async def sync_entities(
    client,
    manager,
    langs: tuple[str, ...] | None = None,
    force: bool = False,
) -> dict[str, int]:
    """Synchronise les entités localisées en base.

    Étapes : index par langue -> filtrage des catégories retenues ->
    téléchargement (cache) -> extraction -> upsert into
    ``game_entities_i18n``.

    Returns:
        ``{"entities": N, "assets": M, "skipped": K}`` — N lignes écrites,
        M actifs téléchargés/relus, K actifs manquants (404).
    """
    from warframe_lore.db.manager import SQLDatabaseManager

    if not isinstance(manager, SQLDatabaseManager):
        raise TypeError("manager doit être un SQLDatabaseManager connecté.")

    langs = tuple(langs) if langs else client.langs
    client.cache_dir.mkdir(parents=True, exist_ok=True)

    total_entities = 0
    assets_used = 0
    skipped = 0
    for lang in langs:
        assets = fetch_index(client, lang)
        for asset in assets:
            category = asset.split("_", 1)[0]
            if category not in client.categories:
                continue
            payload = fetch_asset(client, lang, asset, force=force)
            if payload is None:
                skipped += 1
                continue
            assets_used += 1
            entities = extract_entities(client.categories, lang,
                                        category, payload)
            if entities:
                written = await manager.upsert_game_entities(
                    [entity.as_tuple() for entity in entities])
                total_entities += written
                log.info("[%s] %s : %d entités.", lang, category, written)
    log.info("Synchronisation Public Export terminée : %d entités, "
             "%d actifs, %d en échec.", total_entities, assets_used, skipped)
    return {"entities": total_entities, "assets": assets_used,
            "skipped": skipped}