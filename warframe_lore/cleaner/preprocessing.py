"""Prétraitement du Wikitext brut AVANT analyse structurelle.

Ce module contient les transformations purement destructives qui ne
nécessitent pas l'arbre de parsing : commentaires HTML, balises HTML,
transclusion, références de fichiers/images et blocs table/code.

Chaque fonction est pure : ``str -> str``, testable isolément.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Expressions régulières de niveau module (précompilées une seule fois).
# ---------------------------------------------------------------------------
_REFERENCES_DE_COMMONS = re.compile(
    r"\[\[(?:File|Image|file|image)\s*:[^\]]*\]\]"
    r"|\[\d+[^\]]*\]",  # références externes numériques (rares)
    re.IGNORECASE,
)

_BALISES_LUA_CODE = (
    r"<syntaxhighlight\b.*?</syntaxhighlight>"
    r"|<source\b.*?</source>"
    r"|<code\b.*?</code>"
)
_FONCTIONS_PARSER = re.compile(
    r"\{\{#(?:invoke|if|ifeq|ifexpr|expr|switch|titleparts|lst|lsth|lstx)"
    r"[^{}]*\}\}",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Fonctions publiques.
# ---------------------------------------------------------------------------
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


def strip_file_and_image_references(wikitext: str) -> str:
    """Supprime les liens internes vers fichiers/images Commons."""
    return _REFERENCES_DE_COMMONS.sub("", wikitext)


def strip_tables_and_code_blocks(wikitext: str) -> str:
    """Enlève les tableaux wiki ``{|...|}`` et les blocs de code Lua/JSON.

    Les tableaux des pages lore sont majoritairement des stats : on les
    supprime purement et simplement (aucune valeur narrative).
    """
    text = wikitext
    text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.DOTALL)
    text = re.sub(_BALISES_LUA_CODE, "", text, flags=re.IGNORECASE | re.DOTALL)
    text = _FONCTIONS_PARSER.sub("", text)
    return text