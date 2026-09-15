"""Non-narrative blocks: wiki tables, Lua/JSON code blocks, files."""

from __future__ import annotations

import re

_COMMONS_FILE_REFS = re.compile(
    r"\[\[(?:File|Image|file|image)\s*:[^\]]*\]\]"
    r"|\[\d+[^\]]*\]",  # numeric external references (rare)
    re.IGNORECASE,
)

_LUA_CODE_TAGS = (
    r"<syntaxhighlight\b.*?</syntaxhighlight>"
    r"|<source\b.*?</source>"
    r"|<code\b.*?</code>"
)
_PARSER_FUNCTIONS = re.compile(
    r"\{\{#(?:invoke|if|ifeq|ifexpr|expr|switch|titleparts|lst|lsth|lstx)"
    r"[^{}]*\}\}",
    re.IGNORECASE,
)


def strip_file_and_image_references(wikitext: str) -> str:
    """Removes internal links to Commons files/images."""
    return _COMMONS_FILE_REFS.sub("", wikitext)


def strip_tables_and_code_blocks(wikitext: str) -> str:
    """Removes wiki tables ``{|...|}`` and Lua/JSON code blocks.

    Tables on lore pages are mostly stats: we remove them entirely
    (no narrative value).
    """
    text = wikitext
    text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.DOTALL)
    text = re.sub(_LUA_CODE_TAGS, "", text, flags=re.IGNORECASE | re.DOTALL)
    text = _PARSER_FUNCTIONS.sub("", text)
    return text


__all__ = ["strip_file_and_image_references", "strip_tables_and_code_blocks"]
