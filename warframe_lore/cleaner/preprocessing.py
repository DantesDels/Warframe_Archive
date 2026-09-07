"""Prétraitement du Wikitext brut — façade de compatibilité.

Transformations destructives applicables AVANT l'analyse structurelle
(commentaires/balises HTML -> ``html`` ; fichiers/tableaux/code -> ``blocks``).
"""

from __future__ import annotations

from warframe_lore.cleaner.blocks import (
    strip_file_and_image_references,
    strip_tables_and_code_blocks,
)
from warframe_lore.cleaner.html import (
    convert_html_tags,
    remove_transclusion_tags,
    strip_wikitext_comments,
)

__all__ = [
    "strip_wikitext_comments",
    "strip_tables_and_code_blocks",
    "convert_html_tags",
    "remove_transclusion_tags",
    "strip_file_and_image_references",
]