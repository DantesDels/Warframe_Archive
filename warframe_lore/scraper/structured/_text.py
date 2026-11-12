"""Tiny line/text helpers shared by the official-site parsers."""

from __future__ import annotations

import re


def non_empty_lines(markdown: str) -> list[str]:
    """Splits markdown into stripped, non-empty lines."""
    return [line.strip() for line in markdown.split("\n") if line.strip()]


def first_match(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    """Returns the first line matching ``pattern``, if any."""
    for line in lines:
        if pattern.match(line):
            return line
    return None
