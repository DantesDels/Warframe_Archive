"""Orchestrateur du nettoyage : la classe :class:`WikitextCleaner`.

Coordonne les sous-modules de la couche cleaner dans un ordre précis :
  1. preprocessing/html+blocks -> assainissement du brut (commentaires,
     HTML, fichiers, tableaux, code) ;
  2. parse          -> analyse structurelle (mwparserfromhell) ;
  3. templates      -> gestion des templates (bruit, quote, spoiler,
                       marqueurs canon/non-canon) ;
  4. formatting     -> liens, gras/italique, titres, dialogues ;
  5. audio/KIM      -> métadonnées audio et instructions de dialogue ;
  6. sections       -> suppression des blocs gameplay ;
  7. polish         -> galeries vides et lignes blanches en excès.

La sortie est un objet :class:`CleanOutput` qui transporte, en plus du
Markdown, les signaux canon détectés *dans le corps* de la page
(speculation en ligne / confirmation en ligne).  Le statut canon au niveau
page (croisement avec ``Category:Speculation``) est calculé par
l'orchestrateur, pas ici.
"""

from __future__ import annotations

from dataclasses import dataclass

import mwparserfromhell
from mwparserfromhell.nodes import Template

from warframe_lore.cleaner.audio import strip_audio_filenames
from warframe_lore.cleaner.blocks import (
    strip_file_and_image_references,
    strip_tables_and_code_blocks,
)
from warframe_lore.cleaner.bullets import BULLET_TOKEN, protect_bullets
from warframe_lore.cleaner.config import CleanerConfig
from warframe_lore.cleaner.dialogue_lines import (
    format_lists_and_dialogue,
    normalise_indentation,
)
from warframe_lore.cleaner.footers import cut_footer_noise
from warframe_lore.cleaner.headings import (
    normalise_deep_headings,
    reflow_headings_to_markdown,
)
from warframe_lore.cleaner.html import (
    convert_html_tags,
    remove_transclusion_tags,
    strip_wikitext_comments,
)
from warframe_lore.cleaner.kim_instructions import strip_kim_dialog_instructions
from warframe_lore.cleaner.links import normalise_links
from warframe_lore.cleaner.markup import convert_markup_to_markdown
from warframe_lore.cleaner.polish import (
    collapse_empty_galleries,
    strip_excess_blank_lines,
)
from warframe_lore.cleaner.sections import drop_gameplay_sections
from warframe_lore.cleaner.templates.noise import (
    is_noise_template,
    is_pure_noise,
    strip_templates_to_text,
)
from warframe_lore.cleaner.templates.render import (
    render_canon_template,
    render_non_canon_template,
    render_quote_template,
    render_spoiler_template,
)
from warframe_lore.cleaner.templates.signal import (
    must_flag_canon,
    must_flag_non_canon,
)


@dataclass
class CleanOutput:
    """Résultat du nettoyage d'une page.

    Attributes:
        markdown: texte final propre, prêt pour la sortie JSON.
        non_canon_detected_in_body: un template ``{{Speculation}}`` ou
            équivalent est apparu dans le corps de la page.
        canon_detected_in_body: un template de confirmation (``{{Canon}}``...)
            est apparu dans le corps de la page.
    """

    markdown: str
    non_canon_detected_in_body: bool = False
    canon_detected_in_body: bool = False


# Nom de classe gardé pour compatibilité avec l'ancien module ``cleaner.py``.
class WikitextCleaner:
    """Convertit le Wikitext d'une page en Markdown propre pour LLM.

        Args:
            title: titre de la page (libellé humain, utilisé en debug).
            cleaner_config: constantes de nettoyage (injectées depuis
                ``config/cleaner_config.json``).
        """

    def __init__(self, title: str = "", cleaner_config: CleanerConfig | None = None) -> None:
        self.page_title = title or ""
        self.cleaner_config = cleaner_config or CleanerConfig.load()

    # ------------------------------------------------------------------ API
    def clean(self, wikitext: str) -> CleanOutput:
        """Nettoye le Wikitext et retourne le Markdown enrichi de signaux canon."""
        non_canon_detected = False
        canon_detected = False

        if not wikitext:
            return CleanOutput(markdown="")

        # Étape 1 — assainissement pré-parse (purges destructives).
        text = wikitext
        text = strip_wikitext_comments(text)
        text = strip_tables_and_code_blocks(text)
        text = convert_html_tags(text)
        text = remove_transclusion_tags(text)
        text = strip_file_and_image_references(text)
        parsed = mwparserfromhell.parse(text)

        # Étape 2 — gestion des templates d'intérêt narratif.
        # Détection canon/non-canon AVANT tout remplacement/aplatissement :
        # un template de signal peut être imbriqué dans un autre template ou
        # un nœud de liste ; filter_templates(recursive=True) le trouve alors
        # qu'une boucle sur parsed.nodes (surface) ne descend pas.
        all_templates = parsed.filter_templates(recursive=True)
        for node in all_templates:
            if must_flag_non_canon(node, self.cleaner_config):
                non_canon_detected = True
                continue
            if must_flag_canon(node, self.cleaner_config):
                canon_detected = True

        for node in list(parsed.nodes):
            if not isinstance(node, Template):
                continue
            template_name = str(node.name).strip().lower()

            if template_name == "quote":
                parsed.replace(node, render_quote_template(node))
            elif template_name == "spoiler":
                parsed.replace(node, render_spoiler_template(node))
            elif must_flag_non_canon(node, self.cleaner_config):
                parsed.replace(node, render_non_canon_template(node, self.cleaner_config))
            elif must_flag_canon(node, self.cleaner_config):
                parsed.replace(node, render_canon_template(node, self.cleaner_config))
            elif is_noise_template(template_name, self.cleaner_config) or \
                    is_pure_noise(template_name, self.cleaner_config):
                parsed.remove(node)

        text = str(parsed)

        # Étape 3 — templates résiduels -> premier argument pipe (fallback).
        text = strip_templates_to_text(text, self.cleaner_config)

        # Étape 4 — mise en forme Markdown.
        text = protect_bullets(text)
        text = convert_markup_to_markdown(text)
        text = normalise_links(text)
        text = drop_gameplay_sections(text, self.cleaner_config)
        text = reflow_headings_to_markdown(text)
        text = normalise_deep_headings(text)
        text = normalise_indentation(text)
        text = format_lists_and_dialogue(text)
        text = strip_kim_dialog_instructions(text)
        text = cut_footer_noise(text)
        text = strip_audio_filenames(text)
        text = collapse_empty_galleries(text)
        text = strip_excess_blank_lines(text)

        return CleanOutput(
            markdown=text.strip(),
            non_canon_detected_in_body=non_canon_detected,
            canon_detected_in_body=canon_detected,
        )


__all__ = ["CleanOutput", "WikitextCleaner", "BULLET_TOKEN"]