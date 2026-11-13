"""PostgreSQL/pgvector auto-start for the local stack.

The RAG database (read by ENGRAM) is booted on demand: if the database is not
accepting connections, the compose stack is brought up — the Docker engine
itself is started first when it is cold (see :mod:`docker_engine`).  A remote
database is never auto-started: only a local host is considered bootable.
Shared by ``cephalon run``, ``cephalon update`` and the Discord bot; the ENGRAM
auto-start itself lives in :mod:`warframe_lore.discord.bootstrap.engram_bootstrap`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .docker_engine import ensure_engine
from .waiting import wait_until

log = logging.getLogger("warframe_lore.core.infra.db_bootstrap")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = "docker-compose.yml"
DB_WAIT_SECONDS = 90.0
PROBE_TIMEOUT_SECONDS = 2.0
DEFAULT_DATABASE_URL = ("postgresql+asyncpg://warframe:warframe@localhost:5432"
                        "/warframe_lore")

# Hosts the local stack is allowed to boot (shared with the ENGRAM auto-start).
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _connection_url(database_url: str | None = None) -> str:
    """SQLAlchemy URL -> plain PostgreSQL DSN accepted by asyncpg."""
    raw = database_url or os.getenv("WF_DATABASE_URL", DEFAULT_DATABASE_URL)
    scheme, separator, rest = raw.partition("://")
    if not separator:
        return raw
    # ``postgresql+asyncpg`` is SQLAlchemy's dialect, not a libpq scheme.
    return f"{scheme.split('+', 1)[0]}://{rest}"


def _endpoint(database_url: str | None) -> tuple[str, int]:
    """Host/port of ``database_url`` (defaults to local 5432)."""
    parts = urlparse(_connection_url(database_url))
    return parts.hostname or "localhost", parts.port or 5432


async def _probe_connection(url: str) -> bool:
    """True when PostgreSQL accepts a trivial query on ``url``."""
    # Lazy: the bot process must not load the DB stack at import time.
    import asyncpg

    try:
        connection = await asyncpg.connect(
            dsn=url, timeout=PROBE_TIMEOUT_SECONDS)
    except (OSError, TimeoutError, asyncpg.PostgresError):
        return False
    try:
        await connection.execute("SELECT 1")
    finally:
        await connection.close()
    return True


def _database_ready(database_url: str | None = None) -> bool:
    """True when the database is STARTED, not merely listening on its port.

    PostgreSQL opens its TCP port before it accepts queries (the server logs
    "the database system is starting up"); probing ``SELECT 1`` closes that
    race so the first real connection never hits ``CannotConnectNowError``.
    """
    try:
        return asyncio.run(_probe_connection(_connection_url(database_url)))
    except Exception:  # noqa: BLE001 — a readiness probe must never raise
        return False


def _start_stack() -> None:
    """Bring the compose stack up (``docker-compose.yml`` at the project root)."""
    compose = _PROJECT_ROOT / COMPOSE_FILE
    log.info("Starting PostgreSQL stack (%s)...", compose)
    proc = subprocess.run(
        ["docker", "compose", "-f", str(compose), "up", "-d"],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"docker compose up failed: {proc.stderr.strip()}")


def ensure_database(database_url: str | None = None) -> None:
    """Ensure PostgreSQL/pgvector accepts connections on the configured URL.

    ``database_url`` is the already-resolved connection string (CLI override or
    config); ``None`` falls back to ``WF_DATABASE_URL``.  An already-started
    database: nothing happens.  Otherwise the engine is started if needed, the
    stack is brought up, and the database is polled until it accepts a query.
    """
    host, port = _endpoint(database_url)
    if host.lower() not in LOCAL_HOSTS:
        log.info("Database host %r is not local — skipping auto-start", host)
        return
    if _database_ready(database_url):
        log.info("PostgreSQL already ready on %s:%d — reusing it", host, port)
        return
    ensure_engine()
    _start_stack()
    if not wait_until(lambda: _database_ready(database_url), DB_WAIT_SECONDS):
        raise RuntimeError(
            f"PostgreSQL did not accept connections on {host}:{port} "
            f"within {DB_WAIT_SECONDS:.0f}s")
    log.info("PostgreSQL ready on %s:%d", host, port)


__all__ = ["DB_WAIT_SECONDS", "LOCAL_HOSTS", "ensure_database"]
