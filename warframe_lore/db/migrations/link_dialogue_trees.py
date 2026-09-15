"""One-shot ``parent_message_id`` linker for the two dialogue tables.

Reads every dialogue row, groups it by ``(wiki_page_id, chapter, context)``,
applies the branching heuristic of :func:`tree_link.link_dialogue_parents`,
and persists the computed adjacency-list edges via executemany updates.

The ``dialogue_tree_graph.sql`` migration must be applied first (the
``parent_message_id`` columns must exist).

Usage (project root):
    python -m warframe_lore.db.migrations.link_dialogue_trees [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict

from sqlalchemy import bindparam, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import SQLDatabaseManager
from ...db.models import GameDialogue, KimDialogue
from ...engram.config import EngramConfig
from .tree_link import link_dialogue_parents

log = logging.getLogger("warframe_lore.db.migrations.link_trees")

LOCK_KEY = 0x4449414C  # "DIAL"


async def _link_table(session: AsyncSession, model, table_name: str) -> int:
    """Compute and persist ``parent_message_id`` for every row of a table."""
    rows = (
        await session.execute(
            select(
                model.id,
                model.wiki_page_id,
                model.chapter,
                model.context,
                model.message_order,
                model.player_choice,
            )
        )
    ).all()
    groups: dict[tuple, list[tuple[int, int, bool]]] = defaultdict(list)
    for row in rows:
        key = (row.wiki_page_id, row.chapter, row.context)
        groups[key].append((row.message_order, row.id, row.player_choice))
    parents: dict[int, int | None] = {}
    for group_rows in groups.values():
        parents.update(link_dialogue_parents(group_rows))
    statement = (
        model.__table__.update()
        .where(model.__table__.c.id == bindparam("row_id"))
        .values(parent_message_id=bindparam("parent_id"))
    )
    params = [
        {"row_id": node_id, "parent_id": parent}
        for node_id, parent in parents.items()
    ]
    if params:
        await session.execute(statement, params)
    log.info("Linked %d %s row(s).", len(params), table_name)
    return len(params)


async def run(dry_run: bool = False) -> None:
    """Link both dialogue tables; log the updated counts."""
    cfg = EngramConfig.load()
    manager = SQLDatabaseManager(cfg.database_url)
    await manager.connect()
    try:
        async with manager.advisory_lock(LOCK_KEY):
            sessions = manager._require_session_factory()
            if dry_run:
                async with sessions() as session:
                    kim = await _link_table(session, KimDialogue, "kim_dialogues")
                    game = await _link_table(session, GameDialogue, "game_dialogues")
                    await session.rollback()
            else:
                async with sessions() as session:
                    kim = await _link_table(session, KimDialogue, "kim_dialogues")
                    game = await _link_table(session, GameDialogue, "game_dialogues")
                    await session.commit()
            log.info("%s: %d kim + %d game dialogue row(s).",
                     "Dry-run" if dry_run else "Linked", kim, game)
    finally:
        await manager.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute parent_message_id for both dialogue tables."
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not persist.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    asyncio.run(run(args.dry_run))


__all__ = ["LOCK_KEY", "main", "run"]

if __name__ == "__main__":
    main()
