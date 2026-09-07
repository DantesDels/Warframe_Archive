"""Blocs non narratifs : tableaux wiki, blocs de code Lua/JSON, fichiers."""

from __future__ import annotations

import re

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


__all__ = ["strip_file_and_image_references", "strip_tables_and_code_blocks"]