"""Cleaner layer: Wikitext -> clean Markdown for LLM.

Sub-modules (one file = one responsibility):
    * markup/          : raw sanitization, links, emphasis, site HTML;
    * templates/       : template detection/rendering/removal;
    * sections*        : gameplay vs lore section filtering;
    * formatting       : formatting facade (links, headings, dialogue);
    * audio/KIM        : audio metadata and KIM instructions;
    * pipeline         : :class:`WikitextCleaner` class (orchestration).

Cleaning constants (noise templates, gameplay sections, etc.) are
externalized to ``config/cleaner_config.json`` and injected at runtime
(SOLID *Dependency Injection* principle).
"""

from __future__ import annotations

from warframe_lore.scraper.cleaner.config import CLEANER_CONFIG_PATH, CleanerConfig
from warframe_lore.scraper.cleaner.markup.site_html import HtmlCleaner
from warframe_lore.scraper.cleaner.pipeline import (
           BULLET_TOKEN,
           CleanOutput,
           WikitextCleaner,
)

__all__ = ["BULLET_TOKEN", "CLEANER_CONFIG_PATH", "CleanOutput",
           "CleanerConfig", "HtmlCleaner", "WikitextCleaner"]
