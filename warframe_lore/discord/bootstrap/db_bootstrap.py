"""PostgreSQL/pgvector auto-start before the Discord bot (``cephalon bot run``).

The bot's RAG database (read by ENGRAM) is booted on demand: if the TCP port of
``WF_DATABASE_URL`` is not listening, the compose stack is brought up — the Docker
engine itself is started first when it is cold (see :mod:`docker_engine`).  A
remote database is never auto-started: only a local host is considered bootable.
ENGRAM auto-start lives in :mod:`engram_bootstrap`.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .docker_engine import ensure_engine
from .waiting import wait_until

log = logging.getLogger("warframe_lore.discord.db_bootstrap")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = "docker-compose.yml"
DB_WAIT_SECONDS = 90.0
DEFAULT_DATABASE_URL = ("postgresql+asyncpg://warframe:warframe@localhost:5432"
                        "/warframe_lore")

# Hosts the bot is allowed to boot locally (shared with the ENGRAM auto-start).
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """True if a TCP connection to ``host:port`` succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _database_url() -> tuple[str, int]:
    """Host/port of ``WF_DATABASE_URL`` (defaults to local 5432)."""
    raw = os.getenv("WF_DATABASE_URL", DEFAULT_DATABASE_URL)
    # Strip the driver suffix (e.g. ``postgresql+asyncpg``) to parse cleanly.
    plain = raw.split("://", 1)
    scheme = plain[0].split("+", 1)[0] if plain else "postgresql"
    rest = plain[1] if len(plain) > 1 else f"//{raw}"
    parts = urlparse(f"{scheme}://{rest}")
    return parts.hostname or "localhost", parts.port or 5432


def _start_stack() -> None:
    """Bring the compose stack up (``docker-compose.yml`` at the project root)."""
    compose = _PROJECT_ROOT / COMPOSE_FILE
    log.info("Starting PostgreSQL stack (%s)...", compose)
    proc = subprocess.run(
        ["docker", "compose", "-f", str(compose), "up", "-d"],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"docker compose up failed: {proc.stderr.strip()}")


def ensure_database() -> None:
    """Ensure PostgreSQL/pgvector listens on the configured port.

    Already-open port: nothing happens.  Otherwise the engine is started if
    needed, the stack is brought up, and the port is polled until reachable.
    """
    host, port = _database_url()
    if host.lower() not in LOCAL_HOSTS:
        log.info("Database host %r is not local — skipping auto-start", host)
        return
    if _tcp_open(host, port):
        log.info("PostgreSQL already reachable on %s:%d — reusing it",
                 host, port)
        return
    ensure_engine()
    _start_stack()
    if not wait_until(lambda: _tcp_open(host, port), DB_WAIT_SECONDS):
        raise RuntimeError(
            f"PostgreSQL did not become reachable on {host}:{port} "
            f"within {DB_WAIT_SECONDS:.0f}s")
    log.info("PostgreSQL ready on %s:%d", host, port)


__all__ = ["DB_WAIT_SECONDS", "LOCAL_HOSTS", "ensure_database"]
