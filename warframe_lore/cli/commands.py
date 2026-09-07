"""Implémentations des commandes du CLI ``cephalon``.

Chaque ``_cmd_*`` correspond à une sous-commande argparse ; les variantes
``_impl`` sont les coroutines async appelées via ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from ..api import BucketConfig
from ..config import PROJECT_ROOT
from ..db import SQLDatabaseManager
from ..scraper import Scraper
from .support import (
    PROJECT_DEFAULT_DB_INIT_SQL,
    VERSION,
    build_config,
    launch_ui,
    print_buckets,
)

log = logging.getLogger("cephalon")


# ------------------------------------------------------------- command: run
async def _cmd_init_database_impl(database_url: str) -> None:
    manager = SQLDatabaseManager(database_url)
    await manager.connect()
    try:
        await manager.run_ddl_script(PROJECT_DEFAULT_DB_INIT_SQL)
    finally:
        await manager.close()
    print(f"Base initialisée depuis {PROJECT_DEFAULT_DB_INIT_SQL.name}.")


def _cmd_init_database(args) -> int:
    config, _ = build_config(args)
    asyncio.run(_cmd_init_database_impl(config.database_url))
    return 0


def _cmd_run(args) -> int:
    config, bucket_config = build_config(args)
    scraper = Scraper(
        config=config,
        bucket_config=bucket_config,
        database_url=None if args.skip_sql else config.database_url,
    )
    try:
        scraper.run(force=args.force)
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130
    print("Synchronisation terminée avec succès.")
    if not getattr(args, "no_ui", False):
        launch_ui(config)
    return 0


async def _cmd_diff_impl(args) -> dict:
    config, bucket_config = build_config(args)
    scraper = Scraper(
        config=config,
        bucket_config=bucket_config,
        database_url=None if args.skip_sql else config.database_url,
    )
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
        print("Aucune mise à jour à faire — contenu déjà à jour.")
        return 0
    print(f"Delta : {total} page(s) à mettre à jour (force={args.force}):")
    for bucket_id, titles in sorted(plan.items()):
        print(f"\n[{bucket_id}]  ({len(titles)} page(s))")
        for title in sorted(titles):
            print(f"    • {title}")
    return 0


async def _cmd_status_impl(args) -> None:
    config, _ = build_config(args)
    manager = SQLDatabaseManager(config.database_url)
    await manager.connect()
    try:
        stats = await manager.db_stats()
    finally:
        await manager.close()

    def _fmt(dt) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "—"

    print("État de la base de lore :")
    print(f"  Pages en base            : {stats['total_pages']}")
    print(f"  Chunks (RAG)             : {stats['total_chunks']}")
    print(f"  Dialogues KIM            : {stats['total_kim_dialogues']}")
    print(f"  Enregistrements de sync  : {stats['total_sync_records']}")
    print(f"  Dernière page créée      : {_fmt(stats['last_page_created_at'])}")
    print(f"  Dernière page mise à jour: {_fmt(stats['last_page_updated_at'])}")
    print(f"  Dernière synchronisation : {_fmt(stats['last_sync_at'])}")

    if stats["total_by_canon"]:
        print("\n  Par statut canon :")
        for status, count in sorted(stats["total_by_canon"].items()):
            print(f"    {status:<18} {count}")
    if stats["pages_by_bucket"]:
        print("\n  Pages par bucket :")
        for name, count in sorted(stats["pages_by_bucket"].items()):
            print(f"    {name:<32} {count}")


def _cmd_status(args) -> int:
    asyncio.run(_cmd_status_impl(args))
    return 0


async def _cmd_recent_impl(args) -> None:
    config, _ = build_config(args)
    manager = SQLDatabaseManager(config.database_url)
    await manager.connect()
    try:
        rows = await manager.recent_pages(limit=args.limit)
    finally:
        await manager.close()

    def _fmt(dt) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "—"

    if not rows:
        print("Aucune page enregistrée.")
        return
    print(f"Dernières {len(rows)} page(s) modifiées :")
    for i, row in enumerate(rows, start=1):
        print(f"  {i:>2}. {row['page_title']:<50} "
              f"[{row['canon_status']:<16}] "
              f"créé {_fmt(row['created_at'])} / maj {_fmt(row['updated_at'])}")


def _cmd_recent(args) -> int:
    asyncio.run(_cmd_recent_impl(args))
    return 0


async def _cmd_export_entities_impl(args) -> None:
    from ..export import EXPORT_CATEGORIES, PublicExportClient

    config, _ = build_config(args)
    manager = SQLDatabaseManager(config.database_url)
    await manager.connect()
    langs = tuple(args.lang) if args.lang else ("en", "fr")
    client = PublicExportClient(
        cache_dir=args.cache_dir or Path("cache") / "public_export",
        langs=langs)
    try:
        if args.categories:
            wanted = {k: v for k, v in EXPORT_CATEGORIES.items()
                      if k in args.categories}
            client.categories = wanted
        stats = await client.sync(manager, langs=langs, force=args.force)
    finally:
        await manager.close()
    print(f"Public Export : {stats['entities']} entités écrites, "
          f"{stats['assets']} actifs traités, {stats['skipped']} en échec.")


def _cmd_export_entities(args) -> int:
    asyncio.run(_cmd_export_entities_impl(args))
    return 0


def _cmd_buckets(args) -> int:
    _, bucket_config = build_config(args)
    if args.init:
        target = args.bucket_config or (PROJECT_ROOT / "buckets.json")
        BucketConfig.write_defaults(target)
        print(f"Config buckets par défaut écrite -> {target}")
        return 0
    print_buckets(bucket_config)
    return 0


def _cmd_version(args) -> int:
    print(f"cephalon (warframe-archives) — {VERSION}")
    print(f"paquet : {Path(__file__).resolve().parent.parent}")
    return 0


def _cmd_ui(args) -> int:
    """Lance l'interface web locale (voir ``warframe_lore.ui.server``)."""
    from ..ui.server import serve_forever

    config, _ = build_config(args)
    serve_forever(output_dir=args.out or config.output_dir,
                  port=args.port,
                  open_browser=not args.no_browser)
    return 0


# --------------------------------------------------------- command: kim-dm
def _cmd_kim_dm(args) -> int:
    from ..kim_dm import mirror_kim_dm

    config, _ = build_config(args)
    output_dir = args.out or config.output_dir
    langs = tuple(args.lang) if args.lang else ("en", "fr")
    downloaded, failed = mirror_kim_dm(output_dir, langs=langs, force=args.force)
    if downloaded:
        print(f"Téléchargés dans {output_dir / 'kim_dm'} : {', '.join(downloaded)}")
    else:
        print("Rien à télécharger (cache déjà à jour — utilisez --force).")
    if failed:
        print("Échecs :")
        for err in failed:
            print(f"  • {err}")
        return 1
    return 0