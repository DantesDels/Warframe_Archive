"""Role-map persistence: fill ``discord_roles.json`` with discovered IDs.

Orchestrates the scan (:mod:`scan`) and writes the result back, preserving the
category structure of the file.  Without ``--write`` nothing is modified.
"""

from __future__ import annotations

import json
from pathlib import Path

from .scan import blank_mapping, console_safe, load_mapping, role_index, scan_roles


def fill_map(guilds, path: Path, write: bool) -> None:
    """Match every guild role against the map keys and (optionally) write."""
    mapping = load_mapping(path)
    if mapping is None:
        print("Aucun mapping lisible (ni discord_roles.json, ni le "
              "discord_roles.example.json) — rien à compléter.")
        return
    filled = blank_mapping(mapping)
    unmatched = scan_roles(guilds, role_index(mapping), filled)
    if not write:
        print("\n(write non activé : aucun fichier modifié — passez --write "
              "pour remplir discord_roles.json)")
        return
    _write_mapping(path, mapping, filled, unmatched)


def _write_mapping(path: Path, mapping: dict, filled: dict[str, str],
                   unmatched: list[str]) -> None:
    """Persist the discovered snowflakes, preserving the file structure."""
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
    _report_gaps(filled, unmatched)


def _report_gaps(filled: dict[str, str], unmatched: list[str]) -> None:
    """Console summary of the roles still empty or absent from the map."""
    remaining = [k for k, v in filled.items() if not v]
    if remaining:
        print(f"Rôles restés vides ({len(remaining)}) : "
              f"{', '.join(console_safe(k) for k in remaining)} "
              "(à remplir à la main dans discord_roles.json).")
    if unmatched:
        print("Rôles du serveur NON mappés (ajoutez-les au mapping si "
              "nécessaire) :")
        for line in unmatched:
            print(f"  - {console_safe(line)}")
    print("discord_roles.json reste local (gitignored) ; seul "
          "discord_roles.example.json est à committer si la structure change.")


__all__ = ["fill_map"]
