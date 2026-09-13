"""Discovery tool for the mission-8 role map: dumps the server roles and
fills ``discord_roles.json`` with their real snowflakes.

The role IDs are NOT knowable from code — they live on the Discord server.
This CLI connects the bot (``DISCORD_TOKEN`` from ``.env``), prints every
role of every visible guild (name → snowflake) and, with ``--write``,
completes ``discord_roles.json`` by matching the role NAMES against the keys
of the current mapping (accents and case-normalised).

Usage:
    python -m warframe_lore.discord.dump_roles            # dump only
    python -m warframe_lore.discord.dump_roles --write    # fill the map
    python -m warframe_lore.discord.dump_roles --write --file my_roles.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import unicodedata
from pathlib import Path

import discord

from ..config import PROJECT_ROOT
from .config import DiscordConfig

# Line-buffered console: the dump must stream live (no reordering against
# stderr and no loss when the process exits).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass


def _norm(name: str) -> str:
    """Accent/case-insensitive key for a role name ('MODÉRATEURS' → 'moderateurs')."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", name).lower()
        if ch.isalnum())


def _disp(text: str) -> str:
    """Console-safe rendering (the mapping file stays UTF-8; the terminal may
    be cp1252 and cannot print arrows or fullwidth glyphs)."""
    text = text.replace("→", ":")
    try:
        return text.encode("cp1252").decode("cp1252")
    except UnicodeEncodeError:
        return text.encode("ascii", "replace").decode("ascii")


class _RoleDumpClient(discord.Client):
    def __init__(self, roles_path: str, write: bool, **kwargs) -> None:
        super().__init__(**kwargs)
        self.roles_path = roles_path
        self.write = write
        self.exit_code = 0
        self._done: asyncio.Event | None = None

    async def on_ready(self) -> None:
        try:
            assert self.user is not None
            print(f"Oracle runtime {self.user} ({self.user.id}) — guilds visibles :")
            if self.guilds:
                _fill_map(self.guilds, Path(self.roles_path), write=self.write)
            else:
                print("Aucun serveur visible : vérifiez que le bot est invité "
                      "avec l'intent `guild members` activé.")
        except Exception as exc:  # noqa: BLE001 (dump failures must surface)
            print(f"Erreur pendant le dump : {exc!r}", file=sys.stderr)
            self.exit_code = 1
        finally:
            try:
                await self.close()
            finally:
                if self._done is not None:
                    self._done.set()

    async def _amain(self, token: str) -> None:
        """Logs in, drives the gateway connection as a background task and
        waits for ``on_ready`` — with a hard timeout so the CLI never hangs."""
        await self.login(token)
        self._done = asyncio.Event()
        connect_task = asyncio.create_task(self.connect())
        try:
            await asyncio.wait_for(self._done.wait(), timeout=90.0)
        except TimeoutError:
            print("Connexion Discord absente après 90 s — vérifiez le réseau, "
                  "le token (DISCORD_TOKEN) et l'intent `guild members`.",
                  file=sys.stderr)
            self.exit_code = 3
        finally:
            if not connect_task.done():
                connect_task.cancel()
            await self.close()

    def run_and_report(self, token: str) -> None:
        print("Connexion à Discord…", flush=True)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._amain(token))
        finally:
            loop.close()


def _load_mapping(path: Path) -> dict | None:
    """Current mapping (real file, else the committed example)."""
    candidates = [path]
    if not path.is_file():
        candidates.append(PROJECT_ROOT / "config" / "discord_roles.example.json")
    for cand in candidates:
        try:
            with open(cand, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            continue
    return None


def _fill_map(guilds, path: Path, write: bool) -> None:
    """Match every guild role against the map keys and (optionally) write."""
    mapping = _load_mapping(path)
    if mapping is None:
        print("Aucun mapping lisible (ni discord_roles.json, ni le "
              "discord_roles.example.json) — rien à compléter.")
        return
    # norm(key) → configured key, preserving the file priority.
    idx: dict[str, str] = {}
    for roles in mapping.values():
        for name in (roles or {}):
            idx.setdefault(_norm(name), name)
    filled: dict[str, str] = {}
    for roles in mapping.values():
        for name in (roles or {}):
            filled[name] = ""
    unmatched: list[str] = []
    guild = next(iter(guilds), None)
    roles = sorted(guild.roles, key=lambda r: r.position, reverse=True) \
        if guild is not None else ()
    for role in roles:
        if role.is_default():  # @everyone
            continue
        name = (role.name or "").strip()
        norm = _norm(name)
        tag = "[mappé]" if norm in idx else "[non mappé]"
        print(f"    {_disp(name)!r:44} : {role.id}  {tag}")
        if norm in idx:
            key = idx[norm]
            prev = filled[key]
            if prev and prev != str(role.id):
                print(f"      ! '{_disp(name)}' existe sur plusieurs guildes "
                      f"avec des IDs différents — le dernier gagne ({role.id})")
            filled[key] = str(role.id)
        else:
            print(f"        exact : {ascii(name)}")
            unmatched.append(f"{name} ({role.id})")
    if not write:
        print("\n(write non activé : aucun fichier modifié — passez --write "
              "pour remplir discord_roles.json)")
        return
    result: dict[str, dict[str, str]] = {}
    for category, roles_obj in mapping.items():
        result[category] = {name: filled[name] for name in (roles_obj or {})}
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"\n: mapping écrit dans {path}")
    except OSError as exc:
        print(f"Impossible d'écrire {path} : {exc}")
        return
    remaining = [k for k, v in filled.items() if not v]
    if remaining:
        print(f"Rôles restés vides ({len(remaining)}) : "
              f"{', '.join(_disp(k) for k in remaining)} "
              "(à remplir à la main dans discord_roles.json).")
    if unmatched:
        print("Rôles du serveur NON mappés (ajoutez-les au mapping si "
              "nécessaire) :")
        for line in unmatched:
            print(f"  - {_disp(line)}")
    print("discord_roles.json reste local (gitignored) ; seul "
          "discord_roles.example.json est à committer si la structure change.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dump_roles",
        description="Dump des rôles Discord (mission-8) et complétion de "
                    "discord_roles.json.")
    parser.add_argument("--write", action="store_true",
                        help="Remplir discord_roles.json avec les IDs trouvés.")
    parser.add_argument("--file", default=None,
                        help=f"Mapping cible (défaut: "
                             f"{PROJECT_ROOT / 'config' / 'discord_roles.json'})")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = DiscordConfig.load()
    token = config.token
    if not token:
        print("Missing DISCORD_TOKEN in .env (ou --token).", file=sys.stderr)
        return 2
    target = args.file or str(PROJECT_ROOT / "config" / "discord_roles.json")
    intents = discord.Intents.default()
    intents.members = True
    client = _RoleDumpClient(target, write=args.write, intents=intents)
    client.run_and_report(token)
    return client.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
