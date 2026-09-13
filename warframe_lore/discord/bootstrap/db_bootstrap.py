"""PostgreSQL/pgvector auto-start before the Discord bot (``cephalon bot run``).

The bot's RAG database (read by ENGRAM) is booted on demand: if the TCP port
of ``WF_DATABASE_URL`` is not listening, ``docker compose up -d`` is tried
(Docker Desktop is launched first if the engine is not running).

A remote database is never auto-started: only a local host (``localhost`` /
``127.0.0.1``) is considered bootable.  ENGRAM auto-start lives in
:mod:`engram_bootstrap`; this module is the database half + the shared local
host constant.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger("warframe_lore.discord.db_bootstrap")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

_DOCKER_DESKTOP_EXE = (
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    / "Docker" / "Docker" / "Docker Desktop.exe")
_ENGINE_WAIT_SECONDS = 120.0
_DB_WAIT_SECONDS = 90.0

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """True if a TCP connection to ``host:port`` succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _database_url() -> tuple[str, int]:
    """Host/port of the ``WF_DATABASE_URL`` (defaults to local 5432)."""
    raw = os.getenv(
        "WF_DATABASE_URL",
        "postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore")
    # Strip the driver suffix (e.g. ``postgresql+asyncpg``) to parse cleanly.
    plain = raw.split("://", 1)
    scheme = plain[0].split("+", 1)[0] if plain else "postgresql"
    rest = plain[1] if len(plain) > 1 else f"//{raw}"
    parts = urlparse(f"{scheme}://{rest}")
    return parts.hostname or "localhost", parts.port or 5432


def _docker_engine_ready() -> bool:
    """True if the Docker engine API answers."""
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=15)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _start_docker_desktop() -> None:
    """Launch Docker Desktop (engine cold start) — best effort."""
    if not _DOCKER_DESKTOP_EXE.exists():
        raise RuntimeError(
            "Docker Desktop not found — start PostgreSQL another way")
    log.info("Docker engine is not running — launching Docker Desktop")
    subprocess.Popen([str(_DOCKER_DESKTOP_EXE)])


def ensure_database() -> None:
    """Ensure PostgreSQL/pgvector listens on the configured port.

    If the port is already open, nothing happens.  Otherwise the compose
    stack (``docker-compose.yml`` at the project root) is brought up with
    ``docker compose up -d`` — Docker Desktop is started first when the
    engine is not running.
    """
    host, port = _database_url()
    if host.lower() not in _LOCAL_HOSTS:
        log.info("Database host %r is not local — skipping auto-start", host)
        return
    if _tcp_open(host, port):
        log.info("PostgreSQL already reachable on %s:%d — reusing it",
                 host, port)
        return
    if not _docker_engine_ready():
        _start_docker_desktop()
        deadline = time.monotonic() + _ENGINE_WAIT_SECONDS
        while time.monotonic() < deadline:
            if _docker_engine_ready():
                break
            time.sleep(2.0)
        if not _docker_engine_ready():
            raise RuntimeError(
                "Docker engine did not start within "
                f"{_ENGINE_WAIT_SECONDS:.0f}s")

    compose = _PROJECT_ROOT / "docker-compose.yml"
    log.info("Starting PostgreSQL stack (%s)...", compose)
    proc = subprocess.run(
        ["docker", "compose", "-f", str(compose), "up", "-d"],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker compose up failed: {proc.stderr.strip()}")

    deadline = time.monotonic() + _DB_WAIT_SECONDS
    while time.monotonic() < deadline:
        if _tcp_open(host, port):
            log.info("PostgreSQL ready on %s:%d", host, port)
            return
        time.sleep(2.0)
    raise RuntimeError(
        f"PostgreSQL did not become reachable on {host}:{port} "
        f"within {_DB_WAIT_SECONDS:.0f}s")
