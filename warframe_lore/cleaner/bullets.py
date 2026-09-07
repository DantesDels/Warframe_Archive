"""Sentinelle + protection des puces Wikitext avant conversion Markdown."""

from __future__ import annotations

import re

# Sentinelle protégeant les puces Wikitext ("* ...") avant la conversion
# en Markdown, pour que le caractère '*' ne collisionne pas avec "**bold**".
BULLET_TOKEN = "\x00BULLET\x00"
_LEADING_BULLETS = re.compile(r"^(\*+)(.*)$", re.MULTILINE)
_BULLET_LINE = re.compile(r"^\s*" + re.escape(BULLET_TOKEN))


def protect_bullets(wikitext: str) -> str:
    """Remplace les puces de début de ligne par la sentinelle BULLET_TOKEN."""
    def _replace_bullet_line(match: re.Match) -> str:
        return BULLET_TOKEN + match.group(2).lstrip()

    return _LEADING_BULLETS.sub(_replace_bullet_line, wikitext)


__all__ = ["BULLET_TOKEN", "protect_bullets"]