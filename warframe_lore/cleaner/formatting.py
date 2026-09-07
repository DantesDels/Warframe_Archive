"""Mise en forme finale du Markdown — façade de compatibilité.

Ré-exporte les fonctions pures ``str -> str`` des sous-modules de mise en
forme, pour préserver les imports historiques (``from ..cleaner.formatting
import cut_footer_noise``).  Voir ``bullets``, ``headings``, ``markup``,
``links``, ``dialogue_lines``, ``footers``, ``polish``.
"""

from __future__ import annotations

from warframe_lore.cleaner.bullets import BULLET_TOKEN, protect_bullets
from warframe_lore.cleaner.dialogue_lines import (
    format_lists_and_dialogue,
    normalise_indentation,
)
from warframe_lore.cleaner.footers import cut_footer_noise
from warframe_lore.cleaner.headings import (
    normalise_deep_headings,
    reflow_headings_to_markdown,
)
from warframe_lore.cleaner.links import normalise_links
from warframe_lore.cleaner.markup import convert_markup_to_markdown
from warframe_lore.cleaner.polish import (
    collapse_empty_galleries,
    strip_excess_blank_lines,
)

__all__ = [
    "BULLET_TOKEN",
    "protect_bullets",
    "convert_markup_to_markdown",
    "normalise_links",
    "normalise_indentation",
    "format_lists_and_dialogue",
    "reflow_headings_to_markdown",
    "normalise_deep_headings",
    "cut_footer_noise",
    "collapse_empty_galleries",
    "strip_excess_blank_lines",
]