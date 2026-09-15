"""Implementations of the ``cephalon`` CLI commands.

Each ``_cmd_*`` maps to an argparse subcommand; the ``_impl`` coroutines
live in :mod:`warframe_lore.cli.commands_aux` and are run through
``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from .. import __version__
from ..api import BucketConfig
from .commands_aux import (
    _cmd_diff_impl,
    _cmd_export_entities_impl,
    _cmd_init_database_impl,
    _cmd_recent_impl,
    _cmd_status_impl,
)
from .support import (
    PROJECT_DEFAULT_BUCKET_CONFIG,
    build_config,
    build_scraper,
    launch_ui,
    print_buckets,
)


# ------------------------------------------------------------- command: run
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


def _cmd_status(args) -> int:
    asyncio.run(_cmd_status_impl(args))
    return 0


def _cmd_recent(args) -> int:
    asyncio.run(_cmd_recent_impl(args))
    return 0


def _cmd_export_entities(args) -> int:
    asyncio.run(_cmd_export_entities_impl(args))
    return 0


def _cmd_buckets(args) -> int:
    _, bucket_config = build_config(args)
    if args.init:
        target = args.bucket_config or PROJECT_DEFAULT_BUCKET_CONFIG
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
