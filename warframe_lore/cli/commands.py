"""Implementations of the ``cephalon`` CLI commands.

Each ``_cmd_*`` maps to an argparse subcommand; the ``_impl`` variants are
the async coroutines called through ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from pathlib import Path

from .. import __version__
from ..api import BucketConfig
from ..config import PROJECT_ROOT
from ..db import SQLDatabaseManager
from .support import (
    PROJECT_DEFAULT_DB_INIT_SQL,
    build_config,
    build_scraper,
    launch_ui,
    print_buckets,
)

log = logging.getLogger("cephalon")


@contextlib.asynccontextmanager
async def _manager_scope(database_url: str):
    """Connect/try/finally/close boilerplate shared by the SQL commands."""
    manager = SQLDatabaseManager(database_url)
    await manager.connect()
    try:
        yield manager
    finally:
        await manager.close()


# ------------------------------------------------------------- command: run
async def _cmd_init_database_impl(database_url: str) -> None:
    async with _manager_scope(database_url) as manager:
        await manager.run_ddl_script(PROJECT_DEFAULT_DB_INIT_SQL)
    print(f"Database initialised from {PROJECT_DEFAULT_DB_INIT_SQL.name}.")


def _cmd_init_database(args) -> int:
    config, _ = build_config(args)
    asyncio.run(_cmd_init_database_impl(config.database_url))
    return 0


def _cmd_run(args) -> int:
    config, _ = build_config(args)
    scraper = build_scraper(args)
    try:
        scraper.run(force=args.force)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    print("Synchronisation completed successfully.")
    if not getattr(args, "no_ui", False):
        launch_ui(config)
    return 0


async def _cmd_diff_impl(args) -> dict:
    scraper = build_scraper(args)
    if scraper.db is not None:
        await scraper.db.connect()
    try:
        return await scraper.delta_plan(force=args.force)
    finally:
        if scraper.db is not None:
            await scraper.db.close()


def _cmd_diff(args) -> int:
    plan = asyncio.run(_cmd_diff_impl(args))
    total = sum(len(t) for t in plan.values())
    if total == 0:
        print("Nothing to update — content is already up to date.")
        return 0
    print(f"Delta: {total} page(s) to update (force={args.force}):")
    for bucket_id, titles in sorted(plan.items()):
        print(f"\n[{bucket_id}]  ({len(titles)} page(s))")
        for title in sorted(titles):
            print(f"    \u2022 {title}")
    return 0


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


def _cmd_status(args) -> int:
    asyncio.run(_cmd_status_impl(args))
    return 0


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


def _cmd_recent(args) -> int:
    asyncio.run(_cmd_recent_impl(args))
    return 0


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


def _cmd_export_entities(args) -> int:
    asyncio.run(_cmd_export_entities_impl(args))
    return 0


def _cmd_buckets(args) -> int:
    _, bucket_config = build_config(args)
    if args.init:
        target = args.bucket_config or (PROJECT_ROOT / "buckets.json")
        BucketConfig.write_defaults(target)
        print(f"Default bucket config written -> {target}")
        return 0
    print_buckets(bucket_config)
    return 0


def _cmd_version(args) -> int:
    print(f"cephalon (warframe-archives) \u2014 {__version__}")
    print(f"package: {Path(__file__).resolve().parent.parent}")
    return 0


def _cmd_ui(args) -> int:
    """Launch the local web interface (see ``warframe_lore.ui.server``)."""
    from ..ui.server import launch

    config, _ = build_config(args)
    launch(output_dir=args.out or config.output_dir,
           port=args.port,
           open_browser=not args.no_browser)
    return 0


# ------------------------------------------------------------ command: bot
def _cmd_bot(args) -> int:
    """Launch the Oracle Discord bot (``cephalon bot run``)."""
    from ..discord.main import launch_bot

    if getattr(args, "bot_action", None) != "run":
        print("Usage: cephalon bot run [--token ...] [--channels ...]",
              file=sys.stderr)
        return 2
    channels = tuple(
        int(x) for x in (args.channels or "").split(",") if x.strip().isdigit())
    return launch_bot(args.token, args.ws, args.prefix, channels,
                      None, args.verbose)


# --------------------------------------------------------- command: kim-dm
def _cmd_kim_dm(args) -> int:
    from ..kim_dm import mirror_kim_dm

    config, _ = build_config(args)
    output_dir = args.out or config.output_dir
    langs = tuple(args.lang) if args.lang else ("en", "fr")
    downloaded, failed = mirror_kim_dm(output_dir, langs=langs, force=args.force)
    if downloaded:
        print(f"Downloaded into {output_dir / 'kim_dm'} : {', '.join(downloaded)}")
    else:
        print("Nothing to download (cache already up to date \u2014 use --force).")
    if failed:
        print("Failures:")
        for err in failed:
            print(f"  \u2022 {err}")
        return 1
    return 0
