"""Extraction des notes de mise à jour (``## Patch History``).

Responsabilité unique : reconnaître une section ``Patch History`` dans un
Markdown et la réduire en structure ``[{version, notes[]}]``.
"""

from __future__ import annotations

import re
from typing import Any

# Notes de mise à jour : les pages wiki listent chaque version sur UNE ligne
# nue (``42``, ``38.5.5``, ``Update 27.2``, ``Vanilla``…) suivie de ses
# correctifs (``> ...`` / ``* ...`` / paragraphes).
_PATCH_HISTORY_HEADING = re.compile(r"^#{2,4}\s*Patch History\s*$", re.M)
_PATCH_VERSION_LINE = re.compile(
    r"^(?:\*\*)?(?:"
    r"\d+(?:\.\d+){0,3}"
    r"|Update\s+\d+(?:\.\d+){0,3}"
    r"|Hotfix\s+\d+(?:\.\d+){0,3}"
    r"|Mainline\s+\d+(?:\.\d+){0,3}"
    r"|Revised\s+\d+(?:\.\d+){0,3}"
    r"|Vanilla|Prime Vault"
    r")(?:\*\*)?\s*$")


def split_lines(text: str) -> list[str]:
    """Découpe un texte multi-lignes en répliques (une entrée par ligne)."""
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _next_heading_after(markdown: str, start: int) -> int:
    """Fin de section : prochain en-tête ``#``/``##`` (ou fin du texte)."""
    following = re.search(r"^#{1,2}\s+", markdown[start:], re.M)
    return start + following.start() if following else len(markdown)


def extract_patch_notes(markdown: str) -> tuple[list[dict[str, list[str]]], str]:
    """Découpe la section ``## Patch History`` de ``markdown``.

    Renvoie ``(patches, reste)`` où ``patches`` est la liste structurée
    ``[{"version": "38.5.5", "notes": ["Fixed ...", ...]}]`` et ``reste``
    le markdown sans la section (pour éviter un double rendu flat).
    Si aucun en-tête n'est présent : ``([], markdown)`` inchangé.
    """
    heading = _PATCH_HISTORY_HEADING.search(markdown)
    if not heading:
        return [], markdown
    section_end = _next_heading_after(markdown, heading.end())
    section = markdown[heading.end():section_end]
    patches: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in section.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if _PATCH_VERSION_LINE.match(line):
            current = {"version": line.strip("*"), "notes": []}
            patches.append(current)
            continue
        if current is None:
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        note = re.sub(r"^[>*]\s*", "", line)
        note = re.sub(r"^-\s+", "", note)
        note = re.sub(r"\{[^{}\n]{0,160}\}", "", note)
        note = note.strip()
        if note:
            current["notes"].append(note)
    return [p for p in patches if p["notes"]], markdown[:heading.start()].rstrip() + "\n"
