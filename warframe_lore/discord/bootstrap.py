"""ENGRAM auto-start before the Discord bot (``cephalon bot run``).

The bot needs the ENGRAM Roleplay server (FastAPI/uvicorn) reachable on its
WebSocket before any question can be answered.  This module checks the
``/health`` endpoint and, if the server is not responding, spawns it in a
child process (same interpreter) and waits for it to become ready.  When
the bot exits, the spawned server is terminated along with it.

The PostgreSQL/pgvector database (which ENGRAM reads for RAG) is also
booted on demand: if the TCP port of ``WF_DATABASE_URL`` is not listening,
``docker compose up -d`` is tried (Docker Desktop is launched first if the
engine is not running).

A remote ``ws://`` URL is never auto-started: only a local host
(``localhost`` / ``127.0.0.1``) is considered bootable.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

log = logging.getLogger("warframe_lore.discord.bootstrap")

_READY_TIMEOUT_SECONDS = 45.0
_HEALTH_POLL_SECONDS = 0.5
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_DOCKER_DESKTOP_EXE = (
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    / "Docker" / "Docker" / "Docker Desktop.exe")
_ENGINE_WAIT_SECONDS = 120.0
_DB_WAIT_SECONDS = 90.0

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _health_ok(http_health_url: str) -> bool:
    """True if ENGRAM answers ``/health`` with HTTP 200."""
    try:
        with urlopen(http_health_url, timeout=3) as response:
            return bool(response.status == 200
                        and b'"ok"' in response.read())
    except Exception:  # noqa: BLE001 (unreachable server -> not ready)
        return False


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


def ensure_engram(ws_url: str) -> subprocess.Popen | None:
    """Ensure the ENGRAM server responds; spawn it otherwise.

    Returns the child process when ENGRAM was started here (so the caller
    can terminate it once the bot stops), or ``None`` when an already
    running server was reused (or the host is remote).
    """
    parts = urlparse(ws_url)
    host = (parts.hostname or "localhost").lower()
    if host not in ("localhost", "127.0.0.1", "::1"):
        # Remote ENGRAM: not ours to start or stop.
        return None
    port = parts.port or 8000
    health_url = f"http://127.0.0.1:{port}/health"
    if _health_ok(health_url):
        log.info("ENGRAM already running (%s) — reusing it", health_url)
        return None

    log.info("ENGRAM not responding (%s) — starting uvicorn...", health_url)
    cmd = [
        sys.executable, "-m", "uvicorn",
        "warframe_lore.engram.api.main:app",
        "--host", "127.0.0.1", "--port", str(port),
        "--no-access-log",
    ]
    child = subprocess.Popen(cmd)
    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if _health_ok(health_url):
            log.info("ENGRAM started (pid %d)", child.pid)
            return child
        if child.poll() is not None:
            raise RuntimeError(
                f"ENGRAM exited before becoming ready "
                f"(return code {child.returncode})")
        time.sleep(_HEALTH_POLL_SECONDS)
    child.terminate()
    raise RuntimeError(
        f"ENGRAM did not become ready within "
        f"{_READY_TIMEOUT_SECONDS:.0f}s (port {port})")


__all__ = ["ensure_database", "ensure_engram"]