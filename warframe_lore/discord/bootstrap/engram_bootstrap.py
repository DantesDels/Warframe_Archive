"""ENGRAM server auto-start before the Discord bot (``cephalon bot run``).

The bot needs the ENGRAM Roleplay server (FastAPI/uvicorn) reachable on its
WebSocket before any question can be answered.  This module checks the
``/health`` endpoint and, if the server is not responding, spawns it in a
child process (same interpreter) and waits for it to become ready.  When
the bot exits, the spawned server is terminated along with it.

A remote ``ws://`` URL is never auto-started: only a local host
(``localhost`` / ``127.0.0.1``) is considered bootable.  The PostgreSQL
auto-start lives in :mod:`db_bootstrap`; this module is the ENGRAM half.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import urlopen

from .db_bootstrap import _LOCAL_HOSTS

log = logging.getLogger("warframe_lore.discord.engram_bootstrap")

_READY_TIMEOUT_SECONDS = 45.0
_HEALTH_POLL_SECONDS = 0.5


def _health_ok(http_health_url: str) -> bool:
    """True if ENGRAM answers ``/health`` with HTTP 200."""
    try:
        with urlopen(http_health_url, timeout=3) as response:
            return bool(response.status == 200
                        and b'"ok"' in response.read())
    except Exception:  # noqa: BLE001 (unreachable server -> not ready)
        return False


def ensure_engram(ws_url: str) -> subprocess.Popen | None:
    """Ensure the ENGRAM server responds; spawn it otherwise.

    Returns the child process when ENGRAM was started here (so the caller
    can terminate it once the bot stops), or ``None`` when an already
    running server was reused (or the host is remote).
    """
    parts = urlparse(ws_url)
    host = (parts.hostname or "localhost").lower()
    if host not in _LOCAL_HOSTS:
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
