"""Final polish: empty galleries and excess blank lines."""

from __future__ import annotations

import re


def collapse_empty_galleries(markdown_text: str) -> str:
    """Removes ``<gallery>`` tags left by preprocessing."""
    return re.sub(r"(?i)<\s*gallery[^>]*>.*?<\s*/\s*gallery\s*>", "",
                  markdown_text, flags=re.DOTALL)


def strip_excess_blank_lines(markdown_text: str) -> str:
    """Collapses runs of empty lines to a single one and trims whitespace."""
    text = re.sub(r"\n{3,}", "\n\n", markdown_text)
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)
    return text


__all__ = ["collapse_empty_galleries", "strip_excess_blank_lines"]
