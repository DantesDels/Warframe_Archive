"""Couche Cleaner : transformation Wikitext -> Markdown propre pour LLM.

Sous-modules (un fichier = une responsabilité) :
    * html/blocks      : assainissement du brut (balises, tableaux, code) ;
    * template_*       : détection/rendu/suppression des templates ;
    * sections*        : filtrage des sections gameplay vs lore ;
    * formatting       : façade mise en forme (liens, titres, dialogues) ;
    * audio/KIM        : métadonnées audio et instructions KIM ;
    * pipeline         : classe :class:`WikitextCleaner` (orchestration).

Les constantes de nettoyage (templates "bruit", sections gameplay, etc.)
sont externalisées dans ``config/cleaner_config.json`` et injectées à
l'exécution (principe SOLID *Dependency Injection*).
"""

from __future__ import annotations

from warframe_lore.cleaner.config import CLEANER_CONFIG_PATH, CleanerConfig
from warframe_lore.cleaner.pipeline import BULLET_TOKEN, CleanOutput, WikitextCleaner

__all__ = ["WikitextCleaner", "CleanerConfig", "CLEANER_CONFIG_PATH"]