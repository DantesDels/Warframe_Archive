"""Async coroutines and helpers behind the ``cephalon`` commands.

Single responsibility: the heavy lifting (SQL scopes, DB state reports,
delta plans, entity exports) referenced by the thin ``_cmd_*`` wrappers
in :mod:`warframe_lore.cli.commands`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from ..db import SQLDatabaseManager
from .support import (
    PROJECT_DEFAULT_DB_INIT_SQL,
    build_config,
    build_scraper,
)


@contextlib.asynccontextmanager
async def _manager_scope(database_url: str):
    """Connect/try/finally/close boilerplate shared by the SQL commands."""
    manager = SQLDatabaseManager(database_url)
    await manager.connect()
    try:
        yield manager
    finally:
        await manager.close()


async def _cmd_init_database_impl(database_url: str) -> None:
    async with _manager_scope(database_url) as manager:
        await manager.run_ddl_script(PROJECT_DEFAULT_DB_INIT_SQL)
    print(f"Database initialised from {PROJECT_DEFAULT_DB_INIT_SQL.name}.")


async def _cmd_diff_impl(args) -> dict:
    scraper = build_scraper(args)
    if scraper.db is not None:
        await scraper.db.connect()
    try:
        return await scraper.delta_plan(force=args.force)
    finally:
        if scraper.db is not None:
            await scraper.db.close()


async def _cmd_status_impl(args) -> None:
    config, _ = build_config(args)
    async with _manager_scope(config.database_url) as manager:
        stats = await manager.db_stats()

    def _fmt(dt) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "\u2014"

    print("Lore database state:")
    print(f"  Pages in database       : {stats['total_pages']}")
    print(f"  Chunks (RAG)            : {stats['total_chunks']}")
    print(f"  KIM dialogues           : {stats['total_kim_dialogues']}")
    print(f"  Sync records            : {stats['total_sync_records']}")
    print(f"  Last page created       : {_fmt(stats['last_page_created_at'])}")
    print(f"  Last page updated       : {_fmt(stats['last_page_updated_at'])}")
    print(f"  Last sync               : {_fmt(stats['last_sync_at'])}")

    if stats["total_by_canon"]:
        print("\n  By canon status :")
        for status, count in sorted(stats["total_by_canon"].items()):
            print(f"    {status:<18} {count}")
    if stats["pages_by_bucket"]:
        print("\n  Pages per bucket :")
        for name, count in sorted(stats["pages_by_bucket"].items()):
            print(f"    {name:<32} {count}")


async def _cmd_recent_impl(args) -> None:
    config, _ = build_config(args)
    async with _manager_scope(config.database_url) as manager:
        rows = await manager.recent_pages(limit=args.limit)

    def _fmt(dt) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "\u2014"

    if not rows:
        print("No recorded pages.")
        return
    print(f"Last {len(rows)} modified page(s):")
    for i, row in enumerate(rows, start=1):
        print(f"  {i:>2}. {row['page_title']:<50} "
              f"[{row['canon_status']:<16}] "
              f"created {_fmt(row['created_at'])} / updated {_fmt(row['updated_at'])}")


async def _cmd_export_entities_impl(args) -> None:
    from ..export import EXPORT_CATEGORIES, PublicExportClient

    config, _ = build_config(args)
    langs = tuple(args.lang) if args.lang else ("en", "fr")
    client = PublicExportClient(
        cache_dir=args.cache_dir or Path("cache") / "public_export",
        langs=langs)
    async with _manager_scope(config.database_url) as manager:
        if args.categories:
            wanted = {k: v for k, v in EXPORT_CATEGORIES.items()
                      if k in args.categories}
            client.categories = wanted
        stats = await client.sync(manager, langs=langs, force=args.force)
    print(f"Public Export: {stats['entities']} entities written, "
          f"{stats['assets']} assets processed, {stats['skipped']} failures.")
