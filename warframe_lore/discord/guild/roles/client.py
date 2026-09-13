"""Throwaway Discord client used by the role-map discovery CLI.

Connects with the ``guild members`` intent, runs the scan once ``on_ready``
fires, then closes itself.  A hard timeout keeps the CLI from hanging when the
gateway never answers (wrong token, missing intent, offline).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import discord

from .persist import fill_map

_CONNECT_TIMEOUT_SECONDS = 90.0


class RoleDumpClient(discord.Client):
    """Single-shot client: dump the visible roles, then exit."""

    def __init__(self, roles_path: str, write: bool, **kwargs) -> None:
        super().__init__(**kwargs)
        self.roles_path = roles_path
        self.write = write
        self.exit_code = 0
        self._done: asyncio.Event | None = None

    async def on_ready(self) -> None:
        try:
            assert self.user is not None
            print(f"Oracle runtime {self.user} ({self.user.id}) "
                  "— guilds visibles :")
            if self.guilds:
                fill_map(self.guilds, Path(self.roles_path), write=self.write)
            else:
                print("Aucun serveur visible : vérifiez que le bot est invité "
                      "avec l'intent `guild members` activé.")
        except Exception as exc:  # noqa: BLE001 (dump failures must surface)
            print(f"Erreur pendant le dump : {exc!r}", file=sys.stderr)
            self.exit_code = 1
        finally:
            await self._finish()

    async def _finish(self) -> None:
        try:
            await self.close()
        finally:
            if self._done is not None:
                self._done.set()

    async def _amain(self, token: str) -> None:
        """Log in, drive the gateway as a task and wait for ``on_ready``."""
        await self.login(token)
        self._done = asyncio.Event()
        connect_task = asyncio.create_task(self.connect())
        try:
            await asyncio.wait_for(self._done.wait(),
                                   timeout=_CONNECT_TIMEOUT_SECONDS)
        except TimeoutError:
            print(f"Connexion Discord absente après "
                  f"{_CONNECT_TIMEOUT_SECONDS:.0f} s — vérifiez le réseau, le "
                  "token (DISCORD_TOKEN) et l'intent `guild members`.",
                  file=sys.stderr)
            self.exit_code = 3
        finally:
            if not connect_task.done():
                connect_task.cancel()
            await self.close()

    def run_and_report(self, token: str) -> None:
        """Blocking entry: runs the single-shot dump on a private loop."""
        print("Connexion à Discord…", flush=True)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._amain(token))
        finally:
            loop.close()


__all__ = ["RoleDumpClient"]
