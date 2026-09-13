"""Role-map scanning primitives: normalisation, loading and role matching.

Role snowflakes are NOT knowable from code — they live on the Discord server.
This module matches every visible guild role by NAME (accent/case normalised)
against the configured map.  Console rendering is cp1252-safe (the mapping
file itself stays UTF-8).  Writing back lives in :mod:`persist`.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from ....config import PROJECT_ROOT


def normalize_role_name(name: str) -> str:
    """Accent/case-insensitive key ('MODÉRATEURS' -> 'moderateurs')."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", name).lower()
        if ch.isalnum())


def console_safe(text: str) -> str:
    """Console-safe rendering (the terminal may be cp1252)."""
    text = text.replace("→", ":")
    try:
        return text.encode("cp1252").decode("cp1252")
    except UnicodeEncodeError:
        return text.encode("ascii", "replace").decode("ascii")


def load_mapping(path: Path) -> dict | None:
    """Current mapping (real file, else the committed example)."""
    candidates = [path]
    if not path.is_file():
        candidates.append(
            PROJECT_ROOT / "config" / "discord_roles.example.json")
    for cand in candidates:
        try:
            with open(cand, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            continue
    return None


def blank_mapping(mapping: dict) -> dict[str, str]:
    """Every configured role name, reset to an empty snowflake."""
    filled: dict[str, str] = {}
    for roles in mapping.values():
        for name in (roles or {}):
            filled[name] = ""
    return filled


def scan_roles(guilds, index: dict[str, str],
               filled: dict[str, str]) -> list[str]:
    """Print each visible role, record matched snowflakes, return the rest."""
    unmatched: list[str] = []
    guild = next(iter(guilds), None)
    roles = sorted(guild.roles, key=lambda r: r.position, reverse=True) \
        if guild is not None else ()
    for role in roles:
        if role.is_default():  # @everyone
            continue
        name = (role.name or "").strip()
        key = normalize_role_name(name)
        tag = "[mappé]" if key in index else "[non mappé]"
        print(f"    {console_safe(name)!r:44} : {role.id}  {tag}")
        if key in index:
            _record(index, filled, key, name, role.id)
        else:
            print(f"        exact : {ascii(name)}")
            unmatched.append(f"{name} ({role.id})")
    return unmatched


def role_index(mapping: dict) -> dict[str, str]:
    """``normalised name -> configured key``, preserving the file priority."""
    index: dict[str, str] = {}
    for roles in mapping.values():
        for name in (roles or {}):
            index.setdefault(normalize_role_name(name), name)
    return index


def _record(index: dict[str, str], filled: dict[str, str], key: str,
            name: str, role_id: int) -> None:
    mapped = index[key]
    previous = filled[mapped]
    if previous and previous != str(role_id):
        print(f"      ! '{console_safe(name)}' existe sur plusieurs guildes "
              f"avec des IDs différents — le dernier gagne ({role_id})")
    filled[mapped] = str(role_id)


__all__ = ["blank_mapping", "console_safe", "load_mapping",
           "normalize_role_name", "role_index", "scan_roles"]
