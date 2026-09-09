"""Wikitext bold/italic markup conversion to Markdown."""

from __future__ import annotations

import re


def convert_markup_to_markdown(wikitext: str) -> str:
    """Converts ''italic'' / '''bold''' / '''''bold-italic''''' to Markdown.

    Critical order: bold-italic (5 apostrophes) first, then bold (3),
    then italic (2), to prevent incorrect matches.
    """
    text = wikitext
    text = re.sub(r"'''''(.*?)'''''", r"**_\1_**", text)  # bold + italic
    text = re.sub(r"'''(.*?)'''", r"**\1**", text)        # bold
    text = re.sub(r"''(.*?)''", r"_\1_", text)            # italic
    return text


__all__ = ["convert_markup_to_markdown"]
