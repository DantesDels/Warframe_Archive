"""Deterministic post-generation wikilinking of entity mentions.

Pure Python pass: mentions of entity names and aliases become
``[[Official Name|Alias]]`` links. Frontmatter, Markdown headings, fenced
code blocks, inline code and existing wikilinks are strictly preserved.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..graph_engine.models import Entity

_PROTECTED_RE = re.compile(r"(`[^`\n]*`|\[\[[^\]\n]*\]\])")


def _surface_map(entities: Iterable[Entity], self_name: str) -> dict[str, str]:
    surfaces: dict[str, str] = {}
    for entity in entities:
        if entity.name == self_name:
            continue
        for surface in [entity.name, *entity.aliases]:
            if surface and surface.casefold() not in surfaces:
                surfaces[surface.casefold()] = entity.name
    return surfaces


def _link_line(line: str, pattern: re.Pattern[str], surfaces: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        official = surfaces[match.group(0).casefold()]
        if match.group(0).casefold() == official.casefold():
            return f"[[{official}]]"
        return f"[[{official}|{match.group(0)}]]"

    parts = _PROTECTED_RE.split(line)
    for index, part in enumerate(parts):
        if index % 2 == 0:
            parts[index] = pattern.sub(replace, part)
    return "".join(parts)


def autolink(text: str, entities: Iterable[Entity], self_name: str = "") -> str:
    """Link every known entity mention outside protected Markdown zones."""
    surfaces = _surface_map(entities, self_name)
    if not surfaces:
        return text
    ordered = sorted(surfaces, key=lambda surface: (-len(surface), surface))
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(surface) for surface in ordered) + r")\b",
        re.IGNORECASE,
    )
    lines = text.splitlines(keepends=True)
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    in_code_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if in_frontmatter:
            if index > 0 and stripped == "---":
                in_frontmatter = False
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence or stripped.startswith("#"):
            continue
        lines[index] = _link_line(line, pattern, surfaces)
    return "".join(lines)
