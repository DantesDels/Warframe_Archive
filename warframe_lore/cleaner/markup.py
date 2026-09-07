"""Conversion du markup gras/italique Wikitext en Markdown."""

from __future__ import annotations

import re


def convert_markup_to_markdown(wikitext: str) -> str:
    """Convertit ''italique'' / '''gras''' / '''''gras-italique''''' en Markdown.

    Ordre critique : gras-italique (5 apostrophes) d'abord, puis gras (3),
    puis italique (2), pour éviter des appariements incorrects.
    """
    text = wikitext
    text = re.sub(r"'''''(.*?)'''''", r"**_\1_**", text)  # gras + italique
    text = re.sub(r"'''(.*?)'''", r"**\1**", text)        # gras
    text = re.sub(r"''(.*?)''", r"_\1_", text)            # italique
    return text


__all__ = ["convert_markup_to_markdown"]