"""Localized entity synchronization to the database (async loop)."""

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
    """Synchronizes localized entities to the database.

    Steps: per-language index -> category filtering ->
    download (cache) -> extraction -> upsert into
    ``game_entities_i18n``.

    Returns:
        ``{"entities": N, "assets": M, "skipped": K}`` -- N rows written,
        M assets downloaded/reused, K missing assets (404).
    """
    from warframe_lore.db.manager import SQLDatabaseManager

    if not isinstance(manager, SQLDatabaseManager):
        raise TypeError("manager must be a connected SQLDatabaseManager.")

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
                log.info("[%s] %s: %d entities.", lang, category, written)
    log.info("Public Export sync complete: %d entities, "
             "%d assets, %d skipped.", total_entities, assets_used, skipped)
    return {"entities": total_entities, "assets": assets_used,
            "skipped": skipped}
