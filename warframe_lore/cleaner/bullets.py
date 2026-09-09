"""Sentinel + Wikitext bullet protection before Markdown conversion."""

from __future__ import annotations

import re

# Sentinel protecting Wikitext bullets ("* ...") before conversion
# to Markdown, so the '*' character does not collide with "**bold**".
BULLET_TOKEN = "\x00BULLET\x00"
_LEADING_BULLETS = re.compile(r"^(\*+)(.*)$", re.MULTILINE)
_BULLET_LINE = re.compile(r"^\s*" + re.escape(BULLET_TOKEN))


def protect_bullets(wikitext: str) -> str:
    """Replaces leading-line bullets with the BULLET_TOKEN sentinel."""
    def _replace_bullet_line(match: re.Match) -> str:
        return BULLET_TOKEN + match.group(2).lstrip()

    return _LEADING_BULLETS.sub(_replace_bullet_line, wikitext)


__all__ = ["BULLET_TOKEN", "protect_bullets"]
