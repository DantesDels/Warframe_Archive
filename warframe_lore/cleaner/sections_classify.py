"""Classification des titres de section : gameplay vs narratif."""

from __future__ import annotations

import re

from warframe_lore.cleaner.config import CleanerConfig


def _normalize_for_comparison(value_to_normalize: str) -> str:
    """Minuscules, sans caractères spéciaux (comparaison fiable).

    Appliqué AUX DEUX termes de la comparaison (titre et mots-clés), sinon
    ``"trivia (gameplay)"`` ne peut jamais correspondre à ``"Trivia (gameplay)"``
    normalisé en ``"trivia gameplay"``.
    """
    return re.sub(r"[^a-z0-9 ]", "", value_to_normalize.lower())


def is_gameplay_section(section_title: str, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le titre de section relève du gameplay (stats, builds, ...)."""
    normalized_title = _normalize_for_comparison(section_title)
    return any(_normalize_for_comparison(keyword) in normalized_title
               for keyword in cleaner_config.gameplay_exclude)


def is_lore_section(section_title: str, cleaner_config: CleanerConfig) -> bool:
    """Vrai si le titre de section est clairement narratif (lore, histoire)."""
    normalized_title = _normalize_for_comparison(section_title)
    return any(_normalize_for_comparison(keyword) in normalized_title
               for keyword in cleaner_config.lore_keep)


__all__ = ["is_gameplay_section", "is_lore_section"]