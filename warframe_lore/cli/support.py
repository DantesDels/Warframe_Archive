"""Support for the ``cephalon`` CLI: logging, config, UI launcher.

Shared constants and cross-cutting helpers (config building, bucket
display, free-port detection, web UI launch in a detached process).
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys

from ..api import BucketConfig
from ..config import PROJECT_ROOT, load_config

log = logging.getLogger("cephalon")

PROJECT_DEFAULT_DB_INIT_SQL = PROJECT_ROOT / "init_db.sql"
DEFAULT_UI_PORT = 49772


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def build_config(args) -> tuple:
    """Build the config + bucket config shared by the commands."""
    config = load_config()
    if getattr(args, "database_url", None):
        config.database_url = args.database_url

    project_default = PROJECT_ROOT / "buckets.json"
    bucket_path = getattr(args, "bucket_config", None) or (
        project_default if project_default.exists() else None)
    if bucket_path is not None:
        bucket_config = BucketConfig.from_file(bucket_path)
    else:
        bucket_config = BucketConfig()
    return config, bucket_config


def build_scraper(args):
    """Single source of truth for constructing the Scraper.

    Used by ``run`` and ``diff`` so the config+bucket+database_url triple is
    resolved exactly once (before: cloned in two places)."""
    from ..scraper import Scraper

    config, bucket_config = build_config(args)
    return Scraper(
        config=config,
        bucket_config=bucket_config,
        database_url=None if getattr(args, "skip_sql", False) else config.database_url,
    )


def print_buckets(bucket_config: BucketConfig) -> None:
    for spec in bucket_config.specs:
        print(f"[{spec.id}]")
        print(f"  title      : {spec.title}")
        print(f"  file       : {spec.filename}")
        print(f"  categories : {', '.join(spec.categories) or '-'}")
        print(f"  include titles: {', '.join(spec.title_include) or '-'}")
        print(f"  exclude titles: {', '.join(spec.title_exclude) or '-'}")
        print()


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def launch_ui(config) -> None:
    """Launch the web UI in the background and open the browser.

    The server runs in a detached process (dedicated console on Windows) and
    points the browser at the chosen port; ``cephalon run`` does not wait.
    """
    out = config.output_dir
    port = DEFAULT_UI_PORT if port_free(DEFAULT_UI_PORT) else 0
    cmd = [sys.executable, "-m", "warframe_lore.ui.server",
           "--out", str(out), "--port", str(port)]
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    try:
        subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        print(f"Could not launch the web UI: {exc}", file=sys.stderr)
        return
    if port:
        print(f"Web UI launched: http://127.0.0.1:{port}/")
    else:
        print("Web UI launched (automatic free port).")
