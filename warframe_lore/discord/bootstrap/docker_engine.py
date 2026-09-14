"""Docker engine cold start (Docker Desktop) for the local stack.

Single responsibility: make sure the Docker engine answers before a compose stack
is brought up — launching Docker Desktop when it is cold, then waiting for the
engine, bounded.  Best effort by nature: a missing Docker Desktop raises with an
explicit message instead of hanging the bot launch.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from .waiting import wait_until

log = logging.getLogger("warframe_lore.discord.docker")

DOCKER_DESKTOP_EXE = (
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    / "Docker" / "Docker" / "Docker Desktop.exe")
ENGINE_WAIT_SECONDS = 120.0


def engine_ready() -> bool:
    """True if the Docker engine API answers."""
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=15)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_engine() -> None:
    """Start Docker Desktop when the engine is cold, then wait for it."""
    if engine_ready():
        return
    if not DOCKER_DESKTOP_EXE.exists():
        raise RuntimeError(
            "Docker Desktop not found — start PostgreSQL another way")
    log.info("Docker engine is not running — launching Docker Desktop")
    subprocess.Popen([str(DOCKER_DESKTOP_EXE)])
    if not wait_until(engine_ready, ENGINE_WAIT_SECONDS):
        raise RuntimeError(
            f"Docker engine did not start within {ENGINE_WAIT_SECONDS:.0f}s")


__all__ = ["DOCKER_DESKTOP_EXE", "ENGINE_WAIT_SECONDS", "engine_ready",
           "ensure_engine"]
