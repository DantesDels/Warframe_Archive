"""Section heading classification: gameplay vs narrative."""

from __future__ import annotations

import re

from warframe_lore.cleaner.config import CleanerConfig


def _normalize_for_comparison(value_to_normalize: str) -> str:
    """Lowercase, no special characters (reliable comparison).

    Applied to BOTH comparison terms (heading and keywords), otherwise
    ``"trivia (gameplay)"`` can never match ``"Trivia (gameplay)"``
    normalized to ``"trivia gameplay"``.
    """
    return re.sub(r"[^a-z0-9 ]", "", value_to_normalize.lower())


def is_gameplay_section(section_title: str, cleaner_config: CleanerConfig) -> bool:
    """True if the section heading is gameplay-related (stats, builds, ...)."""
    normalized_title = _normalize_for_comparison(section_title)
    return any(_normalize_for_comparison(keyword) in normalized_title
               for keyword in cleaner_config.gameplay_exclude)


def is_lore_section(section_title: str, cleaner_config: CleanerConfig) -> bool:
    """True if the section heading is clearly narrative (lore, story)."""
    normalized_title = _normalize_for_comparison(section_title)
    return any(_normalize_for_comparison(keyword) in normalized_title
               for keyword in cleaner_config.lore_keep)


__all__ = ["is_gameplay_section", "is_lore_section"]
