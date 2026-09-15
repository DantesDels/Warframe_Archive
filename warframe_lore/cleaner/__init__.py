"""Cleaner layer: Wikitext -> clean Markdown for LLM.

Sub-modules (one file = one responsibility):
    * html/blocks      : raw sanitization (tags, tables, code);
    * template_*       : template detection/rendering/removal;
    * sections*        : gameplay vs lore section filtering;
    * formatting       : formatting facade (links, headings, dialogue);
    * audio/KIM        : audio metadata and KIM instructions;
    * pipeline         : :class:`WikitextCleaner` class (orchestration).

Cleaning constants (noise templates, gameplay sections, etc.) are
externalized to ``config/cleaner_config.json`` and injected at runtime
(SOLID *Dependency Injection* principle).
"""

from __future__ import annotations

from warframe_lore.cleaner.config import CLEANER_CONFIG_PATH, CleanerConfig
from warframe_lore.cleaner.pipeline import BULLET_TOKEN, CleanOutput, WikitextCleaner
from warframe_lore.cleaner.site_html import HtmlCleaner

__all__ = ["BULLET_TOKEN", "CLEANER_CONFIG_PATH", "CleanOutput",
           "CleanerConfig", "HtmlCleaner", "WikitextCleaner"]
