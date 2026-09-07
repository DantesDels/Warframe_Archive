"""Assainissement HTML du Wikitext brut : commentaires, balises, transclusion.

Fonctions pures ``str -> str``, liées au balisage HTML/XML uniquement.
"""

from __future__ import annotations

import re


def strip_wikitext_comments(wikitext: str) -> str:
    """Supprime les commentaires ``<!-- ... -->`` (contenu obsolète d'édition)."""
    return re.sub(r"<!--.*?-->", "", wikitext, flags=re.DOTALL)


def convert_html_tags(wikitext: str) -> str:
    """Convertit les balises HTML utiles en Markdown/pauses, jette le reste.

    Tables HTML -> sauts de ligne ; liste -> puces ; gras/italique ->
    Markdown ; ``<br>`` -> nouvelle ligne ; ``<math>``/balises inconnues
    -> suppression.
    """
    text = wikitext
    text = re.sub(r"</?table[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?tr[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?td[^>]*>", " | ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?th[^>]*>", " | ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?ul[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?ol[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?li[^>]*>", "\n* ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?b>|</?strong>", "**", text, flags=re.IGNORECASE)
    text = re.sub(r"</?i>|</?em>", "_", text, flags=re.IGNORECASE)
    text = re.sub(r"</?u>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?br[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?div[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?span[^>]*>", "", text, flags=re.IGNORECASE)
    # Références de citation : on jette la balise complète (contenu inclus).
    text = re.sub(r"<ref[^>/]*/>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # Tout le reste (math, balises inconnues) : espace.
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def remove_transclusion_tags(wikitext: str) -> str:
    """Efface les balises de transclusion (<noinclude>, <includeonly>, ...)."""
    text = wikitext
    text = re.sub(r"</?noinclude>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?includeonly>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?onlyinclude>", "", text, flags=re.IGNORECASE)
    return text


__all__ = ["strip_wikitext_comments", "convert_html_tags", "remove_transclusion_tags"]